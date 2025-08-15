"""
Twilio Webhooks מאוחד וחדש - TwiML נכון + Content-Type + אבטחה + Background Processing
UNIFIED CLEAN FILE - לפי המפרט המקצועי
"""
from flask import Blueprint, request, Response, current_app
from urllib.parse import urljoin
from server.twilio_verify import require_twilio_signature
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
        raise RuntimeError("PUBLIC_HOST not set. Set PUBLIC_HOST in Replit Secrets")
    return urljoin(host + "/", path.lstrip("/"))

def get_business_greeting(to_number, call_sid):
    """Get business-specific greeting file based on number"""
    # Extract business_id from number mapping or use default
    # For now, use default greeting - can be extended per business
    return "static/voice_responses/welcome.mp3"

@twilio_bp.post("/webhook/incoming_call")
@require_twilio_signature
def incoming_call():
    """Handle incoming Twilio call - MUST return TwiML XML with correct Content-Type"""
    from_number = _mask_phone(request.form.get("From", ""))
    to_number = _mask_phone(request.form.get("To", ""))
    call_sid = request.form.get("CallSid", "")
    
    log.info("Incoming call: From=%s To=%s CallSid=%s", from_number, to_number, call_sid)
    
    # Get business-specific greeting
    greeting_path = get_business_greeting(to_number, call_sid)
    greeting_url = abs_url(greeting_path)
    
    # TwiML XML response (חובה - לא JSON!)
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>{greeting_url}</Play>
  <Pause length="1"/>
  <Record action="/webhook/handle_recording" 
          method="POST"
          maxLength="30" 
          timeout="5" 
          finishOnKey="*" 
          transcribe="false"/>
</Response>"""
    
    return Response(xml, mimetype="text/xml", status=200)

@twilio_bp.post("/webhook/handle_recording")
@require_twilio_signature
def handle_recording():
    """עיבוד הקלטה - החזרת TwiML מהירה + עיבוד בbackground"""
    recording_url = request.form.get("RecordingUrl", "")
    call_sid = request.form.get("CallSid", "")
    
    log.info("Recording received: CallSid=%s RecordingUrl=%s", call_sid, recording_url)
    
    # שלח לעיבוד ברקע (למנוע timeout) - אסינכרוני בלבד
    try:
        from server.tasks_recording import enqueue_recording
        enqueue_recording(request.form.to_dict())
        log.info("Recording enqueued for background processing")
    except (ImportError, ModuleNotFoundError):
        log.warning("Recording task queue not available - will process in background thread")
        import threading
        def process_in_background():
            try:
                # עיבוד minimal ברקע - ללא חסימה
                log.info("Background processing recording: %s", recording_url)
                # TODO: עיבוד אמיתי כאן
            except Exception as e:
                log.error("Background processing failed: %s", e)
        threading.Thread(target=process_in_background, daemon=True).start()
    
    # TwiML מהיר - תודה ותגובה
    xml = '''<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say language="he-IL">תודה, קיבלנו את ההודעה שלך.</Say>
  <Hangup/>
</Response>'''
    
    return Response(xml, mimetype="text/xml", status=200)

@twilio_bp.post("/webhook/call_status")
def call_status():
    """Call status updates - text/plain response (לא XML)"""
    call_sid = request.form.get("CallSid", "")
    call_status = request.form.get("CallStatus", "")
    
    log.info("Call status update: CallSid=%s Status=%s", call_sid, call_status)
    
    # שמירת סטטוס השיחה לDB
    try:
        # TODO: עדכון DB עם סטטוס השיחה
        pass
    except Exception as e:
        log.error("Failed to update call status: %s", e)
    
    return Response("OK", mimetype="text/plain", status=200)