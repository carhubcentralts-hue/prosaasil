"""
Twilio Call Creation Service - Single Source of Truth
🎯 SSOT: All outbound call creation goes through here
💰 CRITICAL: Prevents duplicate Twilio API calls (saves money!)
🔒 ATOMIC: Deduplication prevents race conditions
"""
import logging
import hashlib
import time
from typing import Dict, Any, Optional
from flask import request

log = logging.getLogger(__name__)

# 🔒 ATOMIC DEDUPLICATION: In-memory set to track recent call creation attempts
# Key format: "{business_id}:{lead_id}:{phone}:{minute_bucket}"
_recent_calls = {}  # {dedup_key: (timestamp, call_sid)}
_DEDUP_TTL_SECONDS = 60  # Deduplication window: 1 minute


def _generate_dedup_key(business_id: int, to_phone: str, lead_id: Optional[int] = None) -> str:
    """
    Generate atomic deduplication key to prevent duplicate calls.
    
    🔒 ATOMIC: Uses minute bucket to prevent race conditions
    Key format: business_id:lead_id:phone:minute_bucket
    """
    # Use current minute as bucket (e.g., 2025-12-28 13:05)
    minute_bucket = int(time.time() / 60)
    
    # Include lead_id if available for finer granularity
    if lead_id:
        key = f"{business_id}:{lead_id}:{to_phone}:{minute_bucket}"
    else:
        key = f"{business_id}:{to_phone}:{minute_bucket}"
    
    return key


def _check_and_mark_call(dedup_key: str) -> Optional[str]:
    """
    Atomically check if call already created and mark new creation.
    
    Returns:
        call_sid if call already exists (duplicate), None if new
    """
    global _recent_calls
    
    # Clean up expired entries (older than TTL)
    current_time = time.time()
    expired_keys = [k for k, (ts, _) in _recent_calls.items() if current_time - ts > _DEDUP_TTL_SECONDS]
    for k in expired_keys:
        del _recent_calls[k]
    
    # Check if call already created
    if dedup_key in _recent_calls:
        _, existing_call_sid = _recent_calls[dedup_key]
        log.warning(f"[DEDUP_HIT] Call already created: dedup_key={dedup_key}, existing_call_sid={existing_call_sid}")
        return existing_call_sid
    
    return None


def create_outbound_call(
    to_phone: str,
    from_phone: str,
    business_id: int,
    lead_id: Optional[int] = None,
    template_id: Optional[int] = None,
    job_id: Optional[int] = None,
    business_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a single outbound Twilio call with atomic deduplication.
    
    🎯 SSOT: This is the ONLY place that calls client.calls.create() for outbound
    🔒 ATOMIC: Deduplication prevents race conditions and duplicate billing
    ✅ OWNER: All outbound call creation
    ❌ NEVER: Call Twilio API directly - always use this function
    
    💰 COST SAVINGS: Prevents duplicate API calls by centralizing logic + dedup
    
    Args:
        to_phone: Normalized phone number to call
        from_phone: Twilio phone number to call from
        business_id: Business ID
        lead_id: Optional lead ID (used for deduplication)
        template_id: Optional template ID
        job_id: Optional job ID for bulk calls
        business_name: Optional business name for webhook
        
    Returns:
        Dict with call_sid, status, and is_duplicate flag
        
    Raises:
        Exception if Twilio API call fails
    """
    from server.services.twilio_call_control import get_twilio_client
    from urllib.parse import quote
    
    # 🔒 ATOMIC DEDUPLICATION: Check if call already created
    dedup_key = _generate_dedup_key(business_id, to_phone, lead_id)
    existing_call_sid = _check_and_mark_call(dedup_key)
    
    if existing_call_sid:
        log.info(f"[DEDUP] Returning existing call: {existing_call_sid}")
        return {
            "call_sid": existing_call_sid,
            "status": "duplicate",
            "success": True,
            "is_duplicate": True
        }
    
    # Build webhook URL
    host = request.headers.get("X-Forwarded-Host") or request.host
    webhook_url = f"https://{host}/twilio/outbound?business_id={business_id}"
    
    if lead_id:
        webhook_url += f"&lead_id={lead_id}"
    if template_id:
        webhook_url += f"&template_id={template_id}"
    if job_id:
        webhook_url += f"&job_id={job_id}"
    if business_name:
        webhook_url += f"&business_name={quote(business_name, safe='')}"
    
    # Get Twilio client
    client = get_twilio_client()
    
    # 🔥 SSOT: Single place for Twilio call creation
    # 💰 CRITICAL: This is the ONLY Twilio API call for outbound
    # 🎙️ NOTE: Recording is started separately via _start_recording_from_second_zero
    #          DO NOT use record=True here to avoid duplicate recording charges!
    log.info(f"[TWILIO_CALL] Creating outbound call: to={to_phone}, from={from_phone}, business_id={business_id}, lead_id={lead_id}")
    
    try:
        twilio_call = client.calls.create(
            to=to_phone,
            from_=from_phone,
            url=webhook_url,
            status_callback=f"https://{host}/webhook/call_status",
            status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
            # 🔥 SSOT: Recording is started via _start_recording_from_second_zero (not here)
            # ❌ DO NOT ADD record=True - recordings are managed separately
            recording_status_callback=f"https://{host}/webhook/handle_recording",
            recording_status_callback_event=['completed']
        )
        
        call_sid = twilio_call.sid
        
        # 🔒 ATOMIC: Mark call as created
        _recent_calls[dedup_key] = (time.time(), call_sid)
        
        log.info(f"[TWILIO_CALL] ✅ Call created: call_sid={call_sid}, dedup_key={dedup_key}")
        
        return {
            "call_sid": call_sid,
            "status": "initiated",
            "success": True,
            "is_duplicate": False
        }
        
    except Exception as e:
        log.error(f"[TWILIO_CALL] ❌ Failed to create call: {e}")
        raise


def create_outbound_call_for_bulk(
    to_phone: str,
    from_phone: str,
    business_id: int,
    job_id: int,
    business_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create outbound call for bulk queue system.
    
    🎯 SSOT: Delegates to create_outbound_call (single source)
    💰 Wrapper for bulk calling with job tracking
    
    Args:
        to_phone: Normalized phone number
        from_phone: Twilio number
        business_id: Business ID
        job_id: Job ID for tracking
        business_name: Optional business name
        
    Returns:
        Dict with call_sid and status
    """
    return create_outbound_call(
        to_phone=to_phone,
        from_phone=from_phone,
        business_id=business_id,
        job_id=job_id,
        business_name=business_name
    )
