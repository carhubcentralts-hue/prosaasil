"""
n8n Workflow Automation Integration
אינטגרציית n8n לאוטומציות עסקיות

This module provides a central function to send events to n8n webhooks.
Events include: WhatsApp messages, calls, leads, and more.

⚠️ DEPLOYMENT ONLY: This runs on external VPS with Docker, not in Replit.
"""
import os
import logging
import requests
from datetime import datetime
from typing import Dict, Any, Optional
from threading import Thread

logger = logging.getLogger(__name__)

# Environment variables
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "")  # Base URL: https://domain.com/n8n/webhook/xxx
N8N_WEBHOOK_SECRET = os.getenv("N8N_WEBHOOK_SECRET", "")  # Secret token for auth
N8N_ENABLED = os.getenv("N8N_ENABLED", "false").lower() == "true"

# Connection pooling for speed
_session = None
def _get_session():
    global _session
    if _session is None:
        _session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=5,
            pool_maxsize=10,
            max_retries=1
        )
        _session.mount('http://', adapter)
        _session.mount('https://', adapter)
    return _session


def send_event_to_n8n(
    event_type: str,
    payload: Dict[str, Any],
    async_send: bool = True
) -> Dict[str, Any]:
    """
    🚀 Central function to send events to n8n webhook
    
    Args:
        event_type: Type of event (e.g., 'whatsapp_incoming', 'whatsapp_outgoing', 'call_started')
        payload: Event data to send
        async_send: If True, sends in background thread (default: True for speed)
    
    Returns:
        Dict with status info
    
    Usage:
        send_event_to_n8n('whatsapp_incoming', {
            'from': '+972501234567',
            'message': 'Hello!',
            'business_id': 'business_1'
        })
    """
    if not N8N_ENABLED:
        logger.debug(f"[N8N] Disabled - skipping event: {event_type}")
        return {"status": "disabled"}
    
    if not N8N_WEBHOOK_URL:
        logger.warning(f"[N8N] N8N_WEBHOOK_URL not configured - skipping event: {event_type}")
        return {"status": "not_configured"}
    
    # 🔒 SECURITY: Require business_id for multi-tenant isolation
    if not payload.get('business_id'):
        logger.error(f"[N8N] ❌ REJECTED event '{event_type}' - missing business_id (multi-tenant requirement)")
        return {"status": "rejected", "error": "missing_business_id"}
    
    # Build event envelope
    event_data = {
        "event_type": event_type,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "source": "prosaas",
        **payload
    }
    
    # Add secret token if configured (for n8n webhook verification)
    params = {}
    if N8N_WEBHOOK_SECRET:
        params["token"] = N8N_WEBHOOK_SECRET
    
    if async_send:
        # ⚡ Fire-and-forget - don't block main thread
        Thread(target=_send_to_n8n, args=(event_data, params), daemon=True).start()
        return {"status": "queued", "event_type": event_type}
    else:
        return _send_to_n8n(event_data, params)


def _send_to_n8n(event_data: Dict[str, Any], params: Dict[str, str]) -> Dict[str, Any]:
    """Internal function to actually send the request to n8n"""
    try:
        session = _get_session()
        response = session.post(
            N8N_WEBHOOK_URL,
            json=event_data,
            params=params,
            headers={"Content-Type": "application/json"},
            timeout=10.0
        )
        
        if response.status_code in (200, 201, 204):
            logger.info(f"[N8N] ✅ Event sent: {event_data.get('event_type')}")
            return {"status": "sent", "code": response.status_code}
        else:
            logger.warning(f"[N8N] ⚠️ Webhook returned {response.status_code}: {response.text[:200]}")
            return {"status": "error", "code": response.status_code, "error": response.text[:200]}
            
    except requests.Timeout:
        logger.warning(f"[N8N] ⏱️ Webhook timeout for event: {event_data.get('event_type')}")
        return {"status": "timeout"}
    except Exception as e:
        logger.error(f"[N8N] ❌ Failed to send event: {e}")
        return {"status": "error", "error": str(e)}


# =============================================================================
# Convenience functions for specific event types
# =============================================================================

def n8n_whatsapp_incoming(
    phone: str,
    message: str,
    business_id: str,
    lead_id: Optional[int] = None,
    lead_name: Optional[str] = None,
    message_id: Optional[str] = None
) -> Dict[str, Any]:
    """Send WhatsApp incoming message event to n8n"""
    return send_event_to_n8n("whatsapp_incoming", {
        "from": phone,
        "message": message,
        "business_id": business_id,
        "lead_id": lead_id,
        "lead_name": lead_name,
        "message_id": message_id,
        "direction": "incoming"
    })


def n8n_whatsapp_outgoing(
    phone: str,
    message: str,
    business_id: str,
    lead_id: Optional[int] = None,
    is_ai: bool = True
) -> Dict[str, Any]:
    """Send WhatsApp outgoing message event to n8n"""
    return send_event_to_n8n("whatsapp_outgoing", {
        "to": phone,
        "message": message,
        "business_id": business_id,
        "lead_id": lead_id,
        "is_ai_response": is_ai,
        "direction": "outgoing"
    })


def n8n_call_started(
    phone: str,
    business_id: str,
    call_sid: Optional[str] = None
) -> Dict[str, Any]:
    """Send call started event to n8n"""
    return send_event_to_n8n("call_started", {
        "phone": phone,
        "business_id": business_id,
        "call_sid": call_sid
    })


def n8n_call_ended(
    phone: str,
    business_id: str,
    call_sid: Optional[str] = None,
    duration_seconds: Optional[int] = None,
    summary: Optional[str] = None
) -> Dict[str, Any]:
    """Send call ended event to n8n"""
    return send_event_to_n8n("call_ended", {
        "phone": phone,
        "business_id": business_id,
        "call_sid": call_sid,
        "duration_seconds": duration_seconds,
        "summary": summary
    })


def n8n_lead_created(
    lead_id: int,
    phone: str,
    name: str,
    business_id: str,
    source: str = "unknown"
) -> Dict[str, Any]:
    """Send new lead created event to n8n"""
    return send_event_to_n8n("lead_created", {
        "lead_id": lead_id,
        "phone": phone,
        "name": name,
        "business_id": business_id,
        "source": source
    })


def n8n_appointment_created(
    appointment_id: int,
    lead_id: int,
    business_id: str,
    datetime_str: str,
    title: Optional[str] = None
) -> Dict[str, Any]:
    """Send appointment created event to n8n"""
    return send_event_to_n8n("appointment_created", {
        "appointment_id": appointment_id,
        "lead_id": lead_id,
        "business_id": business_id,
        "datetime": datetime_str,
        "title": title
    })
