from flask import Blueprint, request, Response, current_app
from twilio.twiml.voice_response import VoiceResponse
from whisper_handler import transcribe_hebrew
from ai_service import generate_reply_tts

twilio_bp = Blueprint("twilio", __name__)

@twilio_bp.route("/incoming_call", methods=["POST"])
def incoming_call():
    host = current_app.config.get("HOST", request.host_url.rstrip("/"))
    vr = VoiceResponse()
    # ברכה (בחר: Play קובץ או Say)
    # vr.say("ברוך הבא, איך אפשר לעזור?", language="he-IL")
    vr.play(f"{host}/static/greeting.mp3")
    vr.record(
        finish_on_key="*",
        timeout=5,
        max_length=30,
        play_beep=True,
        action="/webhook/handle_recording"
    )
    return Response(str(vr), mimetype="text/xml")

@twilio_bp.route("/handle_recording", methods=["POST"])
def handle_recording():
    rec_url = request.form.get("RecordingUrl", "")
    text = transcribe_hebrew(rec_url)  # Whisper עברית
    audio_url = generate_reply_tts(text)  # מחזיר URL ל-MP3
    vr = VoiceResponse()
    vr.play(audio_url)
    return Response(str(vr), mimetype="text/xml")

@twilio_bp.route("/call_status", methods=["POST"])
def call_status():
    return ("", 200)