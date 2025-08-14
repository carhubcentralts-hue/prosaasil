# server/routes_twilio.py
from flask import Blueprint, request, Response
from twilio.twiml.voice_response import VoiceResponse
import os, requests, io, logging
from server.logging_setup import _mask_phone

twilio_bp = Blueprint("twilio", __name__, url_prefix="/webhook")
log = logging.getLogger("twilio.voice")

@twilio_bp.route("/incoming_call", methods=["POST"])
def incoming_call():
    from_number = _mask_phone(request.form.get("From", ""))
    to_number = _mask_phone(request.form.get("To", ""))
    call_sid = request.form.get("CallSid", "")
    
    log.info("Incoming call: From=%s To=%s CallSid=%s", from_number, to_number, call_sid)
    
    host = os.getenv("HOST", "").rstrip("/")
    vr = VoiceResponse()
    if host:
        vr.play(f"{host}/static/voice_responses/welcome.mp3")  # optional greeting
    vr.record(
        max_length=30,       # required
        timeout=5,           # required
        finish_on_key="*",   # required
        play_beep=True,
        action="/webhook/handle_recording",
        method="POST",
        trim="do-not-trim"
    )
    return Response(str(vr), mimetype="text/xml", status=200)

@twilio_bp.route("/handle_recording", methods=["POST"])
def handle_recording():
    rec_url = request.form.get("RecordingUrl")
    call_sid = request.form.get("CallSid", "")
    
    log.info("Handle recording: url=%s CallSid=%s", rec_url, call_sid)
    
    if not rec_url:
        log.warning("No recording URL provided")
        return _say("סליחה, לא קיבלתי הקלטה. איך אפשר לעזור?")
    
    audio_url = f"{rec_url}.mp3"
    try:
        r = requests.get(audio_url, timeout=20); r.raise_for_status()
        audio_bytes = io.BytesIO(r.content)
        log.info("Successfully downloaded recording: %d bytes", len(audio_bytes.getvalue()))
    except Exception as e:
        log.error("Failed to download recording: %s", e)
        return _say("תקלה זמנית בהורדת ההקלטה. כיצד לעזור?")

    # Hebrew transcription using Whisper
    try:
        from server.whisper_handler import transcribe_he
        text_he = transcribe_he(audio_bytes)
        log.info("Transcription result: %s", text_he)
    except Exception as e:
        log.error("Transcription failed: %s", e, exc_info=True)
        return _say("לא הצלחתי להבין את ההקלטה. איך לעזור?")

    # Generate AI response
    try:
        from server.ai_conversation import generate_response
        ai_text = generate_response(text_he, call_sid)
        log.info("AI response generated: %s", ai_text)
    except Exception as e:
        log.error("AI response failed: %s", e, exc_info=True)
        ai_text = "אני כאן לעזור בנדל״ן. איך אפשר לסייע?"

    # Generate Hebrew TTS
    try:
        from server.hebrew_tts_enhanced import create_hebrew_audio
        audio_path = create_hebrew_audio(ai_text, call_sid)
        if audio_path:
            host = os.getenv("HOST", "").rstrip("/")
            if host:
                audio_url = f"{host}/{audio_path}"
                log.info("TTS generated: %s", audio_url)
                vr = VoiceResponse()
                vr.play(audio_url)
                vr.record(
                    max_length=30,
                    timeout=5,
                    finish_on_key="*",
                    play_beep=True,
                    action="/webhook/handle_recording",
                    method="POST",
                    trim="do-not-trim"
                )
                return Response(str(vr), mimetype="text/xml", status=200)
    except Exception as e:
        log.error("TTS failed: %s", e, exc_info=True)

    return _say(ai_text)

@twilio_bp.route("/call_status", methods=["POST","GET"])
def call_status():
    call_sid = request.form.get("CallSid", "")
    call_status = request.form.get("CallStatus", "")
    log.info("Call status update: CallSid=%s Status=%s", call_sid, call_status)
    return ("", 200)

def _say(text_he: str):
    vr = VoiceResponse()
    vr.say(text_he, language="he-IL")
    return Response(str(vr), mimetype="text/xml", status=200)

# Hebrew AI modules are now integrated above