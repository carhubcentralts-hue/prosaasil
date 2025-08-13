#!/usr/bin/env python3
"""
HEBREW AI CALL CENTER - FINAL DIRECT VERSION
NO App Factory, NO Blueprint, DIRECT ROUTES ONLY
"""
import os
from flask import Flask, Response, request, send_from_directory

# Create simple Flask app
app = Flask(__name__)

# PUBLIC HOST
PUBLIC_HOST = "https://ai-crmd.replit.app"

@app.route("/webhook/incoming_call", methods=['POST'])
def incoming_call_hebrew():
    """DIRECT Hebrew webhook - Play verb only"""
    call_sid = request.form.get('CallSid', 'TEST')
    print(f"🎯 NEW INCOMING CALL: {call_sid}")
    
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
    
    print(f"✅ RETURNING PLAY VERB: {PUBLIC_HOST}/static/voice_responses/greeting.mp3")
    return Response(xml, mimetype="text/xml")

@app.route("/webhook/handle_recording", methods=['POST'])
def handle_recording_hebrew():
    """Handle recording - Play verb only"""
    call_sid = request.form.get('CallSid', 'TEST')
    print(f"🎙️ RECORDING: {call_sid}")
    
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>{PUBLIC_HOST}/static/voice_responses/listening.mp3</Play>
  <Hangup/>
</Response>"""
    
    return Response(xml, mimetype="text/xml")

@app.route("/webhook/call_status", methods=['POST'])
def call_status_webhook():
    """Call status - always return 200"""
    return "OK", 200

@app.route('/static/voice_responses/<filename>')
def serve_voice_files(filename):
    """Serve Hebrew voice files"""
    voice_dir = os.path.join(os.path.dirname(__file__), 'server', 'static', 'voice_responses')
    print(f"🎵 Serving voice file: {filename} from {voice_dir}")
    return send_from_directory(voice_dir, filename)

@app.route('/')
def home():
    return "Hebrew AI Call Center - DIRECT VERSION"

if __name__ == '__main__':
    print("🔥 DIRECT HEBREW CALL CENTER - NO APP FACTORY")
    print("📞 Webhook: /webhook/incoming_call")
    print("🎵 Voice files: /static/voice_responses/")
    print("=" * 50)
    
    app.run(host='0.0.0.0', port=5000, debug=False)