"""
WhatsApp outbound messaging - unified provider system
"""
import os
import time
import logging
import requests
from twilio.rest import Client
from server.dao_crm import insert_message

log = logging.getLogger(__name__)

def send_whatsapp_message(to: str, text: str = None, media_url: str = None, provider: str = "auto") -> dict:
    """
    Send WhatsApp message through specified or auto-selected provider
    Returns: {"ok": True/False, "provider_used": "twilio"/"baileys", "provider_msg_id": "...", "error": "..."}
    """
    # Clean phone number
    to_clean = to.replace("whatsapp:", "").strip()
    
    # Resolve provider
    if provider == "auto":
        provider = resolve_provider()
    
    try:
        if provider == "twilio":
            return _send_twilio(to_clean, text, media_url)
        elif provider == "baileys":
            return _send_baileys(to_clean, text, media_url)
        else:
            return {"ok": False, "error": f"Unknown provider: {provider}"}
            
    except Exception as e:
        log.error(f"WhatsApp send failed: {e}")
        return {"ok": False, "error": str(e)}

def resolve_provider() -> str:
    """
    Auto-resolve WhatsApp provider based on ENV configuration
    """
    enable_twilio = os.getenv("ENABLE_WA_TWILIO", "true").lower() == "true"
    enable_baileys = os.getenv("ENABLE_WA_BAILEYS", "true").lower() == "true"
    priority = os.getenv("WA_PROVIDER_PRIORITY", "baileys,twilio").lower()
    
    # Check priority order
    for provider in priority.split(","):
        provider = provider.strip()
        if provider == "baileys" and enable_baileys:
            return "baileys"
        elif provider == "twilio" and enable_twilio:
            return "twilio"
    
    # Fallback
    if enable_baileys:
        return "baileys"
    elif enable_twilio:
        return "twilio"
    else:
        raise Exception("No WhatsApp provider enabled")

def _send_twilio(to: str, text: str = None, media_url: str = None) -> dict:
    """Send via Twilio WhatsApp API"""
    try:
        client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
        
        # Prepare message parameters
        msg_params = {
            "from_": os.getenv("TWILIO_WA_FROM"),
            "to": f"whatsapp:{to}",
            "body": text or None
        }
        
        if media_url:
            msg_params["media_url"] = [media_url]
        
        msg = client.messages.create(**msg_params)
        
        log.info("WA_OUT_TWILIO", extra={"to": to, "msg_sid": msg.sid})
        
        return {
            "ok": True,
            "provider_used": "twilio",
            "provider_msg_id": msg.sid
        }
        
    except Exception as e:
        log.error(f"Twilio WhatsApp send failed: {e}")
        return {"ok": False, "error": str(e), "provider_used": "twilio"}

def _send_baileys(to: str, text: str = None, media_url: str = None) -> dict:
    """Send via Baileys bridge (local HTTP)"""
    try:
        port = int(os.getenv("WA_BAILEYS_PORT", "8000"))
        url = f"http://127.0.0.1:{port}/send"
        
        payload = {
            "to": to,
            "text": text or "",
            "media_url": media_url
        }
        
        response = requests.post(url, json=payload, timeout=6)
        response.raise_for_status()
        
        result = response.json()
        provider_msg_id = result.get("message_id", "baileys_" + str(int(time.time())))
        
        log.info("WA_OUT_BAILEYS", extra={"to": to, "msg_id": provider_msg_id})
        
        return {
            "ok": True,
            "provider_used": "baileys",
            "provider_msg_id": provider_msg_id
        }
        
    except Exception as e:
        log.error(f"Baileys WhatsApp send failed: {e}")
        return {"ok": False, "error": str(e), "provider_used": "baileys"}

def send_and_record(to: str, text: str = None, media_url: str = None, provider: str = "auto", 
                   thread_id: int = None, business_id: int = 1) -> dict:
    """
    Send WhatsApp message and record in CRM
    """
    # Send message
    result = send_whatsapp_message(to, text, media_url, provider)
    
    # Find/create thread if not provided
    if thread_id is None:
        from server.dao_crm import upsert_thread
        thread_id = upsert_thread(
            business_id=business_id, 
            type_="whatsapp", 
            provider=result.get("provider_used", provider), 
            peer_number=to
        )
    
    # Record outbound message
    status = "sent" if result["ok"] else "failed"
    try:
        insert_message(
            thread_id=thread_id,
            direction="out",
            message_type="text" if not media_url else "media",
            content_text=text,
            media_url=media_url,
            provider_msg_id=result.get("provider_msg_id"),
            status=status
        )
    except Exception as e:
        log.error(f"Failed to record outbound message: {e}")
    
    result["thread_id"] = thread_id
    return result