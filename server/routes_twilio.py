# server/routes_twilio.py
from flask import Blueprint, request, Response
from twilio.twiml.voice_response import VoiceResponse
import os, requests, io

twilio_bp = Blueprint("twilio", __name__, url_prefix="/webhook")

@twilio_bp.route("/incoming_call", methods=["POST"])
def incoming_call():
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
    if not rec_url:
        return _say("סליחה, לא קיבלתי הקלטה. איך אפשר לעזור?")
    audio_url = f"{rec_url}.mp3"
    try:
        r = requests.get(audio_url, timeout=20); r.raise_for_status()
        audio_bytes = io.BytesIO(r.content)
    except Exception:
        return _say("תקלה זמנית בהורדת ההקלטה. כיצד לעזור?")

    # === Replace these stubs with your real modules ===
    try:
        text_he = transcribe_he(audio_bytes)        # Whisper Hebrew
    except Exception:
        return _say("לא הצלחתי להבין את ההקלטה. איך לעזור?")

    try:
        reply_he = generate_reply(text_he)          # GPT/business logic
    except Exception:
        reply_he = "קיבלתי את הבקשה. לבצע כעת?"

    try:
        tts_url = synthesize_tts_he(reply_he)       # should return a public URL or None
        if tts_url:
            vr = VoiceResponse(); vr.play(tts_url)
            return Response(str(vr), mimetype="text/xml", status=200)
    except Exception:
        pass

    return _say("אוקיי. רשמתי לפני. איך עוד לעזור?")

@twilio_bp.route("/call_status", methods=["POST","GET"])
def call_status():
    return ("", 200)

def _say(text_he: str):
    vr = VoiceResponse()
    vr.say(text_he, language="he-IL")
    return Response(str(vr), mimetype="text/xml", status=200)

# === Stubs to connect to your real code (replace) ===
def transcribe_he(audio_bytes): return "שלום, מה הסטטוס?"
def generate_reply(text_he: str): return "הסטטוס: הוזמן וייצא היום."
def synthesize_tts_he(text_he: str): return None