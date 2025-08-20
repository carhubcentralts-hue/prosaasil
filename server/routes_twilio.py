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
from server.twilio_security import require_twilio_signature

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
    """יצירת URL מוחלט עבור Twilio webhooks - PRODUCTION READY"""
    # Always use external domain for Twilio - never localhost!
    host = os.getenv("PUBLIC_HOST", "https://ai-crmd.replit.app")
    
    # Clean up host URL
    host = host.rstrip("/")
    if not host.startswith('http'):
        host = f"https://{host}"
    
    # Ensure no double slashes
    path = path.lstrip("/")
    return f"{host}/{path}"

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
@require_twilio_signature  # 5) אבטחת Webhooks - PRODUCTION READY
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
        
        # 2) TwiML עם URLs מוחלטים (סוגר 11100 "Invalid Play URL") - PRODUCTION READY
        greeting_url = abs_url("/static/tts/greeting_he.mp3")  # Use global abs_url function
        
        # Use external domain for WebSocket - never localhost!
        host = os.getenv("PUBLIC_HOST", "https://ai-crmd.replit.app")
        wss_host = host.replace("https://","").replace("http://","").strip("/")
        business_id = 1  # Default to Shai Real Estate
        
        print(f"🎯 Using absolute greeting URL: {greeting_url}", flush=True)
        print(f"🔗 WebSocket URL: wss://{wss_host}/ws/twilio-media", flush=True)
        
        # RAW WEBSOCKET - Real-time Hebrew conversation (NO Socket.IO!)
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>{greeting_url}</Play>
  <Connect action="/webhook/stream_ended">
    <Stream url="wss://{wss_host}/ws/twilio-media">
      <Parameter name="call_sid" value="{call_sid}"/>
    </Stream>
  </Connect>
</Response>"""
        
        print(f"✅ TwiML generated for call {call_sid}", flush=True)
        
        # Final debug write
        with open('/tmp/webhook_debug.log', 'a') as f:
            f.write(f"SUCCESS: TwiML returned for {call_sid}\n")
            f.flush()
            
        # START WATCHDOG - monitor RAW WebSocket and fallback if needed
        watchdog_thread = threading.Thread(target=_watchdog, args=(call_sid, wss_host), daemon=True)
        watchdog_thread.start()
        print(f"🐕 WATCHDOG: Thread STARTED for {call_sid} (RAW WebSocket)", flush=True)
        print(f"🐕 WATCHDOG: Will monitor RAW WebSocket for 8 seconds", flush=True)
            
        return Response(xml, status=200, mimetype="text/xml")
        
    except Exception as e:
        print(f"❌ WEBHOOK ERROR: {e}")
        # Always return 200 to Twilio with WebSocket Media Stream fallback
        # Dynamic host resolution - no hardcoded addresses
        host = os.getenv("PUBLIC_HOST") or os.getenv("PUBLIC_BASE_URL") or request.url_root.rstrip("/") or f"https://{request.host}"
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
@require_twilio_signature  # אבטחת Webhooks
def stream_ended():
    """Stream ended - fallback to recording"""
    try:
        call_sid = request.form.get('CallSid', 'unknown')
        log.warning("Stream failover to recording", extra={"call_sid": call_sid, "mode": "record"})
        
        # Fallback TwiML with recording - RECORD FIRST! (Production URLs)
        host = os.getenv("PUBLIC_HOST", "https://ai-crmd.replit.app")
        fallback_url = f"{host}/static/tts/fallback_he.mp3"
        recording_action = f"{host}/webhook/handle_recording"
        
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Record playBeep="false" timeout="8" maxLength="30" transcribe="false"
          action="{recording_action}" />
  <Play>{fallback_url}</Play>
  <Hangup/>
</Response>"""
        return Response(xml, status=200, mimetype="text/xml")
        
    except Exception as e:
        log.error("Stream ended webhook failed: %s", e)
        # Fallback TwiML - Hebrew (Dynamic URL)
        def abs_url(path: str) -> str:
            base = os.getenv("PUBLIC_BASE_URL") or request.url_root.rstrip("/")
            return f"{base}{path}"
        
        fallback_url = abs_url("/static/tts/fallback_he.mp3")
        
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{fallback_url}</Play>
    <Hangup/>
