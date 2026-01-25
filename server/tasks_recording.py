"""
Background Recording Processing - תמלול והקלטות ברקע

DB RESILIENCE: Recording worker handles DB outages gracefully and continues processing
"""
import os
import requests
import logging
import queue
import wave
import contextlib
import traceback
from threading import Thread, Semaphore
import threading
from datetime import datetime
from typing import Optional
from sqlalchemy.exc import OperationalError, DisconnectionError

# 🔒 Import Lead model at top level for efficient access
from server.models_sql import CallLog, Business, Lead, BusinessTopic


logger = logging.getLogger(__name__)

log = logging.getLogger("tasks.recording")

# 🔥 BUILD 342: Transcript source constants
TRANSCRIPT_SOURCE_RECORDING = "recording"  # Transcribed from recording file
TRANSCRIPT_SOURCE_REALTIME = "realtime"    # Using realtime transcript
TRANSCRIPT_SOURCE_FAILED = "failed"        # Transcription attempt failed

# ✅ Global queue for recording jobs - single shared instance
RECORDING_QUEUE = queue.Queue()

# 🔥 Global DEBUG flag - matches logging_setup.py
# DEBUG=1 → Production (minimal logs)
# DEBUG=0 → Development (full logs)
DEBUG = os.getenv("DEBUG", "1") == "1"

# 🔥 DEDUPLICATION: Track last enqueue time per call_sid to prevent spam
# Key: call_sid, Value: timestamp of last enqueue
_last_enqueue_time: dict = {}
_enqueue_lock = threading.Lock()

# Cooldown period in seconds - don't enqueue same call_sid more than once per 10 minutes
ENQUEUE_COOLDOWN_SECONDS = 600  # 🔥 FIX: Increased from 60s to 10min (600s)

# 🔥 FIX: Concurrency limiter - max simultaneous recording downloads
# This prevents overwhelming the system with too many parallel downloads
MAX_CONCURRENT_DOWNLOADS = int(os.getenv("MAX_CONCURRENT_DOWNLOADS", "3"))
_download_semaphore = Semaphore(MAX_CONCURRENT_DOWNLOADS)

# 🔥 FIX: Track active downloads with thread-safe counter (don't use Semaphore._value)
_active_downloads_count = 0
_active_downloads_lock = threading.Lock()

# 🔥 AI Customer Service: Minimum call duration (in seconds) to generate full summary
# Calls shorter than this get a simple "not answered" message instead of attempting full summary
MIN_CALL_DURATION_FOR_SUMMARY = 5

# 🔥 FIX: Redis-based deduplication for distributed systems
# Fallback to in-memory if Redis not available
_redis_client = None
REDIS_DEDUP_ENABLED = False

try:
    import redis
    REDIS_URL = os.getenv('REDIS_URL')
    if REDIS_URL:
        _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        _redis_client.ping()
        REDIS_DEDUP_ENABLED = True
        logger.info("✅ [RECORDING] Redis deduplication enabled")
        log.info("[RECORDING] Redis-based job deduplication active")
    else:
        logger.info("ℹ️ [RECORDING] REDIS_URL not set - using in-memory deduplication")
        log.info("[RECORDING] In-memory job deduplication active (for production use Redis)")
except Exception as e:
    logger.warning(f"⚠️ [RECORDING] Redis not available, using in-memory deduplication: {e}")
    log.warning(f"[RECORDING] Redis initialization failed: {e}")


def _acquire_redis_dedup_lock(call_sid: str, business_id: int, job_type: str = "download") -> tuple[bool, str]:
    """
    🔥 FIX: Try to acquire Redis-based deduplication lock for a job.
    
    Uses Redis SET with NX (only if not exists) and EX (expiry) to create distributed locks.
    This prevents the same CallSid from being enqueued multiple times across workers/processes.
    
    🔥 CRITICAL: Key includes business_id to prevent cross-business blocking
    
    Args:
        call_sid: The call SID to lock
        business_id: Business ID to ensure cross-business isolation
        job_type: Type of job ("download" or "full")
    
    Returns:
        tuple: (acquired: bool, reason: str)
    """
    if not REDIS_DEDUP_ENABLED or not _redis_client:
        return True, "redis_not_available"  # Fall through to in-memory check
    
    try:
        # 🔥 FIX: Include business_id in key to prevent cross-business blocking
        redis_key = f"recording_job:{business_id}:{job_type}:{call_sid}"
        # Try to set key with 10-minute expiry (600 seconds)
        # NX = only set if not exists (atomic operation)
        acquired = _redis_client.set(redis_key, "locked", nx=True, ex=ENQUEUE_COOLDOWN_SECONDS)
        
        if acquired:
            log.debug(f"[RECORDING] ✅ Redis dedup lock acquired for {call_sid} (business:{business_id}, {job_type})")
            return True, "lock_acquired"
        else:
            # Key already exists - job recently enqueued
            ttl = _redis_client.ttl(redis_key)
            log.debug(f"[RECORDING] ⏭️  Redis dedup lock exists for {call_sid} (business:{business_id}, TTL: {ttl}s)")
            return False, f"redis_locked (TTL: {ttl}s)"
    except Exception as e:
        logger.error(f"[RECORDING] Redis dedup error for {call_sid}: {e}")
        # On Redis error, fall through to allow job (don't block on Redis failures)
        return True, "redis_error_fallthrough"


def normalize_call_direction(twilio_direction):
    """
    Normalize Twilio's direction values to simple inbound/outbound/unknown.
    
    Twilio Direction values:
    - 'inbound' -> 'inbound'
    - 'outbound-api' -> 'outbound' (parent call)
    - 'outbound-dial' -> 'outbound' (actual outbound call to customer)
    - anything else -> 'unknown'
    
    Args:
        twilio_direction: Original direction from Twilio webhook
    
    Returns:
        Normalized direction: 'inbound', 'outbound', or 'unknown'
    """
    if not twilio_direction:
        return "unknown"
    
    twilio_dir_lower = str(twilio_direction).lower()
    
    if twilio_dir_lower.startswith("outbound"):
        return "outbound"
    elif twilio_dir_lower.startswith("inbound"):
        return "inbound"
    else:
        return "unknown"


def _should_enqueue_download(call_sid: str, business_id: int, job_type: str = "download") -> tuple[bool, str]:
    """
    🔥 DEDUPLICATION: Check if we should enqueue a download for this call_sid.
    
    Prevents duplicate downloads by (in order):
    1. Checking if file already cached locally
    2. Checking if download already in progress (via recording_service)
    3. Checking Redis dedup lock (distributed, 10min TTL, per-business)
    4. Checking in-memory cooldown (fallback if Redis unavailable)
    
    Args:
        call_sid: The call SID to check
        business_id: Business ID for cross-business isolation
        job_type: Type of job ("download" or "full")
        
    Returns:
        tuple: (should_enqueue: bool, reason: str)
    """
    import time
    from server.services.recording_service import is_download_in_progress, check_local_recording_exists
    
    # Check 1: File already cached locally
    if check_local_recording_exists(call_sid):
        return False, "already_cached"
    
    # Check 2: Download already in progress
    if is_download_in_progress(call_sid):
        return False, "download_in_progress"
    
    # Check 3: Redis-based deduplication (distributed lock)
    # 🔥 FIX: Pass business_id to prevent cross-business blocking
    redis_acquired, redis_reason = _acquire_redis_dedup_lock(call_sid, business_id, job_type)
    if not redis_acquired:
        return False, redis_reason
    
    # Check 4: In-memory cooldown (fallback/additional safety)
    # This is needed even with Redis for single-process deduplication
    with _enqueue_lock:
        last_time = _last_enqueue_time.get(call_sid)
        if last_time:
            elapsed = time.time() - last_time
            if elapsed < ENQUEUE_COOLDOWN_SECONDS:
                return False, f"cooldown_active ({int(ENQUEUE_COOLDOWN_SECONDS - elapsed)}s remaining)"
        
        # Mark as enqueued now
        _last_enqueue_time[call_sid] = time.time()
    
    return True, "ok"

def enqueue_recording_job(call_sid, recording_url, business_id, from_number="", to_number="", retry_count=0):
    """Enqueue recording job for background processing
    
    Args:
        call_sid: Twilio call SID
        recording_url: URL to recording file
        business_id: Business ID for the call
        from_number: Caller phone number
        to_number: Called phone number
        retry_count: Current retry attempt (0-2 allowed, max 3 attempts total)
    
    🔥 NEW: Rate limiting removed - now using semaphore system for UI-triggered downloads
    This function is for webhook-triggered background processing only
    """
    # 🔥 REMOVED: rate_limit check - only applies to UI-triggered downloads
    
    # Basic deduplication: Check if file already cached
    from server.services.recording_service import check_local_recording_exists
    if check_local_recording_exists(call_sid):
        log.debug(f"[OFFLINE_STT] File already cached for {call_sid}")
        return  # Don't enqueue
    
    # Enqueue full processing job (download + transcribe)
    RECORDING_QUEUE.put({
        "call_sid": call_sid,
        "recording_url": recording_url,
        "business_id": business_id,
        "from_number": from_number,
        "to_number": to_number,
        "retry_count": retry_count,
        "type": "full"  # Full processing (download + transcribe)
    })
    
    if retry_count == 0:
        log.info(f"[OFFLINE_STT] Recording job enqueued: {call_sid}")
    else:
        log.info(f"[OFFLINE_STT] Recording job retry {retry_count}: {call_sid}")


def enqueue_recording_download_only(call_sid, recording_url, business_id, from_number="", to_number="", retry_count=0):
    """
    🔥 FIX: Enqueue PRIORITY job to download recording (without transcription)
    Used by UI when user clicks "play" to get recording ASAP
    
    This creates a high-priority job that only downloads the file, skipping transcription.
    Transcription will happen later via the normal webhook flow.
    
    🔥 NEW: Rate limiting removed - now using semaphore system in stream_recording
    The semaphore system handles slot management before this function is called.
    """
    # 🔥 REMOVED: rate_limit check - replaced by semaphore system in stream_recording
    
    # Basic deduplication: Check if file already cached
    from server.services.recording_service import check_local_recording_exists
    if check_local_recording_exists(call_sid):
        log.debug(f"[DOWNLOAD_ONLY] File already cached for {call_sid}")
        return  # Don't enqueue
    
    # Enqueue download job
    RECORDING_QUEUE.put({
        "call_sid": call_sid,
        "recording_url": recording_url,
        "business_id": business_id,
        "from_number": from_number,
        "to_number": to_number,
        "retry_count": retry_count,
        "type": "download_only"  # Just download, skip transcription
    })
    
    if retry_count == 0:
        log.info(f"[DOWNLOAD_ONLY] Priority download job enqueued: {call_sid}")
    else:
        log.info(f"[DOWNLOAD_ONLY] Retry {retry_count} enqueued: {call_sid}")

def enqueue_recording(form_data):
    """Legacy wrapper - converts form_data to new queue format"""
    call_sid = form_data.get("CallSid")
    recording_url = form_data.get("RecordingUrl")
    to_number = form_data.get("To", "")
    from_number = form_data.get("From", "")
    
    # Identify business_id
    business_id = None
    try:
        from server.app_factory import get_process_app
        app = get_process_app()
        with app.app_context():
            business = _identify_business_for_call(to_number, from_number)
            if business:
                business_id = business.id
    except Exception as e:
        log.warning(f"Could not identify business for recording: {e}")
    
    # Enqueue for worker processing
    enqueue_recording_job(call_sid, recording_url, business_id, from_number, to_number)

