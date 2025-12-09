"""
Background Recording Processing - תמלול והקלטות ברקע
"""
import os
import requests
import logging
import queue
from threading import Thread
from datetime import datetime
from typing import Optional

log = logging.getLogger("tasks.recording")

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
    """Background worker loop - processes recording jobs from queue"""
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
                
            except Exception as e:
                log.error(f"[OFFLINE_STT] Worker error: {e}")
                import traceback
                traceback.print_exc()
            finally:
                RECORDING_QUEUE.task_done()

def process_recording_async(form_data):
    """✨ עיבוד הקלטה אסינכרוני מלא: תמלול + סיכום חכם + 🆕 POST-CALL EXTRACTION"""
    try:
        recording_url = form_data.get("RecordingUrl")
        call_sid = form_data.get("CallSid")
        from_number = form_data.get("From", "")
        
        log.info("Starting async processing for CallSid=%s", call_sid)
        
        # 1. הורד קובץ הקלטה
        audio_file = download_recording(recording_url, call_sid)
        
        if not audio_file:
            print(f"⚠️ [OFFLINE_STT] Audio download failed for {call_sid} - skipping offline processing")
            log.warning(f"[OFFLINE_STT] Audio download failed for {call_sid}")
        
        # 2. תמלול עברית (Google STT v2 + Whisper fallback) - for summary
        # transcribe_hebrew handles None gracefully and returns ""
        transcription = transcribe_hebrew(audio_file)
        
        # 🆕 2.5. POST-CALL: High-quality full transcript using Whisper (offline)
        # This is separate from realtime transcription - runs after call ends
        final_transcript = None
        extracted_service = None
        extracted_city = None
        extraction_confidence = None
        
        if audio_file and os.path.exists(audio_file):
            try:
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
                else:
                    # Success - we have a valid transcript!
                    print(f"[OFFLINE_STT] ✅ Transcript obtained: {len(final_transcript)} chars for {call_sid}")
                    log.info(f"[OFFLINE_STT] ✅ Transcript obtained: {len(final_transcript)} chars")
                    
                    # 🆕 Extract service + city from transcript using AI
                    # Get business context for extraction
                    from server.app_factory import get_process_app
                    to_number = form_data.get('To', '')
                    
                    business_prompt = None
                    business_id = None
                    try:
                        app = get_process_app()
                        with app.app_context():
                            business = _identify_business_for_call(to_number, from_number)
                            if business:
                                business_id = business.id
                                # Try to get business prompt for context
                                try:
                                    from server.services.ai_service import get_ai_service
                                    prompt_data = get_ai_service().get_business_prompt(business_id, "calls")
                                    business_prompt = prompt_data.get("system_prompt")
                                except Exception as e:
                                    log.warning(f"⚠️ Could not load business prompt: {e}")
                    except Exception as e:
                        log.warning(f"⚠️ Could not get business context for extraction: {e}")
                    
                    # Extract lead info from transcript
                    print(f"[OFFLINE_EXTRACT] Starting extraction for {call_sid}")
                    log.info(f"[OFFLINE_EXTRACT] Starting extraction for {call_sid}")
                    extraction_result = extract_lead_from_transcript(
                        final_transcript, 
                        business_prompt=business_prompt,
                        business_id=business_id
                    )
                    
                    if extraction_result:
                        extracted_service = extraction_result.get("service")
                        extracted_city = extraction_result.get("city")
                        extraction_confidence = extraction_result.get("confidence", 0.0)
                        
                        if extracted_service or extracted_city:
                            print(f"[OFFLINE_EXTRACT] ✅ Extracted: service='{extracted_service}', city='{extracted_city}', confidence={extraction_confidence:.2f}")
                            log.info(f"[OFFLINE_EXTRACT] ✅ Extracted: service='{extracted_service}', city='{extracted_city}', confidence={extraction_confidence:.2f}")
                        else:
                            print(f"[OFFLINE_EXTRACT] No reliable data extracted from transcript")
                            log.info(f"[OFFLINE_EXTRACT] No reliable data extracted from transcript")
                    
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
        else:
            print(f"⚠️ [OFFLINE_STT] Audio file not available for {call_sid} - skipping offline transcription")
            log.warning(f"[OFFLINE_STT] Audio file not available: {audio_file}")
        
        # 3. ✨ BUILD 143: סיכום חכם ודינמי GPT - מותאם לסוג העסק!
        summary = ""
        if transcription and len(transcription) > 10:
            from server.services.summary_service import summarize_conversation
            from server.app_factory import get_process_app
            
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
            
            summary = summarize_conversation(transcription, call_sid, business_type, business_name)
            log.info(f"✅ Dynamic summary generated: {summary[:50]}...")
        
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
        
    except Exception as e:
        log.error("❌ Recording processing failed: %s", e)
        import traceback
        traceback.print_exc()

