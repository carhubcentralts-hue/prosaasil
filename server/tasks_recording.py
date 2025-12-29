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
from threading import Thread
import threading
from datetime import datetime
from typing import Optional
from sqlalchemy.exc import OperationalError, DisconnectionError

# 🔒 Import Lead model at top level for efficient access
from server.models_sql import CallLog, Business, Lead, BusinessTopic

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

# Cooldown period in seconds - don't enqueue same call_sid more than once per minute
ENQUEUE_COOLDOWN_SECONDS = 60


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


def _should_enqueue_download(call_sid: str) -> tuple[bool, str]:
    """
    🔥 DEDUPLICATION: Check if we should enqueue a download for this call_sid.
    
    Prevents duplicate downloads by:
    1. Checking if file already cached locally
    2. Checking if download already in progress (via recording_service)
    3. Checking DB-backed status (queued, downloading, ready)
    4. Checking cooldown period to prevent spam
    5. Checking exponential backoff for failed downloads
    
    Args:
        call_sid: The call SID to check
        
    Returns:
        tuple: (should_enqueue: bool, reason: str)
    """
    import time
    from datetime import datetime, timezone
    from server.services.recording_service import is_download_in_progress, check_local_recording_exists
    from server.app_factory import get_process_app
    from server.models_sql import CallLog
    from server.db import db
    
    # Check 1: File already cached locally
    if check_local_recording_exists(call_sid):
        return False, "already_cached"
    
    # Check 2: Download already in progress (in-memory check)
    if is_download_in_progress(call_sid):
        return False, "download_in_progress"
    
    # Check 3: DB-backed status check
    try:
        app = get_process_app()
        with app.app_context():
            call_log = CallLog.query.filter_by(call_sid=call_sid).first()
            
            if not call_log:
                # Call doesn't exist in DB yet - allow enqueue
                return True, "ok_no_call_log"
            
            # Check status
            status = call_log.recording_download_status
            
            # Don't enqueue if already queued or downloading
            if status in ('queued', 'downloading'):
                return False, f"status_{status}"
            
            # Don't enqueue if ready
            if status == 'ready':
                return False, "status_ready"
            
            # Check cooldown period
            if call_log.recording_last_enqueue_at:
                last_enqueue = call_log.recording_last_enqueue_at
                if last_enqueue.tzinfo is None:
                    last_enqueue = last_enqueue.replace(tzinfo=timezone.utc)
                
                elapsed = (datetime.now(timezone.utc) - last_enqueue).total_seconds()
                if elapsed < ENQUEUE_COOLDOWN_SECONDS:
                    return False, f"cooldown_active ({int(ENQUEUE_COOLDOWN_SECONDS - elapsed)}s remaining)"
            
            # Check exponential backoff for failed downloads
            if status == 'failed' and call_log.recording_next_retry_at:
                next_retry = call_log.recording_next_retry_at
                if next_retry.tzinfo is None:
                    next_retry = next_retry.replace(tzinfo=timezone.utc)
                
                if datetime.now(timezone.utc) < next_retry:
                    wait_seconds = (next_retry - datetime.now(timezone.utc)).total_seconds()
                    return False, f"backoff_active ({int(wait_seconds)}s remaining, attempt {call_log.recording_fail_count})"
            
            return True, "ok"
            
    except Exception as e:
        log.warning(f"Error checking DB status for {call_sid}: {e}")
        # Fall back to in-memory check on DB error
        with _enqueue_lock:
            last_time = _last_enqueue_time.get(call_sid)
            if last_time:
                elapsed = time.time() - last_time
                if elapsed < ENQUEUE_COOLDOWN_SECONDS:
                    return False, f"cooldown_active ({int(ENQUEUE_COOLDOWN_SECONDS - elapsed)}s remaining)"
            
            # Mark as enqueued now
            _last_enqueue_time[call_sid] = time.time()
        
        return True, "ok_fallback"

