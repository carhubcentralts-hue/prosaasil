"""
Multi-tenant Business Resolver
Resolves business_id from contact channel identifiers (phone numbers, tenant IDs)
"""
from server.models_sql import Business, BusinessContactChannel
from server.db import db
import logging
from functools import lru_cache
from typing import Optional, Tuple

log = logging.getLogger(__name__)

@lru_cache(maxsize=256)
def resolve_business_by_channel(channel_type: str, identifier: str) -> Optional[int]:
    """
    Resolve business_id from channel identifier with caching
    
    Args:
        channel_type: 'twilio_voice', 'twilio_sms', 'whatsapp'
        identifier: E.164 phone number or tenant slug (business_1)
    
    Returns:
        business_id or None if not found
    
    Examples:
        resolve_business_by_channel('twilio_voice', '+972501234567') -> 1
        resolve_business_by_channel('whatsapp', 'business_1') -> 1
    """
    if not identifier:
        log.warning(f"Empty identifier for channel_type={channel_type}")
        return None
    
    # Normalize identifier
    identifier = identifier.strip()
    
    # Query the mapping table
    channel = BusinessContactChannel.query.filter_by(
        channel_type=channel_type,
        identifier=identifier
    ).first()
    
    if channel:
        log.info(f"✅ Resolved {channel_type}:{identifier} → business_id={channel.business_id}")
        return channel.business_id
    
    log.warning(f"⚠️ No business found for {channel_type}:{identifier}")
    return None


def _normalize_identifier(identifier: str) -> str:
    """נרמול מזהה - הסרת קידומות וסימנים מיוחדים"""
    if not identifier:
        return ""
    
    # הסר WhatsApp prefix, spaces, hyphens
    normalized = identifier.replace('whatsapp:', '').replace(' ', '').replace('-', '').strip()
    
    # וודא E.164 format
    if normalized and (normalized[0] == '+' or normalized[0].isdigit()):
        if not normalized.startswith('+'):
            normalized = f'+{normalized}'
        return normalized
    
    return identifier  # Return original if not a phone

def resolve_business_with_fallback(channel_type: str, identifier: str) -> Tuple[Optional[int], str]:
    """
    ✅ FIXED: Smart business resolution with proper caching and transactions
    
    Returns:
        (business_id, status) where status is:
        - 'found': Successfully resolved via BusinessContactChannel
        - 'tenant_id': Resolved from business_X format tenant ID
        - 'phone_match': Matched by Business.phone_number or whatsapp_number
        - 'rejected_unknown': Unknown identifier rejected for security
    """
    from sqlalchemy import or_
    import re
    
    # ✅ FIX: Handle business_X format from Baileys (e.g., "business_1" -> 1)
    if identifier and identifier.startswith('business_'):
        match = re.match(r'^business_(\d+)$', identifier)
        if match:
            extracted_id = int(match.group(1))
            business = Business.query.filter_by(id=extracted_id, is_active=True).first()
            if business:
                log.info(f"✅ Resolved tenant_id format: {identifier} → business_id={extracted_id}")
                return extracted_id, 'tenant_id'
            else:
                log.warning(f"⚠️ Business not found for tenant_id: {identifier}")
    
    # Normalize identifier
    normalized = _normalize_identifier(identifier)
    
    # ✅ FIX: Query for BOTH normalized AND original identifier (supports legacy data)
    channel_match = BusinessContactChannel.query.filter(
        BusinessContactChannel.channel_type == channel_type
    ).filter(
        or_(
            BusinessContactChannel.identifier == normalized,
            BusinessContactChannel.identifier == identifier  # Legacy format
        )
    ).first()
    
    if channel_match:
        log.info(f"✅ Channel match: {channel_type}:{identifier} → business_id={channel_match.business_id}")
        return channel_match.business_id, 'found'
    
    # Try phone match (if it's a valid phone number)
    # 🔥 FIX: Use phone_number column (not phone_e164 which doesn't exist!)
    if normalized.startswith('+'):
        business = Business.query.filter_by(phone_number=normalized, is_active=True).first()
        if not business:
            # Also try whatsapp_number as fallback
            business = Business.query.filter_by(whatsapp_number=normalized, is_active=True).first()
        
        if business:
            log.info(f"✅ AUTO-DETECTED business_id={business.id} by phone_number={normalized}")
            
            # ✅ FIX: Atomic get-or-create with proper transaction handling
            try:
                from sqlalchemy.exc import IntegrityError
                
                # Try to create (will fail if exists due to unique constraint)
                channel = BusinessContactChannel()
                channel.business_id = business.id
                channel.channel_type = channel_type
                channel.identifier = normalized  # Always use normalized
                channel.is_primary = True
                db.session.add(channel)
                
                try:
                    db.session.commit()
                    log.info(f"📝 Auto-registered {channel_type}:{normalized} → business_id={business.id}")
                except IntegrityError:
                    # Already exists - safe to ignore
                    db.session.rollback()
                    log.debug(f"Channel already exists: {channel_type}:{normalized}")
                    
            except Exception as e:
                db.session.rollback()
                log.warning(f"⚠️ Auto-registration failed (non-critical): {e}")
            
            # Clear cache
            resolve_business_by_channel.cache_clear()
            
            return business.id, 'phone_match'
    
    # 🔒 SECURITY: NO FALLBACK - reject unknown phones to prevent cross-tenant exposure
    # Previously: would fall back to first active business, causing wrong prompts/data
    # Now: return None for unknown identifiers, forcing proper channel registration
    log.error(f"❌ REJECTED: Unknown {channel_type} identifier {identifier} - no business match found!")
    log.error(f"   → Add this phone to Business.phone_number/whatsapp_number or create BusinessContactChannel entry")
    return None, 'rejected_unknown'


