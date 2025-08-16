# routes_twilio.py - FIXED VERSION
import threading
from flask import Blueprint, request, Response, current_app
from urllib.parse import urljoin
from server.twilio_security import require_twilio_signature
import os, logging

def _mask_phone(phone):
    """Mask phone number for logging privacy"""
    if not phone or len(phone) < 4:
        return phone
    return phone[:3] + "****" + phone[-2:]

twilio_bp = Blueprint("twilio_bp_v2", __name__, url_prefix="")
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

@twilio_bp.route("/webhook/incoming_call", methods=['POST'])
def incoming_call():
    """
    Twilio webhook for incoming calls - Real-time Hebrew AI conversation
    Returns TwiML to start Media Stream for live audio processing ONLY
    """
    try:
        # IMMEDIATE debug log - before anything else
        with open('/tmp/webhook_debug.log', 'a') as f:
            f.write(f"=== WEBHOOK ENTRY POINT HIT ===\n")
            
        print("=== WEBHOOK ENTRY POINT HIT ===")
        
        # Get call details
        call_sid = request.form.get('CallSid', 'unknown')
        from_number = request.form.get('From', '')
        to_number = request.form.get('To', '')
        
        # Get public host - use correct domain
        host = "https://ai-crmd.replit.app"
        ws_host = host.replace('https://', '').replace('http://', '')
        
        log.info("📞 INCOMING CALL: %s → %s (SID: %s)", from_number, to_number, call_sid)
        print(f"🔥🔥🔥 WEBHOOK HIT: Call {call_sid} from {from_number} to {to_number}")
        print(f"🎯 TwiML will connect to: wss://{ws_host}/ws/twilio-media")
        
        # Force logging to see if we get here at all
        with open('/tmp/webhook_debug.log', 'a') as f:
            f.write(f"WEBHOOK CALLED: {call_sid} from {from_number} to {to_number}\n")
        log.info("Using host: %s", host)
        
        # Find business by phone number
        business_id = "1"  # Default to Shai Real Estate
        
        # For Shai Real Estate: +972 3 376 3805 / +972-50-123-4567
        if to_number in ["+972337636805", "+972501234567", "+97233763805"]:
            business_id = "1"
            log.info("📞 Identified business: Shai Real Estate for %s", to_number)
        
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Connect action="/webhook/stream_ended">
    <Stream url="wss://{ws_host}/ws/twilio-media">
      <Parameter name="business_id" value="{business_id}"/>
    </Stream>
  </Connect>
</Response>"""
        
        log.info("TwiML generated", extra={
            "call_sid": call_sid,
            "host": host,
            "ws_url": f"wss://{ws_host}/ws/twilio-media"
        })
        
        return Response(xml, status=200, mimetype="text/xml")
        
    except Exception as e:
        log.error("Incoming call webhook failed: %s", e)
        return Response("", 200)  # Always 200 for Twilio

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
  <Say language="he-IL">תודה. מעבד את הודעתך וחוזר מיד.</Say>
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