def start_recording_worker(app):
    """
    🔧 WORKER: Background worker loop - processes recording jobs from queue.
    
    🔥 CRITICAL: This runs in a WORKER thread/container, NOT in API!
    All recording downloads happen here, not in the API endpoints.
    
    DB RESILIENCE: This worker continues processing even if DB is temporarily unavailable.
    Jobs that fail due to DB errors are logged but don't crash the worker.
    
    SEMAPHORE SYSTEM: Uses Redis-based slot management (3 concurrent per business)
    - When job completes: release_slot() is called (atomic)
    - Automatically processes next from queue
    
    RETRY LOGIC: If recording isn't ready yet, retries with exponential backoff:
    - Attempt 1: Immediate (0s delay)
    - Attempt 2: After 10s delay
    - Attempt 3: After 30s delay  
    - Attempt 4: After 90s delay (final attempt)
    Max 3 retries = 4 total attempts
    """
    logger.info("✅ [WORKER] Recording worker loop started")
    logger.info("🔧 [WORKER] All downloads happen here, not in API!")
    log.info("[WORKER] Recording worker thread initialized")
    
    # 🔥 FIX: Start metrics logging thread
    def log_system_metrics():
        """Background thread to log queue metrics every 60 seconds"""
        import time
        
        while True:
            try:
                # Get queue size
                queue_size = RECORDING_QUEUE.qsize()
                
                # Get active downloads from thread-safe counter
                with _active_downloads_lock:
                    active_downloads = _active_downloads_count
                
                # Log metrics
                if queue_size > 10:
                    logger.warning(
                        f"⚠️ [WORKER METRICS] Recording queue: {queue_size} jobs pending | "
                        f"Active downloads: {active_downloads}/{MAX_CONCURRENT_DOWNLOADS} | "
                        f"Dedup entries: {len(_last_enqueue_time)}"
                    )
                elif queue_size > 0 or active_downloads > 0:
                    logger.info(
                        f"📊 [WORKER METRICS] Recording queue: {queue_size} jobs pending | "
                        f"Active downloads: {active_downloads}/{MAX_CONCURRENT_DOWNLOADS} | "
                        f"Dedup entries: {len(_last_enqueue_time)}"
                    )
                else:
                    logger.debug(
                        f"📊 [WORKER METRICS] Recording queue: idle | "
                        f"Dedup entries: {len(_last_enqueue_time)}"
                    )
            except Exception as e:
                logger.error(f"[WORKER METRICS] Error logging metrics: {e}")
            
            # Sleep for 60 seconds before next log
            time.sleep(60)
    
    # Start metrics thread (daemon so it stops when main thread exits)
    metrics_thread = threading.Thread(target=log_system_metrics, daemon=True, name="RecordingMetrics")
    metrics_thread.start()
    logger.info("📊 [WORKER] System metrics logging started (every 60s)")
    
    # Retry backoff delays in seconds (0s, 10s, 30s, 90s)
    RETRY_DELAYS = [0, 10, 30, 90]
    MAX_RETRIES = 2  # 0-indexed, so 0, 1, 2 = 3 total attempts
    
    with app.app_context():
        while True:
            task_done_called = False  # 🔥 FIX: Track if we already called task_done()
            try:
                # Block until a job is available
                job = RECORDING_QUEUE.get()
                
                call_sid = job["call_sid"]
                recording_url = job["recording_url"]
                business_id = job.get("business_id")
                from_number = job.get("from_number", "")
                to_number = job.get("to_number", "")
                retry_count = job.get("retry_count", 0)
                job_type = job.get("type", "full")  # 🔥 NEW: "full" or "download_only"
                
                # 🔥 FIX: Acquire semaphore to limit concurrent downloads
                # This prevents too many parallel downloads from overwhelming the system
                log.debug(f"[RECORDING] Waiting for download slot (max {MAX_CONCURRENT_DOWNLOADS} concurrent)...")
                _download_semaphore.acquire()
                
                # Increment active downloads counter
                with _active_downloads_lock:
                    global _active_downloads_count
                    _active_downloads_count += 1
                
                try:
                    log.debug(f"[WORKER] Download slot acquired for {call_sid}")
                    
                    # 🔥 FIX: Handle download_only jobs (priority for UI)
                    if job_type == "download_only":
                        logger.info(f"⚡ [WORKER] Processing priority download for {call_sid}")
                        log.info(f"[WORKER DOWNLOAD_ONLY] Processing priority download: {call_sid}")
                        
                        # Just download the file, don't transcribe
                        success = download_recording_only(call_sid, recording_url)
                        
                        if success:
                            logger.info(f"✅ [WORKER] Recording downloaded for {call_sid}")
                            log.info(f"[WORKER DOWNLOAD_ONLY] Recording downloaded successfully: {call_sid}")
                        else:
                            # 🔥 FIX: Retry download_only jobs on failure (up to 2 retries)
                            if retry_count < 2:
                                import time
                                
                                delay = 5  # Short delay for download retries
                                logger.error(f"⚠️ [WORKER] Download failed for {call_sid}, retrying in {delay}s")
                                log.warning(f"[WORKER DOWNLOAD_ONLY] Download failed for {call_sid}, scheduling retry {retry_count + 1}")
                                
                                def delayed_retry():
                                    time.sleep(delay)
                                    enqueue_recording_download_only(
                                        call_sid=call_sid,
                                        recording_url=recording_url,
                                        business_id=business_id,
                                        from_number=from_number,
                                        to_number=to_number,
                                        retry_count=retry_count + 1  # 🔥 FIX: Increment retry count
                                    )
                                
                                retry_thread = threading.Thread(target=delayed_retry, daemon=True)
                                retry_thread.start()
                            else:
                                logger.error(f"❌ [DOWNLOAD_ONLY] Max retries reached for {call_sid}")
                                log.error(f"[DOWNLOAD_ONLY] Max retries reached for {call_sid}")
                        
                        # 🔥 FIX: Mark as done and set flag to prevent double task_done()
                        RECORDING_QUEUE.task_done()
                        task_done_called = True
                    
                    # Normal full processing (download + transcribe)
                    else:
                        logger.info(f"🎧 [OFFLINE_STT] Starting offline transcription for {call_sid} (attempt {retry_count + 1})")
                        log.info(f"[OFFLINE_STT] Processing recording: {call_sid} (attempt {retry_count + 1})")
                        
                        # Build form_data for legacy processing function
                        form_data = {
                            "CallSid": call_sid,
                            "RecordingUrl": recording_url,
                            "From": from_number,
                            "To": to_number,
                        }
                        
                        # Process the recording
                        success = process_recording_async(form_data)
                        
                        # Check if recording was actually processed (audio file existed)
                        # If audio_file was None, we should retry
                        if success is False and retry_count < MAX_RETRIES:
                            # Recording not ready yet - schedule retry with backoff
                            import time
                            
                            delay = RETRY_DELAYS[retry_count + 1] if retry_count + 1 < len(RETRY_DELAYS) else RETRY_DELAYS[-1]
                            logger.info(f"⏰ [OFFLINE_STT] Recording not ready for {call_sid}, retrying in {delay}s")
                            log.info(f"[OFFLINE_STT] Scheduling retry {retry_count + 1} for {call_sid} with {delay}s delay")
                            
                            # Schedule retry in background thread
                            def delayed_retry():
                                time.sleep(delay)
                                enqueue_recording_job(
                                    call_sid=call_sid,
                                    recording_url=recording_url,
                                    business_id=business_id,
                                    from_number=from_number,
                                    to_number=to_number,
                                    retry_count=retry_count + 1
                                )
                            
                            retry_thread = threading.Thread(target=delayed_retry, daemon=True)
                            retry_thread.start()
                        elif retry_count >= MAX_RETRIES and not success:
                            logger.error(f"❌ [OFFLINE_STT] Max retries reached for {call_sid} - giving up")
                            log.error(f"[OFFLINE_STT] Max retries ({MAX_RETRIES}) exceeded for {call_sid}")
                        else:
                            logger.info(f"✅ [OFFLINE_STT] Completed processing for {call_sid}")
                            log.info(f"[OFFLINE_STT] Recording processed successfully: {call_sid}")
                
                finally:
                    # 🔥 WORKER: Release semaphore slot and process next from queue
                    # This runs in WORKER container, not API!
                    if job_type == "download_only":
                        # Release slot and get next from queue (ATOMIC operation)
                        from server.recording_semaphore import release_slot
                        logger.info(f"🔧 [WORKER] Releasing slot for {call_sid} in business {business_id}")
                        next_call_sid = release_slot(business_id, call_sid)
                        
                        # If there's a next job waiting, enqueue it
                        if next_call_sid:
                            # Get call info for next job
                            try:
                                from server.models_sql import CallLog
                                next_call = CallLog.query.filter_by(call_sid=next_call_sid).first()
                                if next_call and next_call.recording_url:
                                    logger.info(f"🔧 [WORKER] Processing next from queue: {next_call_sid}")
                                    enqueue_recording_download_only(
                                        call_sid=next_call_sid,
                                        recording_url=next_call.recording_url,
                                        business_id=business_id,
                                        from_number=next_call.from_number or "",
                                        to_number=next_call.to_number or ""
                                    )
                                else:
                                    logger.warning(f"⚠️ [WORKER] Next call {next_call_sid} not found in DB or no recording_url")
                            except Exception as e:
                                logger.error(f"❌ [WORKER] Error enqueuing next job: {e}")
                    
                    # Always release global semaphore
                    with _active_downloads_lock:
                        _active_downloads_count -= 1
                    _download_semaphore.release()
                    log.debug(f"[WORKER] Download slot released for {call_sid}")
                
            except (OperationalError, DisconnectionError) as e:
                # 🔥 DB RESILIENCE: DB error - log and continue with next job
                from server.utils.db_health import log_db_error
                log_db_error(e, context="recording_worker")
                logger.error(f"🔴 [OFFLINE_STT] DB error processing {job.get('call_sid', 'unknown')} - skipping")
                
                # Rollback to clean up session
                try:
                    from server.db import db
                    db.session.rollback()
                    db.session.close()
                except Exception:
                    pass
                
                # Do NOT crash worker - continue with next job
                
            except Exception as e:
                # 🔥 DB RESILIENCE: Any other error - log and continue
                log.error(f"[OFFLINE_STT] Worker error: {e}")
                logger.error(f"❌ [OFFLINE_STT] Error processing {job.get('call_sid', 'unknown')}: {e}")
                import traceback
                traceback.print_exc()
                
                # Do NOT crash worker - continue with next job
                
            finally:
                # 🔥 FIX: Only call task_done() if we haven't already called it
                if not task_done_called:
                    RECORDING_QUEUE.task_done()


def download_recording_only(call_sid, recording_url):
    """
    🔥 FIX: Download recording file only (no transcription)
    Used for priority download when UI requests playback
    
    Returns:
        bool: True if download succeeded, False otherwise
    """
    try:
        logger.info(f"⚡ [DOWNLOAD_ONLY] Starting download for {call_sid}")
        log.info(f"[DOWNLOAD_ONLY] Starting download for {call_sid}")
        
        # Get CallLog to access recording details
        from server.app_factory import get_process_app
        from server.models_sql import CallLog
        from server.services.recording_service import get_recording_file_for_call
        
        app = get_process_app()
        with app.app_context():
            call_log = CallLog.query.filter_by(call_sid=call_sid).first()
            
            if not call_log:
                logger.warning(f"⚠️ [DOWNLOAD_ONLY] CallLog not found for {call_sid}")
                log.warning(f"[DOWNLOAD_ONLY] CallLog not found for {call_sid}")
                return False
            
            # Use unified recording service to download
            audio_file = get_recording_file_for_call(call_log)
            
            if audio_file and os.path.exists(audio_file):
                file_size = os.path.getsize(audio_file)
                logger.info(f"✅ [DOWNLOAD_ONLY] Downloaded {file_size} bytes for {call_sid}")
                log.info(f"[DOWNLOAD_ONLY] Downloaded {file_size} bytes for {call_sid}")
                return True
            else:
                logger.error(f"❌ [DOWNLOAD_ONLY] Failed to download for {call_sid}")
                log.error(f"[DOWNLOAD_ONLY] Failed to download for {call_sid}")
                return False
                
    except Exception as e:
        logger.error(f"❌ [DOWNLOAD_ONLY] Error downloading {call_sid}: {e}")
        log.error(f"[DOWNLOAD_ONLY] Error downloading {call_sid}: {e}")
        import traceback
        traceback.print_exc()
        return False


