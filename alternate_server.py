#!/usr/bin/env python3
"""
Alternate Server on port 8080 - bypasses existing deployment
Direct database recording without complex architecture
"""
import os
import datetime
import psycopg2
from flask import Flask, request, Response

app = Flask(__name__)

@app.route("/")
def home():
    return "ALTERNATE_SERVER_RUNNING", 200

@app.route("/webhook/test")
def test():
    return "ALTERNATE_TEST_OK", 200

@app.route("/webhook/incoming_call", methods=['POST', 'GET'])
def incoming_call():
    """Direct database recording - no complex architecture"""
    call_sid = request.form.get('CallSid', f'alt_{int(datetime.datetime.now().timestamp())}')
    from_number = request.form.get('From', '')
    to_number = request.form.get('To', '')
    
    print(f"🎯 ALTERNATE SERVER: {call_sid}")
    
    # Direct database insert
    try:
        conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO call_log (call_sid, from_number, to_number, business_id, created_at, call_status, transcription)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (call_sid, from_number, to_number, 1, datetime.datetime.now(), 'incoming', 'ALTERNATE SERVER - Call recorded'))
        
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"✅ ALTERNATE DB SUCCESS: {call_sid}")
        
        # Write to file
        with open('/tmp/alternate_success.log', 'a') as f:
            f.write(f"ALT SUCCESS: {call_sid} at {datetime.datetime.now()}\n")
        
        # Return simple Hebrew TwiML
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="he-IL">שלום, התקשרתם לשי דירות ומשרדים</Say>
  <Record timeout="10" maxLength="20" />
  <Say voice="alice" language="he-IL">תודה רבה</Say>
</Response>"""
        
        return Response(xml, status=200, mimetype="text/xml")
        
    except Exception as e:
        print(f"❌ ALTERNATE DB ERROR: {e}")
        
        with open('/tmp/alternate_error.log', 'a') as f:
            f.write(f"ALT ERROR: {call_sid} - {e} at {datetime.datetime.now()}\n")
        
        # Return basic fallback
        return Response("""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="he-IL">שגיאה במערכת</Say>
</Response>""", status=200, mimetype="text/xml")

if __name__ == '__main__':
    print("🚀 ALTERNATE SERVER - PORT 8080")
    print("✅ Bypassing port 5000 deployment")
    app.run(host='0.0.0.0', port=8080, debug=False)