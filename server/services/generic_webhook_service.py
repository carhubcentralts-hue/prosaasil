"""
BUILD 177: Generic Webhook Service for external integrations
Sends call data to n8n, Zapier, Monday.com, or any webhook endpoint
"""
import hashlib
import hmac
import json
import os
import threading
import time
from datetime import datetime
from typing import Any, Dict, Optional

import requests

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "prosaas-webhook-secret-key")
MAX_RETRIES = 3
RETRY_DELAYS = [1, 3, 10]


def generate_signature(payload: str) -> str:
    """Generate HMAC-SHA256 signature for webhook payload"""
    return hmac.new(
        WEBHOOK_SECRET.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()


def send_generic_webhook(
    business_id: int,
    event_type: str,
    data: Dict[str, Any],
    webhook_url: Optional[str] = None,
    direction: Optional[str] = None  # 🔥 BUILD 183: "inbound" or "outbound" for call direction routing
) -> bool:
    """
    Send webhook to external service (n8n, Zapier, etc.)
    
    Args:
        business_id: The business ID
        event_type: Event type (e.g., "call.completed", "lead.created")
        data: Payload data to send
        webhook_url: Optional webhook URL (if not provided, fetches from BusinessSettings)
        direction: Call direction for routing ("inbound" or "outbound")
    
    🔥 BUILD 183: Webhook Routing Logic:
        - Inbound calls: Use inbound_webhook_url, fallback to generic_webhook_url
        - Outbound calls: Use outbound_webhook_url ONLY - if not set, NO webhook sent
        - Non-call events: Use generic_webhook_url
    
    Returns:
        True if successful, False otherwise
    """
    from server.models_sql import BusinessSettings, db
    
    try:
        if not webhook_url:
            settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
            if not settings:
                print(f"[WEBHOOK] No settings found for business {business_id}")
                return False
            
            # 🔥 BUILD 183: Route webhook by call direction
            if direction == "outbound":
                # Outbound calls: ONLY use outbound_webhook_url - no fallback
                webhook_url = getattr(settings, 'outbound_webhook_url', None)
                if not webhook_url:
                    print(f"[WEBHOOK] No outbound webhook URL configured for business {business_id} - skipping")
                    return False
            elif direction == "inbound":
                # Inbound calls: Use inbound_webhook_url, fallback to generic
                webhook_url = getattr(settings, 'inbound_webhook_url', None) or settings.generic_webhook_url
                if not webhook_url:
                    print(f"[WEBHOOK] No inbound/generic webhook URL configured for business {business_id}")
                    return False
            else:
                # Non-call events or unspecified: Use generic webhook
                if not settings.generic_webhook_url:
                    print(f"[WEBHOOK] No webhook URL configured for business {business_id}")
                    return False
                webhook_url = settings.generic_webhook_url
        
        if not webhook_url:
            return False
        
        payload = {
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "business_id": str(business_id),
            **data
        }
        
        payload_json = json.dumps(payload, ensure_ascii=False, default=str)
        signature = generate_signature(payload_json)
        
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "X-ProSaaS-Signature": signature,
            "X-ProSaaS-Event": event_type,
            "X-ProSaaS-Timestamp": datetime.utcnow().isoformat()
        }
        
        def send_with_retry():
            # 🔧 BUILD 177: Handle redirects properly to preserve POST method
            current_url = webhook_url
            
            for attempt in range(MAX_RETRIES):
                try:
                    print(f"[WEBHOOK] Sending {event_type} to {current_url[:50]}... (attempt {attempt + 1})")
                    
                    # Disable auto-redirects to handle them manually (preserve POST on redirect)
                    response = requests.post(
                        current_url,
                        data=payload_json.encode('utf-8'),
                        headers=headers,
                        timeout=30,
                        allow_redirects=False  # Handle redirects manually to preserve POST
                    )
                    
                    # Handle redirect (301, 302, 307, 308) - follow with POST
                    if response.status_code in (301, 302, 307, 308):
                        redirect_url = response.headers.get('Location')
                        if redirect_url:
                            print(f"[WEBHOOK] 🔀 Following redirect to: {redirect_url}")
                            current_url = redirect_url
                            continue  # Retry with new URL
                    
                    if response.status_code >= 200 and response.status_code < 300:
                        print(f"[WEBHOOK] ✅ Success: {event_type} sent to webhook (status {response.status_code})")
                        return True
                    else:
                        print(f"[WEBHOOK] ⚠️ Response {response.status_code}: {response.text[:200]}")
                        
                except requests.exceptions.Timeout:
                    print(f"[WEBHOOK] ⏱️ Timeout on attempt {attempt + 1}")
                except requests.exceptions.RequestException as e:
                    print(f"[WEBHOOK] ❌ Request error on attempt {attempt + 1}: {e}")
                
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAYS[attempt]
                    print(f"[WEBHOOK] Retrying in {delay}s...")
                    time.sleep(delay)
            
            print(f"[WEBHOOK] ❌ Failed after {MAX_RETRIES} attempts")
            return False
        
        thread = threading.Thread(target=send_with_retry, daemon=True)
        thread.start()
        
        return True
        
    except Exception as e:
        print(f"[WEBHOOK] ❌ Error sending webhook: {e}")
        import traceback
        traceback.print_exc()
        return False


