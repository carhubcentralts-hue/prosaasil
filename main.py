#!/usr/bin/env python3
"""
Professional Hebrew Auth Server with WebSocket Support
מערכת התחברות מקצועית עם תמיכת WebSocket לTwilio
"""

import os
import sys

# Set up gevent environment for WebSocket support  
os.environ['EVENTLET_NO_GREENDNS'] = '1'

print("✅ Gevent setup for WebSocket support")

# Create Flask app using app_factory
from server.app_factory import create_app
app = create_app()

print("✅ Flask app created with app_factory")

# WebSocket support is now in app_factory.py - no duplication needed
print("✅ WebSocket route handled by app_factory.py")
print("📞 /ws/twilio-media ready for Twilio Media Streams")

# Entry point for production
if __name__ == '__main__':
    print("⚠️ Use 'python -m gunicorn wsgi:app -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker' for production")
    app.run(host='0.0.0.0', port=5000, debug=False)