#!/usr/bin/env python3
"""
WSGI Entry Point for Gunicorn
FORCE clean eventlet environment
"""

import os
import sys

# CRITICAL FIX: Force eventlet to use working hub for NixOS
os.environ['EVENTLET_HUB'] = 'epolls'

# Set ONLY safe eventlet variables
os.environ['EVENTLET_NO_GREENDNS'] = '1'

print(f"🔧 Eventlet hub forced to: {os.environ.get('EVENTLET_HUB')}")

# Don't force monkey_patch - let gunicorn eventlet worker handle it
try:
    import eventlet  # Just import, no patching
except ImportError:
    pass

# Load app from main.py
try:
    # Add current directory to path
    sys.path.insert(0, os.path.dirname(__file__))
    
    # Import main module
    import main
    flask_app = main.app
    print("✅ Flask app loaded from main.py")
except Exception as e:
    print(f"❌ Failed to load main.py: {e}")
    # Fallback
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))
    from app_factory import create_app
    flask_app = create_app()
    print("✅ Fallback app loaded")

# CRITICAL FIX: Create proper WebSocket WSGI app here in wsgi.py
def twilio_websocket_handler(ws):
    """EventLet WebSocket handler for Twilio Media Streams"""
    print("🔗 WSGI WebSocket handler started", flush=True)
    
    try:
        # Import MediaStreamHandler
        from server.media_ws_ai import MediaStreamHandler
        
        # Create handler with eventlet WebSocket
        handler = MediaStreamHandler(ws)
        print("✅ MediaStreamHandler ready", flush=True)
        
        # Run the AI conversation
        handler.run()
        print("✅ AI conversation completed", flush=True)
        
    except Exception as e:
        print(f"❌ WebSocket handler error: {e}", flush=True)
        import traceback
        traceback.print_exc()

# Create WebSocket WSGI app with Twilio subprotocol
from eventlet.websocket import WebSocketWSGI
from werkzeug.middleware.dispatcher import DispatcherMiddleware

# WebSocket WSGI app with proper subprotocol
ws_app = WebSocketWSGI(twilio_websocket_handler, protocols=['audio.twilio.com'])
print("✅ EventLet WebSocket WSGI created with subprotocol: audio.twilio.com")

# Map WebSocket to specific path, Flask handles everything else
app = DispatcherMiddleware(flask_app, {
    '/ws/twilio-media': ws_app
})

print("✅ WSGI DispatcherMiddleware: /ws/twilio-media → EventLet WebSocket")
print("✅ All other routes → Flask app")

if __name__ == "__main__":
    print("🚀 WSGI loaded successfully")