# routes_twilio.py - DEBUG VERSION
import threading
import time
import os
import datetime
import logging
import psycopg2
from flask import Blueprint, request, Response, current_app
from urllib.parse import urljoin
from twilio.rest import Client
from server.stream_state import stream_registry

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

def generate_business_greeting(business_id=1):
    """Generate dynamic Hebrew greeting based on business prompt"""
    try:
        import openai
        
        # Set OpenAI client
        client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # Business-specific prompts
        business_prompts = {
            1: """אתה מומחה נדל"ן ישראלי של חברת "שי דירות ומשרדים בע״מ". 
                  החברה מתמחה במכירת דירות ומשרדים איכותיים באזור המרכז. 
                  אתה מקצועי, ידידותי ומסייע למציאת הנכס המושלם.""",
            # Add more businesses here as needed
        }
        
        prompt = business_prompts.get(business_id, business_prompts[1])
        
        # Generate greeting using OpenAI
        response = client.chat.completions.create(
            model="gpt-4o",  # the newest OpenAI model is "gpt-4o" which was released May 13, 2024. do not change this unless explicitly requested by the user
            messages=[
                {"role": "system", "content": f"{prompt}\n\nצור ברכת פתיחה קצרה (10-15 מילים) לשיחת טלפון נכנסת. תשובה רק בעברית, פשוטה ומקצועית."},
                {"role": "user", "content": "צור ברכת פתיחה לשיחה"}
            ],
            max_tokens=50,
            temperature=0.7
        )
        
        content = response.choices[0].message.content
        generated_greeting = content.strip() if content else ""
        
        # Fallback to default if generation fails
        if not generated_greeting or len(generated_greeting) < 5:
            return "שלום, ברוכים הבאים לשי דירות ומשרדים בע״מ. איך אוכל לעזור לכם?"
            
        return generated_greeting
        
    except Exception as e:
        print(f"❌ Error generating greeting: {e}")
        # Fallback greeting
        return "שלום, ברוכים הבאים לשי דירות ומשרדים בע״מ. איך אוכל לעזור לכם?"

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
        
        # ✅ CRITICAL: RECORD CALL TO DATABASE IMMEDIATELY
        try:
            import psycopg2
            import datetime
            
            conn = psycopg2.connect(os.getenv('DATABASE_URL'))
            cur = conn.cursor()
            
            # Insert call record
            cur.execute("""
                INSERT INTO call_log (call_sid, from_number, to_number, business_id, created_at, call_status, transcription)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (call_sid, from_number, to_number, 1, datetime.datetime.now(), 'incoming', 'Live call started'))
            
            conn.commit()
            cur.close()
            conn.close()
            
            print(f"✅ CALL RECORDED TO DATABASE: {call_sid}", flush=True)
            
        except Exception as db_error:
            print(f"❌ Database error: {db_error}", flush=True)
        
        # Write to debug file  
        with open('/tmp/webhook_debug.log', 'a') as f:
            f.write(f"CALL: {call_sid} from {from_number} to {to_number}\n")
            f.flush()
        
        # Create WebSocket URL - DYNAMIC HOST (תיקון 31920)
        host = os.getenv("PUBLIC_HOST") or request.host
        if not host.startswith('http'):
            host = f"https://{host}" if 'replit.app' in host else f"http://{host}"
        host = host.rstrip('/')  # Remove trailing slash to prevent double slash
        ws_host = host.replace('https://', '').replace('http://', '')
        business_id = 1  # Default to Shai Real Estate
        
        # Use static Hebrew greeting to avoid OpenAI delay in webhook
        # Dynamic greeting moved to Media Stream for faster response
        greeting_url = f"{host}/static/tts/greeting_he.mp3"
        print(f"🎯 Using static greeting: {greeting_url}", flush=True)
        
        # SOCKETIO WEBSOCKET - Real-time Hebrew conversation restored!
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>{greeting_url}</Play>
  <Connect action="/webhook/stream_ended">
    <Stream url="wss://{ws_host}/socket.io/?EIO=4&transport=websocket&path=/twilio-media">
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
            
        # START WATCHDOG - monitor SocketIO WebSocket and fallback if needed
        watchdog_thread = threading.Thread(target=_watchdog, args=(call_sid, host), daemon=True)
        watchdog_thread.start()
        print(f"🐕 WATCHDOG: Thread STARTED for {call_sid} (SocketIO)", flush=True)
        print(f"🐕 WATCHDOG: Will monitor SocketIO WebSocket for 3 seconds", flush=True)
            
        return Response(xml, status=200, mimetype="text/xml")
        
    except Exception as e:
        print(f"❌ WEBHOOK ERROR: {e}")
        # Always return 200 to Twilio with WebSocket Media Stream fallback
        host = os.getenv("PUBLIC_HOST", "ai-crmd.replit.app")
        if not host.startswith('http'):
            host = f"https://{host}" if 'replit.app' in host else f"http://{host}"
        host = host.rstrip('/')  # Remove trailing slash to prevent double slash
        ws_host = host.replace('https://', '').replace('http://', '')
        
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>{host}/static/tts/fallback_he.mp3</Play>
  <Connect action="/webhook/stream_ended">
    <Stream url="wss://{ws_host}/ws/twilio-media">
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
  <Play>https://ai-crmd.replit.app/static/tts/fallback_he.mp3</Play>
</Response>"""
        return Response(xml, status=200, mimetype="text/xml")
        
    except Exception as e:
        log.error("Stream ended webhook failed: %s", e)
        # Fallback TwiML - Hebrew
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>https://ai-crmd.replit.app/static/tts/fallback_he.mp3</Play>
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

# WATCHDOG SYSTEM - FIXES "SILENCE AFTER GREETING" ISSUE
def _redirect_to_record(call_sid, host):
    """Force Twilio to redirect call to Record if WebSocket fails"""
    try:
        account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
        auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
        
        print(f"🔐 WATCHDOG: Checking credentials for {call_sid}", flush=True)
        print(f"🔐 TWILIO_ACCOUNT_SID: {'present' if account_sid else 'MISSING'}", flush=True)
        print(f"🔐 TWILIO_AUTH_TOKEN: {'present' if auth_token else 'MISSING'}", flush=True)
        
        if not account_sid or not auth_token:
            print(f"❌ WATCHDOG: Cannot redirect {call_sid} - missing Twilio credentials in deployment!", flush=True)
            return
            
        client = Client(account_sid, auth_token)
        
        # Clean host URL for TwiML  
        clean_host = host.replace('https://', '').replace('http://', '')
        
        # TwiML Fallback direct (not dependent on stream_ended) - IMMEDIATE RECORD
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="he-IL">אנא השאירו הודעה קצרה. ההודעה תתמלל ונישמר במערכת.</Say>
  <Record playBeep="true" timeout="10" maxLength="60" transcribe="false"
          action="/webhook/handle_recording" />
</Response>"""
        
        print(f"📞 WATCHDOG: Attempting Twilio REST redirect for {call_sid}", flush=True)
        client.calls(call_sid).update(twiml=twiml)
        print(f"✅ WATCHDOG: Successfully redirected {call_sid} to Record fallback!", flush=True)
        
    except Exception as e:
        print(f"❌ WATCHDOG: Failed to redirect {call_sid}: {e}", flush=True)
        import traceback
        traceback.print_exc()

def _watchdog(call_sid, host, start_timeout=3, no_media_timeout=2):
    """Watch WebSocket stream and redirect to Record if needed - ENHANCED VERSION"""
    try:
        print(f"🐕 WATCHDOG: Started monitoring {call_sid} (wait {start_timeout}s)", flush=True)
        
        # Wait for stream to start
        time.sleep(start_timeout)
        st = stream_registry.get(call_sid)
        
        print(f"🐕 WATCHDOG: After {start_timeout}s, stream state: {st}", flush=True)
        
        if not st.get("started"):
            print(f"⚠️ WATCHDOG: No WebSocket stream for {call_sid} - redirecting to Record!", flush=True)
            _redirect_to_record(call_sid, host)
            return

        # Check if there's media activity
        last = st.get("last_media_at", 0)
        current_time = time.time()
        
        print(f"🐕 WATCHDOG: Media check - last: {last}, current: {current_time}, diff: {current_time - last}", flush=True)
        
        if current_time - last > no_media_timeout:
            print(f"⚠️ WATCHDOG: No media activity for {call_sid} - redirecting to Record!", flush=True) 
            _redirect_to_record(call_sid, host)
            return
            
        print(f"✅ WATCHDOG: Stream healthy for {call_sid} - no intervention needed", flush=True)
        
    except Exception as e:
        print(f"❌ WATCHDOG: Critical error monitoring {call_sid}: {e}", flush=True)
        import traceback
        traceback.print_exc()