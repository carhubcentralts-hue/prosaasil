# server/routes_twilio.py
from flask import Blueprint, request, Response, current_app
from urllib.parse import urljoin
from server.twilio_verify import require_twilio_signature
import os, requests, io, logging, json, threading, time

def _mask_phone(phone):
    """Mask phone number for logging privacy"""
    if not phone or len(phone) < 4:
        return phone
    return phone[:3] + "****" + phone[-2:]

twilio_bp = Blueprint("twilio_bp", __name__, url_prefix="")
log = logging.getLogger("twilio.voice")

def abs_url(path: str) -> str:
    """Generate absolute URL for Twilio webhooks - FAIL FAST if no host configured"""
    host = (current_app.config.get("PUBLIC_HOST") or os.getenv("PUBLIC_HOST") or "").rstrip("/")
    if not host:  # No fallback to old domain
        raise RuntimeError("PUBLIC_HOST not set. Set PUBLIC_HOST=https://your-domain")
    return urljoin(host + "/", path.lstrip("/"))

def get_business_greeting(to_number, call_sid):
    """Get business-specific greeting file based on number"""
    # Extract business_id from number mapping or use default
    # For now, use default greeting - can be extended per business
    return "static/voice_responses/welcome.mp3"

@twilio_bp.post("/webhook/incoming_call")
@require_twilio_signature
def incoming_call():
    """Handle incoming Twilio call - MUST return TwiML XML"""
    from_number = _mask_phone(request.form.get("From", ""))
    to_number = _mask_phone(request.form.get("To", ""))
    call_sid = request.form.get("CallSid", "")
    
    log.info("Incoming call: From=%s To=%s CallSid=%s", from_number, to_number, call_sid)
    
    # Get business-specific greeting
    greeting_path = get_business_greeting(to_number, call_sid)
    greeting_url = abs_url(greeting_path)
    
    # Build TwiML XML response (NO JSON!)
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>{greeting_url}</Play>
  <Pause length="1"/>
  <Record action="/webhook/handle_recording"
          method="POST"
          maxLength="30" timeout="5" finishOnKey="*"
          transcribe="false" />
</Response>"""
    
    return Response(xml, mimetype="text/xml", status=200)

def process_recording_sync(rec_url, call_sid, from_number):
    """Process recording SYNCHRONOUSLY for immediate response in continuous conversation"""
    try:
        log.info("Sync processing recording: %s for call %s", rec_url, call_sid)
        
        # Download recording
        audio_url = f"{rec_url}.mp3"
        r = requests.get(audio_url, timeout=15)
        r.raise_for_status()
        audio_bytes = io.BytesIO(r.content)
        
        # Save call data to database/storage
        call_data = {
            "call_sid": call_sid,
            "from_number": from_number,
            "recording_url": rec_url,
            "timestamp": time.time(),
            "status": "processing"
        }
        
        # Hebrew transcription using Whisper
        from server.whisper_handler import transcribe_he
        text_he = transcribe_he(audio_bytes)
        call_data["transcription"] = text_he
        log.info("Hebrew transcription for %s: %s", call_sid, text_he[:100])
        
        # Generate AI response
        from server.ai_conversation import generate_response
        ai_text = generate_response(text_he, call_sid)
        call_data["ai_response"] = ai_text
        call_data["status"] = "completed"
        
        log.info("AI response for %s: %s", call_sid, ai_text[:100])
        
        return ai_text
        
    except Exception as e:
        log.error("Sync recording processing failed for %s: %s", call_sid, e, exc_info=True)
        return "מצטער, לא הצלחתי לעבד את ההקלטה. אנא חזור על השאלה."

def process_recording_async(rec_url, call_sid, from_number):
    """Process recording in background thread - for logging/storage only"""
    try:
        log.info("Background logging for call %s", call_sid)
        # TODO: Save to database for analytics and history
        
    except Exception as e:
        log.error("Background logging failed for %s: %s", call_sid, e, exc_info=True)

@twilio_bp.route("/handle_recording_new", methods=["POST"])
def handle_recording_new():
    """NEW ROUTE - Handle recording - Process immediately and continue conversation"""
    rec_url = request.form.get("RecordingUrl")
    call_sid = request.form.get("CallSid", "")
    from_number = _mask_phone(request.form.get("From", ""))
    
    log.info("🚀 NEW HANDLER WORKS! url=%s CallSid=%s", rec_url, call_sid)
    
    # Simple test response
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say language="he-IL">בדיקה - זה הhandler החדש שעובד!</Say>
    <Pause length="1"/>
    <Record action="/webhook/handle_recording_new"
            method="POST"
            maxLength="30"
            timeout="5"
            finishOnKey="*"
            transcribe="false"
            language="he-IL"/>
</Response>"""
    
    return Response(xml, mimetype="text/xml", status=200)

@twilio_bp.post("/webhook/handle_recording")
@require_twilio_signature
def handle_recording():
    """Handle recording - lightweight processing with queue for heavy work"""
    form = request.form.to_dict()
    current_app.logger.info("handle_recording form=%s", form)
    
    # Don't do heavy transcription/AI here; just enqueue for background processing
    # enqueue_recording(form.get("RecordingUrl"), form.get("CallSid"), ...)
    
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say language="he-IL">תודה, קיבלנו את ההודעה.</Say>
  <Hangup/>
</Response>"""
    
    return Response(xml, mimetype="text/xml", status=200)

@twilio_bp.post("/webhook/call_status")
@require_twilio_signature
def call_status():
    """Handle Twilio call status callbacks - MUST return 200 OK with text/plain"""
    return ("OK", 200, {"Content-Type": "text/plain"})

def _say(text_he: str):
    """Helper to create SAY response in Hebrew - returns TwiML XML with CONTINUOUS RECORDING"""
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say language="he-IL">{text_he}</Say>
    <Pause length="1"/>
    <Record action="/webhook/handle_recording"
            method="POST"
            maxLength="30"
            timeout="5"
            finishOnKey="*"
            transcribe="false"
            language="he-IL"/>
</Response>"""
    return Response(xml, mimetype="text/xml", status=200)