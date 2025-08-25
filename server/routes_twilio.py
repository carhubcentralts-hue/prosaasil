"""
Hebrew AI Call Center - Twilio Routes FIXED לפי ההנחיות המדויקות
"""
import os
import time
import threading
from flask import Blueprint, request, current_app, make_response
from twilio.rest import Client
from server.stream_state import stream_registry
from server.twilio_security import require_twilio_signature

twilio_bp = Blueprint("twilio", __name__)

def abs_url(path: str) -> str:
    """Generate absolute URL for TwiML"""
    base = os.getenv("PUBLIC_BASE_URL") or os.getenv("PUBLIC_HOST") or request.url_root.rstrip("/")
    base = base.rstrip('/')  # Prevent double slashes
    return f"{base}{path}"

def _watchdog(call_sid, wss_host, start_timeout=6, no_media_timeout=6):
    """Watchdog to redirect calls if WebSocket fails"""
    time.sleep(start_timeout)
    st = stream_registry.get(call_sid)
    if not st.get("started"):
        _do_redirect(call_sid, wss_host, reason="no_stream_start")
        return
    if time.time() - st.get("last_media_at", 0) > no_media_timeout:
        _do_redirect(call_sid, wss_host, reason="no_media")

def _do_redirect(call_sid, wss_host, reason):
    """Watchdog redirect function"""
    current_app.logger.warning("WATCHDOG_REDIRECT", extra={"call_sid": call_sid, "reason": reason})
    twiml = f"""<Response>
  <Record playBeep="false" timeout="4" maxLength="30" transcribe="false"
          action="/webhook/handle_recording" />
  <Play>https://{wss_host}/static/tts/fallback_he.mp3</Play>
</Response>"""
    try:
        # Use Deployment ENV vars (critical for production)
        client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
        client.calls(call_sid).update(twiml=twiml)
        current_app.logger.info("WATCHDOG_REDIRECT_OK", extra={"call_sid": call_sid})
    except Exception:
        current_app.logger.exception("WATCHDOG_REDIRECT_FAIL")

@twilio_bp.route("/webhook/incoming_call", methods=["POST"])
@require_twilio_signature
def incoming_call():
    """Generate TwiML with <Connect><Stream> structure per guidelines"""
    call_sid = request.form.get("CallSid")
    
    greeting_url = abs_url("/static/tts/greeting_he.mp3")
    public_base = os.getenv("PUBLIC_BASE_URL") or os.getenv("PUBLIC_HOST") or request.url_root.rstrip("/")
    wss_host = public_base.replace("https://","").replace("http://","").strip("/")

    # CRITICAL: Use <Connect><Stream> without greeting - AI starts immediately!
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Connect action="/webhook/stream_ended">
    <Stream url="wss://{wss_host}/ws/twilio-media" statusCallback="/webhook/stream_status">
      <Parameter name="call_sid" value="{call_sid}"/>
    </Stream>
  </Connect>
</Response>"""
    
    # Start watchdog - TESTING MODE: 3s for immediate verification
    threading.Thread(target=_watchdog, args=(call_sid, wss_host, 3, 3), daemon=True).start()

    current_app.logger.info("TWIML_GENERATED", extra={
        "call_sid": call_sid, 
        "structure": "Connect-Stream",
        "wss_url": f"wss://{wss_host}/ws/twilio-media"
    })
    
    # Return TwiML with cache-busting headers
    resp = make_response(twiml, 200)
    resp.headers["Content-Type"] = "text/xml"
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    return resp

@twilio_bp.route("/webhook/stream_ended", methods=["POST"])
@require_twilio_signature
def stream_ended():
    """Handle stream ended event"""
    fallback = abs_url("/static/tts/fallback_he.mp3")
    twiml = f"""<Response>
  <Record playBeep="false" timeout="4" maxLength="30" transcribe="false"
          action="/webhook/handle_recording" />
  <Play>{fallback}</Play>
</Response>"""
    resp = make_response(twiml, 200)
    resp.headers["Content-Type"] = "text/xml"
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    return resp

@twilio_bp.route("/webhook/handle_recording", methods=["POST"])
@require_twilio_signature
def handle_recording():
    """Handle recording webhook"""
    call_sid = request.form.get("CallSid")
    rec_url = request.form.get("RecordingUrl")
    if rec_url:
        try:
            from server.tasks_recording import enqueue_recording
            enqueue_recording(request.form)
        except Exception:
            current_app.logger.exception("recording_queue_fail")
    resp = make_response("", 204)
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    return resp

@twilio_bp.route("/webhook/stream_status", methods=["POST"])
def stream_status():
    """Handle stream status events for diagnostics - NO signature required for Stream callbacks"""
    # אולטרה-סלחני: לא חותמת, לא JSON, לא extra בלוגים - בלי שום סיכוי ל-500
    try:
        form = request.form.to_dict()  # Twilio שולחת form-encoded
        # חשוב: בלי extra= בלוגים (פורמטרים רבים נופלים מזה)
        current_app.logger.info(
            "STREAM_STATUS call=%s stream=%s event=%s",
            form.get("CallSid"), form.get("StreamSid"), form.get("Status")
        )
    except Exception as e:
        # לעולם לא להפיל את הבקשה בגלל לוג
        try:
            current_app.logger.exception("STREAM_STATUS_HANDLER_FAILED: %s", e)
        except Exception:
            pass
    # תמיד 204 ומהר
    resp = make_response("", 204)
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    return resp

@twilio_bp.route("/webhook/call_status", methods=["POST"])
@require_twilio_signature
def call_status():
    """Handle call status updates"""
    call_sid = request.form.get("CallSid")
    call_status = request.form.get("CallStatus")
    try:
        current_app.logger.info("CALL_STATUS", extra={"call_sid": call_sid, "status": call_status})
        if call_status in ["completed", "busy", "no-answer", "failed", "canceled"]:
            from server.tasks_recording import save_call_status
            save_call_status(call_sid, call_status)
    except Exception:
        current_app.logger.exception("CALL_STATUS_HANDLER_ERROR")
    resp = make_response("", 204)
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    return resp

@twilio_bp.route("/webhook/test", methods=["POST", "GET"])
def test_webhook():
    """Test webhook endpoint"""
    return "TEST OK", 200

# All health endpoints are handled by app_factory.py to avoid conflicts