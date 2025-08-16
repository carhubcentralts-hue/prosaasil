# routes_twilio.py - DEBUG VERSION
import threading
from flask import Blueprint, request, Response, current_app
from urllib.parse import urljoin
import os, logging

# Force immediate debug output
print("🚀 ROUTES_TWILIO.PY LOADED!")
logging.basicConfig(level=logging.DEBUG)

def _mask_phone(phone):
    """Mask phone number for logging privacy"""
    if not phone or len(phone) < 4:
        return phone
    return phone[:3] + "****" + phone[-2:]

twilio_bp = Blueprint("twilio_bp_v2", __name__, url_prefix="")

# Simple test endpoint to verify Flask routing works
@twilio_bp.route("/webhook/test", methods=['GET', 'POST'])
def test_endpoint():
    print("🧪 TEST ENDPOINT HIT!")
    with open('/tmp/test_debug.log', 'w') as f:
        f.write("TEST ENDPOINT WAS CALLED\n")
    return "TEST OK", 200

# Test endpoint NOT under /webhook/ path
@twilio_bp.route("/twilio-test", methods=['GET', 'POST'])
def twilio_test():
    print("🧪 TWILIO-TEST ENDPOINT HIT!")
    with open('/tmp/twilio_test.log', 'w') as f:
        f.write("TWILIO TEST ENDPOINT WAS CALLED\n")
    return "TWILIO TEST OK", 200
log = logging.getLogger("twilio.unified")

def abs_url(path: str) -> str:
    """יצירת URL מוחלט עבור Twilio webhooks - FAIL FAST אם לא מוגדר HOST"""
    host = (current_app.config.get("PUBLIC_HOST") or os.getenv("PUBLIC_HOST") or "").rstrip("/")
    if not host:
        raise RuntimeError("PUBLIC_HOST not configured - Hebrew fallback will be used")
    return urljoin(host + "/", path.lstrip("/"))

def get_business_greeting(to_number, call_sid):
    """Get business-specific greeting file based on number"""
    # Extract business_id from number mapping or use default
    # For now, use default greeting - can be extended per business
    return "static/voice_responses/welcome.mp3"

@twilio_bp.route("/webhook/incoming_call", methods=['POST', 'GET'])
def incoming_call():
    """
    Twilio webhook for incoming calls - Real-time Hebrew AI conversation
    Returns TwiML to start Media Stream for live audio processing ONLY
    """
    # CRITICAL DEBUG - MUST SEE THIS
    print("🚨🚨🚨 INCOMING_CALL WEBHOOK EXECUTING!", flush=True)
    
    # Force multiple debug outputs
    import datetime
    now = datetime.datetime.now()
    with open('/tmp/webhook_hit.log', 'w') as f:
        f.write(f"WEBHOOK HIT: {now}\n")
    
    print(f"📞 WEBHOOK DATA: method={request.method}, path={request.path}", flush=True)
    
    try:
        # Get call details
        call_sid = request.form.get('CallSid', 'unknown')
        from_number = request.form.get('From', '')
        to_number = request.form.get('To', '')
        
        print(f"📞 CALL RECEIVED: {from_number} → {to_number} (SID: {call_sid})", flush=True)
        
        # Write to debug file  
        with open('/tmp/webhook_debug.log', 'a') as f:
            f.write(f"CALL: {call_sid} from {from_number} to {to_number}\n")
            f.flush()
        
        # Create WebSocket URL
        ws_host = "ai-crmd.replit.app"
        business_id = "1"  # Default to Shai Real Estate
        # Generate TwiML with greeting + WebSocket connection
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="en">Welcome to Shai Real Estate. Starting Hebrew conversation.</Say>
  <Connect action="/webhook/stream_ended">
    <Stream url="wss://{ws_host}/ws/twilio-media">
      <Parameter name="business_id" value="{business_id}"/>
      <Parameter name="from_number" value="{from_number}"/>
      <Parameter name="to_number" value="{to_number}"/>
      <Parameter name="call_sid" value="{call_sid}"/>
    </Stream>
  </Connect>