</Response>"""
        return Response(xml, status=200, mimetype="text/xml")

@twilio_bp.post("/webhook/handle_recording")
@require_twilio_signature  # אבטחת Webhooks
def handle_recording():
    """עיבוד הקלטה עברית - תמלול + תשובת AI בעברית"""
    recording_url = request.form.get('RecordingUrl')
    call_sid = request.form.get('CallSid', 'unknown')
    from_number = request.form.get('From', 'unknown')
    
    print(f"📹 RECORDING RECEIVED: {call_sid} -> {recording_url}")
    
    def process_recording_async():
        """Process recording in background thread"""
        try:
            if not recording_url:
                print(f"❌ No recording URL for {call_sid}")
                return
                
            print(f"🎤 PROCESSING: {recording_url}")
            
            # Download and process recording
            import requests
            import tempfile
            import os
            from openai import OpenAI
            
            response = requests.get(recording_url, timeout=30)
            if response.status_code != 200:
                print(f"❌ Failed to download recording: {response.status_code}")
                return
                
            print(f"📁 Downloaded: {len(response.content)} bytes")
            
            # Save to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_file:
                temp_file.write(response.content)
                temp_path = temp_file.name
                
            print(f"💾 Temp file: {temp_path}")
            
            try:
                # Transcribe with Whisper
                client = OpenAI()
                with open(temp_path, "rb") as audio_file:
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language="he"  # Hebrew language
                    )
                    
                transcription = transcript.text.strip()
                print(f"🎤 TRANSCRIPTION: '{transcription}' ({len(transcription)} chars)")
                
                if transcription and len(transcription) > 2:
                    # Generate AI response
                    print(f"🤖 Generating AI response...")
                    _generate_ai_response_recording(transcription, call_sid, from_number)
                else:
                    print(f"⚠️ Transcription too short: '{transcription}'")
                    
            except Exception as e:
                print(f"❌ WHISPER ERROR: {e}")
                import traceback
                traceback.print_exc()
            finally:
                # Clean up
                try:
                    os.unlink(temp_path)
                    print(f"🗑️ Cleaned temp file")
                except:
                    pass
                    
        except Exception as e:
            print(f"❌ RECORDING PROCESSING ERROR: {e}")
            import traceback
            traceback.print_exc()

    # Start background processing
    import threading
    thread = threading.Thread(target=process_recording_async)
    thread.daemon = True
    thread.start()
    
    # Return 200 immediately to Twilio
    return Response("", 200)

def _generate_ai_response_recording(transcription, call_sid, from_number):
    """Generate AI response for recording"""
    try:
        from openai import OpenAI
        
        client = OpenAI()
        
        print(f"🤖 Generating AI response for: '{transcription}'")
        
        response = client.chat.completions.create(
            model="gpt-4o",  # the newest OpenAI model is "gpt-4o" which was released May 13, 2024
            messages=[
                {"role": "system", "content": "אתה עוזר וירטואלי של 'שי דירות ומשרדים בע״מ' - חברת נדל״ן מובילה. ענה בעברית בצורה מקצועית, עוזרת וידידותית. התמחה בנושאי דירות, משרדים, השכרות ומכירות בישראל."},
                {"role": "user", "content": transcription}
            ]
        )
        
        ai_response = response.choices[0].message.content
        print(f"🤖 AI RESPONSE: '{ai_response}'")
        
        # Log the complete interaction
        print(f"💾 INTERACTION COMPLETE:")
        print(f"   Call: {call_sid}")
        print(f"   From: {from_number}")
        print(f"   Customer: '{transcription}'")
        print(f"   AI: '{ai_response}'")
        
        return ai_response
        
    except Exception as e:
        print(f"❌ AI RESPONSE ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None
    
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
        
        # Build absolute URLs properly
        if not host.startswith(('http://', 'https://')):
            host = f"https://{host}"
        
        fallback_url = f"{host}/static/tts/fallback_he.mp3"
        recording_action = f"{host}/webhook/handle_recording"
        
        # TwiML Fallback - RECORD FIRST, then play message
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Record playBeep="false" timeout="8" maxLength="30" transcribe="false"
          action="{recording_action}" />
  <Play>{fallback_url}</Play>
  <Hangup/>
</Response>"""
        
        print(f"📞 WATCHDOG: Attempting Twilio REST redirect for {call_sid}", flush=True)
        client.calls(call_sid).update(twiml=twiml)
        print(f"✅ WATCHDOG: Successfully redirected {call_sid} to Record fallback!", flush=True)
        
    except Exception as e:
        print(f"❌ WATCHDOG: Failed to redirect {call_sid}: {e}", flush=True)
        import traceback
        traceback.print_exc()