def _update_download_status(call_sid: str, status: str, fail_count: int = None, next_retry_at: datetime = None):
    """
    Update download status in DB to prevent duplicate jobs
    
    Args:
        call_sid: Call SID to update
        status: New status (missing|queued|downloading|ready|failed)
        fail_count: Optional failure count
        next_retry_at: Optional next retry time
    """
    try:
        from server.app_factory import get_process_app
        from server.models_sql import CallLog
        from server.db import db
        from datetime import datetime, timezone
        
        app = get_process_app()
        with app.app_context():
            call_log = CallLog.query.filter_by(call_sid=call_sid).first()
            if call_log:
                call_log.recording_download_status = status
                call_log.recording_last_enqueue_at = datetime.now(timezone.utc)
                
                if fail_count is not None:
                    call_log.recording_fail_count = fail_count
                
                if next_retry_at is not None:
                    call_log.recording_next_retry_at = next_retry_at
                
                db.session.commit()
                log.debug(f"[DOWNLOAD_STATUS] Updated {call_sid}: status={status}, fail_count={fail_count}")
    except Exception as e:
        log.warning(f"[DOWNLOAD_STATUS] Failed to update status for {call_sid}: {e}")
        # Don't fail the download if DB update fails


def enqueue_recording_job(call_sid, recording_url, business_id, from_number="", to_number="", retry_count=0):
    """Enqueue recording job for background processing
    
    Args:
        call_sid: Twilio call SID
        recording_url: URL to recording file
        business_id: Business ID for the call
        from_number: Caller phone number
        to_number: Called phone number
        retry_count: Current retry attempt (0-2 allowed, max 3 attempts total)
    
    🔥 IDEMPOTENT: Checks for duplicates before enqueueing to prevent spam
    """
    # 🔥 DEDUPLICATION: Check if we should enqueue this job
    should_enqueue, reason = _should_enqueue_download(call_sid)
    
    if not should_enqueue:
        # Don't enqueue - log at DEBUG level to reduce noise
        if reason == "already_cached":
            log.debug(f"[OFFLINE_STT] ⏭️  File already cached for {call_sid} - skipping enqueue")
        elif reason == "download_in_progress":
            log.debug(f"[OFFLINE_STT] ⏭️  Download already in progress for {call_sid} - skipping enqueue")
        elif reason.startswith("cooldown_active") or reason.startswith("backoff_active") or reason.startswith("status_"):
            log.debug(f"[OFFLINE_STT] ⏭️  Skipping enqueue for {call_sid}: {reason}")
        return  # Don't enqueue
    
    # Passed deduplication checks - update status to 'queued' and enqueue
    _update_download_status(call_sid, 'queued')
    
    RECORDING_QUEUE.put({
        "call_sid": call_sid,
        "recording_url": recording_url,
        "business_id": business_id,
        "from_number": from_number,
        "to_number": to_number,
        "retry_count": retry_count,  # Track retry attempts
        "type": "full"  # Default: full processing (download + transcribe)
    })
    if retry_count == 0:
        print(f"✅ [OFFLINE_STT] Job enqueued for {call_sid} (dedup key acquired)")
        log.info(f"[OFFLINE_STT] Recording job enqueued: {call_sid}")
    else:
        print(f"🔁 [OFFLINE_STT] Job re-enqueued for {call_sid} (retry {retry_count}/2)")
        log.info(f"[OFFLINE_STT] Recording job retry {retry_count}: {call_sid}")


