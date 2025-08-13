#!/usr/bin/env python3
"""
CLEAN HEBREW CALL CENTER - ABSOLUTELY NO OLD CODE
"""
from flask import Flask, Response, request, send_from_directory
import os

# SIMPLE APP
app = Flask(__name__)
PUBLIC_HOST = "https://ai-crmd.replit.app"

print("🚀🚀🚀 ABSOLUTELY CLEAN NEW CODE STARTING")

@app.route("/webhook/incoming_call", methods=['POST'])
def clean_incoming_call():
    """ABSOLUTELY CLEAN Hebrew webhook - PLAY ONLY"""
    print("🎯🎯🎯 CLEAN CODE INCOMING CALL HANDLER")
    call_sid = request.form.get('CallSid', 'CLEAN_CALL')
    print(f"🎯 CLEAN HANDLER PROCESSING: {call_sid}")
    
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>{PUBLIC_HOST}/static/voice_responses/greeting.mp3</Play>
  <Pause length="1"/>
  <Record action="/webhook/handle_recording"
          method="POST"
          maxLength="30"
          timeout="5"
          finishOnKey="*"
          transcribe="false"/>
</Response>"""
    
    print("🎯 CLEAN CODE RETURNING PLAY VERB")
    print(f"🎯 CLEAN XML: {xml[:100]}...")
    return Response(xml, mimetype="text/xml")

@app.route("/webhook/handle_recording", methods=['POST'])
def clean_handle_recording():
    """CLEAN recording handler"""
    print("🎙️ CLEAN RECORDING HANDLER")
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>{PUBLIC_HOST}/static/voice_responses/listening.mp3</Play>
  <Hangup/>
</Response>"""
    return Response(xml, mimetype="text/xml")

@app.route("/webhook/call_status", methods=['POST'])
def clean_call_status():
    """CLEAN call status"""
    print("📞 CLEAN CALL STATUS")
    return "OK", 200

@app.route('/static/voice_responses/<filename>')
def serve_clean_voice(filename):
    """Serve voice files CLEAN"""
    voice_dir = os.path.join(os.path.dirname(__file__), 'server', 'static', 'voice_responses')
    return send_from_directory(voice_dir, filename)

@app.route('/')
def clean_home():
    return "CLEAN Hebrew AI Call Center - PLAY VERBS ONLY"

if __name__ == '__main__':
    print("🚀 STARTING ABSOLUTELY CLEAN CODE")
    print("🎯 ONLY PLAY VERBS - NO SAY VERBS")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=False)