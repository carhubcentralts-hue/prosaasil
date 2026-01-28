"""
WhatsApp Send Service - Unified Message Sending (SSOT)
שירות שליחת WhatsApp מאוחד - נקודת אמת יחידה

This is the SINGLE SOURCE OF TRUTH for all WhatsApp message sending.
All paths (chat, lead, broadcast) MUST go through this service.

Key Features:
- Unified phone normalization
- Provider selection based on business settings
- Consistent error handling
- Support for text and media messages
- Context-aware retry logic
"""
import logging
from typing import Dict, Any, Optional
from server.models_sql import Business
from server.utils.whatsapp_utils import normalize_whatsapp_to

logger = logging.getLogger(__name__)


def send_message(
    business_id: int,
    to_phone: str,
    text: str,
    media: Optional[Dict] = None,
    media_type: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    context: Optional[str] = None,
    retries: int = 2
) -> Dict[str, Any]:
    """
    🎯 UNIFIED: Single source of truth for sending WhatsApp messages
    
    This function is used by:
    - WhatsApp chat page
    - Lead page (send to customer)
    - Broadcasts (bulk sending)
    
    Args:
        business_id: Business ID for multi-tenant routing
        to_phone: Recipient phone number (will be normalized)
        text: Message text or caption
        media: Optional media dict with keys: data (base64), mimetype, filename
        media_type: Optional media type (image, video, audio, document)
        idempotency_key: Optional key for deduplication
        context: Optional context ('chat', 'lead', 'broadcast')
        retries: Number of retry attempts (0 = no retries, used for broadcast)
    
    Returns:
        Dict with status, message_id, error, etc.
        
    Examples:
        >>> send_message(1, "+972501234567", "Hello")
        {"status": "sent", "message_id": "...", "provider": "baileys"}
        
        >>> send_message(1, "+972501234567", "Image", media={...}, media_type="image")
        {"status": "sent", "message_id": "...", "provider": "baileys"}
    """
    from server.db import db
    
    # Validate inputs
    if not business_id:
        logger.error("[WA-SEND-SERVICE] business_id is required")
        return {
            "status": "error",
            "error": "business_id required"
        }
    
    if not to_phone:
        logger.error("[WA-SEND-SERVICE] to_phone is required")
        return {
            "status": "error",
            "error": "to_phone required"
        }
    
    # Get business
    business = Business.query.get(business_id)
    if not business:
        logger.error(f"[WA-SEND-SERVICE] Business {business_id} not found")
        return {
            "status": "error",
            "error": f"Business {business_id} not found"
        }
    
    # Normalize phone number to JID
    try:
        normalized_jid, source = normalize_whatsapp_to(
            to=to_phone,
            business_id=business_id
        )
        logger.info(f"[WA-SEND-SERVICE] business_id={business_id} to={to_phone} → jid={normalized_jid} source={source} context={context}")
    except ValueError as e:
        logger.error(f"[WA-SEND-SERVICE] Phone normalization failed: {e}")
        return {
            "status": "error",
            "error": f"Invalid phone number: {str(e)}"
        }
    
    # Get tenant ID for Baileys routing
    tenant_id = f"business_{business_id}"
    
    # Determine provider (Baileys or Meta)
    provider = getattr(business, 'whatsapp_provider', 'baileys')
    if provider not in ('baileys', 'meta'):
        provider = 'baileys'
    
    logger.info(f"[WA-SEND-SERVICE] Using provider={provider} tenant_id={tenant_id} context={context}")
    
    # Route to appropriate provider
    if provider == 'baileys':
        return _send_via_baileys(
            tenant_id=tenant_id,
            to=normalized_jid,
            text=text,
            media=media,
            media_type=media_type,
            idempotency_key=idempotency_key,
            context=context,
            retries=retries
        )
    elif provider == 'meta':
        return _send_via_meta(
            business=business,
            to=normalized_jid,
            text=text,
            media=media,
            media_type=media_type,
            context=context
        )
    else:
        logger.error(f"[WA-SEND-SERVICE] Unknown provider: {provider}")
        return {
            "status": "error",
            "error": f"Unknown provider: {provider}"
        }


