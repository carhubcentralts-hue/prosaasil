# server/routes_twilio.py
from flask import Blueprint, request, Response, current_app
from urllib.parse import urljoin
import os, requests, io, logging, json, threading, time

def _mask_phone(phone):
    """Mask phone number for logging privacy"""
    if not phone or len(phone) < 4:
        return phone
    return phone[:3] + "****" + phone[-2:]

twilio_bp = Blueprint("twilio", __name__, url_prefix="/webhook")
log = logging.getLogger("twilio.voice")

def abs_url(path):
    """Create absolute URL for Twilio webhooks"""
    host = current_app.config.get("PUBLIC_HOST") or os.getenv("PUBLIC_HOST") or os.getenv("HOST", "").rstrip("/")
    if not host:
        host = "https://ai-crmd.replit.app"  # Production fallback
    return urljoin(host + "/", path.lstrip("/"))

def get_business_greeting(to_number, call_sid):
    """Get business-specific greeting file"""
    # Use the working welcome file that exists
    return "static/voice_responses/welcome.mp3"

@twilio_bp.route("/incoming_call", methods=["POST"])
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
            maxLength="30"
            timeout="5"
            finishOnKey="*"
            transcribe="false"
            language="he-IL"/>
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

@twilio_bp.route("/handle_recording", methods=["POST"])
def handle_recording():
    """Handle recording - Process immediately and continue conversation"""
    rec_url = request.form.get("RecordingUrl")
    call_sid = request.form.get("CallSid", "")
    from_number = _mask_phone(request.form.get("From", ""))
    
    log.info("Handle recording: url=%s CallSid=%s", rec_url, call_sid)
    
    # Process recording IMMEDIATELY (not in background for continuous conversation)
    ai_response_text = process_recording_sync(rec_url, call_sid, from_number)
    
    # Generate Hebrew TTS response file
    try:
        from server.hebrew_tts_enhanced import create_hebrew_audio
        response_file = create_hebrew_audio(ai_response_text, f"call_{call_sid}")
        if response_file:
            response_url = abs_url(response_file)
            
            # Continue conversation - Play AI response then record again
            xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{response_url}</Play>
    <Pause length="1"/>
    <Record action="/webhook/handle_recording"
            method="POST"
            maxLength="30"
            timeout="5"
            finishOnKey="*"
            transcribe="false"
            language="he-IL"/>
</Response>"""
        else:
            # Fallback - use Say instead of Play
            xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say language="he-IL">{ai_response_text}</Say>
    <Pause length="1"/>
    <Record action="/webhook/handle_recording"
            method="POST"
            maxLength="30"
            timeout="5"
            finishOnKey="*"
            transcribe="false"
            language="he-IL"/>
</Response>"""
            
    except Exception as e:
        log.error("Error generating TTS response: %s", e)
        # Fallback response
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say language="he-IL">מצטער, נתקלתי בבעיה טכנית. אנא נסה שוב.</Say>
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

@twilio_bp.route("/call_status", methods=["POST"])
def call_status():
    """Handle Twilio call status callbacks - MUST return 200 OK with text/plain"""
    call_sid = request.form.get("CallSid", "")
    call_status_value = request.form.get("CallStatus", "")
    duration = request.form.get("CallDuration", "0")
    
    log.info("Call status update: CallSid=%s Status=%s Duration=%ss", 
             call_sid, call_status_value, duration)
    
    # Save status to database/storage (non-blocking)
    try:
        # TODO: Update call record in database with status and duration
        pass
    except Exception as e:
        log.error("Failed to save call status: %s", e)
    
    # MUST return 200 OK with text/plain (NOT JSON, NOT TwiML)
    response = Response("OK", mimetype="text/plain", status=200)
    return response

def _say(text_he: str):
    """Helper to create SAY response in Hebrew - returns TwiML XML"""
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say language="he-IL">{text_he}</Say>
    <Hangup/>
</Response>"""
    return Response(xml, mimetype="text/xml", status=200)