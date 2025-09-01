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
        
        # EventLet handles WebSocket response - just complete the handler
        return []
    
    return websocket_app

def create_composite_wsgi():
    """Composite WSGI: WebSocket BEFORE Flask"""
    from server.app_factory import create_app
    
    # Create Flask app
    flask_app = create_app()
    
    # Create custom WebSocket WSGI wrapper with subprotocol support
    websocket_handler = create_websocket_handler()
    
    def websocket_with_subprotocol(environ, start_response):
        """WebSocket wrapper that handles Twilio subprotocol in handshake"""
        # Check for Twilio subprotocol in request
        req_protocols = environ.get('HTTP_SEC_WEBSOCKET_PROTOCOL', '')
        
        if 'audio.twilio.com' in req_protocols:
            print("🎯 Twilio subprotocol detected in handshake", flush=True)
            
            # Create WebSocket with subprotocol support
            def start_response_with_protocol(status, headers, exc_info=None):
                # Add subprotocol to response headers
                if status.startswith('101'):  # WebSocket upgrade
                    headers = list(headers) if headers else []
                    headers.append(('Sec-WebSocket-Protocol', 'audio.twilio.com'))
                    print("✅ Added Twilio subprotocol to response headers", flush=True)
                return start_response(status, headers, exc_info)
            
            # Use EventLet WebSocketWSGI with modified start_response
            websocket_wsgi = WebSocketWSGI(websocket_handler)
            return websocket_wsgi(environ, start_response_with_protocol)
        
        # Fallback to regular WebSocket
        websocket_wsgi = WebSocketWSGI(websocket_handler)
        return websocket_wsgi(environ, start_response)
    
    def composite_app(environ, start_response):
        """Route WebSocket before Flask"""
        path = environ.get('PATH_INFO', '')
        
        # WebSocket routing BEFORE Flask
        if path == '/ws/twilio-media':
            print("📞 Routing to WebSocket with subprotocol support", flush=True)
            return websocket_with_subprotocol(environ, start_response)
        
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