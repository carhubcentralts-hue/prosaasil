#!/usr/bin/env python3
"""
Hebrew AI Call Center CRM - Simple Stable Version
Fixed for database recording and Hebrew responses
"""
import os
import datetime
import psycopg2
from flask import Flask, request, Response

# FORCE IMPORT DB RECORDING
try:
    from force_db_recording import force_record_call
    print("✅ FORCE DB RECORDING LOADED")
except ImportError:
    print("⚠️ Force DB recording not available")
    def force_record_call():
        return False

app = Flask(__name__)

@app.route("/webhook/test", methods=['GET', 'POST'])
def test_endpoint():
    print("🧪 TEST ENDPOINT HIT!")
    return "UPDATED_CODE_LOADED", 200

@app.route("/webhook/force_test", methods=['GET', 'POST'])
def force_test_endpoint():
    """New endpoint to verify updated code is loaded"""
    print("🎯 FORCE TEST - NEW CODE LOADED!")
    
    # Test database connection
    try:
        conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM call_log")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return f"NEW_CODE_WITH_DB_ACCESS_WORKS_{count}", 200
    except Exception as e:
        return f"NEW_CODE_DB_FAILED_{e}", 500

@app.route("/webhook/incoming_call", methods=['POST', 'GET'])  
def incoming_call():
    """Fixed incoming call handler - records to database"""
    try:
        # FORCE DB RECORDING FIRST
        print("🎯 EXECUTING FORCE DB RECORDING...")
        force_success = force_record_call()
        
        # Get call details
        call_sid = request.form.get('CallSid', f'call_{int(datetime.datetime.now().timestamp())}')
        from_number = request.form.get('From', '')
        to_number = request.form.get('To', '')
        business_id = 1
        
        print(f"📞 INCOMING CALL: {from_number} → {to_number} (SID: {call_sid})")
        if force_success:
            print(f"✅ FORCE DB RECORDING SUCCESS for {call_sid}")
        else:
            print(f"❌ FORCE DB RECORDING FAILED for {call_sid}")
        
        # Record to database FIRST
        try:
            conn = psycopg2.connect(os.getenv('DATABASE_URL'))
            cur = conn.cursor()
            
            cur.execute("""
                INSERT INTO call_log (call_sid, from_number, to_number, business_id, created_at, call_status, transcription)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (call_sid, from_number, to_number, business_id, datetime.datetime.now(), 'incoming', 'New call received'))
            
            conn.commit()
            cur.close()
            conn.close()
            
            print(f"✅ CALL RECORDED TO DATABASE: {call_sid}")
            
        except Exception as db_error:
            print(f"❌ Database error: {db_error}")
        
        # Return Hebrew TwiML with recording for transcription  
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>https://ai-crmd.replit.app/static/tts/greeting_he.mp3</Play>
  <Record playBeep="false" timeout="10" maxLength="30" transcribe="false" action="/webhook/handle_recording" />
  <Say voice="alice" language="he-IL">תודה שהתקשרתם לשי דירות ומשרדים בע״מ</Say>
</Response>"""
        
        return Response(xml, status=200, mimetype="text/xml")
        
    except Exception as e:
        print(f"❌ WEBHOOK ERROR: {e}")
        # Hebrew fallback
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="he-IL">שלום ותודה שהתקשרתם</Say>  
</Response>"""
        return Response(xml, status=200, mimetype="text/xml")

@app.route("/webhook/handle_recording", methods=['POST'])
def handle_recording():
    """Handle recording completion"""
    call_sid = request.form.get('CallSid', 'unknown')
    recording_url = request.form.get('RecordingUrl', '')
    
    print(f"📼 Recording completed for call {call_sid}")
    
    # Update database with recording
    if recording_url:
        try:
            conn = psycopg2.connect(os.getenv('DATABASE_URL'))
            cur = conn.cursor()
            
            cur.execute("""
                UPDATE call_log 
                SET transcription = %s, call_status = %s 
                WHERE call_sid = %s
            """, (f'Recording: {recording_url}', 'completed', call_sid))
            
            conn.commit()
            cur.close()
            conn.close()
            
            print(f"✅ Recording updated for {call_sid}")
            
        except Exception as e:
            print(f"❌ Recording update error: {e}")
    
    return """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="he-IL">תודה רבה. נחזור אליכם בהקדם</Say>
</Response>"""

@app.route("/webhook/stream_ended", methods=['POST'])
def stream_ended():
    """Stream ended handler"""  
    return """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="he-IL">השיחה הסתיימה</Say>
</Response>"""

@app.route("/webhook/call_status", methods=['POST'])
def call_status():
    """Call status updates"""
    return "OK", 200

if __name__ == '__main__':
    print("🚀 Hebrew AI Call Center - Fixed Version")
    print("✅ Database recording enabled")
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)