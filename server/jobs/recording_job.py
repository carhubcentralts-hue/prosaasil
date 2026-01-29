"""
Recording download and transcription job for RQ worker.

This replaces the Thread-based RECORDING_QUEUE with proper Redis-backed RQ jobs.
Uses RecordingRun model as single source of truth for job state.
"""
import logging
import time
from datetime import datetime
from server.app_factory import get_process_app
from server.db import db

logger = logging.getLogger(__name__)

# 🔥 RETRY CONFIGURATION
# Max retry attempts for missing CallLog or audio files
MAX_RECORDING_RETRIES = 5
# Exponential backoff: 60s, 120s, 240s, 480s, 960s (capped at 1200s)
def calculate_retry_delay(retry_count):
    """Calculate exponential backoff delay in seconds"""
    return min(60 * (2 ** (retry_count - 1)), 1200)


def process_recording_download_job(call_sid, recording_url, business_id, from_number="", to_number="", recording_sid=None):
    """
    RQ Worker job - wrapper for download-only jobs (legacy compatibility).
    
    This function creates a RecordingRun and then delegates to process_recording_rq_job.
    Used by enqueue_recording_download_only() which passes individual parameters.
    
    Args:
        call_sid: Twilio Call SID
        recording_url: URL to recording file
        business_id: Business ID for slot management
        from_number: Caller phone number (optional)
        to_number: Called phone number (optional)
        recording_sid: Twilio recording SID (optional)
        
    Returns:
        dict: Job result with success status
    """
    app = get_process_app()
    
    with app.app_context():
        from server.models_sql import RecordingRun
        from server.db import db
        
        # Create RecordingRun entry for tracking
        try:
            run = RecordingRun(
                business_id=business_id,
                call_sid=call_sid,
                recording_sid=recording_sid,
                recording_url=recording_url,
                job_type='download',
                status='queued'
            )
            db.session.add(run)
            db.session.commit()
            
            logger.info(f"🎯 [RQ_RECORDING] Created RecordingRun {run.id} for call_sid={call_sid}")
            
            # Delegate to unified processing function
            return process_recording_rq_job(run.id)
            
        except Exception as e:
            logger.error(f"❌ [RQ_RECORDING] Failed to create RecordingRun for {call_sid}: {e}")
            db.session.rollback()
            return {"success": False, "error": str(e)}


