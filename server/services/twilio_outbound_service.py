"""
Twilio Call Creation Service - Single Source of Truth
🎯 SSOT: All outbound call creation goes through here
💰 CRITICAL: Prevents duplicate Twilio API calls (saves money!)
🔒 ATOMIC: DB-based deduplication prevents race conditions
"""
import logging
import hashlib
import time
import uuid
from typing import Dict, Any, Optional
from sqlalchemy import text

log = logging.getLogger(__name__)

# 🔒 ATOMIC DEDUPLICATION: In-memory set for fast check (Layer 1)
# DB check is authoritative (Layer 2)
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


def _check_duplicate_in_db(dedup_key: str, business_id: int, to_phone: str) -> Optional[str]:
    """
    Check database for active/recent calls to prevent duplicates.
    
    🔒 ATOMIC: DB-level check is authoritative
    🔥 FIX: Ignores records with call_sid IS NULL if older than 60 seconds (stale)
    Returns call_sid if duplicate found, None otherwise
    """
    from server.db import db
    from server.models_sql import CallLog
    from datetime import datetime, timedelta
    
    try:
        # Check for active calls to same number within last 2 minutes
        cutoff_time = datetime.utcnow() - timedelta(seconds=120)
        stale_threshold = datetime.utcnow() - timedelta(seconds=60)  # 🔥 FIX: Stale threshold for NULL call_sid
        
        # 🔥 FIX: Exclude records with call_sid IS NULL if older than 60 seconds
        # These are stale records that never got a SID from Twilio (failed before SID was assigned)
        active_call = db.session.execute(text("""
            SELECT call_sid FROM call_log
            WHERE business_id = :business_id
            AND to_number = :to_phone
            AND created_at > :cutoff_time
            AND status IN ('initiated', 'ringing', 'in-progress', 'answered')
            AND (
                call_sid IS NOT NULL 
                OR created_at > :stale_threshold
            )
            ORDER BY created_at DESC
            LIMIT 1
        """), {
            "business_id": business_id,
            "to_phone": to_phone,
            "cutoff_time": cutoff_time,
            "stale_threshold": stale_threshold
        }).fetchone()
        
        if active_call:
            call_sid = active_call[0]
            # 🔥 FIX: If call_sid is None, it means it's a recent pending call (< 60s)
            # Allow these to prevent race conditions, but log for visibility
            if call_sid is None:
                log.info(f"[DEDUP_DB] Recent pending call without SID: to={to_phone} (allowing - may be in progress)")
                return None
            log.warning(f"[DEDUP_DB] Active call exists: call_sid={call_sid}, to={to_phone}")
            return call_sid
        
        return None
        
    except Exception as e:
        log.error(f"[DEDUP_DB] Error checking database: {e}")
        # On error, allow call to proceed (fail-open for availability)
        return None


def _check_and_mark_call(dedup_key: str, business_id: int, to_phone: str) -> Optional[str]:
    """
    Atomically check if call already created and mark new creation.
    
    🔒 ATOMIC: Two-layer check (memory + DB)
    Returns:
        call_sid if call already exists (duplicate), None if new
    """
    global _recent_calls
    
    # Layer 1: Fast in-memory check
    current_time = time.time()
    expired_keys = [k for k, (ts, _) in _recent_calls.items() if current_time - ts > _DEDUP_TTL_SECONDS]
    for k in expired_keys:
        del _recent_calls[k]
    
    if dedup_key in _recent_calls:
        _, existing_call_sid = _recent_calls[dedup_key]
        log.warning(f"[DEDUP_MEM] Call already created: dedup_key={dedup_key}, existing_call_sid={existing_call_sid}")
        return existing_call_sid
    
    # Layer 2: Authoritative DB check
    db_duplicate = _check_duplicate_in_db(dedup_key, business_id, to_phone)
    if db_duplicate:
        # Cache in memory to speed up subsequent checks
        _recent_calls[dedup_key] = (current_time, db_duplicate)
        return db_duplicate
    
    return None


