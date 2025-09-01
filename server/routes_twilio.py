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
    """Generate absolute URL for TwiML - תיקון קריטי להסבת https://"""
    scheme = (request.headers.get("X-Forwarded-Proto") or "https").split(",")[0].strip()
    host   = (request.headers.get("X-Forwarded-Host")  or request.host).split(",")[0].strip()
    base   = f"{scheme}://{host}"
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
</Response>"""
    try:
        # Use Deployment ENV vars (critical for production)
        client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
        client.calls(call_sid).update(twiml=twiml)
        current_app.logger.info("WATCHDOG_REDIRECT_OK", extra={"call_sid": call_sid})
    except Exception:
        current_app.logger.exception("WATCHDOG_REDIRECT_FAIL")

# TwiML Preview endpoint (ללא Play, מינימלי)
@twilio_bp.route("/webhook/incoming_call_preview", methods=["GET"])
def incoming_call_preview():
    """GET endpoint for TwiML preview - MEDIA STREAMS MODE"""
    call_sid = "CA_PREVIEW_" + str(int(time.time()))
    
    # תיקון קריטי: וידוא https:// ב-base URLs  
    scheme = (request.headers.get("X-Forwarded-Proto") or "https").split(",")[0].strip()
    host   = (request.headers.get("X-Forwarded-Host")  or request.host).split(",")[0].strip()
    base   = f"{scheme}://{host}"
    
    # שלב 4: TwiML נקי לפי ההנחיות - Media Streams עם Connect בלבד
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<Response>',
        f'  <Connect action="{base}/webhook/stream_ended">',
        f'    <Stream url="wss://{host}/ws/twilio-media"',
        f'            statusCallback="{base}/webhook/stream_status">',
        f'      <Parameter name="call_sid" value="{call_sid}"/>',
        f'    </Stream>',
        f'  </Connect>',
        '</Response>',
    ]
    twiml = "".join(parts)
    
    resp = make_response(twiml, 200)
    resp.headers["Content-Type"] = "text/xml"
    resp.headers["Cache-Control"] = "no-store"
    return resp

@twilio_bp.route("/webhook/incoming_call", methods=["POST"])
@require_twilio_signature
def incoming_call():
    """TwiML מהיר וללא עיכובים - One True Path"""
    call_sid = request.form.get("CallSid", "")
    
    # תיקון קריטי: וידוא https:// ב-base URLs (לפי ההנחיות)
    scheme = (request.headers.get("X-Forwarded-Proto") or "https").split(",")[0].strip()
    host   = (request.headers.get("X-Forwarded-Host")  or request.host).split(",")[0].strip()
    base   = f"{scheme}://{host}"
    
    # שלב 4: TwiML נקי לפי ההנחיות - Media Streams עם Connect בלבד  
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<Response>',
        f'  <Connect action="{base}/webhook/stream_ended">',
        f'    <Stream url="wss://{host}/ws/twilio-media"',
        f'            statusCallback="{base}/webhook/stream_status">',
        f'      <Parameter name="call_sid" value="{call_sid}"/>',
        f'    </Stream>',
        f'  </Connect>',
        '</Response>',
    ]
    twiml = "".join(parts)
    
    # החזרה מיידית ללא עיכובים
    resp = make_response(twiml, 200)
    resp.headers["Content-Type"] = "text/xml"     # מונע 12300
    resp.headers["Cache-Control"] = "no-store"
    return resp

@twilio_bp.route("/webhook/stream_ended", methods=["POST"])
def stream_ended():
    """שלב 5: Webhooks קשיחים - מחזיר 204 ללא TwiML"""
    form = request.form.to_dict()
    print(f"STREAM_ENDED call={form.get('CallSid')} stream={form.get('StreamSid')} status={form.get('Status')}")
    return ("", 204)

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
    """שלב 5: Webhooks קשיחים - קורא form.to_dict(flat=True), מחזיר 204"""
    form = request.form.to_dict()  # Fixed: removed flat parameter
    print(f"STREAM_STATUS call={form.get('CallSid')} stream={form.get('StreamSid')} event={form.get('Status')}")
    return ("", 204)

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
@twilio_bp.route("/webhook/test_media_streams_1756667590", methods=["GET"])
def test_media_streams_new():
    """Test endpoint for Media Streams - no cache, no Play"""
    # תיקון: דינמי במקום hardcoded
    scheme = (request.headers.get("X-Forwarded-Proto") or "https").split(",")[0].strip()
    host   = (request.headers.get("X-Forwarded-Host")  or request.host).split(",")[0].strip()
    base   = f"{scheme}://{host}"
    call_sid = "TEST_NEW"
    
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Connect action="{base}/webhook/stream_ended">
    <Stream url="wss://{host}/ws/twilio-media" statusCallback="{base}/webhook/stream_status">
      <Parameter name="call_sid" value="{call_sid}"/>
    </Stream>
  </Connect>
</Response>"""
    
    resp = make_response(twiml, 200)
    resp.headers["Content-Type"] = "text/xml"
    resp.headers["Cache-Control"] = "no-store, no-cache"
    return resp