def process_recording_rq_job(run_id: int):
    """
    RQ Worker job - processes a single recording run
    
    This is the NEW unified job function that handles both download-only
    and full processing based on RecordingRun.job_type.
    
    Args:
        run_id: RecordingRun.id to process
        
    Returns:
        dict: Job result with success status
    """
    app = get_process_app()
    
    with app.app_context():
        from server.models_sql import RecordingRun
        from server.services.recording_semaphore import acquire_slot, release_slot
        
        # Load RecordingRun from DB
        run = RecordingRun.query.get(run_id)
        if not run:
            logger.error(f"❌ [RQ_RECORDING] RecordingRun {run_id} not found")
            return {"success": False, "error": "run_not_found"}
        
        # Check cancel_requested before starting
        if run.cancel_requested:
            logger.info(f"⚠️ [RQ_RECORDING] Run {run_id} cancelled before start")
            run.status = 'cancelled'
            run.completed_at = datetime.utcnow()
            db.session.commit()
            return {"success": False, "error": "cancelled"}
        
        logger.info(f"🎯 [RQ_RECORDING] Job picked: run_id={run_id} call_sid={run.call_sid} business_id={run.business_id} job_type={run.job_type}")
        
        # 🔥 IDEMPOTENCY: Early exit if file already exists
        from server.services.recording_service import check_local_recording_exists
        if check_local_recording_exists(run.call_sid):
            logger.info(f"✅ [RQ_RECORDING] File already cached for {run.call_sid} - marking complete")
            run.status = 'completed'
            run.completed_at = datetime.utcnow()
            db.session.commit()
            return {"success": True, "call_sid": run.call_sid, "cached": True}
        
        slot_acquired = False
        try:
            # Acquire Redis semaphore slot (3 concurrent per business)
            acquired, status = acquire_slot(run.business_id, run_id)
            if not acquired:
                logger.warning(f"⚠️ [RQ_RECORDING] No slot available for business {run.business_id}, status={status}")
                # RQ will retry automatically
                raise Exception(f"No slot available: {status}")
            
            slot_acquired = True
            logger.info(f"✅ [RQ_RECORDING] Slot acquired: run_id={run_id} business_id={run.business_id}")
            
            # Update run.status = 'running', run.started_at = now()
            run.status = 'running'
            run.started_at = datetime.utcnow()
            db.session.commit()
            
            # Check cancel_requested again after acquiring slot
            if run.cancel_requested:
                logger.info(f"⚠️ [RQ_RECORDING] Run {run_id} cancelled after slot acquired")
                run.status = 'cancelled'
                run.completed_at = datetime.utcnow()
                db.session.commit()
                return {"success": False, "error": "cancelled"}
            
            # Process based on job_type
            start_time = time.time()
            success = False
            result = None
            
            # 🔥 FIX: Handle missing CallLog/audio gracefully (no exception)
            # Check if CallLog exists before processing
            from server.models_sql import CallLog
            call_log = CallLog.query.filter_by(call_sid=run.call_sid).first()
            
            # 🔥 CRITICAL: Don't throw exception for missing CallLog - use retry with backoff
            if not call_log and run.job_type == 'full':
                # CallLog not found yet - may be commit race condition
                
                # Check if we've exceeded retry limit
                if run.retry_count >= MAX_RECORDING_RETRIES:
                    # Max retries exceeded - mark as permanently failed
                    logger.error(
                        f"❌ [RQ_RECORDING] CallLog not found for {run.call_sid} "
                        f"after {MAX_RECORDING_RETRIES} retries - marking as failed"
                    )
                    run.status = 'failed'
                    run.error_message = f'CallLog not found after {MAX_RECORDING_RETRIES} retries'
                    run.completed_at = datetime.utcnow()
                    db.session.commit()
                    return {"success": False, "error": "CallLog not found", "permanent": True}
                
                # Increment retry count
                run.retry_count += 1
                delay = calculate_retry_delay(run.retry_count)
                
                logger.warning(
                    f"⚠️ [RQ_RECORDING] CallLog not found for {run.call_sid} "
                    f"(attempt {run.retry_count}/{MAX_RECORDING_RETRIES}) - will retry in {delay}s"
                )
                
                # Update run status back to 'queued' with retry info
                run.status = 'queued'
                run.error_message = f'Waiting for CallLog (attempt {run.retry_count}/{MAX_RECORDING_RETRIES})'
                db.session.commit()
                
                # Re-enqueue with delay using RQ's retry mechanism
                # NOTE: RQ will handle the retry automatically
                raise Exception(f"CallLog not found - retry {run.retry_count}/{MAX_RECORDING_RETRIES}")
            
            if run.job_type == 'download':
                # Download only (for UI playback)
                from server.tasks_recording import download_recording_only
                result = download_recording_only(run.call_sid, run.recording_url)
                success = result
            else:
                # Full processing (download + transcription)
                from server.tasks_recording import process_recording_async
                form_data = {
                    "CallSid": run.call_sid,
                    "RecordingUrl": run.recording_url,
                    "From": "",
                    "To": "",
                }
                result = process_recording_async(form_data)
                success = result
            
            # 🔥 FIX: Check if result indicates missing audio file
            # process_recording_async returns False when audio file is not available
            if not success and run.job_type == 'full':
                # Check if we've exceeded retry limit
                if run.retry_count >= MAX_RECORDING_RETRIES:
                    logger.error(
                        f"❌ [RQ_RECORDING] Audio file not available for {run.call_sid} "
                        f"after {MAX_RECORDING_RETRIES} retries - marking as failed"
                    )
                    run.status = 'failed'
                    run.error_message = f'Audio file not available after {MAX_RECORDING_RETRIES} retries'
                    run.completed_at = datetime.utcnow()
                    db.session.commit()
                    return {"success": False, "error": "Audio not available", "permanent": True}
                
                # Increment retry count
                run.retry_count += 1
                delay = calculate_retry_delay(run.retry_count)
                
                logger.warning(
                    f"⚠️ [RQ_RECORDING] Audio file not available for {run.call_sid} "
                    f"(attempt {run.retry_count}/{MAX_RECORDING_RETRIES}) - will retry in {delay}s"
                )
                
                run.status = 'queued'
                run.error_message = f'Waiting for audio file (attempt {run.retry_count}/{MAX_RECORDING_RETRIES})'
                db.session.commit()
                
                # Re-enqueue with delay
                raise Exception(f"Audio file not available - retry {run.retry_count}/{MAX_RECORDING_RETRIES}")
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Update run.status = 'completed', run.completed_at = now()
            if success:
                run.status = 'completed'
                run.completed_at = datetime.utcnow()
                run.error_message = None  # Clear any previous error
                db.session.commit()
                logger.info(f"✅ [RQ_RECORDING] Complete: run_id={run_id} call_sid={run.call_sid} duration_ms={duration_ms}")
                return {"success": True, "run_id": run_id, "duration_ms": duration_ms}
            else:
                # This should not happen now - we handle failures above with retry logic
                run.status = 'failed'
                run.error_message = 'Processing failed (unknown reason)'
                run.completed_at = datetime.utcnow()
                db.session.commit()
                logger.error(f"❌ [RQ_RECORDING] Failed: run_id={run_id} call_sid={run.call_sid}")
                # Don't raise - just return failure
                return {"success": False, "error": "Processing failed"}
        
        except Exception as e:
            # Update run with error
            # NOTE: retry_count is already incremented in the retry logic above
            # Don't increment it here to avoid double-counting
            run.status = 'failed'
            run.error_message = str(e)[:500]  # Limit length
            run.completed_at = datetime.utcnow()
            # run.retry_count += 1  # REMOVED: Already incremented above
            db.session.commit()
            
            logger.error(f"❌ [RQ_RECORDING] Job error: run_id={run_id} error={e}")
            raise
        
        finally:
            # Release semaphore in finally block
            if slot_acquired:
                release_slot(run.business_id, run_id)
                logger.info(f"🔓 [RQ_RECORDING] Slot released: run_id={run_id} business_id={run.business_id}")
