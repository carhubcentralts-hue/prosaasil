"""
Recording download and transcription job for RQ worker.

This replaces the in-memory RECORDING_QUEUE with proper Redis-backed RQ jobs.
"""
import logging
import time
from server.app_factory import get_process_app
from server.db import db

logger = logging.getLogger(__name__)

def process_recording_download_job(call_sid, recording_url, business_id, from_number="", to_number="", recording_sid=None):
    """
    RQ job function for downloading recordings (priority for UI playback).
    
    This function runs in the RQ worker process with proper app context.
    It replaces the threading-based RECORDING_QUEUE system.
    
    Args:
        call_sid: Twilio call SID
        recording_url: URL to download recording from
        business_id: Business ID for slot management
        from_number: Caller phone number  
        to_number: Callee phone number
        recording_sid: Twilio recording SID (optional)
    
    Returns:
        dict: Job result with success status
    """
    app = get_process_app()
    
    with app.app_context():
        logger.info(f"🎯 [RQ_RECORDING] Download job picked: call_sid={call_sid} business_id={business_id}")
        
        # 🔥 IDEMPOTENCY: Early exit if file already exists
        # This handles race conditions where multiple jobs might have been enqueued
        from server.services.recording_service import check_local_recording_exists
        if check_local_recording_exists(call_sid):
            logger.info(f"✅ [RQ_RECORDING] File already cached for {call_sid} - skipping download")
            return {"success": True, "call_sid": call_sid, "cached": True}
        
        slot_acquired = False
        try:
            # Acquire slot for business (prevents overwhelming Twilio API)
            from server.recording_semaphore import try_acquire_slot, release_slot
            
            if business_id:
                acquired, status = try_acquire_slot(business_id, call_sid)
                if not acquired:
                    logger.warning(f"⚠️ [RQ_RECORDING] No slot available for business {business_id}")
                    # RQ will retry automatically
                    raise Exception(f"No slot available: {status}")
                
                slot_acquired = True
                logger.info(f"✅ [RQ_RECORDING] Slot acquired: business_id={business_id}")
            
            # Download recording
            from server.tasks_recording import download_recording_only
            
            start_time = time.time()
            success = download_recording_only(call_sid, recording_url)
            duration_ms = int((time.time() - start_time) * 1000)
            
            if success:
                logger.info(f"✅ [RQ_RECORDING] Downloaded: call_sid={call_sid} duration_ms={duration_ms}")
                return {"success": True, "call_sid": call_sid, "duration_ms": duration_ms}
            else:
                logger.error(f"❌ [RQ_RECORDING] Download failed: call_sid={call_sid}")
                # Let RQ retry
                raise Exception("Download failed")
        
        except Exception as e:
            logger.error(f"❌ [RQ_RECORDING] Job error: {e}")
            raise
        
        finally:
            # Always release slot
            if slot_acquired and business_id:
                from server.recording_semaphore import release_slot
                release_slot(business_id, call_sid)
                logger.info(f"🔓 [RQ_RECORDING] Slot released: business_id={business_id}")


def process_recording_full_job(call_sid, recording_url, business_id, from_number="", to_number=""):
    """
    RQ job function for full recording processing (download + transcription).
    
    Args:
        call_sid: Twilio call SID
        recording_url: URL to download recording from
        business_id: Business ID
        from_number: Caller phone number
        to_number: Callee phone number
    
    Returns:
        dict: Job result with success status
    """
    app = get_process_app()
    
    with app.app_context():
        logger.info(f"🎧 [RQ_RECORDING] Full processing job picked: call_sid={call_sid}")
        
        # 🔥 IDEMPOTENCY: Early exit if file already exists and transcribed
        from server.services.recording_service import check_local_recording_exists
        if check_local_recording_exists(call_sid):
            logger.info(f"✅ [RQ_RECORDING] File already cached for {call_sid} - skipping full processing")
            return {"success": True, "call_sid": call_sid, "cached": True}
        
        try:
            from server.tasks_recording import process_recording_async
            
            form_data = {
                "CallSid": call_sid,
                "RecordingUrl": recording_url,
                "From": from_number,
                "To": to_number,
            }
            
            success = process_recording_async(form_data)
            
            if success:
                logger.info(f"✅ [RQ_RECORDING] Full processing complete: call_sid={call_sid}")
                return {"success": True, "call_sid": call_sid}
            else:
                logger.error(f"❌ [RQ_RECORDING] Full processing failed: call_sid={call_sid}")
                raise Exception("Processing failed")
        
        except Exception as e:
            logger.error(f"❌ [RQ_RECORDING] Full processing error: {e}")
            raise