def download_recording(recording_url: str, call_sid: str) -> Optional[str]:
    """
    ✅ הורדת קובץ הקלטה מ-Twilio בצורה נכונה:
    - משתמש באותה לוגיקה כמו ה-UI (multiple URL attempts)
    - מטפל ב-duration=-1 (recording not ready) עם retry mechanism
    - ממתין עד 5 ניסיונות עם backoff לפני ויתור
    """
    import time
    import re
    
    try:
        recording_url = recording_url or ""
        log.info(f"[OFFLINE_STT] Original recording_url for {call_sid}: {recording_url}")
        print(f"[OFFLINE_STT] Original recording_url for {call_sid}: {recording_url}")

        # Get Twilio credentials
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        
        if not account_sid or not auth_token:
            print(f"❌ [OFFLINE_STT] Missing Twilio credentials for {call_sid}")
            log.error("Missing Twilio credentials for download")
            return None

        # Extract Recording SID from URL
        # URL format: "/2010-04-01/Accounts/AC.../Recordings/RE949ef4484c7c2e207a1fb4ef96aee4b1.json"
        # We need the "RExxxxx" part
        match = re.search(r'/Recordings/(RE[a-zA-Z0-9]+)', recording_url)
        
        if not match:
            log.error(f"[OFFLINE_STT] Could not extract recording SID from URL: {recording_url}")
            print(f"❌ [OFFLINE_STT] Could not extract recording SID from URL: {recording_url}")
            return None
        
        recording_sid = match.group(1)
        log.info(f"[OFFLINE_STT] Extracted recording SID: {recording_sid}")
        print(f"[OFFLINE_STT] Extracted recording SID: {recording_sid}")

        # ✅ Use Twilio SDK Client
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        
        # 🔄 RETRY MECHANISM: Wait for recording to be ready
        max_retries = 5
        retry_delays = [3, 5, 5, 10, 10]  # seconds - increasing backoff
        
        recording = None
        for attempt in range(max_retries):
            try:
                recording = client.recordings(recording_sid).fetch()
                duration = recording.duration
                
                # Check if recording is ready
                # duration=-1 or None means Twilio is still processing
                if duration is None or duration == -1:
                    if attempt < max_retries - 1:
                        wait_time = retry_delays[attempt]
                        log.info(f"[OFFLINE_STT] Recording not ready yet (duration={duration}), will retry in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                        print(f"[OFFLINE_STT] Recording not ready yet (duration={duration}), will retry in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                        continue
                    else:
                        log.error(f"[OFFLINE_STT] Giving up on recording {recording_sid} after {max_retries} attempts (still duration={duration})")
                        print(f"❌ [OFFLINE_STT] Giving up on recording {recording_sid} after {max_retries} attempts (still duration={duration})")
                        return None
                else:
                    # Recording is ready!
                    log.info(f"[OFFLINE_STT] Recording fetched: {recording.sid}, duration={duration}s")
                    print(f"[OFFLINE_STT] Recording fetched: {recording.sid}, duration={duration}s")
                    break
                    
            except Exception as fetch_err:
                if attempt < max_retries - 1:
                    wait_time = retry_delays[attempt]
                    log.warning(f"[OFFLINE_STT] Failed to fetch recording (attempt {attempt + 1}/{max_retries}): {fetch_err}, retrying in {wait_time}s")
                    print(f"⚠️ [OFFLINE_STT] Failed to fetch recording (attempt {attempt + 1}/{max_retries}): {fetch_err}, retrying in {wait_time}s")
                    time.sleep(wait_time)
                    continue
                else:
                    log.error(f"[OFFLINE_STT] Failed to fetch recording {recording_sid} after {max_retries} attempts: {fetch_err}")
                    print(f"❌ [OFFLINE_STT] Failed to fetch recording {recording_sid} after {max_retries} attempts: {fetch_err}")
                    return None
        
        if not recording:
            log.error(f"[OFFLINE_STT] Could not fetch recording {recording_sid}")
            print(f"❌ [OFFLINE_STT] Could not fetch recording {recording_sid}")
            return None
        
        # 🎯 Use the EXACT same download logic as the UI (routes_calls.py)
        # Build base URL - handle .json URLs from Twilio properly
        base_url = recording_url
        if base_url.endswith(".json"):
            base_url = base_url[:-5]
        
        # Convert relative URL to absolute
        if not base_url.startswith("http"):
            base_url = f"https://api.twilio.com{base_url}"
        
        # Try multiple formats (same as UI)
        urls_to_try = [
            base_url,  # No extension - Twilio's default format
            f"{base_url}.mp3",
            f"{base_url}.wav",
        ]
        
        recording_content = None
        last_error = None
        auth = (account_sid, auth_token)
        
        for attempt, try_url in enumerate(urls_to_try):
            try:
                log.info(f"[OFFLINE_STT] Trying recording URL (format {attempt + 1}/{len(urls_to_try)}): {try_url[:80]}...")
                print(f"[OFFLINE_STT] Trying recording URL (format {attempt + 1}/{len(urls_to_try)}): {try_url[:80]}...")
                
                response = requests.get(try_url, auth=auth, timeout=30)
                
                log.info(f"[OFFLINE_STT] Download status: {response.status_code}, bytes={len(response.content)}")
                print(f"[OFFLINE_STT] Download status: {response.status_code}, bytes={len(response.content)}")
                
                # Check for 404 - recording might still be processing
                if response.status_code == 404:
                    if attempt == 0:  # First attempt failed with 404
                        # Wait a bit and retry all formats again
                        log.info(f"[OFFLINE_STT] Got 404, recording might still be processing. Waiting 5s before next format...")
                        print(f"[OFFLINE_STT] Got 404, recording might still be processing. Waiting 5s before next format...")
                        time.sleep(5)
                    continue
                    
                if response.status_code == 200 and len(response.content) > 1000:
                    recording_content = response.content
                    log.info(f"[OFFLINE_STT] ✅ Successfully downloaded {len(recording_content)} bytes from {try_url[:50]}...")
                    print(f"[OFFLINE_STT] ✅ Successfully downloaded {len(recording_content)} bytes")
                    break
                else:
                    log.warning(f"[OFFLINE_STT] URL returned {response.status_code} or too small ({len(response.content)} bytes)")
                    print(f"⚠️ [OFFLINE_STT] URL returned {response.status_code} or too small ({len(response.content)} bytes)")
                    
            except requests.RequestException as e:
                log.warning(f"[OFFLINE_STT] Failed URL {try_url[:50]}: {e}")
                print(f"⚠️ [OFFLINE_STT] Failed URL: {e}")
                last_error = e
                continue
        
        if not recording_content:
            log.error(f"[OFFLINE_STT] Giving up on recording {call_sid} after trying all URL formats. Last error: {last_error}")
            print(f"❌ [OFFLINE_STT] Giving up on recording {call_sid} after trying all URL formats")
            return None
        
        # Save to disk
        recordings_dir = "server/recordings"
        os.makedirs(recordings_dir, exist_ok=True)
        
        file_path = f"{recordings_dir}/{call_sid}.mp3"
        with open(file_path, "wb") as f:
            f.write(recording_content)
        
        log.info(f"[OFFLINE_STT] ✅ Recording saved to disk: {file_path} ({len(recording_content)} bytes)")
        print(f"[OFFLINE_STT] ✅ Recording saved to disk: {file_path} ({len(recording_content)} bytes)")
        return file_path

    except Exception as e:
        log.exception(f"[OFFLINE_STT] Fatal error in download_recording for {call_sid}: {e}")
        print(f"❌ [OFFLINE_STT] Fatal error in download_recording for {call_sid}: {e}")
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
                call_log.status = "processed"
                call_log.updated_at = datetime.utcnow()
            
            # 🔥 CRITICAL: Commit to database BEFORE logging
            db.session.commit()
            
            # ✅ Explicit confirmation logging
            if final_transcript and len(final_transcript) > 0:
                print(f"[OFFLINE_STT] ✅ Saved final_transcript ({len(final_transcript)} chars) for {call_sid}")
            else:
                print(f"[OFFLINE_STT] ℹ️ No offline transcript saved for {call_sid} (empty or failed)")
            
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
                
                # עדכון CallLog עם customer_id
                if customer:
                    call_log.customer_id = customer.id
                
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
                
                # 4. ✨ עדכון סטטוס אוטומטי
                new_status = ci.auto_update_lead_status(lead, conversation_summary)
                
                # 5. ✨ שמירת הסיכום בליד (summary מה-GPT + notes עם פרטים)
                lead.summary = summary  # סיכום קצר (10-30 מילים)
                lead.notes = f"סיכום: {conversation_summary.get('summary', '')}\n" + (lead.notes or "")
                
                db.session.commit()
                
                log.info(f"🎯 Call processed with AI: Customer {customer.name} ({'NEW' if was_created else 'EXISTING'}), Lead status: {new_status}")
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
        from server.models_sql import CallLog
        
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