def send_call_completed_webhook(
    business_id: int,
    call_id: str,
    lead_id: Optional[int],
    phone: str,
    started_at: Optional[datetime],
    ended_at: Optional[datetime],
    duration_sec: int,
    transcript: str,
    summary: str,
    agent_name: str,
    direction: str = "inbound",
    city: Optional[str] = None,
    service_category: Optional[str] = None,
    metadata: Optional[Dict] = None
) -> bool:
    """
    Send call.completed webhook with full call data
    
    BUILD 177 Enhanced: Now includes phone, city, and service_category
    
    Args:
        phone: Caller phone number (normalized E.164 format preferred)
        city: Customer's city (e.g., "תל אביב")
        service_category: Type of service/professional (e.g., "חשמלאי", "שיפוצים")
    """
    data = {
        "call_id": str(call_id) if call_id else "",
        "lead_id": str(lead_id) if lead_id else "",
        "phone": phone or "",
        "city": city or "",
        "service_category": service_category or "",
        "started_at": started_at.isoformat() if started_at else "",
        "ended_at": ended_at.isoformat() if ended_at else datetime.utcnow().isoformat(),
        "duration_sec": duration_sec,
        "transcript": transcript or "",
        "summary": summary or "",
        "agent_name": agent_name or "Assistant",
        "direction": direction,
        "metadata": metadata or {}
    }
    
    print(f"[WEBHOOK] 📦 Payload built: call_id={call_id}, phone={phone or 'N/A'}, city={city or 'N/A'}, direction={direction}")
    
    # 🔥 BUILD 183: Pass direction for webhook routing
    return send_generic_webhook(business_id, "call.completed", data, direction=direction)


def send_lead_created_webhook(
    business_id: int,
    lead_id: int,
    name: str,
    phone: str,
    email: Optional[str] = None,
    source: str = "voice",
    metadata: Optional[Dict] = None
) -> bool:
    """Send lead.created webhook when a new lead is created"""
    data = {
        "lead_id": str(lead_id),
        "name": name or "",
        "phone": phone or "",
        "email": email or "",
        "source": source,
        "metadata": metadata or {}
    }
    
    return send_generic_webhook(business_id, "lead.created", data)


def send_appointment_booked_webhook(
    business_id: int,
    appointment_id: int,
    lead_id: Optional[int],
    lead_name: str,
    lead_phone: str,
    scheduled_at: datetime,
    service: Optional[str] = None,
    notes: Optional[str] = None,
    metadata: Optional[Dict] = None
) -> bool:
    """Send appointment.booked webhook when an appointment is scheduled"""
    data = {
        "appointment_id": str(appointment_id),
        "lead_id": str(lead_id) if lead_id else "",
        "lead_name": lead_name or "",
        "lead_phone": lead_phone or "",
        "scheduled_at": scheduled_at.isoformat() if scheduled_at else "",
        "service": service or "",
        "notes": notes or "",
        "metadata": metadata or {}
    }
    
    return send_generic_webhook(business_id, "appointment.booked", data)
