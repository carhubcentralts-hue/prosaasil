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


def resolve_business_with_fallback(channel_type: str, identifier: str) -> Tuple[Optional[int], str]:
    """
    Resolve business with safe fallback logic
    
    Returns:
        (business_id, status) where status is:
        - 'found': Successfully resolved
        - 'fallback_active': Used first active business
        - 'fallback_any': Used any business
        - 'none': No business exists
    """
    # Try exact match first
    business_id = resolve_business_by_channel(channel_type, identifier)
    if business_id:
        return business_id, 'found'
    
    # Fallback 1: First active business
    business = Business.query.filter_by(is_active=True).first()
    if business:
        log.warning(f"⚠️ Using fallback active business_id={business.id} for {channel_type}:{identifier}")
        return business.id, 'fallback_active'
    
    # Fallback 2: Any business
    business = Business.query.first()
    if business:
        log.warning(f"⚠️ Using fallback any business_id={business.id} for {channel_type}:{identifier}")
        return business.id, 'fallback_any'
    
    # Fallback 3: Create default business
    log.error(f"❌ No business exists for {channel_type}:{identifier} - creating default")
    business = Business()
    business.name = "Default Business"
    business.business_type = "real_estate"
    business.phone_e164 = "+972500000000"
    business.is_active = True
    db.session.add(business)
    db.session.commit()
    
    log.info(f"✅ Created default business_id={business.id}")
    return business.id, 'fallback_any'


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
