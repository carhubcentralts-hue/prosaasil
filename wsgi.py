#!/usr/bin/env python3
"""
Professional Hebrew Auth Server - Production Ready
מערכת התחברות מקצועית עם React 19 + Tailwind 4.1 + Motion
"""

import os
import sys

# Apply eventlet monkey patching FIRST - before any imports
os.environ['EVENTLET_HUB'] = 'selects'
os.environ['EVENTLET_NO_GREENDNS'] = '1'

import eventlet
eventlet.monkey_patch()

print("✅ EventLet monkey patching applied")
print("🔧 EVENTLET_HUB=selects for optimal performance")

# Create Flask app using factory (includes WebSocket routes now!)
from server.app_factory import create_app
app = create_app()

print("✅ Flask app created via app_factory")
print("📞 WebSocket support integrated in app_factory.py using simple-websocket")
print("🔧 Simplified approach: Flask handles both HTTP and WebSocket")

# The app_factory.py now includes:
# - All HTTP routes
# - WebSocket route: /ws/twilio-media using simple-websocket
# - MediaStreamHandler integration
# - Twilio subprotocol validation

print("🚀 wsgi:app ready - Flask with integrated WebSocket")
print("📞 WebSocket: simple-websocket in Flask")
print("🌐 HTTP: Flask app_factory")

# Entry point for testing
if __name__ == '__main__':
    print("⚠️ Use 'python -m gunicorn wsgi:app -k eventlet' for production")
    app.run(host='0.0.0.0', port=5000, debug=False)