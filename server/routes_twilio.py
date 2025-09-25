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
from server.extensions import csrf

# ייבוא מראש למניעת עיכובים ב-webhooks
from server.tasks_recording import save_call_status, enqueue_recording

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
    # ✅ FIX: Absolute URL for watchdog redirect
    host = os.environ.get('REPLIT_DEV_DOMAIN') or os.environ.get('REPLIT_DOMAINS', '').split(',')[0] or 'localhost'
    twiml = f"""<Response>
  <Record playBeep="false" timeout="4" maxLength="30" transcribe="false"
          action="https://{host}/webhook/handle_recording" />
</Response>"""
    try:
        # Use Deployment ENV vars (critical for production)
        client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
        client.calls(call_sid).update(twiml=twiml)
        current_app.logger.info("WATCHDOG_REDIRECT_OK", extra={"call_sid": call_sid})
    except Exception:
        current_app.logger.exception("WATCHDOG_REDIRECT_FAIL")

def _trigger_recording_for_call(call_sid):
    """חפש או עורר הקלטה לשיחה לאחר שהזרם נגמר"""
    try:
        # וידוא שיש אישורי Twilio
        account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
        auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
        
        if not account_sid or not auth_token:
            print(f"❌ Missing Twilio credentials for recording {call_sid}")
            return
            
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        
        # קודם נחפש הקלטות קיימות לשיחה
        try:
            recordings = client.recordings.list(call_sid=call_sid, limit=5)
            
            if recordings:
                # נמצאו הקלטות - נעבד אותן
                for recording in recordings:
                    print(f"✅ Found existing recording for {call_sid}: {recording.uri}")
                    
                    # קבל פרטי השיחה למספרי טלפון
                    from_num = ''
                    to_num = ''
                    try:
                        call = client.calls(call_sid).fetch()
                        from_num = getattr(call, 'from_', '') or str(getattr(call, 'from_formatted', '') or '')
                        to_num = getattr(call, 'to', '') or str(getattr(call, 'to_formatted', '') or '')
                    except Exception as e:
                        print(f"⚠️ Could not get call details: {e}")
                    
                    # בנה form data כמו webhook של Twilio
                    # ✅ FIX: Use correct MP3 URL construction
                    recording_mp3_url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Recordings/{recording.sid}.mp3"
                    form_data = {
                        'CallSid': call_sid,
                        'RecordingUrl': recording_mp3_url,
                        'RecordingDuration': str(recording.duration),
                        'RecordingStatus': recording.status,
                        'From': from_num,
                        'To': to_num
                    }
                    
                    # שלח לעיבוד
                    enqueue_recording(form_data)
                    print(f"✅ Recording queued for processing: {call_sid}")
                    return
                    
        except Exception as e:
            print(f"⚠️ Error checking recordings for {call_sid}: {e}")
        
        # אם אין הקלטות, נסה לעדכן השיחה לכלול Record (אם עדיין פעילה)
        try:
            call = client.calls(call_sid).fetch()
            
            if call.status in ['in-progress', 'ringing']:
                # השיחה עדיין פעילה - עדכן ל-Record TwiML
                # ✅ FIX: Use absolute URL for Twilio webhooks
                host = os.environ.get('REPLIT_DEV_DOMAIN') or os.environ.get('REPLIT_DOMAINS', '').split(',')[0] or 'your-app.replit.app'
                record_twiml = f"""<Response>
  <Record playBeep="false" timeout="30" maxLength="300" transcribe="false"
          action="https://{host}/webhook/handle_recording" />
</Response>"""
                
                client.calls(call_sid).update(twiml=record_twiml)
                print(f"✅ Updated call {call_sid} to Record TwiML")
            else:
                print(f"ℹ️ Call {call_sid} ended without recording (status: {call.status})")
                
        except Exception as e:
            print(f"⚠️ Error updating call {call_sid}: {e}")
            
    except Exception as e:
        print(f"❌ Failed to trigger recording for {call_sid}: {e}")

# TwiML Preview endpoint (ללא Play, מינימלי)
@csrf.exempt
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
        f'      <Parameter name="CallSid" value="{call_sid}"/>',
        f'    </Stream>',
        f'  </Connect>',
        '</Response>',
    ]
    twiml = "".join(parts)
    
    # תיקון קריטי לError 12100 - Content-Type נכון + cache busting
    resp = make_response(twiml.encode("utf-8"), 200)
    resp.headers["Content-Type"] = "application/xml; charset=utf-8"  # FIX_12100_PREVIEW
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["X-Debug-Version"] = "TwiML_v2_fixed"
    return resp

@csrf.exempt
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
        f'      <Parameter name="CallSid" value="{call_sid}"/>',
        f'    </Stream>',
        f'  </Connect>',
        '</Response>',
    ]
    twiml = "".join(parts)
    
    # החזרה מיידית ללא עיכובים + תיקון Error 12100
    resp = make_response(twiml.encode("utf-8"), 200)
    resp.headers["Content-Type"] = "application/xml; charset=utf-8"  # FIX_12100_INCOMING
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["X-Debug-Version"] = "TwiML_v2_fixed"
    return resp