def add_business_channel(business_id: int, channel_type: str, identifier: str, is_primary: bool = False, config_json: Optional[str] = None) -> BusinessContactChannel:
    """
    Add a new business contact channel mapping
    
    Args:
        business_id: The business ID
        channel_type: 'twilio_voice', 'twilio_sms', 'whatsapp'
        identifier: E.164 phone or tenant slug
        is_primary: Mark as primary channel
        config_json: Optional JSON configuration
    
    Returns:
        Created BusinessContactChannel
    """
    # Check if already exists
    existing = BusinessContactChannel.query.filter_by(
        channel_type=channel_type,
        identifier=identifier
    ).first()
    
    if existing:
        log.warning(f"Channel {channel_type}:{identifier} already mapped to business_id={existing.business_id}")
        return existing
    
    # Create new mapping
    channel = BusinessContactChannel()
    channel.business_id = business_id
    channel.channel_type = channel_type
    channel.identifier = identifier
    channel.is_primary = is_primary
    channel.config_json = config_json
    
    db.session.add(channel)
    db.session.commit()
    
    # Clear cache
    resolve_business_by_channel.cache_clear()
    
    log.info(f"✅ Added channel {channel_type}:{identifier} → business_id={business_id}")
    return channel


def list_business_channels(business_id: int) -> list:
    """Get all contact channels for a business"""
    channels = BusinessContactChannel.query.filter_by(business_id=business_id).all()
    return [
        {
            'id': c.id,
            'channel_type': c.channel_type,
            'identifier': c.identifier,
            'is_primary': c.is_primary,
            'created_at': c.created_at.isoformat() if c.created_at else None
        }
        for c in channels
    ]


def delete_business_channel(channel_id: int) -> bool:
    """Delete a business channel mapping"""
    channel = BusinessContactChannel.query.get(channel_id)
    if not channel:
        return False
    
    db.session.delete(channel)
    db.session.commit()
    
    # Clear cache
    resolve_business_by_channel.cache_clear()
    
    log.info(f"🗑️ Deleted channel {channel.channel_type}:{channel.identifier}")
    return True
