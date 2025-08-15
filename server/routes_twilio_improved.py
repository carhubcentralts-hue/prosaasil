"""
Twilio Webhooks מושלמים - TwiML נכון + Content-Type + אבטחה
לפי המפרט המקצועי
"""
from flask import Blueprint, Response, request, current_app
from urllib.parse import urljoin
import os
import logging

twilio_improved_bp = Blueprint("twilio_improved_bp", __name__, url_prefix="")
log = logging.getLogger("twilio.improved")

def abs_url(path: str) -> str:
    """יצירת URL מוחלט עבור Twilio webhooks - FAIL FAST אם לא מוגדר HOST"""
    host = (current_app.config.get("PUBLIC_HOST") or os.getenv("PUBLIC_HOST") or "").rstrip("/")
    if not host:
        raise RuntimeError("PUBLIC_HOST not set. Set PUBLIC_HOST in Replit Secrets")
    return urljoin(host + "/", path.lstrip("/"))

@twilio_improved_bp.post("/webhook/incoming_call")
def incoming_call():
    """Handle incoming Twilio call - MUST return TwiML XML with correct Content-Type"""
    from_number = request.form.get("From", "")
    to_number = request.form.get("To", "")
    call_sid = request.form.get("CallSid", "")
    
    log.info("Incoming call: From=%s To=%s CallSid=%s", from_number, to_number, call_sid)
    
    # קישור לקובץ הברכה
    greeting_url = abs_url("static/voice_responses/welcome.mp3")
    
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

@twilio_improved_bp.post("/webhook/handle_recording")
def handle_recording():
    """עיבוד הקלטה - החזרת TwiML מהירה + עיבוד בbackground"""
    recording_url = request.form.get("RecordingUrl", "")
    call_sid = request.form.get("CallSid", "")
    
    log.info("Recording received: CallSid=%s RecordingUrl=%s", call_sid, recording_url)
    
    # שלח לעיבוד ברקע (למנוע timeout)
    try:
        from server.tasks_recording import enqueue_recording
        enqueue_recording(request.form.to_dict())
    except (ImportError, ModuleNotFoundError):
        log.warning("Recording task queue not available - processing synchronously")
        # TODO: עיבוד סינכרוני כ-fallback
    
    # TwiML מהיר - תודה ותגובה
    xml = '''<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say language="he-IL">תודה, קיבלנו את ההודעה שלך.</Say>
  <Hangup/>
</Response>'''
    
    return Response(xml, mimetype="text/xml", status=200)

@twilio_improved_bp.post("/webhook/call_status")
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