def _send_via_baileys(
    tenant_id: str,
    to: str,
    text: str,
    media: Optional[Dict] = None,
    media_type: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    context: Optional[str] = None,
    retries: int = 2
) -> Dict[str, Any]:
    """Send message via Baileys provider with context-aware retry logic"""
    from server.whatsapp_provider import get_whatsapp_service
    
    # Get WhatsApp service (uses cached provider for tenant)
    wa_service = get_whatsapp_service(tenant_id=tenant_id)
    
    # For broadcasts, disable provider-level retries (retries=0)
    # Retries are handled at broadcast_worker level
    if context == 'broadcast':
        # Single attempt only - broadcast_worker handles retries
        result = wa_service.send_message(
            to=to,
            message=text,
            tenant_id=tenant_id,
            media=media,
            media_type=media_type
        )
        return result
    
    # For regular sends (chat, lead), use retry logic
    last_error = None
    for attempt in range(retries):
        try:
            result = wa_service.send_message(
                to=to,
                message=text,
                tenant_id=tenant_id,
                media=media,
                media_type=media_type
            )
            
            if result.get('status') in ['sent', 'queued', 'accepted']:
                return result
            
            # Non-success status
            last_error = result.get('error', 'unknown error')
            if attempt < retries - 1:
                logger.warning(f"[WA-SEND-SERVICE] Attempt {attempt + 1} failed: {last_error}, retrying...")
                continue
            else:
                return result
                
        except Exception as e:
            last_error = str(e)
            if attempt < retries - 1:
                logger.warning(f"[WA-SEND-SERVICE] Attempt {attempt + 1} exception: {last_error}, retrying...")
                continue
            else:
                logger.error(f"[WA-SEND-SERVICE] All attempts failed: {last_error}")
                return {
                    "status": "error",
                    "error": last_error,
                    "provider": "baileys"
                }
    
    # Should not reach here
    return {
        "status": "error",
        "error": last_error or "unknown error",
        "provider": "baileys"
    }


def _send_via_meta(
    business: Business,
    to: str,
    text: str,
    media: Optional[Dict] = None,
    media_type: Optional[str] = None,
    context: Optional[str] = None
) -> Dict[str, Any]:
    """Send message via Meta WhatsApp Business API
    
    Note: Meta API expects different media format than Baileys.
    This implementation needs to be completed when Meta media support is needed.
    """
    from server.services.meta_whatsapp_client import MetaWhatsAppClient
    
    client = MetaWhatsAppClient(business_id=business.id)
    
    # Send text or media
    if media and media_type:
        # Meta media sending - not yet implemented, will use text fallback
        # Meta API requires different format:
        # - For URLs: Pass media URL directly
        # - For uploads: Use media upload API first, then send media_id
        # Current implementation is placeholder
        logger.warning(f"[WA-SEND-SERVICE] Meta media not fully implemented yet")
        
        # If media has 'url' key, try sending via URL
        if 'url' in media:
            return client.send_media(to, media['url'], text)
        else:
            # base64 data needs to be uploaded first via Meta API
            logger.error(f"[WA-SEND-SERVICE] Meta doesn't support base64 media directly")
            return {
                "status": "error",
                "error": "Meta provider requires media URL, not base64 data",
                "provider": "meta"
            }
    else:
        # Text message
        return client.send_message(to, text)


def send_message_to_lead(
    business_id: int,
    lead_id: int,
    text: str,
    media: Optional[Dict] = None,
    media_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    Helper function for sending message to a lead
    
    Args:
        business_id: Business ID
        lead_id: Lead ID
        text: Message text
        media: Optional media
        media_type: Optional media type
    
    Returns:
        Dict with status and details
    """
    from server.models_sql import Lead
    
    # Get lead
    lead = Lead.query.get(lead_id)
    if not lead:
        return {
            "status": "error",
            "error": f"Lead {lead_id} not found"
        }
    
    if lead.tenant_id != business_id:
        return {
            "status": "error",
            "error": "Lead does not belong to this business"
        }
    
    # Get lead phone
    phone = lead.phone_e164 or lead.phone
    if not phone:
        return {
            "status": "error",
            "error": "Lead has no phone number"
        }
    
    # Send via unified service
    return send_message(
        business_id=business_id,
        to_phone=phone,
        text=text,
        media=media,
        media_type=media_type,
        context='lead'
    )
