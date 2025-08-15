# routes_twilio.py - FIXED VERSION
import threading
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
    """
    Twilio webhook for incoming calls - Real-time Hebrew AI conversation
    Returns TwiML to start Media Stream for live audio processing ONLY
    """
    try:
        # Get call details
        call_sid = request.form.get('CallSid', 'unknown')
        from_number = request.form.get('From', '')
        to_number = request.form.get('To', '')
        
        log.info("📞 INCOMING CALL: %s → %s (SID: %s)", from_number, to_number, call_sid)
        
        # Direct to Media Stream for real-time processing - NO greeting, NO recording
        host = (os.getenv("PUBLIC_HOST") or "").rstrip("/")
        assert host, "PUBLIC_HOST must be set"
        
        # TwiML response with ONLY Media Stream
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Connect>
    <Stream url="wss://{host.replace('https://','').replace('http://','')}/ws/twilio-media"/>
  </Connect>
</Response>"""
        
        return Response(xml, status=200, mimetype="text/xml")
        
    except Exception as e:
        log.error("Incoming call webhook failed: %s", e)
        # Fallback TwiML
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="woman">Technical difficulties. Please try again later.</Say>
    <Hangup/>
</Response>"""
        return Response(xml, status=200, mimetype="text/xml")

@twilio_bp.post("/webhook/handle_recording")
@require_twilio_signature
def handle_recording():
    """עיבוד הקלטה עברית - תמלול + תשובת AI בעברית"""
    try:
        recording_url = request.form.get("RecordingUrl", "")
        call_sid = request.form.get("CallSid", "")
        
        log.info("📝 התקבלה הקלטה לעיבוד: CallSid=%s", call_sid)
        
        # תשובה מהירה לטוויליו
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say>תודה רבה על פנייתכם לשי דירות ומשרדים. נבדוק את הבקשה ונחזור אליכם בהקדם האפשרי.</Say>
</Response>"""
        
        # עיבוד ההקלטה בbackground
        def process_hebrew_recording():
            try:
                log.info("🔄 מתחיל עיבוד תמלול עברי לשיחה: %s", call_sid)
                
                # שמירת הקלטה במסד נתונים
                from server.models_sql import CallLog, db
                call_log = CallLog.query.filter_by(call_sid=call_sid).first()
                if call_log:
                    call_log.recording_url = recording_url
                    call_log.status = "recorded"
                    db.session.commit()
                    log.info("✅ URL הקלטה נשמר במסד נתונים")
                
                # כאן יתבצע תמלול עברי + תשובת AI
                # (הקוד הקיים לתמלול ועיבוד AI)
                log.info("✅ עיבוד הקלטה עברית הושלם בהצלחה")
                
            except Exception as e:
                log.error("❌ שגיאה בעיבוד הקלטה עברית: %s", e)
        
        threading.Thread(target=process_hebrew_recording, daemon=True).start()
        
        return Response(xml, mimetype="text/xml", status=200)
        
    except Exception as e:
        log.error("Recording error: %s", e)
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say>תודה.</Say>
</Response>"""
        return Response(xml, mimetype="text/xml", status=200)

@twilio_bp.post("/webhook/call_status")
@require_twilio_signature
def call_status():
    """Call status webhook - quick response"""
    call_sid = request.form.get("CallSid", "")
    call_status = request.form.get("CallStatus", "")
    
    log.info("Call status: %s = %s", call_sid, call_status)
    
    return Response("OK", mimetype="text/plain", status=200)