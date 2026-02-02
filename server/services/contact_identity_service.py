"""
🎯 BUILD 200: Contact Identity Service - Unified Lead Management

This service provides a single source of truth for customer identification and
lead creation/update across all channels (WhatsApp, Phone Calls).

Key Principles:
1. ONE person = ONE lead (no duplicates across channels)
2. External IDs (JID/phone) are the source of truth, not lead_id
3. contact_identities table is the authoritative mapping layer
4. Cross-channel linking when same phone number is detected

Flow for WhatsApp:
1. Normalize remoteJid (e.g., "972525951893@s.whatsapp.net")
2. Check contact_identities for existing mapping (business_id + 'whatsapp' + jid)
3. If found → return existing lead
4. If not found → try to link by phone number
5. If still not found → create new lead + mapping entry

Flow for Phone Calls:
1. Normalize phone to E.164 (e.g., "+972525951893")
2. Check contact_identities for existing mapping (business_id + 'phone' + phone)
3. If found → return existing lead
4. If not found → try to link by phone number
5. If still not found → create new lead + mapping entry
"""

import logging
import re
from typing import Optional, Tuple
from datetime import datetime

from server.db import db
from server.models_sql import Lead, ContactIdentity

logger = logging.getLogger(__name__)


class ContactIdentityService:
    """
    Unified service for contact identification and lead management across channels.
    """
    
    @staticmethod
    def normalize_whatsapp_jid(remote_jid: str) -> str:
        """
        Normalize WhatsApp remoteJid to consistent format.
        
        Examples:
        - "972525951893@s.whatsapp.net" → "972525951893@s.whatsapp.net"
        - "972525951893@s.whatsapp.net " → "972525951893@s.whatsapp.net" (strip whitespace)
        - "972525951893:55@s.whatsapp.net" → "972525951893@s.whatsapp.net" (remove device suffix)
        
        Args:
            remote_jid: Raw remoteJid from Baileys
            
        Returns:
            Normalized JID string
        """
        if not remote_jid:
            return ""
        
        # Strip whitespace
        jid = remote_jid.strip()
        
        # Remove device suffix (e.g., ":55" for multi-device)
        # Format: 972525951893:55@s.whatsapp.net → 972525951893@s.whatsapp.net
        if ':' in jid and '@' in jid:
            parts = jid.split('@')
            if len(parts) == 2:
                phone_part = parts[0].split(':')[0]  # Remove everything after ":"
                domain_part = parts[1]
                jid = f"{phone_part}@{domain_part}"
        
        return jid
    
    @staticmethod
    def normalize_phone(phone: str) -> str:
        """
        Normalize phone number to E.164 format.
        
        Examples:
        - "0525951893" → "+972525951893"
        - "+972525951893" → "+972525951893"
        - "972525951893" → "+972525951893"
        - "+972-52-595-1893" → "+972525951893"
        
        Args:
            phone: Raw phone number
            
        Returns:
            Normalized E.164 phone string (with leading +)
        """
        if not phone:
            return ""
        
        # Remove all non-digit characters except leading +
        phone = phone.strip()
        if phone.startswith('+'):
            # Keep the + and remove all non-digits after it
            phone = '+' + re.sub(r'\D', '', phone[1:])
        else:
            phone = re.sub(r'\D', '', phone)
        
        # Handle Israeli numbers starting with 0
        if phone.startswith('0') and len(phone) == 10:
            phone = '972' + phone[1:]
        
        # Ensure leading + for E.164
        if not phone.startswith('+'):
            phone = '+' + phone
        
        return phone
    
    @staticmethod
    def extract_phone_from_jid(jid: str) -> Optional[str]:
        """
        Extract phone number from WhatsApp JID.
        
        Examples:
        - "972525951893@s.whatsapp.net" → "+972525951893"
        - "82399031480511@lid" → "+82399031480511" (try to normalize @lid prefix)
        - "status@broadcast" → None (special format)
        
        Args:
            jid: WhatsApp JID
            
        Returns:
            E.164 phone number or None if not extractable
        """
        if not jid:
            return None
        
        # Skip special JID formats (but NOT @lid - we want to try that!)
        if '@broadcast' in jid or '@g.us' in jid or '@newsletter' in jid:
            return None
        
        # Extract phone part (before @)
        if '@' in jid:
            phone_part = jid.split('@')[0]
            
            # Remove device suffix if present
            if ':' in phone_part:
                phone_part = phone_part.split(':')[0]
            
            # Validate it looks like a phone number (all digits, reasonable length)
            # 🔥 NEW: Also try to normalize @lid prefixes - they might be phone numbers!
            if phone_part.isdigit() and 8 <= len(phone_part) <= 15:
                normalized = ContactIdentityService.normalize_phone(phone_part)
                if normalized:
                    if '@lid' in jid:
                        logger.info(f"[ContactIdentity] ✅ Extracted phone from @lid JID: {jid[:30]} -> {normalized}")
                    return normalized
        
        return None
    
    @staticmethod
    def get_or_create_lead_for_whatsapp(
        business_id: int,
        remote_jid: str,
        push_name: Optional[str] = None,
        phone_e164_override: Optional[str] = None,
        message_text: Optional[str] = None,
        wa_message_id: Optional[str] = None,
        ts: Optional[datetime] = None
    ) -> Lead:
        """
        Get or create lead for WhatsApp message - with cross-channel linking.
        
        Algorithm:
        Step A: Check for existing mapping by JID
        Step B: Try to link by phone number (if JID contains phone)
        Step C: Create new lead + mapping if not found
        Step D: Update name if appropriate
        
        Args:
            business_id: Business ID
            remote_jid: WhatsApp remoteJid
            push_name: WhatsApp display name (optional)
            phone_e164_override: E.164 phone number extracted from participant (optional, for @lid messages)
            message_text: Message content (for context)
            wa_message_id: WhatsApp message ID (for logging)
            ts: Timestamp of message
            
        Returns:
            Lead object (existing or newly created)
        """
        # Normalize JID
        normalized_jid = ContactIdentityService.normalize_whatsapp_jid(remote_jid)
        if not normalized_jid:
            raise ValueError("Invalid remoteJid")
        
        logger.info(f"[ContactIdentity] WhatsApp lookup: biz={business_id}, jid={normalized_jid[:30]}...")
        
        # Step A: Check for existing mapping by JID
        identity = ContactIdentity.query.filter_by(
            business_id=business_id,
            channel='whatsapp',
            external_id=normalized_jid
        ).first()
        
        if identity:
            logger.info(f"[ContactIdentity] ✅ Found existing lead via JID mapping: lead_id={identity.lead_id}")
            lead = identity.lead
            
            # Update last_contact_at
            lead.last_contact_at = ts or datetime.utcnow()
            db.session.commit()
            
            # Update name if appropriate
            ContactIdentityService._update_lead_name(lead, push_name, 'whatsapp')
            
            return lead
        
        # Step B: Try to link by phone number
        # 🔥 FIX: Use phone_e164_override if provided (for @lid messages with participant)
        phone_e164 = phone_e164_override or ContactIdentityService.extract_phone_from_jid(normalized_jid)
        if phone_e164:
            logger.info(f"[ContactIdentity] 📞 Extracted phone from JID: {phone_e164}")
            
            # Check if lead exists with this phone number
            existing_lead = Lead.query.filter_by(
                tenant_id=business_id,
                phone_e164=phone_e164
            ).first()
            
            if existing_lead:
                logger.info(f"[ContactIdentity] 🔗 Linking WhatsApp JID to existing lead: lead_id={existing_lead.id}")
                
                # Create mapping for this JID
                identity = ContactIdentity(
                    business_id=business_id,
                    channel='whatsapp',
                    external_id=normalized_jid,
                    lead_id=existing_lead.id
                )
                db.session.add(identity)
                
                # Update lead fields
                existing_lead.whatsapp_jid = normalized_jid
                existing_lead.reply_jid = remote_jid  # Original JID for replies
                existing_lead.reply_jid_type = remote_jid.split('@')[-1] if '@' in remote_jid else 's.whatsapp.net'
                existing_lead.last_contact_at = ts or datetime.utcnow()
                
                # Set phone_raw if not already set (for consistency)
                if not existing_lead.phone_raw and normalized_jid:
                    existing_lead.phone_raw = normalized_jid.split('@')[0] if '@' in normalized_jid else None
                
                if existing_lead.source in ['form', 'manual', 'imported_outbound']:
                    existing_lead.source = 'whatsapp'  # Update source if was generic
                
                db.session.commit()
                
                # Update name if appropriate
                ContactIdentityService._update_lead_name(existing_lead, push_name, 'whatsapp')
                
                return existing_lead
        
        # Step C: Create new lead + mapping
        logger.info(f"[ContactIdentity] 🆕 Creating new lead for WhatsApp: {normalized_jid[:30]}...")
        
        lead = Lead()
        lead.tenant_id = business_id
        lead.phone_e164 = phone_e164  # May be None for @lid
        # Set phone_raw for consistency - used by scheduled messages and other services
        # that may fallback to phone_raw when whatsapp_jid is not set
        if phone_e164:
            # Store the raw phone extracted from JID (just the digits without domain)
            lead.phone_raw = normalized_jid.split('@')[0] if '@' in normalized_jid else None
        lead.source = 'whatsapp'
        lead.whatsapp_jid = normalized_jid
        lead.reply_jid = remote_jid  # Original JID for replies
        lead.reply_jid_type = remote_jid.split('@')[-1] if '@' in remote_jid else 's.whatsapp.net'
        lead.last_contact_at = ts or datetime.utcnow()
        
        # Set name from push_name if available and not generic
        if push_name and push_name.strip() and push_name.lower() not in ['unknown', '']:
            lead.name = push_name.strip()
            lead.name_source = 'whatsapp'
            lead.name_updated_at = datetime.utcnow()
        else:
            lead.name = "ליד WhatsApp"  # Fallback name
            lead.name_source = 'whatsapp'
        
        db.session.add(lead)
        db.session.flush()  # Get lead.id
        
        # Create contact identity mapping
        identity = ContactIdentity(
            business_id=business_id,
            channel='whatsapp',
            external_id=normalized_jid,
            lead_id=lead.id
        )
        db.session.add(identity)
        db.session.commit()
        
        logger.info(f"[ContactIdentity] ✅ Created new lead: lead_id={lead.id}, jid={normalized_jid[:30]}")
        return lead
    
    @staticmethod
    def get_or_create_lead_for_call(
        business_id: int,
        from_e164: str,
        caller_name: Optional[str] = None,
        call_sid: Optional[str] = None,
        ts: Optional[datetime] = None
    ) -> Lead:
        """
        Get or create lead for phone call - with cross-channel linking.
        
        Algorithm:
        Step A: Check for existing mapping by phone
        Step B: Try to find by phone in leads table (legacy)
        Step C: Create new lead + mapping if not found
        Step D: Update name if appropriate
        
        Args:
            business_id: Business ID
            from_e164: Caller phone number (E.164 format)
            caller_name: Caller name from caller ID (optional)
            call_sid: Twilio call SID (for logging)
            ts: Timestamp of call
            
        Returns:
            Lead object (existing or newly created)
        """
        # Normalize phone
        normalized_phone = ContactIdentityService.normalize_phone(from_e164)
        if not normalized_phone:
            raise ValueError("Invalid phone number")
        
        logger.info(f"[ContactIdentity] Call lookup: biz={business_id}, phone={normalized_phone}")
        
        # Step A: Check for existing mapping by phone
        identity = ContactIdentity.query.filter_by(
            business_id=business_id,
            channel='phone',
            external_id=normalized_phone
        ).first()
        
        if identity:
            logger.info(f"[ContactIdentity] ✅ Found existing lead via phone mapping: lead_id={identity.lead_id}")
            lead = identity.lead
            
            # Update last_contact_at
            lead.last_contact_at = ts or datetime.utcnow()
            db.session.commit()
            
            # Update name if appropriate
            ContactIdentityService._update_lead_name(lead, caller_name, 'call')
            
            return lead
        
        # Step B: Try to find by phone in leads table (legacy support)
        existing_lead = Lead.query.filter_by(
            tenant_id=business_id,
            phone_e164=normalized_phone
        ).first()
        
        if existing_lead:
            logger.info(f"[ContactIdentity] 🔗 Linking phone to existing lead: lead_id={existing_lead.id}")
            
            # Create mapping for this phone
            identity = ContactIdentity(
                business_id=business_id,
                channel='phone',
                external_id=normalized_phone,
                lead_id=existing_lead.id
            )
            db.session.add(identity)
            
            # Update lead fields
            existing_lead.last_contact_at = ts or datetime.utcnow()
            
            if existing_lead.source in ['form', 'manual', 'imported_outbound']:
                existing_lead.source = 'call'  # Update source if was generic
            
            db.session.commit()
            
            # Update name if appropriate
            ContactIdentityService._update_lead_name(existing_lead, caller_name, 'call')
            
            return existing_lead
        
        # Step C: Create new lead + mapping
        logger.info(f"[ContactIdentity] 🆕 Creating new lead for call: {normalized_phone}")
        
        lead = Lead()
        lead.tenant_id = business_id
        lead.phone_e164 = normalized_phone
        lead.source = 'call'
        lead.last_contact_at = ts or datetime.utcnow()
        
        # Set name from caller_name if available and not generic
        if caller_name and caller_name.strip() and caller_name.lower() not in ['unknown', 'anonymous']:
            lead.name = caller_name.strip()
            lead.name_source = 'call'
            lead.name_updated_at = datetime.utcnow()
        else:
            lead.name = "ליד חדש"  # Fallback name
            lead.name_source = 'call'
        
        db.session.add(lead)
        db.session.flush()  # Get lead.id
        
        # Create contact identity mapping
        identity = ContactIdentity(
            business_id=business_id,
            channel='phone',
            external_id=normalized_phone,
            lead_id=lead.id
        )
        db.session.add(identity)
        db.session.commit()
        
        logger.info(f"[ContactIdentity] ✅ Created new lead: lead_id={lead.id}, phone={normalized_phone}")
        return lead
    
    @staticmethod
    def _update_lead_name(lead: Lead, new_name: Optional[str], source: str):
        """
        Update lead name intelligently - respects name_source priority.
        
        Priority (highest to lowest):
        1. user_provided (manual entry) - NEVER overwrite
        2. call / whatsapp (from actual conversation)
        3. No name / generic name - always overwrite
        
        Args:
            lead: Lead object to update
            new_name: New name to potentially set
            source: Source of new name ('whatsapp' or 'call')
        """
        if not new_name or not new_name.strip():
            return
        
        new_name = new_name.strip()
        
        # Skip generic names
        if new_name.lower() in ['unknown', 'anonymous', 'ליד חדש', 'ליד whatsapp']:
            return
        
        # Never overwrite user_provided names
        if lead.name_source == 'user_provided':
            logger.debug(f"[ContactIdentity] Skipping name update: user_provided takes precedence")
            return
        
        # Always overwrite if no current name or generic name
        current_name = lead.name or ""
        if not current_name or current_name in ['ליד חדש', 'ליד WhatsApp', 'ללא שם']:
            logger.info(f"[ContactIdentity] Updating name: '{current_name}' → '{new_name}' (source: {source})")
            lead.name = new_name
            lead.name_source = source
            lead.name_updated_at = datetime.utcnow()
            db.session.commit()
            return
        
        # If current name is from same or lower priority source, update
        if lead.name_source in [source, 'whatsapp', 'call']:
            # Check if new name is "better" (longer, more informative)
            if len(new_name) > len(current_name):
                logger.info(f"[ContactIdentity] Updating name (better): '{current_name}' → '{new_name}'")
                lead.name = new_name
                lead.name_source = source
                lead.name_updated_at = datetime.utcnow()
                db.session.commit()
