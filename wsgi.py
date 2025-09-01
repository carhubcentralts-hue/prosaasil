#!/usr/bin/env python3
"""
Hebrew AI Call Center - eventlet Composite WSGI
CRITICAL: eventlet.monkey_patch() MUST be first!
"""

# STEP 0: Set eventlet environment BEFORE import
import os
os.environ['EVENTLET_NO_GREENDNS'] = '1'
os.environ['EVENTLET_HUB'] = 'poll'  # Use valid hub: poll (available)

# STEP 1: eventlet.monkey_patch() FIRST - before ANY other imports
import eventlet
eventlet.monkey_patch()

# STEP 2: Only AFTER monkey_patch, import Flask app
import os
import json
from eventlet.websocket import WebSocketWSGI

def create_websocket_handler():
    """EventLet WebSocket handler with audio.twilio.com subprotocol"""
    def websocket_app(environ, start_response):
        """WebSocket handler with proper Twilio subprotocol"""
        print("📞 EventLet WebSocket handler called!", flush=True)
        
        # Check for Twilio subprotocol in headers
        subprotocol = None
        headers = environ.get('HTTP_SEC_WEBSOCKET_PROTOCOL', '')
        if 'audio.twilio.com' in headers:
            subprotocol = 'audio.twilio.com'
            print(f"✅ Twilio subprotocol detected: {subprotocol}", flush=True)
        
        try:
            # Import MediaStreamHandler after monkey_patch
            from server.media_ws_ai import MediaStreamHandler
            
            # Get WebSocket from eventlet environ
            ws = environ['wsgi.websocket']
            print(f"✅ WebSocket connection established: {ws}", flush=True)
            
            # Set subprotocol on WebSocket if needed
            if subprotocol and hasattr(ws, 'protocol'):
                ws.protocol = subprotocol
                print(f"✅ Subprotocol set: {subprotocol}", flush=True)
            
            # Create and run handler
            handler = MediaStreamHandler(ws)
            handler.run()
            
        except Exception as e:
            print(f"❌ WebSocket handler error: {e}", flush=True)
            import traceback
            traceback.print_exc()
        
        # Return empty response (WebSocket handles its own protocol)
        start_response('200 OK', [])
        return [b'']
    
    return websocket_app

def create_composite_wsgi():
    """Composite WSGI: WebSocket BEFORE Flask"""
    from server.app_factory import create_app
    
    # Create Flask app
    flask_app = create_app()
    
    # Create WebSocket WSGI (protocols handled in handshake)
    websocket_handler = create_websocket_handler()
    websocket_wsgi = WebSocketWSGI(websocket_handler)
    
    def composite_app(environ, start_response):
        """Route WebSocket before Flask"""
        path = environ.get('PATH_INFO', '')
        
        # WebSocket routing BEFORE Flask
        if path == '/ws/twilio-media':
            print("📞 Routing to EventLet WebSocketWSGI", flush=True)
            return websocket_wsgi(environ, start_response)
        
        # All other routes go to Flask
        return flask_app.wsgi_app(environ, start_response)
    
    return composite_app

# STEP 3: Export the composite app (NOT Flask app directly!)
app = create_composite_wsgi()

print("✅ EventLet Composite WSGI created:")
print("   📞 /ws/twilio-media → EventLet WebSocketWSGI with audio.twilio.com")  
print("   🌐 All other routes → Flask app")
print("   🔧 Worker: eventlet (Twilio compatible)")
print("🚀 Ready for Twilio Media Streams!")