</Response>"""
        
        print(f"✅ TwiML generated for call {call_sid}", flush=True)
        
        # Final debug write
        with open('/tmp/webhook_debug.log', 'a') as f:
            f.write(f"SUCCESS: TwiML returned for {call_sid}\n")
            f.flush()
            
        return Response(xml, status=200, mimetype="text/xml")
        
    except Exception as e:
        print(f"❌ WEBHOOK ERROR: {e}")
        # Always return 200 to Twilio with basic TwiML + greeting
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="en">Welcome to Shai Real Estate. Technical issue, connecting now.</Say>
  <Connect action="/webhook/stream_ended">
    <Stream url="wss://ai-crmd.replit.app/ws/twilio-media">
      <Parameter name="business_id" value="1"/>
    </Stream>
  </Connect>
</Response>"""
        return Response(xml, status=200, mimetype="text/xml")

@twilio_bp.post("/webhook/stream_ended")
def stream_ended():
    """Stream ended - fallback to recording"""
    try:
        call_sid = request.form.get('CallSid', 'unknown')
        log.warning("Stream failover to recording", extra={"call_sid": call_sid, "mode": "record"})
        
        # Fallback TwiML with recording
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Record playBeep="false" timeout="4" maxLength="30" transcribe="false"
          action="/webhook/handle_recording" />
  <Say>Thank you. Processing your message.</Say>
</Response>"""
        return Response(xml, status=200, mimetype="text/xml")
        
    except Exception as e:
        log.error("Stream ended webhook failed: %s", e)
        # Fallback TwiML
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="woman">Technical difficulties. Please try again later.</Say>
    <Hangup/>
</Response>"""
        return Response(xml, status=200, mimetype="text/xml")

@twilio_bp.post("/webhook/handle_recording")
def handle_recording():
    """עיבוד הקלטה עברית - תמלול + תשובת AI בעברית"""
    def process_recording_async():
        """Process recording in background thread"""
        call_sid = "unknown"  # Initialize to avoid unbound error
        try:
            recording_url = request.form.get('RecordingUrl')
            call_sid = request.form.get('CallSid', 'unknown')
            
            if not recording_url:
                log.error("No recording URL provided", extra={"call_sid": call_sid})
                return
                
            # Download and process recording
            import requests
            import time
            start_time = time.time()
            
            response = requests.get(recording_url, timeout=10, stream=True)
            response.raise_for_status()
            
            audio_data = response.content
            log.info("Recording downloaded", extra={
                "call_sid": call_sid, 
                "size_bytes": len(audio_data),
                "download_ms": int((time.time() - start_time) * 1000)
            })
            
            # Transcribe with Whisper
            from server.services.whisper_handler import transcribe_he
            transcript = transcribe_he(audio_data, call_sid)
            
            if transcript:
                # Save to database
                from server.models_sql import CallLog
                from server.db import db
                call_log = CallLog.query.filter_by(call_sid=call_sid).first()
                if call_log:
                    call_log.transcript = transcript
                    db.session.commit()
                    log.info("Recording transcribed", extra={
                        "call_sid": call_sid,
                        "chars": len(transcript)
                    })
                    
        except Exception as e:
            log.error("Recording processing failed", extra={
                "call_sid": call_sid,
                "error": str(e)
            })
    
    # Start background processing
    thread = threading.Thread(target=process_recording_async)
    thread.daemon = True
    thread.start()
    
    # Return 204 immediately to Twilio
    return Response("", 204)

@twilio_bp.post("/webhook/call_status")
def call_status():
    """Call status webhook - quick response"""
    call_sid = request.form.get("CallSid", "")
    call_status = request.form.get("CallStatus", "")
    
    log.info("Call status: %s = %s", call_sid, call_status)
    
    return Response("OK", mimetype="text/plain", status=200)