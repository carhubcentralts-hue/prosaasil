"""
Background Recording Processing - תמלול והקלטות ברקע
"""
import os
import requests
import logging
from threading import Thread
from datetime import datetime

log = logging.getLogger("tasks.recording")

def enqueue_recording(form_data):
    """שלח הקלטה לעיבוד ברקע (Thread) למנוע timeout"""
    thread = Thread(target=process_recording_async, args=(form_data,))
    thread.daemon = True
    thread.start()
    log.info("Recording processing queued for CallSid=%s", form_data.get("CallSid"))

def process_recording_async(form_data):
    """✨ עיבוד הקלטה אסינכרוני מלא: תמלול + סיכום חכם"""
    try:
        recording_url = form_data.get("RecordingUrl")
        call_sid = form_data.get("CallSid")
        from_number = form_data.get("From", "")
        
        log.info("Starting async processing for CallSid=%s", call_sid)
        
        # 1. הורד קובץ הקלטה
        audio_file = download_recording(recording_url, call_sid)
        
        # 2. תמלול עברית (Google STT v2 + Whisper fallback)
        transcription = transcribe_hebrew(audio_file)
        
        # 3. ✨ סיכום חכם GPT (10-30 מילים)
        summary = ""
        if transcription and len(transcription) > 10:
            from server.services.summary_service import summarize_conversation
            summary = summarize_conversation(transcription, call_sid)
            log.info(f"✅ Summary generated: {summary[:50]}...")
        
        # 4. שמור לDB עם תמלול + סיכום
        to_number = form_data.get('To', '')
        save_call_to_db(call_sid, from_number, recording_url, transcription, to_number, summary)
        
        log.info("✅ Recording processed successfully: CallSid=%s", call_sid)
        
    except Exception as e:
        log.error("❌ Recording processing failed: %s", e)

def download_recording(recording_url, call_sid):
    """הורד קובץ הקלטה מTwilio"""
    try:
        # Twilio מחזיר רק metadata, צריך להוסיף .mp3
        mp3_url = f"{recording_url}.mp3"
        
        # הורד עם Basic Auth של Twilio
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        
        if not account_sid or not auth_token:
            log.error("Missing Twilio credentials for download")
            return None
            
        auth = (account_sid, auth_token)
        response = requests.get(mp3_url, auth=auth, timeout=30)
        response.raise_for_status()
        
        # שמור לדיסק
        recordings_dir = "server/recordings"
        os.makedirs(recordings_dir, exist_ok=True)
        
        file_path = f"{recordings_dir}/{call_sid}.mp3"
        with open(file_path, "wb") as f:
            f.write(response.content)
        
        log.info("Recording downloaded: %s (%d bytes)", file_path, len(response.content))
        return file_path
        
    except Exception as e:
        log.error("Failed to download recording: %s", e)
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

def save_call_to_db(call_sid, from_number, recording_url, transcription, to_number=None, summary=None):
    """✨ שמור שיחה + תמלול + סיכום ל-DB + יצירת לקוח/ליד אוטומטית"""
    try:
        # ✅ Use PostgreSQL + SQLAlchemy instead of SQLite
        from server.app_factory import create_app
        from server.db import db
        from server.models_sql import CallLog, Business
        from server.services.customer_intelligence import CustomerIntelligence
        
        app = create_app()
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
                call_log.transcription = transcription
                call_log.summary = summary  # ✨ סיכום חכם
                call_log.status = "processed"
                call_log.updated_at = datetime.utcnow()
            
            db.session.commit()
            
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
    
    # שלב 3: fallback לעסק הראשון הפעיל
    business = Business.query.filter(Business.is_active == True).first()
    if business:
        print(f"✅ שימוש בעסק ברירת מחדל (פעיל): {business.name}")
        return business
        
    # שלב 4: fallback אחרון לכל עסק
    business = Business.query.first()
    if business:
        print(f"⚠️ שימוש בעסק ברירת מחדל (כללי): {business.name}")
        return business
        
    print("❌ לא נמצא שום עסק במערכת")
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
        from server.app_factory import create_app
        from server.db import db
        from server.models_sql import CallLog
        
        app = create_app()
        with app.app_context():
            # עדכון מהיר ישירות ב-PostgreSQL 
            call_log = CallLog.query.filter_by(call_sid=call_sid).first()
            if call_log:
                call_log.call_status = status
                call_log.duration = duration  # ✅ BUILD 106: Save duration
                call_log.direction = direction  # ✅ BUILD 106: Save direction
                call_log.updated_at = db.func.now()
                db.session.commit()
                log.info("PostgreSQL call status updated: %s -> %s", call_sid, status)
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
    """✨ מחיקה אוטומטית של הקלטות ישנות (יותר מיומיים) + קבצים מהדיסק"""
    try:
        from server.app_factory import create_app
        from server.db import db
        from server.models_sql import CallLog
        from datetime import datetime, timedelta
        import os
        
        app = create_app()
        with app.app_context():
            # מחק הקלטות מעל יומיים
            cutoff_date = datetime.utcnow() - timedelta(days=2)
            
            old_calls = CallLog.query.filter(
                CallLog.created_at < cutoff_date,
                CallLog.recording_url.isnot(None)
            ).all()
            
            deleted_count = 0
            files_deleted = 0
            
            for call in old_calls:
                # מחק קובץ מהדיסק אם קיים
                if call.call_sid:
                    recordings_dir = "server/recordings"
                    file_path = f"{recordings_dir}/{call.call_sid}.mp3"
                    
                    if os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                            files_deleted += 1
                            log.info(f"🗑️ Deleted recording file: {file_path}")
                        except Exception as e:
                            log.error(f"Failed to delete file {file_path}: {e}")
                
                # נקה URL מהDB (שמור transcription - זה טקסט קטן)
                call.recording_url = None
                deleted_count += 1
            
            db.session.commit()
            
            log.info(f"✅ Auto cleanup completed: {deleted_count} DB entries cleared, {files_deleted} files deleted")
            return deleted_count, files_deleted
            
    except Exception as e:
        log.error(f"❌ Auto cleanup failed: {e}")
        return 0, 0