def _watchdog(call_sid, wss_host, start_timeout=8, no_media_timeout=6):
    """Watch WebSocket stream and redirect to Record if needed - CANONICAL VERSION"""
    try:
        print(f"🐕 WATCHDOG: Started monitoring {call_sid} (wait {start_timeout}s)", flush=True)
        
        # Wait for stream to start
        time.sleep(start_timeout)
        
        # Import here to avoid circular imports
        from server.stream_state import stream_registry
        st = stream_registry.get(call_sid)
        
        print(f"🐕 WATCHDOG: After {start_timeout}s, stream state: {st}", flush=True)
        
        # Check if stream started
        if not st.get("started"):
            print(f"⚠️ WATCHDOG: No WebSocket stream for {call_sid} - redirecting to Record!", flush=True)
            _do_redirect(call_sid, wss_host, reason="no_stream_start")
            return

        # Check if there's media activity
        last = st.get("last_media_at", 0)
        current_time = time.time()
        
        print(f"🐕 WATCHDOG: Media check - last: {last}, current: {current_time}, diff: {current_time - last}", flush=True)
        
        if current_time - last > no_media_timeout:
            print(f"⚠️ WATCHDOG: No media activity for {call_sid} - redirecting to Record!", flush=True) 
            _do_redirect(call_sid, wss_host, reason="no_media")
            return
            
        print(f"✅ WATCHDOG: Stream healthy for {call_sid} - no intervention needed", flush=True)
        
    except Exception as e:
        print(f"❌ WATCHDOG: Critical error monitoring {call_sid}: {e}", flush=True)
        import traceback
        traceback.print_exc()

def _do_redirect(call_sid, wss_host, reason):
    """Execute the redirect to Record fallback"""
    from twilio.rest import Client
    
    try:
        current_app.logger.warning("WATCHDOG_REDIRECT", extra={"call_sid": call_sid, "reason": reason})
        
        account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
        auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
        
        if not account_sid or not auth_token:
            print(f"❌ WATCHDOG: Cannot redirect {call_sid} - missing Twilio credentials!", flush=True)
            return
            
        client = Client(account_sid, auth_token)
        
        # CANONICAL TwiML: Record FIRST, then Play, then Hangup (Dynamic URLs)
        twiml = f"""<Response>
  <Record playBeep="false" timeout="8" maxLength="30" transcribe="false"
          action="https://{wss_host}/webhook/handle_recording" />
  <Play>https://{wss_host}/static/tts/fallback_he.mp3</Play>
  <Hangup/>
</Response>"""

        client.calls(call_sid).update(twiml=twiml)
        print(f"✅ WATCHDOG: Successfully redirected {call_sid} to Record fallback!", flush=True)
        
    except Exception as e:
        print(f"❌ WATCHDOG: Failed to redirect {call_sid}: {e}", flush=True)
        import traceback
        traceback.print_exc()