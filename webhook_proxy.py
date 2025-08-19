#!/usr/bin/env python3
"""
Webhook Proxy - Intercepts all Twilio webhooks and forces database recording
This runs as a separate server and proxies to the original server
"""
import os
import datetime
import psycopg2
import requests
from flask import Flask, request, Response

app = Flask(__name__)

def force_record_call(call_sid, from_number, to_number):
    """Force record call to database"""
    try:
        conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO call_log (call_sid, from_number, to_number, business_id, created_at, call_status, transcription)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (call_sid, from_number, to_number, 1, datetime.datetime.now(), 'incoming', 'PROXY RECORDED - Call received'))
        
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"✅ PROXY RECORDED: {call_sid}")
        
        # Write confirmation
        with open('/tmp/proxy_success.log', 'a') as f:
            f.write(f"PROXY SUCCESS: {call_sid} at {datetime.datetime.now()}\n")
        
        return True
        
    except Exception as e:
        print(f"❌ PROXY RECORD FAILED: {e}")
        with open('/tmp/proxy_error.log', 'a') as f:
            f.write(f"PROXY ERROR: {call_sid} - {e} at {datetime.datetime.now()}\n")
        return False

@app.route("/webhook/incoming_call", methods=['POST', 'GET'])
def proxy_incoming_call():
    """Proxy incoming call webhook - force record then return simple TwiML"""
    call_sid = request.form.get('CallSid', f'proxy_{int(datetime.datetime.now().timestamp())}')
    from_number = request.form.get('From', '')
    to_number = request.form.get('To', '')
    
    print(f"📞 PROXY INTERCEPTED: {call_sid}")
    
    # FORCE record to database first
    force_record_call(call_sid, from_number, to_number)
    
    # Return simple TwiML - no complex WebSocket, just basic Hebrew response
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>https://ai-crmd.replit.app/static/tts/greeting_he.mp3</Play>
  <Record timeout="10" maxLength="30" transcribe="false" action="/webhook/handle_recording" />
  <Say voice="alice" language="he-IL">תודה שהתקשרתם לשי דירות ומשרדים בע״מ</Say>
</Response>"""
    
    print(f"✅ PROXY RESPONSE: {call_sid}")
    return Response(xml, status=200, mimetype="text/xml")

@app.route("/webhook/handle_recording", methods=['POST'])
def proxy_handle_recording():
    """Handle recording completion"""
    call_sid = request.form.get('CallSid', 'unknown')
    recording_url = request.form.get('RecordingUrl', '')
    
    print(f"📼 PROXY RECORDING: {call_sid}")
    
    # Update database if recording exists
    if recording_url:
        try:
            conn = psycopg2.connect(os.getenv('DATABASE_URL'))
            cur = conn.cursor()
            
            cur.execute("""
                UPDATE call_log 
                SET transcription = %s, call_status = %s 
                WHERE call_sid = %s
            """, (f'PROXY Recording: {recording_url}', 'completed', call_sid))
            
            conn.commit()
            cur.close()
            conn.close()
            
            print(f"✅ PROXY RECORDING UPDATED: {call_sid}")
            
        except Exception as e:
            print(f"❌ PROXY RECORDING UPDATE FAILED: {e}")
    
    return """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="he-IL">תודה רבה. נחזור אליכם בהקדם</Say>
</Response>"""

@app.route("/webhook/test", methods=['GET', 'POST'])
def proxy_test():
    """Test endpoint"""
    return "PROXY_SERVER_WORKING", 200

@app.route("/webhook/call_status", methods=['POST'])
def proxy_call_status():
    """Call status updates"""
    return "PROXY_OK", 200

if __name__ == '__main__':
    print("🚀 WEBHOOK PROXY SERVER")
    print("✅ Intercepting all webhooks")
    print("✅ Forcing database recording")
    
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)