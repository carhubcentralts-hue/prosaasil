#!/usr/bin/env python3
"""
Hebrew AI Call Center - Simple WSGI Entry Point
פתרון פשוט ללא EventLet monkey patching
"""

import os
import sys

# Basic environment setup (no eventlet hub conflicts)
os.environ['EVENTLET_NO_GREENDNS'] = '1'

print("✅ Environment setup without eventlet hub conflicts")

# Create Flask app via app_factory (includes WebSocket route)
from server.app_factory import create_app
app = create_app()

print("✅ Flask app created")
print("📞 WebSocket route: /ws/twilio-media in Flask (simple-websocket)")
print("🔧 Using Werkzeug + simple-websocket (no eventlet monkey patching)")

# Flask app includes everything:
# - All HTTP routes
# - WebSocket route using simple-websocket
# - MediaStreamHandler integration

print("🚀 wsgi:app ready for Gunicorn")
print("📞 WebSocket: simple-websocket in Flask route")
print("🌐 HTTP: Flask app_factory")

if __name__ == '__main__':
    print("⚠️ Use Gunicorn for production")
    app.run(host='0.0.0.0', port=5000, debug=False)