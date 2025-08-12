#!/usr/bin/env python3
"""
Direct route test - verify which webhook is actually running
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'server'))

from flask import Flask, Response

# Create direct test app
app = Flask(__name__)

@app.route("/webhook/incoming_call", methods=['POST'])
def direct_incoming_call():
    """Direct webhook test with Play"""
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>https://ai-crmd.replit.app/static/greeting.mp3</Play>
  <Pause length="1"/>
  <Record action="/webhook/handle_recording"
          method="POST"
          maxLength="45"
          timeout="10"
          finishOnKey="*"
          transcribe="false"/>
</Response>"""
    return Response(xml, mimetype="text/xml")

@app.route('/static/<path:filename>')
def serve_static_direct(filename):
    """Direct static file serving"""
    from flask import send_from_directory
    import os
    static_dir = os.path.join(os.path.dirname(__file__), 'server', 'static')
    return send_from_directory(static_dir, filename)

if __name__ == '__main__':
    print("🧪 Direct route test - bypassing all imports")
    print("This should work with Hebrew MP3 files")
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)