#!/usr/bin/env python3
"""
Simple Stable Flask Server for Hebrew AI Call Center
Minimal dependencies, maximum stability
"""
import os
import datetime
import psycopg2
from flask import Flask, request, Response

app = Flask(__name__)

@app.route("/webhook/test", methods=['GET', 'POST'])
def test_endpoint():
    print("🧪 TEST ENDPOINT HIT!")
    return "TEST OK", 200

@app.route("/webhook/incoming_call", methods=['POST', 'GET'])
def incoming_call():
    """Simple incoming call handler with database logging"""
    try:
        # Get call details
        call_sid = request.form.get('CallSid', f'simple_{datetime.datetime.now().timestamp()}')
        from_number = request.form.get('From', '')
        to_number = request.form.get('To', '')
        business_id = 1
        
        print(f"📞 CALL: {from_number} → {to_number} (SID: {call_sid})")
        
        # Record to database
        try:
            conn = psycopg2.connect(os.getenv('DATABASE_URL'))
            cur = conn.cursor()
            
            cur.execute("""
                INSERT INTO call_log (call_sid, from_number, to_number, business_id, created_at, call_status)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (call_sid, from_number, to_number, business_id, datetime.datetime.now(), 'incoming'))
            
            conn.commit()
            cur.close()
            conn.close()
            
            print(f"✅ CALL RECORDED: {call_sid}")
            
        except Exception as db_error:
            print(f"❌ Database error: {db_error}")
        
        # Return simple TwiML with Hebrew greeting
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>https://ai-crmd.replit.app/static/tts/greeting_he.mp3</Play>
  <Record playBeep="false" timeout="10" maxLength="30" transcribe="false" action="/webhook/handle_recording" />
  <Say voice="alice" language="he-IL">תודה שהתקשרתם לשי דירות ומשרדים</Say>
</Response>"""
        
        return Response(xml, status=200, mimetype="text/xml")
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        # Fallback TwiML
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="he-IL">שלום, תודה שהתקשרתם</Say>
</Response>"""
        return Response(xml, status=200, mimetype="text/xml")

@app.route("/webhook/handle_recording", methods=['POST'])
def handle_recording():
    """Handle recording for simple test"""
    return """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="he-IL">תודה. השיחה הסתיימה</Say>
</Response>"""

if __name__ == '__main__':
    print("🚀 Simple Hebrew AI Server Starting...")
    app.run(host='0.0.0.0', port=5000, debug=False)