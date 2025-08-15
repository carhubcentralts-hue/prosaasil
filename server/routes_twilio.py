"""
Twilio Webhooks מאוחד וחדש - TwiML נכון + Content-Type + אבטחה + Background Processing
UNIFIED CLEAN FILE - לפי המפרט המקצועי
"""
from flask import Blueprint, request, Response, current_app
from urllib.parse import urljoin
from server.twilio_security import require_twilio_signature
import os, logging

def _mask_phone(phone):
    """Mask phone number for logging privacy"""
    if not phone or len(phone) < 4:
        return phone
    return phone[:3] + "****" + phone[-2:]

twilio_bp = Blueprint("twilio_bp", __name__, url_prefix="")
log = logging.getLogger("twilio.unified")

def abs_url(path: str) -> str:
    """יצירת URL מוחלט עבור Twilio webhooks - FAIL FAST אם לא מוגדר HOST"""
    host = (current_app.config.get("PUBLIC_HOST") or os.getenv("PUBLIC_HOST") or "").rstrip("/")
    if not host:
        raise RuntimeError("PUBLIC_HOST not configured - Hebrew fallback will be used")
    return urljoin(host + "/", path.lstrip("/"))

def get_business_greeting(to_number, call_sid):
    """Get business-specific greeting file based on number"""
    # Extract business_id from number mapping or use default
    # For now, use default greeting - can be extended per business
    return "static/voice_responses/welcome.mp3"

@twilio_bp.post("/webhook/incoming_call")
@require_twilio_signature
def incoming_call():
    """Handle incoming Twilio call - MEDIA STREAMS (no more <Say> language errors!)"""
    try:
        from_number = _mask_phone(request.form.get("From", ""))
        to_number = _mask_phone(request.form.get("To", ""))
        call_sid = request.form.get("CallSid", "")
        
        log.info("Incoming call: From=%s To=%s CallSid=%s", from_number, to_number, call_sid)
        
        # שמירת שיחה במסד נתונים
        try:
            from server.models_sql import CallLog, db
            call_log = CallLog()
            call_log.business_id = 1  # ברירת מחדל לעסק הראשון
            call_log.call_sid = call_sid
            call_log.from_number = request.form.get("From", "")
            call_log.status = "received"
            db.session.add(call_log)
            db.session.commit()
            log.info("Call logged: %s", call_sid)
        except Exception as e:
            log.error("Failed to log call %s: %s", call_sid, e)

        # Media Streams - פותח WebSocket דו־כיווני
        public_host = os.getenv("PUBLIC_HOST", "https://ai-crmd.replit.app").rstrip("/")
        ws_url = public_host.replace("https://", "wss://").replace("http://", "ws://")
        
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Connect>
    <Stream url="{ws_url}/ws/twilio-media"/>
  </Connect>
</Response>"""
        
    except Exception as e:
        log.error("Incoming call error: %s", e)
        # גם ה-fallback עכשיו עם Media Streams!
        public_host = os.getenv("PUBLIC_HOST", "https://ai-crmd.replit.app").rstrip("/")
        ws_url = public_host.replace("https://", "wss://").replace("http://", "ws://")
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Connect>
    <Stream url="{ws_url}/ws/twilio-media"/>
  </Connect>
</Response>"""
    
    return Response(xml, mimetype="text/xml", status=200)

@twilio_bp.post("/webhook/handle_recording")
@require_twilio_signature
def handle_recording():
    """עיבוד הקלטה - החזרת TwiML מהירה + עיבוד בbackground"""
    try:
        recording_url = request.form.get("RecordingUrl", "")
        call_sid = request.form.get("CallSid", "")
        
        log.info("Recording received: CallSid=%s RecordingUrl=%s", call_sid, recording_url)
        
        # Quick DB save - no heavy processing here
        try:
            from server.models_sql import CallLog
            from server.db import db
            
            rec = CallLog.query.filter_by(call_sid=call_sid).first()
            if not rec:
                rec = CallLog()
                rec.call_sid = call_sid
                rec.business_id = 1
                rec.status = "recorded"
                db.session.add(rec)
            
            rec.recording_url = recording_url
            rec.status = "recorded"
            db.session.commit()
            
            log.info("Recording saved to DB: CallSid=%s", call_sid)
            
        except Exception as e:
            log.error("Failed to save recording to DB: %s", e)
        
        # Background processing - don't wait for it
        try:
            from server.tasks_recording import enqueue_recording
            enqueue_recording(request.form.to_dict())
            log.info("Recording enqueued for background processing")
        except (ImportError, ModuleNotFoundError):
            log.warning("Recording task queue not available - will process in background thread")
            import threading
            def process_in_background():
                try:
                    log.info("Background processing recording: %s", recording_url)
                    # TODO: עיבוד אמיתי כאן (Whisper transcription, etc.)
                except Exception as e:
                    log.error("Background processing failed: %s", e)
            threading.Thread(target=process_in_background, daemon=True).start()
        except Exception as e:
            log.error("Failed to enqueue recording: %s", e)
        
        # Return fast TwiML response - no waiting
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say language="he-IL">תודה. ההודעה התקבלה.</Say>
  <Hangup/>
</Response>"""
        
        return Response(xml, mimetype="text/xml", status=200)
        
    except Exception as e:
        log.error("Error in handle_recording: %s", e)
        # Always return valid TwiML, never 500
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say language="he-IL">תודה.</Say>
  <Hangup/>
</Response>"""
        return Response(xml, mimetype="text/xml", status=200)

@twilio_bp.post("/webhook/call_status")
@require_twilio_signature
def call_status():
    """Call status updates - text/plain response (לא XML)"""
    try:
        call_sid = request.form.get("CallSid", "")
        call_status_val = request.form.get("CallStatus", "")
        
        log.info("Call status update: CallSid=%s Status=%s", call_sid, call_status_val)
        
        # שמירת סטטוס השיחה לDB - עדכון CallLog
        try:
            from server.models_sql import CallLog
            from server.db import db
            
            rec = CallLog.query.filter_by(call_sid=call_sid).first()
            if not rec:
                # יצירת רשומת שיחה חדשה
                rec = CallLog()
                rec.call_sid = call_sid
                rec.status = call_status_val
                rec.business_id = 1
                db.session.add(rec)
            else:
                # עדכון סטטוס קיים
                rec.status = call_status_val
            
            db.session.commit()
            log.info("Call status saved to DB: CallSid=%s Status=%s", call_sid, call_status_val)
            
        except Exception as e:
            log.error("Failed to save call status to DB: %s", e)
        
        # החזר תגובת סטטוס פשוטה - 204 No Content (לא TwiML)
        return ("", 204)
        
    except Exception as e:
        log.error("Error in call_status: %s", e)
        # Always return success to avoid retries
        return ("", 204)