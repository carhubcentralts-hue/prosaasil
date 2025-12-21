"""
BUILD 177: Generic Webhook Service for external integrations
Sends call data to n8n, Zapier, Monday.com, or any webhook endpoint
"""
import hashlib
import hmac
import json
import logging
import os
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

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
            # 🔥 BUILD 186 FIX: Handle missing columns gracefully
            settings = None
            try:
                settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
            except Exception as db_err:
                logger.error(f"[WEBHOOK] Could not load settings for business {business_id} (DB schema issue): {db_err}")
                return False
            
            if not settings:
                logger.warning(f"[WEBHOOK] No settings found for business {business_id}")
                return False
            
            # 🔥 BUILD 183: Route webhook by call direction
            if direction == "outbound":
                # Outbound calls: ONLY use outbound_webhook_url - no fallback
                webhook_url = getattr(settings, 'outbound_webhook_url', None)
                if not webhook_url:
                    logger.warning(f"[WEBHOOK] No outbound webhook URL configured for business {business_id} - skipping webhook send (direction={direction}, event={event_type})")
                    return False
                logger.info(f"[WEBHOOK] Using outbound_webhook_url for business {business_id}")
            elif direction == "inbound":
                # Inbound calls: Use inbound_webhook_url, fallback to generic
                inbound_url = getattr(settings, 'inbound_webhook_url', None)
                generic_url = settings.generic_webhook_url
                
                webhook_url = inbound_url or generic_url
                if not webhook_url:
                    logger.warning(f"[WEBHOOK] No inbound/generic webhook URL configured for business {business_id} (direction={direction}, event={event_type})")
                    return False
                
                if inbound_url:
                    logger.info(f"[WEBHOOK] Using inbound_webhook_url for business {business_id}")
                else:
                    logger.info(f"[WEBHOOK] Using generic_webhook_url (fallback) for business {business_id}")
            else:
                # Non-call events or unspecified: Use generic webhook
                if not settings.generic_webhook_url:
                    logger.warning(f"[WEBHOOK] No webhook URL configured for business {business_id}")
                    return False
                webhook_url = settings.generic_webhook_url
                logger.info(f"[WEBHOOK] Using generic_webhook_url for business {business_id}")
        
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
        
        # 🔍 Enhanced logging: Show payload preview (first 300 chars for debugging)
        payload_preview = payload_json[:300] + "..." if len(payload_json) > 300 else payload_json
        logger.debug(f"[WEBHOOK] Payload preview ({len(payload_json)} bytes): {payload_preview}")
        
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
                    logger.info(f"[WEBHOOK] Sending {event_type} to webhook (attempt {attempt + 1}/{MAX_RETRIES})")
                    
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
                            logger.info(f"[WEBHOOK] Following redirect to: {redirect_url}")
                            current_url = redirect_url
                            continue  # Retry with new URL
                    
                    if response.status_code >= 200 and response.status_code < 300:
                        logger.info(f"[WEBHOOK] Successfully sent {event_type} (status: {response.status_code})")
                        return True
                    else:
                        logger.warning(f"[WEBHOOK] Webhook returned error status {response.status_code}, response: {response.text[:200]}")
                        
                except requests.exceptions.Timeout:
                    logger.warning(f"[WEBHOOK] Timeout on attempt {attempt + 1}/{MAX_RETRIES}")
                except requests.exceptions.RequestException as e:
                    logger.warning(f"[WEBHOOK] Request error on attempt {attempt + 1}/{MAX_RETRIES}: {e}")
                
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAYS[attempt]
                    logger.info(f"[WEBHOOK] Retrying in {delay}s...")
                    time.sleep(delay)
            
            logger.error(f"[WEBHOOK] Failed to send {event_type} after {MAX_RETRIES} attempts")
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
    raw_city: Optional[str] = None,
    city_confidence: Optional[float] = None,
    city_raw_attempts: Optional[List[str]] = None,
    city_autocorrected: bool = False,
    name_raw_attempts: Optional[List[str]] = None,
    preferred_time: Optional[str] = None,
    customer_name: Optional[str] = None,
    recording_url: Optional[str] = None,
    metadata: Optional[Dict] = None,
    service_category_canonical: Optional[str] = None  # 🔥 NEW: Canonical service from lead.service_type
) -> bool:
    """
    Send call.completed webhook with full call data
    
    BUILD 177 Enhanced: Now includes phone, city, and service_category
    BUILD 184: Added raw_city and city_confidence from fuzzy matching
    BUILD 185: Added city_raw_attempts, city_autocorrected, name_raw_attempts
              for STT accuracy tracking and majority voting
    FIX: Added recording_url to ensure Monday/n8n always get recording link
    FIX: Added service_category_canonical for n8n to receive canonicalized service type
    
    Args:
        phone: Caller phone number (normalized E.164 format preferred)
        city: Canonical city name (e.g., "תל אביב")
        service_category: Type of service/professional (e.g., "חשמלאי", "שיפוצים") - RAW extracted value
        service_category_canonical: Canonical service type from lead.service_type (e.g., "מנעולן") - after canonicalization
        raw_city: Raw city input from customer before normalization
        city_confidence: Fuzzy matching confidence score (0-100)
        city_raw_attempts: List of all raw STT attempts for city (for debugging)
        city_autocorrected: Whether majority voting was used to correct STT
        name_raw_attempts: List of all raw STT attempts for name (for debugging)
        recording_url: URL to call recording (if available)
    """
    # 🔍 Enhanced logging: Show all key parameters for debugging
    logger.info(f"[WEBHOOK] send_call_completed_webhook called: call_id={call_id}, business_id={business_id}, direction={direction}")
    logger.debug(f"[WEBHOOK] Details: phone={phone or 'N/A'}, city={city or 'N/A'}, service={service_category or 'N/A'}, canonical={service_category_canonical or 'N/A'}")
    logger.debug(f"[WEBHOOK] Content: duration={duration_sec}s, transcript={len(transcript or '')} chars, summary={len(summary or '')} chars")
    logger.debug(f"[WEBHOOK] Recording: {'Available' if recording_url else 'N/A'}")
    
    # 🔥 FIX: Ensure ALL fields are properly serialized with NO null/undefined values
    # Monday.com and n8n expect consistent field types
    data = {
        "call_id": str(call_id) if call_id else "",
        "lead_id": str(lead_id) if lead_id else "",
        "phone": str(phone) if phone else "",
        "customer_name": str(customer_name) if customer_name else "",
        "city": str(city) if city else "",
        "raw_city": str(raw_city) if raw_city else "",
        "city_confidence": float(city_confidence) if city_confidence is not None else 0.0,
        "city_raw_attempts": list(city_raw_attempts) if city_raw_attempts else [],
        "city_autocorrected": bool(city_autocorrected) if city_autocorrected else False,
        "name_raw_attempts": list(name_raw_attempts) if name_raw_attempts else [],
        "service_category": str(service_category) if service_category else "",
        # 🔥 NEW: Canonical service fields for n8n compatibility
        "service_category_2": str(service_category_canonical) if service_category_canonical else "",
        "service_type_canonical": str(service_category_canonical) if service_category_canonical else "",
        "preferred_time": str(preferred_time) if preferred_time else "",
        "started_at": started_at.isoformat() if started_at else "",
        "ended_at": ended_at.isoformat() if ended_at else datetime.utcnow().isoformat(),
        "duration_sec": int(duration_sec) if duration_sec else 0,
        "transcript": str(transcript) if transcript else "",
        "summary": str(summary) if summary else "",
        "agent_name": str(agent_name) if agent_name else "Assistant",
        "direction": str(direction) if direction else "inbound",
        "recording_url": str(recording_url) if recording_url else "",  # 🔥 FIX: Always include recording URL for Monday/n8n
        "metadata": dict(metadata) if metadata else {},
        # 🔥 Monday.com field mapping (alternative field names for compatibility)
        "service": str(service_category) if service_category else "",  # Some integrations use "service" not "service_category"
        "call_status": "completed",  # Explicit status for filtering
        "call_direction": str(direction) if direction else "inbound"  # Alternative field name
    }
    
    # 🔥 CRITICAL LOGGING: Verify canonical values before webhook send
    logger.info(f"[WEBHOOK_PAYLOAD] service_category={data.get('service_category')} "
                f"service_category_2={data.get('service_category_2')} "
                f"service_type_canonical={data.get('service_type_canonical')}")
    
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