@csrf.exempt
@twilio_bp.route("/webhook/stream_ended", methods=["POST"])
@require_twilio_signature
def stream_ended():
    """Stream ended - trigger recording + fast response"""
    call_sid = request.form.get('CallSid', '')
    
    # החזרה מיידית
    resp = make_response("", 204)
    resp.headers["Cache-Control"] = "no-store"
    
    # עיבוד ברקע - עורר הקלטה או חפש הקלטה קיימת
    if call_sid:
        threading.Thread(
            target=_trigger_recording_for_call, 
            args=(call_sid,), 
            daemon=True
        ).start()
        
    try:
        call_sid = request.form.get('CallSid', 'N/A')
        stream_sid = request.form.get('StreamSid', 'N/A') 
        status = request.form.get('Status', 'N/A')
        print(f"STREAM_ENDED call={call_sid} stream={stream_sid} status={status}")
    except:
        pass
        
    return resp

@csrf.exempt
@twilio_bp.route("/webhook/handle_recording", methods=["POST"])
@require_twilio_signature
def handle_recording():
    """
    Handle recording webhook - ULTRA FAST response with immediate processing
    שלב 4: שדרוג למענה מיידי עם monitoring משופר
    """
    import time
    start_time = time.time()
    
    # Fast data extraction
    call_sid = request.form.get("CallSid", "unknown")
    rec_url = request.form.get("RecordingUrl")
    rec_duration = request.form.get("RecordingDuration", "0")
    rec_status = request.form.get("RecordingStatus", "unknown")
    
    # Immediate response preparation (no blocking operations)
    resp = make_response("", 204)
    resp.headers.update({
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Connection": "close"  # Ensure connection closes immediately
    })
    
    # TRUE non-blocking background processing with daemon thread
    if rec_url and rec_url.strip():
        try:
            # Truly async - starts thread and returns immediately
            form_copy = dict(request.form)  # Copy form data before thread
            
            def async_enqueue():
                """Background thread for recording processing"""
                try:
                    enqueue_recording(form_copy)
                    current_app.logger.info("REC_QUEUED_ASYNC", extra={
                        "call_sid": call_sid[:16],
                        "duration": rec_duration,
                        "status": rec_status
                    })
                except Exception as e:
                    current_app.logger.error("REC_QUEUE_ASYNC_FAIL", extra={
                        "call_sid": call_sid[:16],
                        "error_type": type(e).__name__
                    })
            
            # Fire daemon thread and return immediately (non-blocking)
            threading.Thread(target=async_enqueue, daemon=True).start()
            
            # Immediate success log (thread started, not completed)
            current_app.logger.info("REC_THREAD_STARTED", extra={
                "call_sid": call_sid[:16],
                "processing_ms": int((time.time() - start_time) * 1000)
            })
            
        except Exception as e:
            # Thread creation failed - ultra-fast error log
            current_app.logger.error("REC_THREAD_FAIL", extra={
                "call_sid": call_sid[:16],
                "error_type": type(e).__name__,
                "processing_ms": int((time.time() - start_time) * 1000)
            })
    else:
        # Log missing recording URL
        current_app.logger.warning("REC_NO_URL", extra={
            "call_sid": call_sid[:16],
            "status": rec_status,
            "processing_ms": int((time.time() - start_time) * 1000)
        })
    
    return resp

@csrf.exempt
@twilio_bp.route("/webhook/stream_status", methods=["POST"])  
@require_twilio_signature
def stream_status():
    """שלב 5: Webhooks קשיחים - ULTRA FAST מחזיר 204"""
    # החזרה מיידית ללא עיבוד כלל
    resp = make_response("", 204)
    resp.headers["Cache-Control"] = "no-store"
    
    # לוגים ברקע (לא חוסמים את הresponse)  
    try:
        call_sid = request.form.get('CallSid', 'N/A')
        stream_sid = request.form.get('StreamSid', 'N/A')
        event = request.form.get('Status', 'N/A')
        print(f"STREAM_STATUS call={call_sid} stream={stream_sid} event={event}")
    except:
        pass  # אף פעם לא לחסום על לוגים
        
    return resp

@csrf.exempt
@twilio_bp.route("/webhook/call_status", methods=["POST"])
@require_twilio_signature
def call_status():
    """Handle call status updates - FAST אסינכרוני"""
    call_sid = request.form.get("CallSid")
    call_status = request.form.get("CallStatus")
    
    # החזרה מיידית ללא עיכובים
    resp = make_response("", 204)
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    
    # עיבוד ברקע אחרי שהחזרנו response
    try:
        current_app.logger.info("CALL_STATUS", extra={"call_sid": call_sid, "status": call_status})
        if call_status in ["completed", "busy", "no-answer", "failed", "canceled"]:
            save_call_status(call_sid, call_status)  # כעת אסינכרוני
    except Exception:
        current_app.logger.exception("CALL_STATUS_HANDLER_ERROR")
    
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
    
    resp = make_response(twiml.encode("utf-8"), 200)
    resp.headers["Content-Type"] = "application/xml; charset=utf-8"
    resp.headers["Cache-Control"] = "no-store, no-cache"
    return resp
