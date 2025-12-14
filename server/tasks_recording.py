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
from datetime import datetime
from typing import Optional
from sqlalchemy.exc import OperationalError, DisconnectionError

log = logging.getLogger("tasks.recording")

# 🔥 BUILD 342: Transcript source constants
TRANSCRIPT_SOURCE_RECORDING = "recording"  # Transcribed from recording file
TRANSCRIPT_SOURCE_REALTIME = "realtime"    # Using realtime transcript
TRANSCRIPT_SOURCE_FAILED = "failed"        # Transcription attempt failed

# ✅ Global queue for recording jobs - single shared instance
RECORDING_QUEUE = queue.Queue()

def enqueue_recording_job(call_sid, recording_url, business_id, from_number="", to_number=""):
    """Enqueue recording job for background processing"""
    RECORDING_QUEUE.put({
        "call_sid": call_sid,
        "recording_url": recording_url,
        "business_id": business_id,
        "from_number": from_number,
        "to_number": to_number,
    })
    print(f"✅ [OFFLINE_STT] Job enqueued for {call_sid}")
    log.info(f"[OFFLINE_STT] Recording job enqueued: {call_sid}")

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
    """
    print("✅ [OFFLINE_STT] Recording worker loop started")
    log.info("[OFFLINE_STT] Recording worker thread initialized")
    
    with app.app_context():
        while True:
            try:
                # Block until a job is available
                job = RECORDING_QUEUE.get()
                
                call_sid = job["call_sid"]
                recording_url = job["recording_url"]
                business_id = job.get("business_id")
                from_number = job.get("from_number", "")
                to_number = job.get("to_number", "")
                
                print(f"🎧 [OFFLINE_STT] Starting offline transcription for {call_sid}")
                log.info(f"[OFFLINE_STT] Processing recording: {call_sid}")
                
                # Build form_data for legacy processing function
                form_data = {
                    "CallSid": call_sid,
                    "RecordingUrl": recording_url,
                    "From": from_number,
                    "To": to_number,
                }
                
                # Process the recording
                process_recording_async(form_data)
                
                print(f"✅ [OFFLINE_STT] Completed processing for {call_sid}")
                log.info(f"[OFFLINE_STT] Recording processed successfully: {call_sid}")
                
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
                except:
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
                RECORDING_QUEUE.task_done()

def process_recording_async(form_data):
    """✨ עיבוד הקלטה אסינכרוני מלא: תמלול + סיכום חכם + 🆕 POST-CALL EXTRACTION"""
    try:
        recording_url = form_data.get("RecordingUrl")
        call_sid = form_data.get("CallSid")
        from_number = form_data.get("From", "")
        to_number = form_data.get("To", "")
        
        log.info("Starting async processing for CallSid=%s", call_sid)
        
        # ✅ NEW: Use unified recording service - same source as UI
        from server.services.recording_service import get_recording_file_for_call
        from server.app_factory import get_process_app
        
        # Get CallLog to access recording_url (single source of truth)
        audio_file = None
        try:
            app = get_process_app()
            with app.app_context():
                from server.models_sql import CallLog
                call_log = CallLog.query.filter_by(call_sid=call_sid).first()
                
                if call_log:
                    # ✅ Use the EXACT same recording that UI plays
                    audio_file = get_recording_file_for_call(call_log)
                else:
                    log.warning(f"[OFFLINE_STT] CallLog not found for {call_sid}, cannot get recording")
                    print(f"⚠️ [OFFLINE_STT] CallLog not found for {call_sid}")
        except Exception as e:
            log.error(f"[OFFLINE_STT] Error getting recording from service: {e}")
            print(f"❌ [OFFLINE_STT] Error getting recording: {e}")
        
        if not audio_file:
            print(f"⚠️ [OFFLINE_STT] Audio file not available for {call_sid} - skipping offline processing")
            log.warning(f"[OFFLINE_STT] Audio file not available for {call_sid}")
        
        # 2. תמלול עברית (Google STT v2 + Whisper fallback) - for summary
        # transcribe_hebrew handles None gracefully and returns ""
        transcription = transcribe_hebrew(audio_file)
        
        # 🆕 2.5. POST-CALL: High-quality full transcript using Whisper (offline)
        # This is separate from realtime transcription - runs after call ends
        final_transcript = None
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
                
                # Try to get duration from audio file
                try:
                    with contextlib.closing(wave.open(audio_file, 'r')) as f:
                        frames = f.getnframes()
                        rate = f.getframerate()
                        audio_duration_sec = frames / float(rate)
                        log.info(f"[OFFLINE_STT] Audio duration: {audio_duration_sec:.2f} seconds")
                except Exception as duration_error:
                    # WAV parsing failed, try alternative method or skip duration
                    log.warning(f"[OFFLINE_STT] Could not determine audio duration: {duration_error}")
                    # Set approximate duration based on call_log.duration if available
                    if call_log and call_log.duration:
                        audio_duration_sec = float(call_log.duration)
                        log.info(f"[OFFLINE_STT] Using call duration as fallback: {audio_duration_sec}s")
                
                from server.services.lead_extraction_service import transcribe_recording_with_whisper, extract_lead_from_transcript
                
                # Get full offline transcript (higher quality than realtime)
                print(f"[OFFLINE_STT] Starting Whisper transcription for {call_sid}")
                log.info(f"[OFFLINE_STT] Starting offline transcription for {call_sid}")
                
                final_transcript = transcribe_recording_with_whisper(audio_file, call_sid)
                
                # ✅ CRITICAL: Only proceed if we got a valid transcript
                if not final_transcript or len(final_transcript.strip()) < 10:
                    print(f"⚠️ [OFFLINE_STT] Empty or invalid transcript for {call_sid} - NOT updating call_log.final_transcript")
                    log.warning(f"[OFFLINE_STT] Transcription returned empty/invalid result: {len(final_transcript or '')} chars")
                    final_transcript = None  # Set to None so we don't save empty string
                    transcript_source = TRANSCRIPT_SOURCE_FAILED  # 🔥 BUILD 342: Mark as failed transcription
                else:
                    # Success - we have a valid transcript!
                    print(f"[OFFLINE_STT] ✅ Transcript obtained: {len(final_transcript)} chars for {call_sid}")
                    log.info(f"[OFFLINE_STT] ✅ Transcript obtained: {len(final_transcript)} chars")
                    transcript_source = TRANSCRIPT_SOURCE_RECORDING  # 🔥 BUILD 342: Mark as recording-based
                    
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
            # 🔥 BUILD 342: If no audio file, will use realtime transcript as fallback
            transcript_source = None  # Will be set to TRANSCRIPT_SOURCE_REALTIME later if we use realtime transcript
        
        # 3. ✨ BUILD 143: סיכום חכם ודינמי GPT - מותאם לסוג העסק!
        # 🔥 CRITICAL: Use final_transcript (high-quality Whisper) if available, fallback to realtime transcription
        summary = ""
        
        # Choose best transcript for summary: final_transcript (Whisper) > transcription (Google STT)
        source_text_for_summary = final_transcript if (final_transcript and len(final_transcript) > 10) else transcription
        
        if source_text_for_summary and len(source_text_for_summary) > 10:
            from server.services.summary_service import summarize_conversation
            from server.app_factory import get_process_app
            
            # Log which transcript we're using
            transcript_source = "final_transcript (Whisper)" if source_text_for_summary == final_transcript else "transcription (realtime)"
            print(f"[SUMMARY] Using {transcript_source} for summary generation ({len(source_text_for_summary)} chars)")
            log.info(f"[SUMMARY] Using {transcript_source} for summary generation")
            
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
            
            summary = summarize_conversation(source_text_for_summary, call_sid, business_type, business_name)
            log.info(f"✅ Dynamic summary generated from {transcript_source}: {summary[:50]}...")
        else:
            print(f"[SUMMARY] ⚠️ No valid transcript available for summary (final_transcript={len(final_transcript or '')} chars, transcription={len(transcription or '')} chars)")
            log.warning(f"[SUMMARY] No valid transcript for summary")
        
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
                        print(f"[OFFLINE_EXTRACT] ⏭️ Extraction already exists - skipping (city='{extracted_city}', service='{extracted_service}')")
                        log.info(f"[OFFLINE_EXTRACT] Extraction already exists for {call_sid} - skipping duplicate processing")
            except Exception as e:
                print(f"⚠️ [OFFLINE_EXTRACT] Could not check existing extraction: {e}")
                log.warning(f"[OFFLINE_EXTRACT] Could not check existing extraction: {e}")
        
        if not skip_extraction:
            # 🔥 SMART FALLBACK: Choose best text for extraction
            # Priority 1: summary (if exists and sufficient length)
            # Priority 2: final_transcript (Whisper) as fallback
            extraction_text = None
            extraction_source = None
            
            if summary and len(summary) >= 30:
                extraction_text = summary
                extraction_source = "summary"
            elif final_transcript and len(final_transcript) >= 30:
                extraction_text = final_transcript
                extraction_source = "transcript"
            elif transcription and len(transcription) >= 30:
                extraction_text = transcription
                extraction_source = "realtime_transcript"
            
            if extraction_text:
                try:
                    from server.services.lead_extraction_service import extract_city_and_service_from_summary
                    
                    print(f"[OFFLINE_EXTRACT] Using {extraction_source} for city/service extraction ({len(extraction_text)} chars)")
                    log.info(f"[OFFLINE_EXTRACT] Starting extraction from {extraction_source}")
                    
                    extraction = extract_city_and_service_from_summary(extraction_text)
                    
                    # עדכן את המשתנים שיישמרו ב-DB
                    if extraction.get("city"):
                        extracted_city = extraction.get("city")
                        print(f"[OFFLINE_EXTRACT] ✅ Extracted city from {extraction_source}: '{extracted_city}'")
                    
                    if extraction.get("service_category"):
                        extracted_service = extraction.get("service_category")
                        print(f"[OFFLINE_EXTRACT] ✅ Extracted service from {extraction_source}: '{extracted_service}'")
                    
                    if extraction.get("confidence") is not None:
                        extraction_confidence = extraction.get("confidence")
                        print(f"[OFFLINE_EXTRACT] ✅ Extraction confidence: {extraction_confidence:.2f}")
                    
                    # Log final extraction result
                    if extracted_city or extracted_service:
                        print(f"[OFFLINE_EXTRACT] ✅ Extracted from {extraction_source}: city='{extracted_city}', service='{extracted_service}', conf={extraction_confidence}")
                    else:
                        print(f"[OFFLINE_EXTRACT] ⚠️ No city/service found in {extraction_source}")
                        
                except Exception as e:
                    print(f"❌ [OFFLINE_EXTRACT] Failed to extract from {extraction_source}: {e}")
                    log.error(f"[OFFLINE_EXTRACT] Failed to extract from {extraction_source}: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print(f"[OFFLINE_EXTRACT] ⚠️ No valid text for extraction (summary={len(summary or '')} chars, transcript={len(final_transcript or '')} chars)")
                log.warning(f"[OFFLINE_EXTRACT] No valid text for extraction")
        
        # 4. שמור לDB עם תמלול + סיכום + 🆕 POST-CALL DATA
        to_number = form_data.get('To', '')
        save_call_to_db(
            call_sid, from_number, recording_url, transcription, to_number, summary,
            # 🆕 Pass extracted data
            final_transcript=final_transcript,
            extracted_service=extracted_service,
            extracted_city=extracted_city,
            extraction_confidence=extraction_confidence
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
                        
                        print(f"[WEBHOOK] Preparing call_completed webhook: call={call_sid}, business={business.id}, direction={direction}")
                        log.info(f"[WEBHOOK] Preparing webhook for call {call_sid}: direction={direction}, business={business.id}")
                        
                        # Build payload with all available data
                        webhook_sent = send_call_completed_webhook(
                            business_id=business.id,
                            call_id=call_sid,
                            lead_id=call_log.lead_id if hasattr(call_log, 'lead_id') else None,
                            phone=call_log.from_number or from_number,
                            started_at=call_log.created_at,
                            ended_at=call_log.updated_at,
                            duration_sec=call_log.duration or 0,
                            transcript=final_transcript or transcription or "",
                            summary=summary or "",
                            agent_name=business.name or "Assistant",
                            direction=direction,
                            city=extracted_city,
                            service_category=extracted_service
                        )
                        
                        if webhook_sent:
                            print(f"[WEBHOOK] ✅ Webhook queued for call {call_sid} (direction={direction})")
                            log.info(f"[WEBHOOK] Webhook queued successfully for {call_sid}")
                        else:
                            print(f"[WEBHOOK] ⚠️ Webhook not sent for call {call_sid} (no URL configured for direction={direction})")
                            log.warning(f"[WEBHOOK] Webhook not sent - no URL configured for direction={direction}")
                            
        except Exception as webhook_err:
            # Don't fail the entire pipeline if webhook fails - just log it
            print(f"❌ [WEBHOOK] Failed to send webhook for {call_sid}: {webhook_err}")
            log.error(f"[WEBHOOK] Failed to send webhook for {call_sid}: {webhook_err}")
            import traceback
            traceback.print_exc()
        
    except Exception as e:
        log.error("❌ Recording processing failed: %s", e)
        import traceback
        traceback.print_exc()

def download_recording(recording_url: str, call_sid: str) -> Optional[str]:
    """
    ⚠️ DEPRECATED - DO NOT USE
    Use server.services.recording_service.get_recording_file_for_call() instead
    
    This function is kept only for backward compatibility but should not be called.
    The new unified recording service provides the single source of truth.
    """
    log.warning(f"[DEPRECATED] download_recording called for {call_sid} - should use recording_service instead")
    return None

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
                   final_transcript=None, extracted_service=None, extracted_city=None, extraction_confidence=None):
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
                        raise
            else:
                # עדכן תמלול וסיכום לCall קיים
                # 🔥 BUILD 149 FIX: Always update recording_url if provided!
                if recording_url and not call_log.recording_url:
                    call_log.recording_url = recording_url
                    log.info(f"✅ Updated recording_url for existing call: {call_sid}")
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
                call_log.updated_at = datetime.utcnow()
            
            # 🔥 CRITICAL: Commit to database BEFORE logging
            db.session.commit()
            
            # ✅ Explicit confirmation logging
            if final_transcript and len(final_transcript) > 0:
                print(f"[OFFLINE_STT] ✅ Saved final_transcript ({len(final_transcript)} chars) for {call_sid}")
            else:
                print(f"[OFFLINE_STT] ℹ️ No offline transcript saved for {call_sid} (empty or failed)")
            
            # 🔥 BUILD 342: Log recording quality metadata for verification
            if audio_bytes_len and audio_bytes_len > 0:
                print(f"[BUILD 342] ✅ Recording metadata: bytes={audio_bytes_len}, duration={audio_duration_sec:.2f}s, source={transcript_source}")
                log.info(f"[BUILD 342] Recording quality: bytes={audio_bytes_len}, duration={audio_duration_sec}, source={transcript_source}")
            else:
                print(f"[BUILD 342] ⚠️ No recording file downloaded (audio_bytes_len={audio_bytes_len})")
                log.warning(f"[BUILD 342] No valid recording file for {call_sid}")
            
            if extracted_service or extracted_city:
                print(f"[OFFLINE_STT] ✅ Extracted: service='{extracted_service}', city='{extracted_city}', confidence={extraction_confidence}")
            else:
                print(f"[OFFLINE_STT] ℹ️ No extraction data for {call_sid} (service=None, city=None)")
            
            log.info(f"[OFFLINE_STT] Database committed successfully for {call_sid}")
            
            # 2. ✨ יצירת לקוח/ליד אוטומטית עם Customer Intelligence
            if from_number and call_log and call_log.business_id:
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
                        lead.service_type = extracted_service
                        log.info(f"[OFFLINE_EXTRACT] ✅ Updated lead {lead.id} service_type: '{extracted_service}'")
                    
                    if update_city:
                        lead.city = extracted_city
                        log.info(f"[OFFLINE_EXTRACT] ✅ Updated lead {lead.id} city: '{extracted_city}'")
                
                # 3. ✨ סיכום חכם של השיחה (שימוש בסיכום שכבר יצרנו!)
                conversation_summary = ci.generate_conversation_summary(transcription)
                
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
                    call_transcript=final_transcript or transcription
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

def _identify_business_for_call(to_number, from_number):
    """זהה עסק לפי מספרי הטלפון בשיחה - חכם"""
    from server.models_sql import Business
    from sqlalchemy import or_
    
    # שלב 1: נסה לזהות לפי מספר הנכנס (to_number)
    if to_number:
        # נקה את המספר מסימנים מיוחדים
        clean_to = to_number.replace('+', '').replace('-', '').replace(' ', '')
        
        # חפש עסק שהמספר שלו תואם למספר הנכנס
        business = Business.query.filter(
            or_(
                Business.phone_number.ilike(f'%{clean_to[-10:]}%'),  # 10 ספרות אחרונות
                Business.phone_e164.ilike(f'%{clean_to[-10:]}%')
            )
        ).first()
        
        if business:
            print(f"✅ זיהוי עסק לפי מספר נכנס {to_number}: {business.name}")
            return business
    
    # שלב 2: אם לא נמצא, חפש לפי מספר היוצא (from_number) - אולי עסק שמתקשר החוצה
    if from_number:
        clean_from = from_number.replace('+', '').replace('-', '').replace(' ', '')
        
        business = Business.query.filter(
            or_(
                Business.phone_number.ilike(f'%{clean_from[-10:]}%'),
                Business.phone_e164.ilike(f'%{clean_from[-10:]}%')
            )
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

def save_call_status(call_sid, status, duration=0, direction="inbound"):
    """שלח עדכון סטטוס שיחה לעיבוד ברקע (Thread) למנוע timeout - BUILD 106"""
    thread = Thread(target=save_call_status_async, args=(call_sid, status, duration, direction))
    thread.daemon = True
    thread.start()
    log.info("Call status queued for update: %s -> %s (duration=%s)", call_sid, status, duration)

def save_call_status_async(call_sid, status, duration=0, direction="inbound"):
    """עדכון סטטוס שיחה אסינכרוני מלא - PostgreSQL מתוקן - BUILD 106"""
    try:
        # שימוש ב-PostgreSQL דרך SQLAlchemy במקום SQLite
        from server.app_factory import get_process_app
        from server.db import db
        from server.models_sql import CallLog, OutboundCallJob, OutboundCallRun
        
        app = get_process_app()
        with app.app_context():
            # עדכון מהיר ישירות ב-PostgreSQL 
            call_log = CallLog.query.filter_by(call_sid=call_sid).first()
            if call_log:
                call_log.call_status = status
                # ✅ BUILD 106: Only update duration/direction if provided (avoid overwriting with 0)
                if duration > 0:
                    call_log.duration = duration
                if direction:
                    call_log.direction = direction
                call_log.updated_at = db.func.now()
                db.session.commit()
                log.info("PostgreSQL call status updated: %s -> %s (duration=%s)", call_sid, status, duration)
                
                # ✅ Update OutboundCallJob if this is part of a bulk run
                if status in ["completed", "busy", "no-answer", "failed", "canceled"]:
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
            else:
                log.warning("Call SID not found for status update: %s", call_sid)
        
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