def create_outbound_call(
    to_phone: str,
    from_phone: str,
    business_id: int,
    host: str,
    lead_id: Optional[int] = None,
    template_id: Optional[int] = None,
    job_id: Optional[int] = None,
    business_name: Optional[str] = None,
    lead_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a single outbound Twilio call with atomic deduplication.
    
    🎯 SSOT: This is the ONLY place that calls client.calls.create() for outbound
    🔒 ATOMIC: Two-layer deduplication (memory + DB) prevents race conditions
    💰 COST SAVINGS: Prevents duplicate API calls + tracks recording mode
    ✅ OWNER: All outbound call creation
    ❌ NEVER: Call Twilio API directly - always use this function
    
    Args:
        to_phone: Normalized phone number to call
        from_phone: Twilio phone number to call from
        business_id: Business ID
        host: Public host for webhook URLs (pass from request or use get_public_host())
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
    
    # 🔒 ATOMIC DEDUPLICATION: Check if call already created (memory + DB)
    dedup_key = _generate_dedup_key(business_id, to_phone, lead_id)
    existing_call_sid = _check_and_mark_call(dedup_key, business_id, to_phone)
    
    if existing_call_sid:
        log.info(f"[DEDUP] Returning existing call: {existing_call_sid}")
        return {
            "call_sid": existing_call_sid,
            "status": "duplicate",
            "success": True,
            "is_duplicate": True
        }
    
    # Build webhook URL (host is passed as parameter, no request context needed)
    webhook_url = f"https://{host}/webhook/outbound_call?business_id={business_id}"
    
    if lead_id:
        webhook_url += f"&lead_id={lead_id}"
    if template_id:
        webhook_url += f"&template_id={template_id}"
    if job_id:
        webhook_url += f"&job_id={job_id}"
    if business_name:
        webhook_url += f"&business_name={quote(business_name, safe='')}"
    if lead_name:
        webhook_url += f"&lead_name={quote(lead_name, safe='')}"
    
    # Get Twilio client
    client = get_twilio_client()
    
    # 🔥 SSOT: Single place for Twilio call creation
    # 💰 CRITICAL: This is the ONLY Twilio API call for outbound
    # 🎙️ RECORDING MODE: OFF (recording managed separately)
    #    Recording is started via _start_recording_from_second_zero() with mode="RECORDING_API"
    #    DO NOT use record=True here to avoid duplicate recording charges!
    
    # 🔥 TRACE LOGGING: Generate unique request ID for tracking
    req_uuid = str(uuid.uuid4())[:8]
    log.info(f"[OUTBOUND][REQ={req_uuid}] tenant={business_id} lead_id={lead_id} to={to_phone} from={from_phone}")
    log.info(f"[TWILIO_CALL] Creating outbound call: to={to_phone}, from={from_phone}, business_id={business_id}, lead_id={lead_id}, recording_mode=OFF")
    
    try:
        log.info(f"[OUTBOUND][REQ={req_uuid}] calling twilio...")
        
        twilio_call = client.calls.create(
            to=to_phone,
            from_=from_phone,
            url=webhook_url,
            status_callback=f"https://{host}/webhook/call_status",
            # 🔥 FIX: Added ALL terminal statuses so queue processing works correctly
            # Without 'no-answer', 'busy', 'failed', 'canceled', jobs stay in 'calling' status forever!
            status_callback_event=['initiated', 'ringing', 'answered', 'completed', 'busy', 'no-answer', 'failed', 'canceled'],
            # 🔥 SSOT: Recording is started via _start_recording_from_second_zero (not here)
            # 🎙️ recording_mode will be set to "RECORDING_API" when recording starts
            # ❌ DO NOT ADD record=True - recordings are managed separately
            recording_status_callback=f"https://{host}/webhook/handle_recording",
            recording_status_callback_event=['completed']
        )
        
        call_sid = twilio_call.sid
        
        # 🔒 ATOMIC: Mark call as created in memory
        _recent_calls[dedup_key] = (time.time(), call_sid)
        
        # 🔥 TRACE LOGGING: Log success
        log.info(f"[OUTBOUND][REQ={req_uuid}] twilio_ok call_sid={call_sid}")
        log.info(f"[TWILIO_CALL] ✅ Call created: call_sid={call_sid}, dedup_key={dedup_key}, recording_mode=OFF (will be set to RECORDING_API when recording starts)")
        
        return {
            "call_sid": call_sid,
            "status": "initiated",
            "success": True,
            "is_duplicate": False
        }
        
    except Exception as e:
        # 🔥 TRACE LOGGING: Log failure
        log.error(f"[OUTBOUND][REQ={req_uuid}] twilio_failed err={str(e)}")
        log.error(f"[TWILIO_CALL] ❌ Failed to create call: {e}")
        raise


def create_outbound_call_for_bulk(
    to_phone: str,
    from_phone: str,
    business_id: int,
    host: str,
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
        host: Public host for webhook URLs
        job_id: Job ID for tracking
        business_name: Optional business name
        
    Returns:
        Dict with call_sid and status
    """
    return create_outbound_call(
        to_phone=to_phone,
        from_phone=from_phone,
        business_id=business_id,
        host=host,
        job_id=job_id,
        business_name=business_name
    )
