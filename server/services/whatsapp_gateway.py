"""
WhatsApp Gateway - Unified Service Layer
שכבת שער WhatsApp מאוחדת - Baileys ו-Meta Cloud API

This module provides a unified interface for sending WhatsApp messages
regardless of the underlying provider (Baileys or Meta Cloud API).
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def get_business_whatsapp_provider(business) -> str:
    """Get the WhatsApp provider for a business
    
    Returns "baileys" as default for backwards compatibility.
    
    Args:
        business: Business object or None
    
    Returns:
        str: "baileys" or "meta"
    """
    if business is None:
        return "baileys"
    
    provider = getattr(business, "whatsapp_provider", None)
    
    if provider not in ("baileys", "meta"):
        return "baileys"
    
    return provider


def send_whatsapp_message(business, to: str, text: str, tenant_id: str = None) -> Dict[str, Any]:
    """Send a WhatsApp message via the appropriate provider
    
    This is the unified interface for sending WhatsApp messages.
    It routes to Baileys or Meta based on the business configuration.
    
    Args:
        business: Business object with whatsapp_provider field
        to: Recipient phone number
        text: Message text to send
        tenant_id: Optional tenant ID for Baileys routing
    
    Returns:
        Dict with status and message_id or error
    """
    provider = get_business_whatsapp_provider(business)
    business_id = getattr(business, 'id', None)
    
    logger.info(f"[WA-GATEWAY] Sending via {provider} (business_id={business_id})")
    
    if provider == "baileys":
        from server.whatsapp_provider import get_whatsapp_service
        effective_tenant = tenant_id or (f"business_{business_id}" if business_id else None)
        
        if not effective_tenant:
            logger.error("[WA-GATEWAY] Baileys requires tenant_id but none provided")
            return {
                "provider": "baileys",
                "status": "error",
                "error": "tenant_id required for Baileys"
            }
        
        wa_service = get_whatsapp_service(tenant_id=effective_tenant)
        return wa_service.send_message(to, text, tenant_id=effective_tenant)
    
    if provider == "meta":
        from server.services.meta_whatsapp_client import send_message_meta
        return send_message_meta(business, to, text)
    
    logger.error(f"[WA-GATEWAY] Unknown provider: {provider}")
    return {
        "provider": provider,
        "status": "error",
        "error": f"Unknown WhatsApp provider: {provider}"
    }


def send_whatsapp_media(business, to: str, media_url: str, caption: str = "", 
                        tenant_id: str = None) -> Dict[str, Any]:
    """Send a media message via the appropriate provider
    
    Args:
        business: Business object
        to: Recipient phone number
        media_url: URL of the media to send
        caption: Optional caption
        tenant_id: Optional tenant ID for Baileys
    
    Returns:
        Dict with status and message_id or error
    """
    provider = get_business_whatsapp_provider(business)
    business_id = getattr(business, 'id', None)
    
    logger.info(f"[WA-GATEWAY] Sending media via {provider} (business_id={business_id})")
    
    if provider == "baileys":
        from server.whatsapp_provider import get_whatsapp_service
        effective_tenant = tenant_id or (f"business_{business_id}" if business_id else None)
        
        if not effective_tenant:
            return {
                "provider": "baileys",
                "status": "error",
                "error": "tenant_id required for Baileys"
            }
        
        wa_service = get_whatsapp_service(tenant_id=effective_tenant)
        return wa_service.send_media(to, media_url, caption, tenant_id=effective_tenant)
    
    if provider == "meta":
        from server.services.meta_whatsapp_client import MetaWhatsAppClient
        client = MetaWhatsAppClient(business_id=business_id)
        return client.send_media(to, media_url, caption)
    
    return {
        "provider": provider,
        "status": "error",
        "error": f"Unknown WhatsApp provider: {provider}"
    }


def handle_incoming_whatsapp_message(
    *,
    provider: str,
    business,
    from_number: str,
    to_number: str,
    body: str,
    raw_payload: dict,
    message_type: str = "text",
    media_url: str = None,
) -> Dict[str, Any]:
    """Handle an incoming WhatsApp message from any provider
    
    This is the unified handler for incoming messages.
    It normalizes the data and routes to shared CRM/AI logic.
    
    Args:
        provider: "baileys" or "meta"
        business: Business object
        from_number: Sender phone number
        to_number: Recipient phone number (business number)
        body: Message text
        raw_payload: Original webhook payload
        message_type: Type of message (text, image, etc.)
        media_url: URL of media if applicable
    
    Returns:
        Dict with processing result
    """
    from server.db import db
    from server.models_sql import WhatsAppMessage, Business
    
    business_id = getattr(business, 'id', None) if business else None
    business_name = getattr(business, 'name', 'Unknown') if business else 'Unknown'
    
    logger.info(f"[WA-GATEWAY] Incoming from {provider}: business={business_name}, from={from_number[:8]}...")
    
    if not business_id:
        logger.error("[WA-GATEWAY] No business_id - cannot process message")
        return {"status": "error", "error": "no_business_id"}
    
    from_clean = from_number.replace("@s.whatsapp.net", "").replace("+", "").strip()
    
    # 🔥 FIX: Initialize was_created before try block to prevent unbound error
    was_created = None
    
    try:
        from server.services.customer_intelligence import CustomerIntelligence
        
        ci_service = CustomerIntelligence(business_id=business_id)
        customer, lead, was_created = ci_service.find_or_create_customer_from_whatsapp(
            phone_number=from_clean,
            message_text=body
        )
        
        action = "created" if was_created else "updated"
        logger.info(f"[WA-GATEWAY] {action} customer/lead for {from_clean}")
        
    except Exception as e:
        logger.error(f"[WA-GATEWAY] Customer intelligence failed: {e}")
    
    try:
        wa_msg = WhatsAppMessage()
        wa_msg.business_id = business_id
        wa_msg.to_number = from_clean
        wa_msg.body = body
        wa_msg.message_type = message_type
        wa_msg.direction = 'in'
        wa_msg.provider = provider
        wa_msg.status = 'received'
        wa_msg.media_url = media_url
        db.session.add(wa_msg)
        db.session.commit()
        
        logger.info(f"[WA-GATEWAY] Saved message ID={wa_msg.id}")
        
    except Exception as e:
        logger.error(f"[WA-GATEWAY] Failed to save message: {e}")
        db.session.rollback()
        return {"status": "error", "error": str(e)}
    
    try:
        from server.services.whatsapp_session_service import update_session_activity
        session = update_session_activity(
            business_id=business_id,
            customer_wa_id=from_clean,
            direction="in",
            provider=provider
        )
        logger.info(f"[WA-GATEWAY] Updated session id={session.id if session else 'N/A'}")
    except Exception as e:
        logger.error(f"[WA-GATEWAY] Session tracking failed: {e}")
    
    from server.routes_whatsapp import is_ai_active_for_conversation
    ai_enabled = is_ai_active_for_conversation(business_id, from_clean)
    
    return {
        "status": "success",
        "message_id": wa_msg.id,
        "customer_created": was_created,  # Now properly initialized before try block
        "ai_enabled": ai_enabled,
        "provider": provider
    }


def get_whatsapp_provider_info(business) -> Dict[str, Any]:
    """Get information about the WhatsApp provider configuration
    
    Args:
        business: Business object
    
    Returns:
        Dict with provider info including type and connection status
    """
    provider = get_business_whatsapp_provider(business)
    business_id = getattr(business, 'id', None)
    
    info = {
        "provider": provider,
        "business_id": business_id,
        "whatsapp_enabled": getattr(business, 'whatsapp_enabled', False),
    }
    
    if provider == "baileys":
        from server.whatsapp_provider import BaileysProvider
        baileys = BaileysProvider()
        info["connected"] = baileys._check_health()
        info["requires_qr"] = True
        info["description"] = "WhatsApp Web (Baileys)"
    
    elif provider == "meta":
        from server.services.meta_whatsapp_client import MetaWhatsAppClient
        client = MetaWhatsAppClient(business_id=business_id)
        info["configured"] = client.is_configured()
        info["requires_qr"] = False
        info["description"] = "WhatsApp Business Cloud API (Meta)"
    
    return info
