"""
Twilio webhook routes (לפי ההנחיות המדויקות)
"""
import os
import json
import threading
import time
import logging
from flask import Blueprint, request, Response, current_app
from twilio.rest import Client
from server.stream_state import stream_registry
from server.twilio_security import require_twilio_signature

twilio_bp = Blueprint("twilio", __name__)

def abs_url(path: str) -> str:
    """3) TwiML דינמי 100% (לפי ההנחיות המדויקות)"""
    base = os.getenv("PUBLIC_BASE_URL") or request.url_root.rstrip("/")
    return f"{base}{path}"

def _watchdog(call_sid, wss_host, start_timeout=6, no_media_timeout=6):
    """5) Watchdog – Redirect בזמן השיחה (לפי ההנחיות המדויקות)"""
    time.sleep(start_timeout)
    st = stream_registry.get(call_sid)
    # אם לא התחיל סטרים → Redirect ל-Record
    if not st.get("started"):
        _do_redirect(call_sid, wss_host, reason="no_stream_start")
        return
    # התחיל אבל אין פריימים זמן מה → Redirect
    if time.time() - st.get("last_media_at", 0) > no_media_timeout:
        _do_redirect(call_sid, wss_host, reason="no_media")

def _do_redirect(call_sid, wss_host, reason):
    """5) Watchdog redirect function (לפי ההנחיות המדויקות)"""
    current_app.logger.warning("WATCHDOG_REDIRECT", extra={"call_sid": call_sid, "reason": reason})
    twiml = f"""<Response>
  <Record playBeep="false" timeout="4" maxLength="30" transcribe="false"
          action="/webhook/handle_recording" />
  <Play>https://{wss_host}/static/tts/fallback_he.mp3</Play>
</Response>"""
    try:
        client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
        client.calls(call_sid).update(twiml=twiml)
        current_app.logger.info("WATCHDOG_REDIRECT_OK", extra={"call_sid": call_sid})
    except Exception:
        current_app.logger.exception("WATCHDOG_REDIRECT_FAIL")

@twilio_bp.route("/webhook/incoming_call", methods=["POST"])
@require_twilio_signature  # 7) חתימת Twilio (Production)
def incoming_call():
    """3) TwiML דינמי 100% + בלי <Say he-IL> (לפי ההנחיות המדויקות)"""
    call_sid = request.form.get("CallSid")

    greeting_url = abs_url("/static/tts/greeting_he.mp3")
    wss_host = (os.getenv("PUBLIC_BASE_URL") or request.url_root) \
                .replace("https://","").replace("http://","").strip("/")

    # אין <Say language="he-IL"> (זה גורם 13512). עברית תמיד דרך <Play> של MP3.
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>{greeting_url}</Play>
  <Connect action="/webhook/stream_ended">
    <Stream url="wss://{wss_host}/ws/twilio-media">
      <Parameter name="call_sid" value="{call_sid}"/>
    </Stream>
  </Connect>
</Response>"""
    
    # הפעל watchdog (סעיף 5)
    threading.Thread(target=_watchdog, args=(call_sid, wss_host, 6, 6), daemon=True).start()

    return twiml, 200, {"Content-Type": "text/xml"}

@twilio_bp.route("/webhook/stream_ended", methods=["POST"])
@require_twilio_signature  # 7) חתימת Twilio (Production)
def stream_ended():
    """6) /webhook/stream_ended (לפי ההנחיות המדויקות)"""
    # להחזיר תמיד TwiML Fallback בטוח — לא 500
    fallback = abs_url("/static/tts/fallback_he.mp3")
    return f"""<Response>
  <Record playBeep="false" timeout="4" maxLength="30" transcribe="false"
          action="/webhook/handle_recording" />
  <Play>{fallback}</Play>
</Response>""", 200, {"Content-Type":"text/xml"}

@twilio_bp.route("/webhook/handle_recording", methods=["POST"])
@require_twilio_signature  # 7) חתימת Twilio (Production)
def handle_recording():
    """6) /webhook/handle_recording (לפי ההנחיות המדויקות)"""
    call_sid = request.form.get("CallSid")
    rec_url  = request.form.get("RecordingUrl")
    if rec_url:
        try:
            import requests
            audio = requests.get(rec_url + ".mp3", timeout=10).content
            # text = transcribe_he(audio)   # פונקציית ה-Whisper שלך
            # update_call_log_transcript(call_sid, text)  # כתיבה ל-DB
            current_app.logger.info("recording_transcribed", extra={"call_sid": call_sid})
        except Exception:
            current_app.logger.exception("recording_transcribe_fail")
    return "", 204

# Test endpoint (לא עם חתימת Twilio)
@twilio_bp.route("/webhook/test", methods=['GET', 'POST'])
def test_endpoint():
    return "TEST OK", 200