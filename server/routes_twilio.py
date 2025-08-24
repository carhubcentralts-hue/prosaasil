"""
Hebrew AI Call Center - Twilio Routes FIXED לפי ההנחיות המדויקות
"""
import os
import time
import threading
from flask import Blueprint, request, current_app
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

    # CRITICAL: Use <Connect><Stream> NOT <Start><Stream> per guidelines!
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>{greeting_url}</Play>
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
    
    return twiml, 200, {"Content-Type": "text/xml"}

@twilio_bp.route("/webhook/stream_ended", methods=["POST"])
@require_twilio_signature
def stream_ended():
    """Handle stream ended event"""
    fallback = abs_url("/static/tts/fallback_he.mp3")
    return f"""<Response>
  <Record playBeep="false" timeout="4" maxLength="30" transcribe="false"
          action="/webhook/handle_recording" />
  <Play>{fallback}</Play>
</Response>""", 200, {"Content-Type":"text/xml"}

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
    return "", 204

@twilio_bp.route("/webhook/stream_status", methods=["POST"])
def stream_status():
    """Handle stream status events for diagnostics"""
    try:
        current_app.logger.info("STREAM_STATUS", extra={"form": dict(request.form)})
    except Exception:
        current_app.logger.exception("STREAM_STATUS_ERROR")
    return "", 204

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
    return "", 204

@twilio_bp.route("/webhook/test", methods=["POST", "GET"])
def test_webhook():
    """Test webhook endpoint"""
    return "TEST OK", 200

# Health endpoints per guidelines §9
@twilio_bp.route("/healthz", methods=["GET"])
def healthz():
    """Basic health check"""
    return "ok", 200

@twilio_bp.route("/readyz", methods=["GET"])
def readyz():
    """Readiness check with service status"""
    import json
    try:
        status = {
            "db": bool(os.getenv("DATABASE_URL")),
            "openai": bool(os.getenv("OPENAI_API_KEY")),
            "tts": bool(os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or os.getenv("GOOGLE_TTS_SA_JSON")),
            "twilio_secrets": bool(os.getenv("TWILIO_ACCOUNT_SID") and os.getenv("TWILIO_AUTH_TOKEN"))
        }
        return json.dumps(status), 200, {"Content-Type": "application/json"}
    except Exception:
        return '{"error": "readiness check failed"}', 500, {"Content-Type": "application/json"}

@twilio_bp.route("/version", methods=["GET"])
def version():
    """Version information"""
    import json
    import time
    try:
        version_info = {
            "app": "AgentLocator",
            "version": "71",
            "build_time": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "status": "production_ready"
        }
        return json.dumps(version_info), 200, {"Content-Type": "application/json"}
    except Exception:
        return '{"error": "version check failed"}', 500, {"Content-Type": "application/json"}