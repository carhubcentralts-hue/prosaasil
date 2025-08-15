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
def incoming_call():
    """Handle incoming Twilio call - ULTRA SIMPLE TEST"""
    # Log everything Twilio sends us
    log.info("🔥 REAL TWILIO CALL - ALL DATA:")
    for key, value in request.form.items():
        log.info("  %s = %s", key, value)
    for key, value in request.headers.items():
        log.info("  HEADER %s = %s", key, value)
    
    call_sid = request.form.get("CallSid", "UNKNOWN")
    
    # MEGA SIMPLE - just works!
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say>Hello from Shai Apartments. This should work now.</Say>
  <Record maxLength="15"/>
</Response>"""
    
    log.info("🚀 MEGA SIMPLE XML FOR CALL: %s", call_sid)
    log.info("🔊 XML CONTENT: %s", xml)
    
    return Response(xml, mimetype="text/xml", status=200)

@twilio_bp.post("/webhook/handle_recording")
@require_twilio_signature
def handle_recording():
    """עיבוד הקלטה - החזרת TwiML מהירה + עיבוד בbackground"""
    try:
        recording_url = request.form.get("RecordingUrl", "")
        call_sid = request.form.get("CallSid", "")
        
        log.info("Recording received: CallSid=%s", call_sid)
        
        # Quick response to Twilio
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say>תודה על הפנייה. נחזור אליכם בהקדם.</Say>
</Response>"""
        
        # Process recording in background
        def process_recording():
            try:
                # Basic processing only
                log.info("Processing recording for call: %s", call_sid)
            except Exception as e:
                log.error("Recording processing error: %s", e)
        
        threading.Thread(target=process_recording, daemon=True).start()
        
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