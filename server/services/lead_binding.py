"""
Lead Binding Service - Deterministic Call → Lead Association

This module ensures every call is correctly linked to a Lead by phone number.
Single source of truth for call-lead binding logic.
"""
import logging
from typing import Optional, Tuple
from server.models_sql import db, Lead, CallLog, Customer
from server.utils.phone_normalization import normalize_phone, phones_match

logger = logging.getLogger(__name__)

def bind_call_to_lead(
    call_log: CallLog,
    create_if_missing: bool = True
) -> Optional[Lead]:
    """
    Deterministically bind a call to the correct Lead by phone number.
    
    This is the SINGLE SOURCE OF TRUTH for call → lead binding.
    
    Rules:
    1. For inbound calls: lead phone = from_number (caller)
    2. For outbound calls: lead phone = to_number (recipient)
    3. Search by: business_id + normalized phone
    4. If found → link call to that lead
    5. If not found and create_if_missing=True → create new lead and link
    6. Never link call to lead from different business
    
    Args:
        call_log: CallLog instance to bind
        create_if_missing: If True, create Lead if it doesn't exist
    
    Returns:
        Lead instance (found or created) or None if not found and not created
    
    Side Effects:
        - Updates call_log.lead_id if binding successful
        - May create new Lead in database
        - Commits changes to database
    """
    if not call_log or not call_log.business_id:
        logger.error("[LEAD_BIND] Invalid call_log or missing business_id")
        return None
    
    # Determine which phone number to use based on direction
    if call_log.direction == 'outbound':
        # Outbound: lead is the person we called (to_number)
        lead_phone = call_log.to_number_norm or call_log.to_number
    else:
        # Inbound (or unknown): lead is the person who called us (from_number)
        lead_phone = call_log.from_number_norm or call_log.from_number
    
    if not lead_phone:
        logger.warning(f"[LEAD_BIND] No phone number available for call {call_log.call_sid}")
        return None
    
    # Normalize phone if not already normalized
    lead_phone_norm = normalize_phone(lead_phone)
    if not lead_phone_norm:
        logger.warning(f"[LEAD_BIND] Could not normalize phone {lead_phone}")
        return None
    
    # Search for existing lead by business_id + phone
    lead = Lead.query.filter_by(
        tenant_id=call_log.business_id,
        phone_e164=lead_phone_norm
    ).first()
    
    if lead:
        # Found existing lead - link call to it
        if call_log.lead_id != lead.id:
            call_log.lead_id = lead.id
            try:
                db.session.commit()
                logger.info(f"[LEAD_BIND] business_id={call_log.business_id} direction={call_log.direction} "
                          f"phone_norm={lead_phone_norm} lead_id={lead.id} status=linked_existing")
            except Exception as e:
                logger.error(f"[LEAD_BIND] Failed to link call to existing lead: {e}")
                db.session.rollback()
                return None
        
        return lead
    
    # Lead not found
    if not create_if_missing:
        logger.info(f"[LEAD_BIND] No lead found for phone {lead_phone_norm}, not creating (create_if_missing=False)")
        return None
    
    # Create new lead
    try:
        lead = Lead()
        lead.tenant_id = call_log.business_id
        lead.phone_e164 = lead_phone_norm
        lead.source = "call"
        lead.external_id = call_log.call_sid
        lead.status = "new"
        
        # Set direction on lead (first interaction direction)
        if call_log.direction == 'outbound':
            lead.last_call_direction = 'outbound'
        else:
            lead.last_call_direction = 'inbound'
        
        # Basic notes
        lead.notes = f"שיחה {call_log.direction} - {call_log.call_sid}"
        
        db.session.add(lead)
        db.session.flush()  # Get lead.id
        
        # Link call to new lead
        call_log.lead_id = lead.id
        
        db.session.commit()
        
        logger.info(f"[LEAD_BIND] business_id={call_log.business_id} direction={call_log.direction} "
                   f"phone_norm={lead_phone_norm} lead_id={lead.id} status=created_new")
        
        return lead
        
    except Exception as e:
        logger.error(f"[LEAD_BIND] Failed to create lead: {e}")
        db.session.rollback()
        return None


def update_call_phone_normalized(call_log: CallLog) -> bool:
    """
    Update normalized phone fields on a CallLog.
    
    Should be called whenever from_number or to_number is set/updated.
    
    Args:
        call_log: CallLog instance to update
    
    Returns:
        True if normalization succeeded, False otherwise
    """
    try:
        if call_log.from_number:
            call_log.from_number_norm = normalize_phone(call_log.from_number)
        
        if call_log.to_number:
            call_log.to_number_norm = normalize_phone(call_log.to_number)
        
        return True
        
    except Exception as e:
        logger.error(f"[LEAD_BIND] Failed to normalize phones for call {call_log.call_sid}: {e}")
        return False


def find_lead_by_phone(business_id: int, phone: str) -> Optional[Lead]:
    """
    Find a lead by business_id and phone number.
    
    Uses normalized phone matching for consistency.
    
    Args:
        business_id: Business ID to search within
        phone: Phone number (will be normalized)
    
    Returns:
        Lead instance or None if not found
    """
    phone_norm = normalize_phone(phone)
    if not phone_norm:
        return None
    
    return Lead.query.filter_by(
        tenant_id=business_id,
        phone_e164=phone_norm
    ).first()


def ensure_lead_for_call(call_sid: str) -> Optional[Lead]:
    """
    Ensure a CallLog has a linked Lead, creating one if necessary.
    
    This is a convenience function that can be called at any time
    to ensure proper call → lead binding.
    
    Args:
        call_sid: Call SID to process
    
    Returns:
        Lead instance or None if call not found or binding failed
    """
    call_log = CallLog.query.filter_by(call_sid=call_sid).first()
    if not call_log:
        logger.warning(f"[LEAD_BIND] Call {call_sid} not found")
        return None
    
    # If already has lead, return it
    if call_log.lead_id:
        return Lead.query.get(call_log.lead_id)
    
    # Otherwise, bind now
    return bind_call_to_lead(call_log, create_if_missing=True)