def enqueue_recording_download_only(call_sid, recording_url, business_id, from_number="", to_number="", retry_count=0):
    """
    🔥 FIX: Enqueue PRIORITY job to download recording (without transcription)
    Used by UI when user clicks "play" to get recording ASAP
    
    This creates a high-priority job that only downloads the file, skipping transcription.
    Transcription will happen later via the normal webhook flow.
    
    🔥 IDEMPOTENT: Checks for duplicates before enqueueing to prevent spam
    """
    # 🔥 DEDUPLICATION: Check if we should enqueue this download
    should_enqueue, reason = _should_enqueue_download(call_sid)
    
    if not should_enqueue:
        # Don't enqueue - log at DEBUG level to reduce noise
        if reason == "already_cached":
            log.debug(f"[DOWNLOAD_ONLY] ⏭️  File already cached for {call_sid} - skipping enqueue")
        elif reason == "download_in_progress":
            log.debug(f"[DOWNLOAD_ONLY] ⏭️  Download already in progress for {call_sid} - skipping enqueue")
        elif reason.startswith("cooldown_active") or reason.startswith("backoff_active") or reason.startswith("status_"):
            log.debug(f"[DOWNLOAD_ONLY] ⏭️  Skipping enqueue for {call_sid}: {reason}")
        return  # Don't enqueue
    
    # Passed deduplication checks - update status to 'queued' and enqueue
    _update_download_status(call_sid, 'queued')
    
    RECORDING_QUEUE.put({
        "call_sid": call_sid,
        "recording_url": recording_url,
        "business_id": business_id,
        "from_number": from_number,
        "to_number": to_number,
        "retry_count": retry_count,  # 🔥 FIX: Track retry count
        "type": "download_only"  # 🔥 NEW: Just download, skip transcription
    })
    if retry_count == 0:
        print(f"⚡ [DOWNLOAD_ONLY] Priority download job enqueued for {call_sid} (dedup key acquired)")
        log.info(f"[DOWNLOAD_ONLY] Priority download job enqueued: {call_sid}")
    else:
        print(f"🔁 [DOWNLOAD_ONLY] Retry {retry_count} enqueued for {call_sid}")
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
    Background worker loop - processes recording jobs from queue.
    
    DB RESILIENCE: This worker continues processing even if DB is temporarily unavailable.
    Jobs that fail due to DB errors are logged but don't crash the worker.
    
    RETRY LOGIC: If recording isn't ready yet, retries with exponential backoff:
    - Attempt 1: Immediate (0s delay)
    - Attempt 2: After 10s delay
    - Attempt 3: After 30s delay  
    - Attempt 4: After 90s delay (final attempt)
    Max 3 retries = 4 total attempts
    """
    print("✅ [OFFLINE_STT] Recording worker loop started")
    log.info("[OFFLINE_STT] Recording worker thread initialized")
    
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
                
                # 🔥 FIX: Handle download_only jobs (priority for UI)
                if job_type == "download_only":
                    print(f"⚡ [DOWNLOAD_ONLY] Processing priority download for {call_sid}")
                    log.info(f"[DOWNLOAD_ONLY] Processing priority download: {call_sid}")
                    
                    # Update status to 'downloading'
                    _update_download_status(call_sid, 'downloading')
                    
                    # Just download the file, don't transcribe
                    success = download_recording_only(call_sid, recording_url)
                    
                    if success:
                        print(f"✅ [DOWNLOAD_ONLY] Recording downloaded for {call_sid}")
                        log.info(f"[DOWNLOAD_ONLY] Recording downloaded successfully: {call_sid}")
                        # Update status to 'ready'
                        _update_download_status(call_sid, 'ready', fail_count=0)
                    else:
                        # 🔥 FIX: Retry download_only jobs on failure (up to 2 retries)
                        if retry_count < 2:
                            import time
                            import threading
                            from datetime import datetime, timedelta, timezone
                            
                            delay = 5  # Short delay for download retries
                            print(f"⚠️ [DOWNLOAD_ONLY] Download failed for {call_sid}, retrying in {delay}s")
                            log.warning(f"[DOWNLOAD_ONLY] Download failed for {call_sid}, scheduling retry {retry_count + 1}")
                            
                            # Update status to 'failed' with retry time
                            next_retry = datetime.now(timezone.utc) + timedelta(seconds=delay)
                            _update_download_status(call_sid, 'failed', fail_count=retry_count + 1, next_retry_at=next_retry)
                            
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
                            print(f"❌ [DOWNLOAD_ONLY] Max retries reached for {call_sid}")
                            log.error(f"[DOWNLOAD_ONLY] Max retries reached for {call_sid}")
                            # Mark as permanently failed
                            _update_download_status(call_sid, 'failed', fail_count=retry_count + 1)
                    
                    # 🔥 FIX: Mark as done and set flag to prevent double task_done()
                    RECORDING_QUEUE.task_done()
                    task_done_called = True
                    continue
                
                # Normal full processing (download + transcribe)
                print(f"🎧 [OFFLINE_STT] Starting offline transcription for {call_sid} (attempt {retry_count + 1})")
                log.info(f"[OFFLINE_STT] Processing recording: {call_sid} (attempt {retry_count + 1})")
                
                # Update status to 'downloading'
                _update_download_status(call_sid, 'downloading')
                
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
                    import threading
                    from datetime import datetime, timedelta, timezone
                    
                    delay = RETRY_DELAYS[retry_count + 1] if retry_count + 1 < len(RETRY_DELAYS) else RETRY_DELAYS[-1]
                    print(f"⏰ [OFFLINE_STT] Recording not ready for {call_sid}, retrying in {delay}s")
                    log.info(f"[OFFLINE_STT] Scheduling retry {retry_count + 1} for {call_sid} with {delay}s delay")
                    
                    # Update status to 'failed' with retry time
                    next_retry = datetime.now(timezone.utc) + timedelta(seconds=delay)
                    _update_download_status(call_sid, 'failed', fail_count=retry_count + 1, next_retry_at=next_retry)
                    
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
                    print(f"❌ [OFFLINE_STT] Max retries reached for {call_sid} - giving up")
                    log.error(f"[OFFLINE_STT] Max retries ({MAX_RETRIES}) exceeded for {call_sid}")
                    # Mark as permanently failed
                    _update_download_status(call_sid, 'failed', fail_count=retry_count + 1)
                else:
                    print(f"✅ [OFFLINE_STT] Completed processing for {call_sid}")
                    log.info(f"[OFFLINE_STT] Recording processed successfully: {call_sid}")
                    # Update status to 'ready'
                    _update_download_status(call_sid, 'ready', fail_count=0)
                
            except (OperationalError, DisconnectionError) as e:
                # 🔥 DB RESILIENCE: DB error - log and continue with next job
                from server.utils.db_health import log_db_error
                log_db_error(e, context="recording_worker")
                print(f"🔴 [OFFLINE_STT] DB error processing {job.get('call_sid', 'unknown')} - skipping")
                
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
                print(f"❌ [OFFLINE_STT] Error processing {job.get('call_sid', 'unknown')}: {e}")
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
        print(f"⚡ [DOWNLOAD_ONLY] Starting download for {call_sid}")
        log.info(f"[DOWNLOAD_ONLY] Starting download for {call_sid}")
        
        # Get CallLog to access recording details
        from server.app_factory import get_process_app
        from server.models_sql import CallLog
        from server.services.recording_service import get_recording_file_for_call
        
        app = get_process_app()
        with app.app_context():
            call_log = CallLog.query.filter_by(call_sid=call_sid).first()
            
            if not call_log:
                print(f"⚠️ [DOWNLOAD_ONLY] CallLog not found for {call_sid}")
                log.warning(f"[DOWNLOAD_ONLY] CallLog not found for {call_sid}")
                return False
            
            # Use unified recording service to download
            audio_file = get_recording_file_for_call(call_log)
            
            if audio_file and os.path.exists(audio_file):
                file_size = os.path.getsize(audio_file)
                print(f"✅ [DOWNLOAD_ONLY] Downloaded {file_size} bytes for {call_sid}")
                log.info(f"[DOWNLOAD_ONLY] Downloaded {file_size} bytes for {call_sid}")
                return True
            else:
                print(f"❌ [DOWNLOAD_ONLY] Failed to download for {call_sid}")
                log.error(f"[DOWNLOAD_ONLY] Failed to download for {call_sid}")
                return False
                
    except Exception as e:
        print(f"❌ [DOWNLOAD_ONLY] Error downloading {call_sid}: {e}")
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
        print(f"🎧 [OFFLINE_STT] Starting processing for {call_sid}")
        
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
                        
                        print(f"✅ [OFFLINE_STT] Call {call_sid} already has final_transcript ({len(call_log.final_transcript)} chars, source={call_log.transcript_source}) - skipping reprocessing")
                        log.info(f"[OFFLINE_STT] Skipping {call_sid} - already processed with transcript_source={call_log.transcript_source}")
                        return True  # Already processed successfully
                    
                    # ✅ Use the EXACT same recording that UI plays
                    audio_file = get_recording_file_for_call(call_log)
                else:
                    log.warning(f"[OFFLINE_STT] CallLog not found for {call_sid}, cannot get recording")
                    print(f"⚠️ [OFFLINE_STT] CallLog not found for {call_sid}")
        except Exception as e:
            log.error(f"[OFFLINE_STT] Error getting recording from service: {e}")
            print(f"❌ [OFFLINE_STT] Error getting recording: {e}")
            # 🔥 CRITICAL FIX: Rollback on DB errors
            try:
                from server.db import db
                db.session.rollback()
            except Exception:
                pass
        
        if not audio_file:
            print(f"⚠️ [OFFLINE_STT] Audio file not available for {call_sid} - need retry")
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
                print(f"📊 [OFFLINE_STT] Recording file: {audio_bytes_len} bytes")
                
                # Try to get duration from audio file
                try:
                    with contextlib.closing(wave.open(audio_file, 'r')) as f:
                        frames = f.getnframes()
                        rate = f.getframerate()
                        audio_duration_sec = frames / float(rate)
                        log.info(f"[OFFLINE_STT] Audio duration: {audio_duration_sec:.2f} seconds")
                        print(f"⏱️ [OFFLINE_STT] Audio duration: {audio_duration_sec:.2f}s")
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
                print(f"🎤 [OFFLINE_STT] Transcribing recording for {call_sid}")
                
                final_transcript = transcribe_recording_with_whisper(audio_file, call_sid)
                
                # ✅ Check if transcription succeeded
                if not final_transcript or len(final_transcript.strip()) < 10:
                    print(f"⚠️ [OFFLINE_STT] Recording transcription empty/failed for {call_sid}")
                    log.warning(f"[OFFLINE_STT] Recording transcription returned empty/invalid result: {len(final_transcript or '')} chars")
                    final_transcript = None  # Clear invalid result
                    transcript_source = TRANSCRIPT_SOURCE_FAILED  # Mark as failed
                else:
                    # Success - we have a valid transcript from recording!
                    if not DEBUG:
                        log.debug(f"[OFFLINE_STT] ✅ Recording transcript obtained: {len(final_transcript)} chars for {call_sid}")
                    log.info(f"[OFFLINE_STT] ✅ Recording transcript obtained: {len(final_transcript)} chars")
                    print(f"✅ [OFFLINE_STT] Recording transcription complete: {len(final_transcript)} chars")
                    transcript_source = TRANSCRIPT_SOURCE_RECORDING  # Mark as recording-based
                    
                    # 🔥 NOTE: City/Service extraction moved to AFTER summary generation
                    # We extract from the summary, not from raw transcript (more accurate!)
                    
            except Exception as e:
                print(f"❌ [OFFLINE_STT/EXTRACT] Post-call processing failed for {call_sid}: {e}")
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
            print(f"⚠️ [OFFLINE_STT] Audio file not available for {call_sid} - skipping offline transcription")
            log.warning(f"[OFFLINE_STT] Audio file not available: {audio_file}")
            transcript_source = TRANSCRIPT_SOURCE_FAILED  # No recording file = failed
        
        # 🔥 FALLBACK: If recording transcription failed/empty, try to use realtime transcript
        if not final_transcript or len(final_transcript.strip()) < 10:
            print(f"🔄 [FALLBACK] Recording transcript empty/failed, checking for realtime transcript")
            log.info(f"[FALLBACK] Attempting to use realtime transcript as fallback for {call_sid}")
            
            try:
                # Load realtime transcript from DB (if exists)
                if call_log and call_log.transcription and len(call_log.transcription.strip()) > 10:
                    realtime_transcript = call_log.transcription
                    final_transcript = realtime_transcript  # Use realtime as fallback
                    transcript_source = TRANSCRIPT_SOURCE_REALTIME
                    print(f"✅ [FALLBACK] Using realtime transcript: {len(final_transcript)} chars")
                    log.info(f"[FALLBACK] Using realtime transcript ({len(final_transcript)} chars) for {call_sid}")
                else:
                    print(f"⚠️ [FALLBACK] No realtime transcript available for {call_sid}")
                    log.warning(f"[FALLBACK] No realtime transcript available for {call_sid}")
                    transcript_source = TRANSCRIPT_SOURCE_FAILED
            except Exception as e:
                print(f"❌ [FALLBACK] Error loading realtime transcript: {e}")
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
            print(f"📝 [SUMMARY] Generating summary from {len(source_text_for_summary)} chars ({source_label})")
            
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
            
            summary = summarize_conversation(source_text_for_summary, call_sid, business_type, business_name)
            # 🔥 Production (DEBUG=1): No logs. Development (DEBUG=0): Full logs
            if not DEBUG:
                if summary and len(summary.strip()) > 0:
                    log.debug(f"✅ Summary generated: {len(summary)} chars from {source_label}")
                else:
                    log.debug(f"⚠️ Summary generation returned empty")
            
            if summary and len(summary.strip()) > 0:
                print(f"✅ [SUMMARY] Generated: {len(summary)} chars")
            else:
                print(f"⚠️ [SUMMARY] Empty summary generated")
        else:
            # No valid transcript available (neither recording nor realtime)
            print(f"⚠️ [SUMMARY] No valid transcript available - skipping summary")
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
                print(f"⚠️ [OFFLINE_EXTRACT] Could not check existing extraction: {e}")
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
                    print(f"🔍 [OFFLINE_EXTRACT] Extracting from {extraction_source}")
                    
                    extraction = extract_city_and_service_from_summary(extraction_text)
                    
                    # עדכן את המשתנים שיישמרו ב-DB
                    if extraction.get("city"):
                        extracted_city = extraction.get("city")
                        if not DEBUG:
                            log.debug(f"[OFFLINE_EXTRACT] ✅ Extracted city from {extraction_source}: '{extracted_city}'")
                        print(f"✅ [OFFLINE_EXTRACT] City: {extracted_city}")
                    
                    if extraction.get("service_category"):
                        extracted_service = extraction.get("service_category")
                        if not DEBUG:
                            log.debug(f"[OFFLINE_EXTRACT] ✅ Extracted service from {extraction_source}: '{extracted_service}'")
                        print(f"✅ [OFFLINE_EXTRACT] Service: {extracted_service}")
                    
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
                    print(f"❌ [OFFLINE_EXTRACT] Failed to extract from {extraction_source}: {e}")
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
        print(f"💾 [OFFLINE_STT] Saving to DB: transcript={len(final_transcript or '')} chars, summary={len(summary or '')} chars")
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
                    print(f"⚠️ [WEBHOOK] CallLog not found for {call_sid} - skipping webhook")
                else:
                    business = Business.query.filter_by(id=call_log.business_id).first()
                    if not business:
                        log.warning(f"[WEBHOOK] Business not found for call {call_sid} - cannot send webhook")
                        print(f"⚠️ [WEBHOOK] Business not found - skipping webhook")
                    else:
                        # Determine call direction
                        direction = call_log.direction or "inbound"
                        
                        # 🔥 CRITICAL: Always print webhook attempt - helps diagnose "no webhook sent" issues
                        print(f"📤 [WEBHOOK] Attempting to send webhook for call {call_sid}: direction={direction}, business_id={business.id}")
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
                            print(f"✅ [WEBHOOK] Webhook successfully queued for call {call_sid} (direction={direction})")
                            log.info(f"[WEBHOOK] Webhook queued for call {call_sid} (direction={direction})")
                        else:
                            print(f"❌ [WEBHOOK] Webhook NOT sent for call {call_sid} (direction={direction}) - check URL configuration")
                            log.warning(f"[WEBHOOK] Webhook not sent for call {call_sid} - no URL configured for direction={direction}")
                            
        except Exception as webhook_err:
            # Don't fail the entire pipeline if webhook fails - just log it
            print(f"❌ [WEBHOOK] Failed to send webhook for {call_sid}: {webhook_err}")
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
                print(f"⚠️ [TOPIC_CLASSIFY] Classification failed for {call_sid}: {topic_err}")
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
                    print(f"✅ [LEAD_ID_LOCK] Using locked lead_id={lead.id} from CallLog for updates")
                    log.info(f"[LEAD_ID_LOCK] Using locked lead {lead.id} for call {call_sid}")
                else:
                    print(f"⚠️ [LEAD_ID_LOCK] CallLog has lead_id={call_log.lead_id} but lead not found!")
                    log.warning(f"[LEAD_ID_LOCK] CallLog has lead_id={call_log.lead_id} but lead not found")
            
            # If no lead_id on CallLog, fall back to creating/finding by phone (legacy behavior)
            if not lead and from_number and call_log and call_log.business_id:
                print(f"⚠️ [LEAD_ID_LOCK] No lead_id on CallLog, falling back to phone lookup")
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
                
                # 🆕 POST-CALL: Update Lead with extracted service/city (if extraction succeeded)
                if lead and (extracted_service or extracted_city):
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
                
                # 4. ✨ עדכון סטטוס אוטומטי - שימוש בשירות החדש
                # Get call direction from call_log
                call_direction = call_log.direction if call_log else "inbound"
                
                # Use new auto-status service
                from server.services.lead_auto_status_service import suggest_lead_status_from_call
                suggested_status = suggest_lead_status_from_call(
                    tenant_id=call_log.business_id,
                    lead_id=lead.id,
                    call_direction=call_direction,
                    call_summary=summary,  # AI-generated summary
                    call_transcript=final_transcript or ""  # 🔥 FIX: Only recording transcript
                )
                
                # Apply status change with validation
                old_status = lead.status
                if suggested_status:
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
                            "call_sid": call_sid
                        }
                        activity.at = datetime.utcnow()
                        db.session.add(activity)
                        
                        log.info(f"[AutoStatus] ✅ Updated lead {lead.id} status: {old_status} → {suggested_status} (source: {call_direction})")
                    else:
                        log.warning(f"[AutoStatus] ⚠️ Suggested status '{suggested_status}' not valid for business {call_log.business_id} - skipping status change")
                else:
                    log.info(f"[AutoStatus] ℹ️ No confident status match for lead {lead.id} - keeping status as '{old_status}'")
                
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
                
                log.info(f"🎯 Call processed with AI: Customer {customer.name} ({'NEW' if was_created else 'EXISTING'}), Final status: {lead.status}")
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
            print(f"✅ זיהוי עסק לפי מספר נכנס {to_number}: {business.name}")
            return business
    
    # שלב 2: אם לא נמצא, חפש לפי מספר היוצא (from_number) - אולי עסק שמתקשר החוצה
    if from_number:
        clean_from = from_number.replace('+', '').replace('-', '').replace(' ', '')
        
        # 🔥 FIX: Use phone_e164 (DB column), not phone_number (Python property)
        business = Business.query.filter(
            Business.phone_e164.ilike(f'%{clean_from[-10:]}%')
        ).first()
        
        if business:
            print(f"✅ זיהוי עסק לפי מספר יוצא {from_number}: {business.name}")
            return business
    
    # ✅ BUILD 155: fallback לעסק פעיל בלבד (אין fallback לכל עסק)
    business = Business.query.filter(Business.is_active == True).first()
    if business:
        print(f"⚠️ שימוש בעסק פעיל ברירת מחדל: {business.name}")
        return business
        
    print("❌ לא נמצא עסק פעיל במערכת - recording יישמר ללא שיוך עסק")
    return None

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
                call_log.call_status = status
                
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
