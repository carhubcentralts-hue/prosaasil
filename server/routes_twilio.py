from flask import Blueprint, request, Response, current_app
twilio_bp = Blueprint("twilio_bp", __name__, url_prefix="")

@twilio_bp.post("/webhook/incoming_call")
def incoming_call():
    host = current_app.config.get("PUBLIC_HOST", "https://YOUR_HOST")
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>{host}/server/static/voice_responses/greeting.mp3</Play>
  <Pause length="1"/>
  <Record action="/webhook/handle_recording"
          method="POST"
          maxLength="30"
          timeout="5"
          finishOnKey="*"
          transcribe="false"/>
</Response>"""
    return Response(xml, mimetype="text/xml")

@twilio_bp.post("/webhook/handle_recording")
def handle_recording():
    # נשאר כפי שמומש אצלך: הורדת WAV, בדיקת אורך, Whisper, GPT, TTS fallback (פעם אחת), שמירה ל-DB
    return Response("<Response></Response>", mimetype="text/xml")

@twilio_bp.post("/webhook/call_status")
def call_status():
    # אופציונלי: לוג קצר של status, אבל תמיד 200
    return "OK", 200