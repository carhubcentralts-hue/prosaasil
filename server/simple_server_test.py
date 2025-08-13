#!/usr/bin/env python3
"""
Simple server test to verify everything works
בדיקה פשוטה של השרת
"""

from flask import Flask, request, Response
import os

app = Flask(__name__)

@app.route('/webhook/incoming_call', methods=['POST'])
def test_incoming():
    """Test professional incoming call"""
    call_sid = request.values.get('CallSid', 'test')
    
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="he-IL" rate="0.9">
    שלום, הגעתם לשי דירות ומשרדים. אני העוזרת הדיגיטלית.
    אשמח לעזור לכם עם כל שאלה בנושא נדלן.
  </Say>
  <Record action="/webhook/conversation_turn"
          method="POST"
          maxLength="30"/>
</Response>"""
    
    print(f"📞 Test call: {call_sid}")
    return Response(xml, mimetype="text/xml")

@app.route('/webhook/conversation_turn', methods=['POST'])
def test_conversation():
    """Test conversation turn"""
    call_sid = request.values.get('CallSid', 'test')
    
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="he-IL" rate="0.9">
    אני בודקת את מה שאמרתם. רגע אחד בבקשה.
  </Say>
  <Record action="/webhook/conversation_turn"
          method="POST"
          maxLength="30"/>
</Response>"""
    
    print(f"🎤 Test conversation: {call_sid}")
    return Response(xml, mimetype="text/xml")

@app.route('/')
def test_home():
    return "✅ Test server is running"

if __name__ == '__main__':
    print("🧪 Starting simple test server...")
    app.run(host='0.0.0.0', port=5000, debug=False)