def process_recording_async(form_data):
    """
    ✨ עיבוד הקלטה אסינכרוני מלא: תמלול + סיכום חכם + 🆕 POST-CALL EXTRACTION
    
    🎯 SSOT RESPONSIBILITIES:
    ✅ OWNER: Post-call transcription (final_transcript)
    ✅ OWNER: Recording metadata (audio_bytes_len, audio_duration_sec, transcript_source)
    ✅ APPENDER: Adds data to CallLog (never changes status or basic fields)
    ❌ NEVER: Update CallLog.status (webhooks own this)
    ❌ NEVER: Update during active calls (only after call ends)
    
    🔥 PRIORITY ORDER (with fallback):
    1. Primary: Transcription from full recording (high quality)
    2. Fallback: Realtime transcript if recording transcription fails/empty
    
    🔥 SSOT: Skip logic prevents duplicate transcriptions:
    - Skips if final_transcript exists AND transcript_source != "failed"
    - Only re-transcribes if previous attempt failed
    
    Returns:
        bool: True if processing succeeded (audio file existed), False if recording not ready (should retry)
    """
    try:
        recording_url = form_data.get("RecordingUrl")
        call_sid = form_data.get("CallSid")
        from_number = form_data.get("From", "")
        to_number = form_data.get("To", "")
        
        log.info("Starting async processing for CallSid=%s", call_sid)
        logger.info(f"🎧 [OFFLINE_STT] Starting processing for {call_sid}")
        
        # ✅ NEW: Use unified recording service - same source as UI
        from server.services.recording_service import get_recording_file_for_call
        from server.app_factory import get_process_app
        
        # Get CallLog to access recording_url (single source of truth)
        audio_file = None
        call_log = None
        try:
            app = get_process_app()
            with app.app_context():
                from server.models_sql import CallLog
                call_log = CallLog.query.filter_by(call_sid=call_sid).first()
                
                if call_log:
                    # 🔥 SSOT: Skip if already successfully transcribed (prevent duplicate transcription)
                    # Policy: Only re-transcribe if source is "failed" or missing
                    if (call_log.final_transcript and 
                        len(call_log.final_transcript.strip()) > 50 and
                        call_log.transcript_source and 
                        call_log.transcript_source != TRANSCRIPT_SOURCE_FAILED):
                        
                        logger.info(f"✅ [OFFLINE_STT] Call {call_sid} already has final_transcript ({len(call_log.final_transcript)} chars, source={call_log.transcript_source}) - skipping reprocessing")
                        log.info(f"[OFFLINE_STT] Skipping {call_sid} - already processed with transcript_source={call_log.transcript_source}")
                        return True  # Already processed successfully
                    
                    # ✅ Use the EXACT same recording that UI plays
                    audio_file = get_recording_file_for_call(call_log)
                else:
                    log.warning(f"[OFFLINE_STT] CallLog not found for {call_sid}, cannot get recording")
                    logger.warning(f"⚠️ [OFFLINE_STT] CallLog not found for {call_sid}")
        except Exception as e:
            log.error(f"[OFFLINE_STT] Error getting recording from service: {e}")
            logger.error(f"❌ [OFFLINE_STT] Error getting recording: {e}")
            # 🔥 CRITICAL FIX: Rollback on DB errors
            try:
                from server.db import db
                db.session.rollback()
            except Exception:
                pass
        
        if not audio_file:
            logger.warning(f"⚠️ [OFFLINE_STT] Audio file not available for {call_sid} - need retry")
            log.warning(f"[OFFLINE_STT] Audio file not available for {call_sid}")
            return False  # Signal that retry is needed
        
        # 🔥 PRIMARY: Transcription from full recording (high quality)
        # 🔥 FALLBACK: Use realtime transcript if recording fails
        final_transcript = None
        realtime_transcript = None  # Will be loaded from DB if needed
        extracted_service = None
        extracted_city = None
        extraction_confidence = None
        
        # 🔥 BUILD 342: Track recording metadata to verify actual transcription from file
        audio_bytes_len = None
        audio_duration_sec = None
        transcript_source = None
        
        if audio_file and os.path.exists(audio_file):
            try:
                # 🔥 BUILD 342: Get audio file metadata
                audio_bytes_len = os.path.getsize(audio_file)
                log.info(f"[OFFLINE_STT] Recording file size: {audio_bytes_len} bytes")
                logger.info(f"📊 [OFFLINE_STT] Recording file: {audio_bytes_len} bytes")
                
                # Try to get duration from audio file
                try:
                    with contextlib.closing(wave.open(audio_file, 'r')) as f:
                        frames = f.getnframes()
                        rate = f.getframerate()
                        audio_duration_sec = frames / float(rate)
                        log.info(f"[OFFLINE_STT] Audio duration: {audio_duration_sec:.2f} seconds")
                        logger.info(f"⏱️ [OFFLINE_STT] Audio duration: {audio_duration_sec:.2f}s")
                except Exception as duration_error:
                    # WAV parsing failed, try alternative method or skip duration
                    log.warning(f"[OFFLINE_STT] Could not determine audio duration: {duration_error}")
                    # Set approximate duration based on call_log.duration if available
                    if call_log and call_log.duration:
                        audio_duration_sec = float(call_log.duration)
                        log.info(f"[OFFLINE_STT] Using call duration as fallback: {audio_duration_sec}s")
                
                from server.services.lead_extraction_service import transcribe_recording_with_whisper, extract_lead_from_transcript
                
                # 🔥 PRIMARY: Transcribe from full recording (best quality)
                if not DEBUG:
                    log.debug(f"[OFFLINE_STT] Starting Whisper transcription for {call_sid}")
                log.info(f"[OFFLINE_STT] Starting transcription from recording for {call_sid}")
                logger.info(f"🎤 [OFFLINE_STT] Transcribing recording for {call_sid}")
                
                final_transcript = transcribe_recording_with_whisper(audio_file, call_sid)
                
                # ✅ Check if transcription succeeded
                if not final_transcript or len(final_transcript.strip()) < 10:
                    logger.error(f"⚠️ [OFFLINE_STT] Recording transcription empty/failed for {call_sid}")
                    log.warning(f"[OFFLINE_STT] Recording transcription returned empty/invalid result: {len(final_transcript or '')} chars")
                    final_transcript = None  # Clear invalid result
                    transcript_source = TRANSCRIPT_SOURCE_FAILED  # Mark as failed
                else:
                    # Success - we have a valid transcript from recording!
                    if not DEBUG:
                        log.debug(f"[OFFLINE_STT] ✅ Recording transcript obtained: {len(final_transcript)} chars for {call_sid}")
                    log.info(f"[OFFLINE_STT] ✅ Recording transcript obtained: {len(final_transcript)} chars")
                    logger.info(f"✅ [OFFLINE_STT] Recording transcription complete: {len(final_transcript)} chars")
                    transcript_source = TRANSCRIPT_SOURCE_RECORDING  # Mark as recording-based
                    
                    # 🔥 NOTE: City/Service extraction moved to AFTER summary generation
                    # We extract from the summary, not from raw transcript (more accurate!)
                    
            except Exception as e:
                logger.error(f"❌ [OFFLINE_STT/EXTRACT] Post-call processing failed for {call_sid}: {e}")
                log.error(f"[OFFLINE_STT/EXTRACT] Post-call processing failed: {e}")
                import traceback
                traceback.print_exc()
                # Set to None to avoid saving empty/corrupted data
                final_transcript = None
                extracted_service = None
                extracted_city = None
                extraction_confidence = None
                transcript_source = TRANSCRIPT_SOURCE_FAILED  # 🔥 BUILD 342: Mark as failed
        else:
            logger.warning(f"⚠️ [OFFLINE_STT] Audio file not available for {call_sid} - skipping offline transcription")
            log.warning(f"[OFFLINE_STT] Audio file not available: {audio_file}")
            transcript_source = TRANSCRIPT_SOURCE_FAILED  # No recording file = failed
        
        # 🔥 FALLBACK: If recording transcription failed/empty, try to use realtime transcript
        if not final_transcript or len(final_transcript.strip()) < 10:
            logger.error(f"🔄 [FALLBACK] Recording transcript empty/failed, checking for realtime transcript")
            log.info(f"[FALLBACK] Attempting to use realtime transcript as fallback for {call_sid}")
            
            try:
                # Load realtime transcript from DB (if exists)
                if call_log and call_log.transcription and len(call_log.transcription.strip()) > 10:
                    realtime_transcript = call_log.transcription
                    final_transcript = realtime_transcript  # Use realtime as fallback
                    transcript_source = TRANSCRIPT_SOURCE_REALTIME
                    logger.info(f"✅ [FALLBACK] Using realtime transcript: {len(final_transcript)} chars")
                    log.info(f"[FALLBACK] Using realtime transcript ({len(final_transcript)} chars) for {call_sid}")
                else:
                    logger.warning(f"⚠️ [FALLBACK] No realtime transcript available for {call_sid}")
                    log.warning(f"[FALLBACK] No realtime transcript available for {call_sid}")
                    transcript_source = TRANSCRIPT_SOURCE_FAILED
            except Exception as e:
                logger.error(f"❌ [FALLBACK] Error loading realtime transcript: {e}")
                log.error(f"[FALLBACK] Error loading realtime transcript for {call_sid}: {e}")
                transcript_source = TRANSCRIPT_SOURCE_FAILED
        
        # 3. ✨ BUILD 143: סיכום חכם ודינמי GPT - מותאם לסוג העסק!
        # 🔥 PRIMARY: Use recording transcript, FALLBACK: Use realtime transcript
        summary = ""
        
        # 🔥 Use final_transcript (which may be from recording OR realtime fallback)
        source_text_for_summary = final_transcript
        
        if source_text_for_summary and len(source_text_for_summary) > 10:
            from server.services.summary_service import summarize_conversation
            from server.app_factory import get_process_app
            
            # Log which transcript source we're using
            source_label = "recording transcript" if transcript_source == TRANSCRIPT_SOURCE_RECORDING else "realtime transcript (fallback)"
            if not DEBUG:
                log.debug(f"[SUMMARY] Using {source_label} for summary generation ({len(source_text_for_summary)} chars)")
            log.info(f"[SUMMARY] Using {source_label} for summary generation")
            logger.info(f"📝 [SUMMARY] Generating summary from {len(source_text_for_summary)} chars ({source_label})")
            
            # Get business context for dynamic summarization (requires app context!)
            business_type = None
            business_name = None
            to_number = form_data.get('To', '')
            
            try:
                app = get_process_app()
                with app.app_context():
                    business = _identify_business_for_call(to_number, from_number)
                    if business:
                        business_type = business.business_type
                        business_name = business.name
                        log.info(f"📊 Using business context: {business_name} ({business_type})")
            except Exception as e:
                log.warning(f"⚠️ Could not get business context for summary: {e}")
                # 🔥 CRITICAL FIX: Rollback on DB errors
                try:
                    from server.db import db
                    db.session.rollback()
                except Exception:
                    pass
            
            summary = summarize_conversation(
                source_text_for_summary, 
                call_sid, 
                business_type, 
                business_name,
                call_duration=call_log.duration if call_log else audio_duration_sec  # 🆕 Pass duration for smart summary!
            )
            # 🔥 Production (DEBUG=1): No logs. Development (DEBUG=0): Full logs
            if not DEBUG:
                if summary and len(summary.strip()) > 0:
                    log.debug(f"✅ Summary generated: {len(summary)} chars from {source_label}")
                else:
                    log.debug(f"⚠️ Summary generation returned empty")
            
            if summary and len(summary.strip()) > 0:
                logger.info(f"✅ [SUMMARY] Generated: {len(summary)} chars")
            else:
                logger.warning(f"⚠️ [SUMMARY] Empty summary generated")
        else:
            # No valid transcript available (neither recording nor realtime)
            logger.warning(f"⚠️ [SUMMARY] No valid transcript available - skipping summary")
            if not DEBUG:
                log.debug(f"[SUMMARY] No valid transcript available ({len(final_transcript or '')} chars)")
        
        # 🆕 3.5. חילוץ עיר ושירות - חכם עם FALLBACK!
        # עדיפות 1: סיכום (אם קיים ובאורך סביר)
        # עדיפות 2: תמלול מלא (Whisper) אם סיכום ריק/קצר
        
        # 🔒 PROTECTION: Check if extraction already exists in DB (avoid duplicate processing)
        skip_extraction = False
        if call_sid:
            try:
                from server.app_factory import get_process_app
                from server.models_sql import CallLog
                app = get_process_app()
                with app.app_context():
                    existing_call = CallLog.query.filter_by(call_sid=call_sid).first()
                    if existing_call and existing_call.extracted_city and existing_call.extracted_service:
                        skip_extraction = True
                        extracted_city = existing_call.extracted_city
                        extracted_service = existing_call.extracted_service
                        extraction_confidence = existing_call.extraction_confidence
                        if not DEBUG:
                            log.debug(f"[OFFLINE_EXTRACT] ⏭️ Extraction already exists - skipping (city='{extracted_city}', service='{extracted_service}')")
                        log.info(f"[OFFLINE_EXTRACT] Extraction already exists for {call_sid} - skipping duplicate processing")
            except Exception as e:
                logger.warning(f"⚠️ [OFFLINE_EXTRACT] Could not check existing extraction: {e}")
                log.warning(f"[OFFLINE_EXTRACT] Could not check existing extraction: {e}")
                # 🔥 CRITICAL FIX: Rollback on DB errors
                try:
                    from server.db import db
                    db.session.rollback()
                except Exception:
                    pass
        
        if not skip_extraction:
            # 🔥 Choose best text for extraction with fallback
            # Priority 1: summary (if exists and sufficient length)
            # Priority 2: final_transcript (may be from recording OR realtime fallback)
            extraction_text = None
            extraction_source = None
            
            if summary and len(summary) >= 30:
                extraction_text = summary
                extraction_source = "summary"
            elif final_transcript and len(final_transcript) >= 30:
                extraction_text = final_transcript
                # Determine source label based on transcript_source
                if transcript_source == TRANSCRIPT_SOURCE_RECORDING:
                    extraction_source = "recording_transcript"
                elif transcript_source == TRANSCRIPT_SOURCE_REALTIME:
                    extraction_source = "realtime_transcript"
                else:
                    extraction_source = "transcript"
            
            if extraction_text:
                try:
                    from server.services.lead_extraction_service import extract_city_and_service_from_summary
                    
                    if not DEBUG:
                    
                        log.debug(f"[OFFLINE_EXTRACT] Using {extraction_source} for city/service extraction ({len(extraction_text)} chars)")
                    log.info(f"[OFFLINE_EXTRACT] Starting extraction from {extraction_source}")
                    logger.info(f"🔍 [OFFLINE_EXTRACT] Extracting from {extraction_source}")
                    
                    extraction = extract_city_and_service_from_summary(extraction_text)
                    
                    # עדכן את המשתנים שיישמרו ב-DB
                    if extraction.get("city"):
                        extracted_city = extraction.get("city")
                        if not DEBUG:
                            log.debug(f"[OFFLINE_EXTRACT] ✅ Extracted city from {extraction_source}: '{extracted_city}'")
                        logger.info(f"✅ [OFFLINE_EXTRACT] City: {extracted_city}")
                    
                    if extraction.get("service_category"):
                        extracted_service = extraction.get("service_category")
                        if not DEBUG:
                            log.debug(f"[OFFLINE_EXTRACT] ✅ Extracted service from {extraction_source}: '{extracted_service}'")
                        logger.info(f"✅ [OFFLINE_EXTRACT] Service: {extracted_service}")
                    
                    if extraction.get("confidence") is not None:
                        extraction_confidence = extraction.get("confidence")
                        if not DEBUG:
                            log.debug(f"[OFFLINE_EXTRACT] ✅ Extraction confidence: {extraction_confidence:.2f}")
                    
                    # Log final extraction result
                    if extracted_city or extracted_service:
                        if not DEBUG:
                            log.debug(f"[OFFLINE_EXTRACT] ✅ Extracted from {extraction_source}: city='{extracted_city}', service='{extracted_service}', conf={extraction_confidence}")
                    else:
                        if not DEBUG:
                            log.debug(f"[OFFLINE_EXTRACT] ⚠️ No city/service found in {extraction_source}")
                        
                except Exception as e:
                    logger.error(f"❌ [OFFLINE_EXTRACT] Failed to extract from {extraction_source}: {e}")
                    log.error(f"[OFFLINE_EXTRACT] Failed to extract from {extraction_source}: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                if not DEBUG:
                    log.debug(f"[OFFLINE_EXTRACT] ⚠️ No valid text for extraction (summary={len(summary or '')} chars, transcript={len(final_transcript or '')} chars)")
                log.warning(f"[OFFLINE_EXTRACT] No valid text for extraction")
        
        # 4. שמור לDB עם תמלול + סיכום + 🆕 POST-CALL DATA
        # 🔥 FIX: תמלול רק מההקלטה - transcription=final_transcript (NO realtime!)
        to_number = form_data.get('To', '')
        logger.info(f"💾 [OFFLINE_STT] Saving to DB: transcript={len(final_transcript or '')} chars, summary={len(summary or '')} chars")
        save_call_to_db(
            call_sid, from_number, recording_url, final_transcript, to_number, summary,
            # 🆕 Pass extracted data
            final_transcript=final_transcript,
            extracted_service=extracted_service,
            extracted_city=extracted_city,
            extraction_confidence=extraction_confidence,
            # 🔥 BUILD 342: Pass recording metadata
            audio_bytes_len=audio_bytes_len,
            audio_duration_sec=audio_duration_sec,
            transcript_source=transcript_source
        )
        
        log.info("✅ Recording processed successfully: CallSid=%s", call_sid)
        
        # 🔥 5. Send call_completed webhook - CRITICAL FIX!
        # This was missing - webhook should always be sent after offline processing completes
        try:
            from server.services.generic_webhook_service import send_call_completed_webhook
            from server.app_factory import get_process_app
            from server.models_sql import CallLog, Business
            
            app = get_process_app()
            with app.app_context():
                # Get call details from DB
                call_log = CallLog.query.filter_by(call_sid=call_sid).first()
                if not call_log:
                    log.warning(f"[WEBHOOK] CallLog not found for {call_sid} - cannot send webhook")
                    logger.warning(f"⚠️ [WEBHOOK] CallLog not found for {call_sid} - skipping webhook")
                else:
                    business = Business.query.filter_by(id=call_log.business_id).first()
                    if not business:
                        log.warning(f"[WEBHOOK] Business not found for call {call_sid} - cannot send webhook")
                        logger.warning(f"⚠️ [WEBHOOK] Business not found - skipping webhook")
                    else:
                        # Determine call direction
                        direction = call_log.direction or "inbound"
                        
                        # 🔥 CRITICAL: Always print webhook attempt - helps diagnose "no webhook sent" issues
                        logger.info(f"📤 [WEBHOOK] Attempting to send webhook for call {call_sid}: direction={direction}, business_id={business.id}")
                        log.info(f"[WEBHOOK] Preparing webhook for call {call_sid}: direction={direction}, business={business.id}")
                        
                        # 🔥 FIX: Fetch canonical service_type from lead (after canonicalization)
                        # If lead.service_type is empty, fallback to topic.canonical_service_type
                        canonical_service_type = None
                        if call_log.lead_id:
                            try:
                                lead = Lead.query.filter_by(id=call_log.lead_id).first()
                                if lead and lead.service_type:
                                    canonical_service_type = lead.service_type
                                    log.info(f"[WEBHOOK] Using canonical service_type from lead {lead.id}: '{canonical_service_type}'")
                                elif lead and lead.topic_id:
                                    # Fallback: Get canonical from topic if lead.service_type is empty
                                    topic = BusinessTopic.query.get(lead.topic_id)
                                    if topic and topic.canonical_service_type:
                                        canonical_service_type = topic.canonical_service_type
                                        log.info(f"[WEBHOOK] Fallback to canonical service_type from topic {topic.id}: '{canonical_service_type}'")
                            except Exception as e:
                                log.warning(f"[WEBHOOK] Could not fetch lead/topic for canonical service: {e}")
                        
                        # Build payload with all available data
                        # 🔥 FIX: Use only final_transcript from recording (NO realtime!)
                        webhook_sent = send_call_completed_webhook(
                            business_id=business.id,
                            call_id=call_sid,
                            lead_id=call_log.lead_id if hasattr(call_log, 'lead_id') else None,
                            phone=call_log.from_number or from_number,
                            started_at=call_log.created_at,
                            ended_at=call_log.updated_at,
                            duration_sec=call_log.duration or 0,
                            transcript=final_transcript or "",
                            summary=summary or "",
                            agent_name=business.name or "Assistant",
                            direction=direction,
                            city=extracted_city,
                            service_category=extracted_service,
                            recording_url=call_log.recording_url,  # 🔥 FIX: Always include recording URL
                            service_category_canonical=canonical_service_type  # 🔥 NEW: Canonical value from lead.service_type
                        )
                        
                        # 🔥 CRITICAL: Always print webhook result
                        if webhook_sent:
                            logger.info(f"✅ [WEBHOOK] Webhook successfully queued for call {call_sid} (direction={direction})")
                            log.info(f"[WEBHOOK] Webhook queued for call {call_sid} (direction={direction})")
                        else:
                            logger.error(f"❌ [WEBHOOK] Webhook NOT sent for call {call_sid} (direction={direction}) - check URL configuration")
                            log.warning(f"[WEBHOOK] Webhook not sent for call {call_sid} - no URL configured for direction={direction}")
                            
        except Exception as webhook_err:
            # Don't fail the entire pipeline if webhook fails - just log it
            logger.error(f"❌ [WEBHOOK] Failed to send webhook for {call_sid}: {webhook_err}")
            log.error(f"[WEBHOOK] Failed to send webhook for {call_sid}: {webhook_err}")
            import traceback
            traceback.print_exc()
        
        # Return success
        return True
        
    except Exception as e:
        log.error("❌ Recording processing failed: %s", e)
        import traceback
        traceback.print_exc()
        return False  # Processing failed, may need retry

def transcribe_hebrew(audio_file):
    """✨ תמלול עברית עם Google STT v2 (Primary) + Whisper (Fallback)"""
    if not audio_file or not os.path.exists(audio_file):
        log.error("Audio file not found: %s", audio_file)
        return ""
    
    try:
        # ✨ שימוש בשירות STT החדש המאוחד - מהיר ואמין!
        from server.services.stt_service import transcribe_audio_file
        
        transcription = transcribe_audio_file(audio_file)
        log.info("✅ Transcription completed: %d chars", len(transcription or ""))
        return transcription or ""
        
    except Exception as e:
        log.error("❌ Transcription failed: %s", e)
        return ""

def save_call_to_db(call_sid, from_number, recording_url, transcription, to_number=None, summary=None,
                   final_transcript=None, extracted_service=None, extracted_city=None, extraction_confidence=None,
                   audio_bytes_len=None, audio_duration_sec=None, transcript_source=None):
    """✨ שמור שיחה + תמלול + סיכום + 🆕 POST-CALL EXTRACTION ל-DB + יצירת לקוח/ליד אוטומטית"""
    try:
        # ✅ Use PostgreSQL + SQLAlchemy instead of SQLite
        from server.app_factory import get_process_app
        from server.db import db
        from server.models_sql import CallLog, Business
        from server.services.customer_intelligence import CustomerIntelligence
        
        app = get_process_app()
        with app.app_context():
            # 1. שמור בCallLog
            call_log = CallLog.query.filter_by(call_sid=call_sid).first()
            if not call_log:
                # זהה business בצורה חכמה - לפי מספר הנכנס/יוצא
                business = _identify_business_for_call(to_number, from_number)
                if not business:
                    log.error("No business found for call processing")
                    return
                
                try:
                    call_log = CallLog()
                    call_log.business_id = business.id
                    call_log.call_sid = call_sid
                    call_log.from_number = from_number
                    call_log.recording_url = recording_url
                    call_log.transcription = transcription
                    call_log.summary = summary  # ✨ סיכום חכם
                    # 🆕 POST-CALL EXTRACTION fields
                    call_log.final_transcript = final_transcript
                    call_log.extracted_service = extracted_service
                    call_log.extracted_city = extracted_city
                    call_log.extraction_confidence = extraction_confidence
                    # 🔥 BUILD 342: Recording quality metadata
                    call_log.audio_bytes_len = audio_bytes_len
                    call_log.audio_duration_sec = audio_duration_sec
                    call_log.transcript_source = transcript_source
                    call_log.status = "processed"
                    call_log.created_at = datetime.utcnow()
                    
                    db.session.add(call_log)
                    db.session.flush()  # Get ID before commit
                except Exception as e:
                    # Handle duplicate key error (race condition)
                    error_msg = str(e).lower()
                    if 'unique' in error_msg or 'duplicate' in error_msg:
                        db.session.rollback()
                        log.warning(f"Call log already exists (race condition): {call_sid}")
                        call_log = CallLog.query.filter_by(call_sid=call_sid).first()
                    else:
                        db.session.rollback()
                        raise
            else:
                # עדכן תמלול וסיכום לCall קיים
                # 🔥 BUILD 149 FIX: Always update recording_url if provided!
                if recording_url and not call_log.recording_url:
                    call_log.recording_url = recording_url
                    log.info(f"✅ Updated recording_url for existing call: {call_sid}")
                
                # 🎯 FIX: UPSERT protection - only update if new value is not NULL/empty
                # Don't overwrite existing good data with empty values
                if transcription and len(transcription.strip()) > 0:
                    call_log.transcription = transcription
                if summary and len(summary.strip()) > 0:
                    call_log.summary = summary
                
                # 🆕 POST-CALL EXTRACTION fields - only update if non-empty
                if final_transcript and len(final_transcript.strip()) > 0:
                    call_log.final_transcript = final_transcript
                if extracted_service and len(extracted_service.strip()) > 0:
                    call_log.extracted_service = extracted_service
                if extracted_city and len(extracted_city.strip()) > 0:
                    call_log.extracted_city = extracted_city
                if extraction_confidence is not None:
                    call_log.extraction_confidence = extraction_confidence
                
                # 🔥 BUILD 342: Recording quality metadata - only update if valid
                if audio_bytes_len and audio_bytes_len > 0:
                    call_log.audio_bytes_len = audio_bytes_len
                if audio_duration_sec and audio_duration_sec > 0:
                    call_log.audio_duration_sec = audio_duration_sec
                if transcript_source and len(transcript_source.strip()) > 0:
                    call_log.transcript_source = transcript_source
                
                call_log.status = "processed"
                call_log.updated_at = datetime.utcnow()
            
            # 🔥 CRITICAL: Commit to database BEFORE logging
            db.session.commit()
            
            # 🆕 AI TOPIC CLASSIFICATION: Run after call is saved
            # 🔒 IDEMPOTENCY: Skip if already classified
            try:
                from server.models_sql import BusinessAISettings, Lead
                from server.services.topic_classifier import topic_classifier
                
                # Check if already classified (idempotency)
                # ✅ FIX: Check detected_topic_id (actual result), not detected_topic_source (which can remain from migration)
                if call_log.detected_topic_id is not None:
                    if not DEBUG:
                        log.debug(f"[TOPIC_CLASSIFY] ⏭️ Call {call_sid} already classified (topic_id={call_log.detected_topic_id}) - skipping")
                    log.info(f"[TOPIC_CLASSIFY] Skipping - already classified with topic_id={call_log.detected_topic_id}")
                else:
                    # Get AI settings to check if classification is enabled
                    ai_settings = BusinessAISettings.query.filter_by(business_id=call_log.business_id).first()
                    
                    if ai_settings and ai_settings.embedding_enabled:
                        if not DEBUG:
                            log.debug(f"[TOPIC_CLASSIFY] 🚀 enabled for business {call_log.business_id} | threshold={ai_settings.embedding_threshold} | top_k={ai_settings.embedding_top_k}")
                        log.info(f"[TOPIC_CLASSIFY] Classification enabled: threshold={ai_settings.embedding_threshold}, top_k={ai_settings.embedding_top_k}")
                        
                        # Use final_transcript if available, otherwise fall back to transcription
                        text_to_classify = final_transcript if (final_transcript and len(final_transcript.strip()) > 50) else transcription
                        text_source = "final_transcript (from recording)" if (final_transcript and len(final_transcript.strip()) > 50) else "transcription (realtime)"
                        
                        if text_to_classify and len(text_to_classify.strip()) > 50:
                            if not DEBUG:
                                log.debug(f"[TOPIC_CLASSIFY] Running classification for call {call_sid} | source={text_source} | length={len(text_to_classify)} chars")
                            log.info(f"[TOPIC_CLASSIFY] Running classification for call {call_sid} using {text_source}")
                            
                            # Classify the text (2-layer: keyword + embeddings)
                            classification_result = topic_classifier.classify_text(call_log.business_id, text_to_classify)
                            
                            if classification_result:
                                topic_id = classification_result['topic_id']
                                confidence = classification_result['score']
                                method = classification_result.get('method', 'embedding')
                                
                                if not DEBUG:
                                
                                    log.debug(f"[TOPIC_CLASSIFY] ✅ Detected topic: '{classification_result['topic_name']}' (confidence={confidence:.3f}, method={method})")
                                log.info(f"[TOPIC_CLASSIFY] Detected topic {topic_id} with confidence {confidence} via {method}")
                                
                                # Update call log if auto_tag_calls is enabled
                                if ai_settings.auto_tag_calls:
                                    call_log.detected_topic_id = topic_id
                                    call_log.detected_topic_confidence = confidence
                                    call_log.detected_topic_source = method  # 'keyword', 'synonym', 'multi_keyword', or 'embedding'
                                    if not DEBUG:
                                        log.debug(f"[TOPIC_CLASSIFY] ✅ Tagged call {call_sid} with topic {topic_id}")
                                
                                # Update lead if auto_tag_leads is enabled and lead exists
                                if ai_settings.auto_tag_leads and call_log.lead_id:
                                    lead = Lead.query.get(call_log.lead_id)
                                    # ✅ FIX: Check detected_topic_id (actual result), not detected_topic_source
                                    if lead and lead.detected_topic_id is None:  # Idempotency for lead too
                                        lead.detected_topic_id = topic_id
                                        lead.detected_topic_confidence = confidence
                                        lead.detected_topic_source = method
                                        if not DEBUG:
                                            log.debug(f"[TOPIC_CLASSIFY] ✅ Tagged lead {call_log.lead_id} with topic {topic_id}")
                                        
                                        # 🔥 NEW: Map topic to service_type if configured
                                        if ai_settings.map_topic_to_service_type and confidence >= ai_settings.service_type_min_confidence:
                                            # Get the topic to check if it has canonical_service_type
                                            topic = BusinessTopic.query.get(topic_id)
                                            if topic and topic.canonical_service_type:
                                                # 🔥 CRITICAL: Only override if:
                                                # 1. lead.service_type is None/empty
                                                # 2. OR lead.service_type is NOT already canonical (prevent overriding good values)
                                                # 3. OR confidence is very high (>= 0.85) AND different from current
                                                from server.services.lead_extraction_service import is_canonical_service, canonicalize_service
                                                
                                                old_service_type = lead.service_type
                                                should_override = False
                                                override_reason = ""
                                                
                                                if not lead.service_type:
                                                    should_override = True
                                                    override_reason = "service_type is empty"
                                                elif not is_canonical_service(lead.service_type):
                                                    should_override = True
                                                    override_reason = f"service_type '{lead.service_type}' is not canonical"
                                                elif confidence >= 0.85 and lead.service_type != topic.canonical_service_type:
                                                    should_override = True
                                                    override_reason = f"high confidence ({confidence:.3f}) and different value"
                                                else:
                                                    override_reason = f"service_type '{lead.service_type}' is already canonical"
                                                
                                                if should_override:
                                                    # 🔥 Apply final canonicalization to ensure consistency
                                                    canonical_value = canonicalize_service(topic.canonical_service_type, call_log.business_id)
                                                    lead.service_type = canonical_value
                                                    if not DEBUG:
                                                        log.debug(f"[TOPIC→SERVICE] ✅ enabled=True topic.canon='{topic.canonical_service_type}' final_canon='{canonical_value}' conf={confidence:.3f}>={ai_settings.service_type_min_confidence} override=True old='{old_service_type}' new='{canonical_value}' reason={override_reason}")
                                                    log.info(f"[TOPIC→SERVICE] Mapped topic {topic_id} to service_type '{canonical_value}' for lead {lead.id} (was: '{old_service_type}')")
                                                else:
                                                    if not DEBUG:
                                                        log.debug(f"[TOPIC→SERVICE] ℹ️ enabled=True topic.canon='{topic.canonical_service_type}' conf={confidence:.3f}>={ai_settings.service_type_min_confidence} override=False old='{old_service_type}' reason={override_reason}")
                                                    log.info(f"[TOPIC→SERVICE] NOT overriding lead {lead.id} service_type '{lead.service_type}' - {override_reason}")
                                            else:
                                                if not topic:
                                                    if not DEBUG:
                                                        log.debug(f"[TOPIC→SERVICE] ⚠️ Topic {topic_id} not found in DB")
                                                else:
                                                    if not DEBUG:
                                                        log.debug(f"[TOPIC→SERVICE] ℹ️ Topic {topic_id} ('{topic.name}') has no canonical_service_type mapping")
                                        else:
                                            if not ai_settings.map_topic_to_service_type:
                                                if not DEBUG:
                                                    log.debug(f"[TOPIC→SERVICE] ℹ️ Topic-to-service mapping disabled for business {call_log.business_id}")
                                            elif confidence < ai_settings.service_type_min_confidence:
                                                if not DEBUG:
                                                    log.debug(f"[TOPIC→SERVICE] ℹ️ Confidence {confidence:.3f} below threshold {ai_settings.service_type_min_confidence} for service_type mapping")
                                
                                db.session.commit()
                            else:
                                if not DEBUG:
                                    log.debug(f"[TOPIC_CLASSIFY] No topic matched threshold for call {call_sid}")
                                log.info(f"[TOPIC_CLASSIFY] No topic matched for call {call_sid}")
                        else:
                            if not DEBUG:
                                log.debug(f"[TOPIC_CLASSIFY] Text too short for classification ({len(text_to_classify or '')} chars)")
                            log.info(f"[TOPIC_CLASSIFY] Skipping classification - text too short")
                    else:
                        if not DEBUG:
                            log.debug(f"[TOPIC_CLASSIFY] Classification disabled for business {call_log.business_id}")
                        log.debug(f"[TOPIC_CLASSIFY] Classification disabled")
                    
            except Exception as topic_err:
                # Don't fail the entire pipeline if classification fails
                logger.error(f"⚠️ [TOPIC_CLASSIFY] Classification failed for {call_sid}: {topic_err}")
                log.error(f"[TOPIC_CLASSIFY] Failed for {call_sid}: {topic_err}")
                import traceback
                traceback.print_exc()
                # Rollback only the topic classification, keep the call data
                db.session.rollback()
                # Re-load call_log and re-commit without topic data
                call_log = CallLog.query.filter_by(call_sid=call_sid).first()
                if call_log:
                    db.session.commit()
            
            # 🔥 Production (DEBUG=1): No logs. Development (DEBUG=0): Full logs
            if not DEBUG:
                processing_summary = []
                if final_transcript and len(final_transcript) > 0:
                    processing_summary.append(f"transcript={len(final_transcript)}chars")
                if audio_bytes_len and audio_bytes_len > 0:
                    processing_summary.append(f"audio={audio_bytes_len}bytes/{audio_duration_sec:.1f}s")
                if extracted_service or extracted_city:
                    processing_summary.append(f"extract='{extracted_service or 'N/A'}/{extracted_city or 'N/A'}'")
                
                log.debug(f"[OFFLINE_STT] ✅ Completed {call_sid}: {', '.join(processing_summary) if processing_summary else 'no data'}")
            
            if not DEBUG:
                log.debug(f"[OFFLINE_STT] Database committed successfully for {call_sid}")
            
            # 2. ✨ יצירת לקוח/ליד אוטומטית עם Customer Intelligence
            # 🔒 CRITICAL: Use lead_id FROM CallLog (locked at call start), NOT phone lookup
            lead = None
            if call_log.lead_id:
                # ✅ Use the locked lead_id from CallLog (imported at top level)
                lead = Lead.query.filter_by(id=call_log.lead_id).first()
                if lead:
                    logger.info(f"✅ [LEAD_ID_LOCK] Using locked lead_id={lead.id} from CallLog for updates")
                    log.info(f"[LEAD_ID_LOCK] Using locked lead {lead.id} for call {call_sid}")
                else:
                    logger.warning(f"⚠️ [LEAD_ID_LOCK] CallLog has lead_id={call_log.lead_id} but lead not found!")
                    log.warning(f"[LEAD_ID_LOCK] CallLog has lead_id={call_log.lead_id} but lead not found")
            
            # If no lead_id on CallLog, fall back to creating/finding by phone (legacy behavior)
            customer = None
            was_created = False
            ci = None  # Will be initialized when needed
            
            if not lead and from_number and call_log and call_log.business_id:
                logger.warning(f"⚠️ [LEAD_ID_LOCK] No lead_id on CallLog, falling back to phone lookup")
                ci = CustomerIntelligence(call_log.business_id)
                
                # זיהוי/יצירת לקוח וליד
                customer, lead, was_created = ci.find_or_create_customer_from_call(
                    from_number, call_sid, transcription
                )
                
                # עדכון CallLog עם customer_id ו-lead_id
                if customer:
                    call_log.customer_id = customer.id
                
                # 🔥 CRITICAL FIX: Link call to lead
                if lead:
                    call_log.lead_id = lead.id
                    log.info(f"✅ Linked call {call_sid} to lead {lead.id}")
            
            # 🔥 FIX: Process lead updates for ALL leads (existing or newly created)
            if lead and call_log and call_log.business_id:
                # Initialize CustomerIntelligence if not already done
                if ci is None:
                    ci = CustomerIntelligence(call_log.business_id)
                
                # 🆕 POST-CALL: Update Lead with extracted service/city (if extraction succeeded)
                if extracted_service or extracted_city:
                    # Only update if fields are empty OR confidence is high (> 0.8)
                    update_service = False
                    update_city = False
                    
                    if extracted_service:
                        if not lead.service_type:
                            update_service = True
                            log.info(f"[OFFLINE_EXTRACT] Lead {lead.id} service_type is empty, will update")
                        elif extraction_confidence and extraction_confidence > 0.8:
                            update_service = True
                            log.info(f"[OFFLINE_EXTRACT] High confidence ({extraction_confidence:.2f}), will overwrite lead {lead.id} service_type")
                    
                    if extracted_city:
                        if not lead.city:
                            update_city = True
                            log.info(f"[OFFLINE_EXTRACT] Lead {lead.id} city is empty, will update")
                        elif extraction_confidence and extraction_confidence > 0.8:
                            update_city = True
                            log.info(f"[OFFLINE_EXTRACT] High confidence ({extraction_confidence:.2f}), will overwrite lead {lead.id} city")
                    
                    if update_service:
                        # 🔥 Canonicalize service category before saving
                        from server.services.lead_extraction_service import canonicalize_service
                        canonical_service = canonicalize_service(extracted_service, call_log.business_id)
                        lead.service_type = canonical_service
                        log.info(f"[OFFLINE_EXTRACT] ✅ Updated lead {lead.id} service_type: '{extracted_service}' → '{canonical_service}'")
                    
                    if update_city:
                        lead.city = extracted_city
                        log.info(f"[OFFLINE_EXTRACT] ✅ Updated lead {lead.id} city: '{extracted_city}'")
                
                # 3. ✨ סיכום חכם של השיחה (שימוש בסיכום שכבר יצרנו!)
                # 🔥 FIX: Use final_transcript from recording (NO realtime!)
                conversation_summary = ci.generate_conversation_summary(final_transcript if final_transcript else "")
                
                # 🎧 CRM Context-Aware Support: Auto-save call summary to lead notes
                # This happens AUTOMATICALLY AFTER EACH call completes (inbound OR outbound)
                # 
                # ⚠️ IMPORTANT DISTINCTION:
                # - This code runs OFFLINE (after call ends) for ALL calls
                # - AI Customer Service (real-time agent) runs ONLY during INBOUND calls (in media_ws_ai.py)
                # - Outbound calls: AI agent does NOT answer, but we still save summary for future reference
                # 
                # 🔥 FIX: ALWAYS update/create call summary to replace temporary transcription from media_ws_ai.py
                # 🆕 CRITICAL: Always create note even if conversation_summary fails
                try:
                    from server.models_sql import LeadNote
                    from datetime import datetime as dt
                    
                    # 🆕 CRITICAL: Create complete customer-service summary for AI context
                    # Include FULL summary that appears in call history, not just first line
                    # This ensures AI has all conversation details for intelligent customer service
                    
                    # Build customer-service focused note content
                    cs_summary_parts = []
                    
                    # Add the FULL summary with all conversation details
                    if summary:
                        cs_summary_parts.append(f"💬 {summary}")
                    else:
                        # Placeholder if no summary was generated
                        if call_log.duration and call_log.duration < MIN_CALL_DURATION_FOR_SUMMARY:
                            cs_summary_parts.append(f"💬 שיחה קצרה מאוד - לא נענתה או נותקה מיד")
                        else:
                            cs_summary_parts.append(f"💬 סיכום לא זמין - שיחה של {call_log.duration or 0} שניות")
                    
                    # Add structured insights if available from conversation analysis
                    if conversation_summary:
                        if conversation_summary.get('intent'):
                            intent_he = {
                                'meeting_request': '🎯 רוצה לקבוע פגישה',
                                'interested': '✅ מעוניין',
                                'not_interested': '❌ לא מעוניין',
                                'information_request': 'ℹ️ ביקש מידע',
                                'general_inquiry': '❓ שאלה כללית'
                            }.get(conversation_summary.get('intent'), '')
                            if intent_he:
                                cs_summary_parts.append(intent_he)
                        
                        # Add next action suggestion
                        if conversation_summary.get('next_action'):
                            cs_summary_parts.append(f"📋 המשך: {conversation_summary.get('next_action')}")
                        
                        # Add sentiment if not neutral
                        sentiment = conversation_summary.get('sentiment', 'neutral')
                        if sentiment != 'neutral':
                            sentiment_emoji = '😊' if sentiment == 'positive' else '😟'
                            cs_summary_parts.append(f"{sentiment_emoji} סנטימנט: {sentiment}")
                    
                    # Build final note content - SHORT and ACTIONABLE for AI
                    note_content = f"""📞 סיכום לשירות לקוחות - {dt.now().strftime('%d/%m/%Y %H:%M')}

{chr(10).join(cs_summary_parts)}

⏱️ {call_log.duration or 0} שניות"""
                    
                    # 🔥 FIX: Check if temporary note exists from media_ws_ai.py and UPDATE it
                    # instead of creating a duplicate (which would fail due to unique constraint)
                    # Order by created_at desc to get the most recent note if multiple exist
                    existing_note = LeadNote.query.filter_by(
                        lead_id=lead.id,
                        call_id=call_log.id,
                        note_type='call_summary'
                    ).order_by(LeadNote.created_at.desc()).first()
                    
                    # 🆕 CRITICAL: Build structured_data safely even if conversation_summary is None/empty
                    structured_data = {
                        'call_duration': call_log.duration,
                        'call_direction': call_log.direction,
                        'call_sid': call_sid,
                        'intent': conversation_summary.get('intent') if conversation_summary else None,
                        'sentiment': conversation_summary.get('sentiment') if conversation_summary else None,
                        'next_action': conversation_summary.get('next_action') if conversation_summary else None,
                        'created_at': dt.utcnow().isoformat(),  # 🆕 Track when note was created/updated
                        'is_latest': True  # 🆕 Mark this as the latest/most accurate note
                    }
                    
                    if existing_note:
                        # Update existing temporary note with proper AI summary
                        existing_note.content = note_content
                        existing_note.structured_data = structured_data
                        # 🆕 Update the timestamp to reflect this is the most recent/accurate version
                        existing_note.created_at = dt.utcnow()
                        log.info(f"[CustomerService] 🔄 Updated existing call summary note for lead {lead.id} with AI-generated summary")
                        log.info(f"[CustomerService] ✅ Note ID {existing_note.id} marked as latest (is_latest=True)")
                    else:
                        # Create new note if none exists
                        call_note = LeadNote()
                        call_note.lead_id = lead.id
                        call_note.tenant_id = call_log.business_id
                        call_note.note_type = 'call_summary'
                        call_note.content = note_content
                        call_note.call_id = call_log.id
                        call_note.structured_data = structured_data
                        call_note.created_at = dt.utcnow()
                        
                        db.session.add(call_note)
                        log.info(f"[CustomerService] 🎧 Created new customer-service optimized call summary for lead {lead.id}")
                        log.info(f"[CustomerService] ✅ Note marked as latest (is_latest=True)")
                    
                    # 🆕 CRITICAL: Mark all previous call_summary notes as NOT latest
                    # This ensures the AI always prioritizes the most recent note
                    try:
                        # Build filter to exclude the current note (whether existing or new)
                        if existing_note:
                            # Exclude by ID if we're updating an existing note
                            old_notes = LeadNote.query.filter(
                                LeadNote.lead_id == lead.id,
                                LeadNote.note_type == 'call_summary',
                                LeadNote.id != existing_note.id
                            ).all()
                        else:
                            # If creating a new note, we don't have an ID yet, so get all call_summary notes
                            # After commit, the new note will be the only one with is_latest=True
                            old_notes = LeadNote.query.filter(
                                LeadNote.lead_id == lead.id,
                                LeadNote.note_type == 'call_summary'
                            ).all()
                        
                        for old_note in old_notes:
                            if old_note.structured_data is None:
                                old_note.structured_data = {}
                            if isinstance(old_note.structured_data, dict):
                                old_note.structured_data['is_latest'] = False
                        
                        if old_notes:
                            log.info(f"[CustomerService] 🔄 Marked {len(old_notes)} previous notes as NOT latest for lead {lead.id}")
                    except Exception as mark_err:
                        log.warning(f"[CustomerService] ⚠️ Failed to mark old notes as not latest: {mark_err}")
                        # Non-critical - the new note is still saved with is_latest=True
                    
                    # 🆕 CRITICAL: Commit note immediately to prevent data loss
                    # Note: This commits within the larger transaction context.
                    # If this function is called within another transaction and fails,
                    # the parent transaction should handle the rollback appropriately.
                    db.session.commit()
                    log.info(f"[CustomerService] ✅ Call summary note committed successfully for lead {lead.id}")
                    
                except Exception as cs_err:
                    log.error(f"[CustomerService] ❌ CRITICAL: Failed to auto-save call summary: {cs_err}")
                    # Log full traceback for debugging
                    log.error(f"[CustomerService] Traceback: {traceback.format_exc()}")
                    # Try to rollback and continue
                    try:
                        db.session.rollback()
                        log.info(f"[CustomerService] Rolled back transaction after note creation failure")
                    except Exception as rollback_err:
                        # Rollback itself failed - this is very rare but possible if connection is lost
                        # Log the error but don't propagate - we want to continue processing
                        log.error(f"[CustomerService] Rollback also failed: {rollback_err}")
                    # Non-critical - continue with other processing
                
                # 4. ✨ עדכון סטטוס אוטומטי - שימוש בשירות החדש
                # Get call direction from call_log
                call_direction = call_log.direction if call_log else "inbound"
                
                # Use new auto-status service with call duration for smart no-summary handling
                from server.services.lead_auto_status_service import suggest_lead_status_from_call, get_auto_status_service
                
                # 🔥 ENHANCED LOGGING: Log what we're passing to auto-status
                log.info(f"[AutoStatus] 🔍 DIAGNOSTIC for lead {lead.id}:")
                log.info(f"[AutoStatus]    - Call direction: {call_direction}")
                log.info(f"[AutoStatus]    - Call duration: {call_log.duration}s")
                log.info(f"[AutoStatus]    - Has summary: {bool(summary)} (length: {len(summary) if summary else 0})")
                log.info(f"[AutoStatus]    - Summary preview: '{summary[:150]}...' " if summary else "[AutoStatus]    - No summary")
                log.info(f"[AutoStatus]    - Current lead status: '{lead.status}'")
                
                suggested_status = suggest_lead_status_from_call(
                    tenant_id=call_log.business_id,
                    lead_id=lead.id,
                    call_direction=call_direction,
                    call_summary=summary,  # AI-generated summary
                    call_transcript=final_transcript or "",  # 🔥 FIX: Only recording transcript
                    call_duration=call_log.duration  # 🆕 Pass duration for smart no-summary logic
                )
                
                # 🔥 ENHANCED LOGGING: Log what auto-status suggested
                if suggested_status:
                    log.info(f"[AutoStatus] 🤖 Suggested status: '{suggested_status}'")
                else:
                    log.warning(f"[AutoStatus] ⚠️ NO STATUS SUGGESTED - check if:")
                    log.warning(f"[AutoStatus]    1. Business has valid statuses configured")
                    log.warning(f"[AutoStatus]    2. OpenAI API key is set for AI matching")
                    log.warning(f"[AutoStatus]    3. Summary/transcript contains matchable keywords")
                
                # 🆕 CRITICAL: Smart status change validation - don't change unnecessarily!
                # Check if we should actually change the status
                old_status = lead.status
                auto_status_service = get_auto_status_service()
                should_change, change_reason = auto_status_service.should_change_status(
                    current_status=old_status,
                    suggested_status=suggested_status,
                    tenant_id=call_log.business_id,
                    call_summary=summary  # 🔥 Pass call summary for context-aware decision!
                )
                
                # 🔥 ENHANCED LOGGING: Log the decision
                log.info(f"[AutoStatus] 🎯 Decision: should_change={should_change}, reason='{change_reason}'")
                
                if should_change and suggested_status:
                    # Extra safety: validate status exists for this business
                    from server.models_sql import LeadStatus
                    valid_status = LeadStatus.query.filter_by(
                        business_id=call_log.business_id,
                        name=suggested_status,
                        is_active=True
                    ).first()
                    
                    if valid_status:
                        lead.status = suggested_status
                        
                        # Create activity for auto status change
                        from server.models_sql import LeadActivity
                        activity = LeadActivity()
                        activity.lead_id = lead.id
                        activity.type = "status_change"
                        activity.payload = {
                            "from": old_status,
                            "to": suggested_status,
                            "source": f"auto_{call_direction}",
                            "call_sid": call_sid,
                            "reason": change_reason  # 🆕 Log why we changed
                        }
                        activity.at = datetime.utcnow()
                        db.session.add(activity)
                        
                        log.info(f"[AutoStatus] ✅ Updated lead {lead.id} status: {old_status} → {suggested_status} (reason: {change_reason})")
                    else:
                        log.warning(f"[AutoStatus] ⚠️ Suggested status '{suggested_status}' not valid for business {call_log.business_id} - skipping status change")
                elif suggested_status:
                    # We have a suggested status but decided not to change
                    log.info(f"[AutoStatus] ⏭️  Keeping lead {lead.id} at status '{old_status}' (suggested '{suggested_status}' but {change_reason})")
                else:
                    log.info(f"[AutoStatus] ℹ️ No confident status match for lead {lead.id} - keeping status as '{old_status}'")
                
                # 4.5. ✨ Auto-detect and update gender from conversation/name
                # 🔥 NEW: Auto-detect gender if not already set or detected from conversation
                try:
                    from server.services.realtime_prompt_builder import detect_gender_from_conversation, detect_gender_from_name
                    
                    detected_gender = None
                    detection_source = None
                    
                    # Priority 1: Check if gender stated in conversation (most reliable)
                    if final_transcript:
                        detected_gender = detect_gender_from_conversation(final_transcript)
                        if detected_gender:
                            detection_source = "conversation"
                            log.info(f"[GENDER] 🎯 Detected from conversation: {detected_gender} for lead {lead.id}")
                    
                    # Priority 2: Detect from first_name if not detected from conversation
                    if not detected_gender and lead.first_name:
                        detected_gender = detect_gender_from_name(lead.first_name)
                        if detected_gender:
                            detection_source = "name"
                            log.info(f"[GENDER] 🎯 Detected from name '{lead.first_name}': {detected_gender} for lead {lead.id}")
                    
                    # Update gender if detected and not already set, or if detected from conversation (override)
                    if detected_gender:
                        should_update = False
                        
                        # Always update if detected from conversation (most reliable)
                        if detection_source == "conversation":
                            should_update = True
                            log.info(f"[GENDER] Will update from conversation-based detection")
                        # Update if not currently set
                        elif not lead.gender:
                            should_update = True
                            log.info(f"[GENDER] Will update (gender not set)")
                        
                        if should_update:
                            old_gender = lead.gender
                            lead.gender = detected_gender
                            log.info(f"[GENDER] ✅ Updated lead {lead.id} gender: {old_gender or 'None'} → {detected_gender} (source: {detection_source})")
                            
                            # Create activity for gender update
                            from server.models_sql import LeadActivity
                            activity = LeadActivity()
                            activity.lead_id = lead.id
                            activity.type = "gender_updated"
                            activity.payload = {
                                "from": old_gender,
                                "to": detected_gender,
                                "source": f"auto_{detection_source}",
                                "call_sid": call_sid
                            }
                            activity.at = datetime.utcnow()
                            db.session.add(activity)
                        else:
                            log.info(f"[GENDER] ℹ️ Keeping existing gender '{lead.gender}' for lead {lead.id} (source was: {detection_source})")
                    else:
                        log.info(f"[GENDER] ℹ️ Could not detect gender for lead {lead.id}")
                        
                except Exception as e:
                    log.error(f"[GENDER] Error detecting/updating gender for lead {lead.id}: {e}")
                    import traceback
                    traceback.print_exc()
                
                # 5. ✨ שמירת הסיכום בליד + עדכון last_contact_at + last_call_direction
                lead.summary = summary  # סיכום קצר (10-30 מילים)
                lead.last_contact_at = datetime.utcnow()  # Update last contact time
                
                # 🔒 CRITICAL: Set last_call_direction ONCE on first interaction, NEVER override
                # 
                # GOLDEN RULE (חוק זהב):
                # last_call_direction is determined ONLY by the FIRST call to/from the lead.
                # Once set, it NEVER changes, regardless of subsequent call directions.
                # 
                # Examples:
                # - Outbound call → Lead answers → Later calls back: Lead remains OUTBOUND
                # - Customer calls in → Later we call them: Lead remains INBOUND
                # 
                # This ensures proper classification for filtering and reporting in the UI.
                if lead.last_call_direction is None:
                    lead.last_call_direction = call_direction
                    log.info(f"🎯 Set lead {lead.id} direction to '{call_direction}' (first interaction)")
                else:
                    log.info(f"ℹ️ Lead {lead.id} direction already set to '{lead.last_call_direction}' (not overriding with '{call_direction}')")
                
                lead.notes = f"סיכום: {conversation_summary.get('summary', '')}\n" + (lead.notes or "")
                
                db.session.commit()
                
                # Log with customer info if available (from creation/lookup), otherwise just log lead info
                if customer:
                    log.info(f"🎯 Call processed with AI: Customer {customer.name} ({'NEW' if was_created else 'EXISTING'}), Final status: {lead.status}")
                else:
                    log.info(f"🎯 Call processed with AI for lead {lead.id}, Final status: {lead.status}")
                log.info(f"📋 Summary: {conversation_summary.get('summary', 'N/A')}")
                log.info(f"🎭 Intent: {conversation_summary.get('intent', 'N/A')}")
                log.info(f"⚡ Next action: {conversation_summary.get('next_action', 'N/A')}")
            
            log.info("Call saved to PostgreSQL with AI processing: %s", call_sid)
        
    except Exception as e:
        log.error("DB save + AI processing failed: %s", e)
        # 🔥 CRITICAL FIX: Rollback on DB errors to prevent InFailedSqlTransaction
        try:
            from server.db import db
            db.session.rollback()
        except Exception:
            pass

def _identify_business_for_call(to_number, from_number):
    """זהה עסק לפי מספרי הטלפון בשיחה - חכם
    
    🔥 CRITICAL FIX: Use phone_e164 column (not phone_number property) for ilike queries.
    phone_number is a Python @property that wraps phone_e164, not a database column.
    """
    from server.models_sql import Business
    from sqlalchemy import or_
    
    # שלב 1: נסה לזהות לפי מספר הנכנס (to_number)
    if to_number:
        # נקה את המספר מסימנים מיוחדים
        clean_to = to_number.replace('+', '').replace('-', '').replace(' ', '')
        
        # 🔥 FIX: Use phone_e164 (DB column), not phone_number (Python property)
        # חפש עסק שהמספר שלו תואם למספר הנכנס
        business = Business.query.filter(
            Business.phone_e164.ilike(f'%{clean_to[-10:]}%')  # 10 ספרות אחרונות
        ).first()
        
        if business:
            logger.info(f"✅ זיהוי עסק לפי מספר נכנס {to_number}: {business.name}")
            return business
    
    # שלב 2: אם לא נמצא, חפש לפי מספר היוצא (from_number) - אולי עסק שמתקשר החוצה
    if from_number:
        clean_from = from_number.replace('+', '').replace('-', '').replace(' ', '')
        
        # 🔥 FIX: Use phone_e164 (DB column), not phone_number (Python property)
        business = Business.query.filter(
            Business.phone_e164.ilike(f'%{clean_from[-10:]}%')
        ).first()
        
        if business:
            logger.info(f"✅ זיהוי עסק לפי מספר יוצא {from_number}: {business.name}")
            return business
    
    # ✅ BUILD 155: fallback לעסק פעיל בלבד (אין fallback לכל עסק)
    business = Business.query.filter(Business.is_active == True).first()
    if business:
        logger.warning(f"⚠️ שימוש בעסק פעיל ברירת מחדל: {business.name}")
        return business
        
    logger.error("❌ לא נמצא עסק פעיל במערכת - recording יישמר ללא שיוך עסק")
    return None


def _handle_failed_call(call_log, call_status, db):
    """
    🆕 CRITICAL FIX: Handle failed calls (no-answer, busy, failed, canceled)
    Create summary and update lead status
    
    When a call fails (not answered, busy, failed, canceled), there's NO recording and NO transcript,
    but we still need to:
    1. Create a summary stating the reason (e.g., "לא נענה", "תפוס", etc.)
    2. Update the lead status with smart progression (no_answer → no_answer_2 → no_answer_3)
    
    This ensures EVERY call gets a summary and status update, even if it failed!
    
    Args:
        call_log: CallLog object for the failed call
        call_status: The call status (no-answer, busy, failed, canceled)
        db: Database session
    """
    try:
        from server.models_sql import Lead, LeadActivity, LeadStatus
        
        log.info(f"[FAILED_CALL] 🔍 Starting handler for {call_status} call {call_log.call_sid} (lead_id={call_log.lead_id})")
        
        # 🔥 DUPLICATION PROTECTION: Check if already processed
        # If summary already exists, this call was already handled - skip!
        if call_log.summary and len(call_log.summary.strip()) > 0:
            log.info(f"[FAILED_CALL] ⏭️ Summary already exists for call {call_log.call_sid}: '{call_log.summary[:50]}...' - SKIPPING to avoid duplicates")
            return
        
        # 1. Create simple summary based on call status
        status_summaries = {
            "no-answer": "שיחה לא נענתה - אין מענה",
            "busy": "שיחה לא נענתה - קו תפוס",
            "failed": "שיחה נכשלה - לא הצליח להתקשר",
            "canceled": "שיחה בוטלה"
        }
        
        summary = status_summaries.get(call_status, f"שיחה לא הושלמה - {call_status}")
        
        # Set summary on call_log
        call_log.summary = summary
        log.info(f"[FAILED_CALL] 📝 Created summary for call {call_log.call_sid}: '{summary}'")
        
        # 🔥 COMMIT SUMMARY FIRST - ensures it's saved even if status update fails
        db.session.commit()
        log.info(f"[FAILED_CALL] ✅ Summary committed to database for call {call_log.call_sid}")
        
        # 2. Get the lead
        lead = Lead.query.get(call_log.lead_id)
        if not lead:
            log.warning(f"[FAILED_CALL] ⚠️ Lead {call_log.lead_id} not found for call {call_log.call_sid} - summary created but status not updated")
            return
        
        log.info(f"[FAILED_CALL] 👤 Found lead {lead.id} with current status: {lead.status}")
        
        # 3. Update lead status using smart auto-status service
        from server.services.lead_auto_status_service import suggest_lead_status_from_call, get_auto_status_service
        
        # 🔥 ENHANCED LOGGING: Log what we're passing to auto-status
        log.info(f"[FAILED_CALL] 🔍 DIAGNOSTIC for lead {lead.id}:")
        log.info(f"[FAILED_CALL]    - Call direction: {call_log.direction or 'outbound'}")
        log.info(f"[FAILED_CALL]    - Call duration: {call_log.duration or 0}s")
        log.info(f"[FAILED_CALL]    - Call status: {call_status}")
        log.info(f"[FAILED_CALL]    - Summary: '{summary}'")
        log.info(f"[FAILED_CALL]    - Current lead status: '{lead.status}'")
        
        suggested_status = suggest_lead_status_from_call(
            tenant_id=call_log.business_id,
            lead_id=lead.id,
            call_direction=call_log.direction or "outbound",
            call_summary=summary,
            call_transcript=None,  # No transcript for failed calls
            call_duration=call_log.duration or 0
        )
        
        # 🔥 ENHANCED LOGGING: Log what auto-status suggested
        if suggested_status:
            log.info(f"[FAILED_CALL] 🤖 Suggested status: '{suggested_status}'")
        else:
            log.warning(f"[FAILED_CALL] ⚠️ NO STATUS SUGGESTED - check if:")
            log.warning(f"[FAILED_CALL]    1. Business has valid statuses configured")
            log.warning(f"[FAILED_CALL]    2. OpenAI API key is set for AI matching")
            log.warning(f"[FAILED_CALL]    3. Summary contains matchable keywords")
        
        # 🆕 CRITICAL: Smart status change validation - don't change unnecessarily!
        old_status = lead.status
        auto_status_service = get_auto_status_service()
        should_change, change_reason = auto_status_service.should_change_status(
            current_status=old_status,
            suggested_status=suggested_status,
            tenant_id=call_log.business_id,
            call_summary=summary  # 🔥 Pass call summary for context-aware decision!
        )
        
        # 🔥 ENHANCED LOGGING: Log the decision
        log.info(f"[FAILED_CALL] 🎯 Decision: should_change={should_change}, reason='{change_reason}'")
        
        # 4. Apply status change with validation
        if should_change and suggested_status:
            # Validate status exists for this business
            valid_status = LeadStatus.query.filter_by(
                business_id=call_log.business_id,
                name=suggested_status,
                is_active=True
            ).first()
            
            if valid_status:
                lead.status = suggested_status
                
                # Create activity for auto status change
                activity = LeadActivity()
                activity.lead_id = lead.id
                activity.type = "status_change"
                activity.payload = {
                    "from": old_status,
                    "to": suggested_status,
                    "source": f"auto_{call_status}_{call_log.direction or 'unknown'}",
                    "call_sid": call_log.call_sid,
                    "reason": f"Failed call: {call_status} - {change_reason}"  # 🆕 Include change reason
                }
                activity.at = datetime.utcnow()
                db.session.add(activity)
                
                db.session.commit()
                log.info(f"[FAILED_CALL] ✅ SUCCESS! Updated lead {lead.id} status: {old_status} → {suggested_status} (reason: {change_reason})")
            else:
                log.warning(f"[FAILED_CALL] ⚠️ Suggested status '{suggested_status}' not valid for business {call_log.business_id} - summary created but status not updated")
        elif suggested_status:
            # We have a suggested status but decided not to change
            log.info(f"[FAILED_CALL] ⏭️  Keeping lead {lead.id} at status '{old_status}' (suggested '{suggested_status}' but {change_reason})")
        else:
            log.info(f"[FAILED_CALL] ℹ️ No confident status match for lead {lead.id} - summary created, keeping current status '{old_status}'")
            
    except Exception as e:
        log.error(f"[FAILED_CALL] ❌ Error handling failed call {call_log.call_sid}: {e}")
        import traceback
        traceback.print_exc()
        # Rollback on error
        try:
            db.session.rollback()
        except Exception:
            pass


def save_call_status(call_sid, status, duration=0, direction="inbound", twilio_direction=None, parent_call_sid=None):
    """
    שלח עדכון סטטוס שיחה לעיבוד ברקע (Thread) למנוע timeout - BUILD 106
    
    Args:
        call_sid: Twilio Call SID
        status: Call status
        duration: Call duration in seconds
        direction: Normalized direction (inbound/outbound) - for backward compatibility
        twilio_direction: Original Twilio direction value
        parent_call_sid: Parent call SID if this is a child leg
    """
    thread = Thread(target=save_call_status_async, 
                   args=(call_sid, status, duration, direction, twilio_direction, parent_call_sid))
    thread.daemon = True
    thread.start()
    log.info("Call status queued for update: %s -> %s (duration=%s, twilio_direction=%s)", 
            call_sid, status, duration, twilio_direction)

def save_call_status_async(call_sid, status, duration=0, direction="inbound", twilio_direction=None, parent_call_sid=None):
    """
    עדכון סטטוס שיחה אסינכרוני מלא - PostgreSQL מתוקן - BUILD 106
    
    UPSERT logic: Updates if call_sid exists, creates if not.
    Prevents duplicate call logs from multiple webhook calls.
    
    Args:
        call_sid: Twilio Call SID
        status: Call status
        duration: Call duration in seconds
        direction: Normalized direction (inbound/outbound)
        twilio_direction: Original Twilio direction value
        parent_call_sid: Parent call SID if this is a child leg
    """
    try:
        # שימוש ב-PostgreSQL דרך SQLAlchemy במקום SQLite
        from server.app_factory import get_process_app
        from server.db import db
        from server.models_sql import CallLog, OutboundCallJob, OutboundCallRun
        
        app = get_process_app()
        with app.app_context():
            # 🔥 UPSERT: Query for existing call_log
            call_log = CallLog.query.filter_by(call_sid=call_sid).first()
            
            if call_log:
                # UPDATE: Call log already exists
                old_status = call_log.status
                old_call_status = call_log.call_status
                
                # 🔥 FIX: Update BOTH status (PRIMARY per models_sql.py) and call_status (backward compat)
                call_log.status = status
                call_log.call_status = status  # Keep in sync for backward compatibility
                
                log.info(f"🔄 [CALL_STATUS] Updating call_sid={call_sid}: status '{old_status}' → '{status}', call_status '{old_call_status}' → '{status}'")
                
                # ✅ Only update duration if provided and greater than current
                if duration > 0 and duration > (call_log.duration or 0):
                    call_log.duration = duration
                
                # 🔥 CRITICAL: Smart direction update logic
                # Allow upgrading from "unknown" to real value, but never overwrite real value with None
                if twilio_direction:
                    # We have a real Twilio direction value
                    if not call_log.twilio_direction or call_log.direction == "unknown":
                        # Update if: (1) never set, OR (2) currently "unknown"
                        call_log.twilio_direction = twilio_direction
                        call_log.direction = normalize_call_direction(twilio_direction)
                elif direction and (not call_log.direction or call_log.direction == "unknown"):
                    # Fallback: use normalized direction if twilio_direction not available
                    # Only update if not set or currently "unknown"
                    call_log.direction = direction
                
                # 🔥 Store parent_call_sid ONLY if provided and not already set
                if parent_call_sid and not call_log.parent_call_sid:
                    call_log.parent_call_sid = parent_call_sid
                
                call_log.updated_at = db.func.now()
                db.session.commit()
                log.info("PostgreSQL call status UPDATED: %s -> %s (duration=%s, direction=%s)", 
                        call_sid, status, duration, call_log.direction)
                
                # 🆕 CRITICAL FIX: Handle failed calls (no-answer, busy, failed, canceled)
                # For these calls, there's NO recording, so we need to handle them here
                # to ensure EVERY call gets a summary and status update!
                if status in ["no-answer", "busy", "failed", "canceled"] and call_log.lead_id:
                    log.info(f"[FAILED_CALL] Handling {status} call for {call_sid} (lead_id={call_log.lead_id})")
                    _handle_failed_call(call_log, status, db)
                    
            else:
                # Call log doesn't exist, but this is just a status update webhook
                # Log warning - call log should have been created in incoming_call or outbound_call
                log.warning("Call SID not found for status update: %s (status=%s). Call log should exist.", 
                           call_sid, status)
                
            # ✅ Update OutboundCallJob if this is part of a bulk run
            # 🔥 GUARD: Protect against missing outbound_call_jobs table
            if status in ["completed", "busy", "no-answer", "failed", "canceled"]:
                try:
                    job = OutboundCallJob.query.filter_by(call_sid=call_sid).first()
                    if job:
                        job.status = "completed" if status == "completed" else "failed"
                        job.completed_at = datetime.utcnow()
                        
                        # Update run counts
                        run = OutboundCallRun.query.get(job.run_id)
                        if run:
                            run.in_progress_count = max(0, run.in_progress_count - 1)
                            if job.status == "completed":
                                run.completed_count += 1
                            else:
                                run.failed_count += 1
                                if job.error_message:
                                    run.last_error = job.error_message[:500]
                        
                        db.session.commit()
                        log.info(f"[BulkCall] Updated job {job.id} status: {job.status}")
                except Exception as outbound_err:
                    # 🔥 GUARD: If outbound_call_jobs table doesn't exist, log and continue
                    log.warning(f"[BulkCall] Could not update OutboundCallJob (table may not exist): {outbound_err}")
        
    except Exception as e:
        log.error("Failed to update call status (PostgreSQL): %s", e)

def transcribe_with_whisper_api(audio_file):
    """תמלול עם OpenAI Whisper API (לא מקומי)"""
    try:
        from server.services.whisper_handler import transcribe_he
        
        with open(audio_file, "rb") as f:
            audio_bytes = f.read()
            
        return transcribe_he(audio_bytes) or "לא זוהה טקסט"
        
    except Exception as e:
        log.error("Whisper API transcription failed: %s", e)
        return "תמלול Whisper נכשל"

def auto_cleanup_old_recordings():
    """✨ BUILD 148: מחיקה אוטומטית של הקלטות ישנות (יותר משבוע) + Twilio + קבצים מהדיסק
    
    Full cleanup process:
    1. Find recordings older than 7 days (per business isolation)
    2. Delete from Twilio servers (if URL is from Twilio)
    3. Delete local files if exist
    4. Clear recording_url from DB ONLY if external deletions succeed
    
    CRITICAL: Only clear recording_url after successful external deletions
    to allow retry on next cleanup pass if deletion fails.
    """
    try:
        from server.app_factory import get_process_app
        from server.db import db
        from server.models_sql import CallLog
        from datetime import datetime, timedelta
        import os
        import re
        
        app = get_process_app()
        with app.app_context():
            # מחק הקלטות מעל שבוע (7 ימים) - תואם ל-UI message
            cutoff_date = datetime.utcnow() - timedelta(days=7)
            
            # Query with business isolation - each business's recordings are handled separately
            old_calls = CallLog.query.filter(
                CallLog.created_at < cutoff_date,
                CallLog.recording_url.isnot(None)
            ).all()
            
            deleted_count = 0
            files_deleted = 0
            twilio_deleted = 0
            skipped_count = 0
            
            # Twilio credentials for API deletion - reuse client
            account_sid = os.getenv("TWILIO_ACCOUNT_SID")
            auth_token = os.getenv("TWILIO_AUTH_TOKEN")
            twilio_client = None
            if account_sid and auth_token:
                try:
                    from twilio.rest import Client
                    twilio_client = Client(account_sid, auth_token)
                except Exception as e:
                    log.warning(f"⚠️ Could not create Twilio client: {e}")
            
            for call in old_calls:
                can_clear_url = True  # Track if we can safely clear the URL
                
                # 1. Delete from Twilio if URL matches Twilio pattern
                if call.recording_url and "api.twilio.com" in call.recording_url:
                    try:
                        # Extract recording SID from URL
                        # Pattern: .../Recordings/RExxxxxx
                        match = re.search(r'/Recordings/(RE[a-zA-Z0-9]+)', call.recording_url)
                        if match and twilio_client:
                            recording_sid = match.group(1)
                            try:
                                twilio_client.recordings(recording_sid).delete()
                                twilio_deleted += 1
                                log.info(f"🗑️ Deleted Twilio recording: {recording_sid} (business_id={call.business_id})")
                            except Exception as twilio_err:
                                err_str = str(twilio_err)
                                if "404" in err_str or "not found" in err_str.lower():
                                    # Recording already deleted - OK to clear
                                    log.info(f"ℹ️ Twilio recording already deleted: {recording_sid}")
                                else:
                                    # Actual error - don't clear URL, retry next time
                                    can_clear_url = False
                                    log.warning(f"⚠️ Twilio deletion failed for {recording_sid}, will retry: {twilio_err}")
                        elif match and not twilio_client:
                            # No credentials - don't clear URL
                            can_clear_url = False
                            log.warning(f"⚠️ No Twilio credentials, cannot delete recording for call {call.call_sid}")
                    except Exception as e:
                        can_clear_url = False
                        log.warning(f"⚠️ Could not extract recording SID from URL: {e}")
                
                # 2. מחק קובץ מהדיסק אם קיים
                if call.call_sid:
                    recordings_dir = "server/recordings"
                    file_path = f"{recordings_dir}/{call.call_sid}.mp3"
                    
                    if os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                            files_deleted += 1
                            log.info(f"🗑️ Deleted local file: {file_path} (business_id={call.business_id})")
                        except Exception as e:
                            can_clear_url = False
                            log.error(f"Failed to delete file {file_path}, will retry: {e}")
                
                # 3. נקה URL מהDB ONLY if external deletions succeeded
                if can_clear_url:
                    call.recording_url = None
                    deleted_count += 1
                else:
                    skipped_count += 1
            
            db.session.commit()
            
            log.info(f"✅ Auto cleanup completed: {deleted_count} DB entries cleared, {twilio_deleted} Twilio deleted, {files_deleted} local files, {skipped_count} skipped for retry")
            return deleted_count, files_deleted
            
    except Exception as e:
        log.error(f"❌ Auto cleanup failed: {e}")
        return 0, 0
