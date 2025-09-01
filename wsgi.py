#!/usr/bin/env python3
import eventlet; eventlet.monkey_patch()

import os
os.environ['EVENTLET_NO_GREENDNS'] = '1'
os.environ['EVENTLET_HUB'] = 'select'

from eventlet.websocket import WebSocketWSGI
from server.app_factory import create_app

def ws_handler(ws):
    """EventLet WebSocket handler for Twilio media streams"""
    print("📞 WebSocket handler called!", flush=True)
    
    try:
        from server.media_ws_ai import MediaStreamHandler
        handler = MediaStreamHandler(ws)
        handler.run()
    except Exception as e:
        print(f"❌ WebSocket error: {e}", flush=True)
        import traceback
        traceback.print_exc()

class WebSocketAppWithProtocol:
    """WebSocket WSGI app that handles Twilio subprotocol"""
    
    def __init__(self, handler_func):
        self.handler_func = handler_func
    
    def __call__(self, environ, start_response):
        # Check for Twilio subprotocol
        protocols = environ.get('HTTP_SEC_WEBSOCKET_PROTOCOL', '')
        
        if 'audio.twilio.com' in protocols:
            print("🎯 Twilio subprotocol requested", flush=True)
            
            # Wrapper for start_response that adds subprotocol
            def twilio_start_response(status, headers, exc_info=None):
                if status == '101 Switching Protocols':
                    headers = list(headers)
                    headers.append(('Sec-WebSocket-Protocol', 'audio.twilio.com'))
                    print("✅ Added Twilio subprotocol to handshake", flush=True)
                return start_response(status, headers, exc_info)
            
            # Use EventLet with custom start_response
            ws_app = WebSocketWSGI(self.handler_func)
            return ws_app(environ, twilio_start_response)
        
        # Default WebSocket without subprotocol
        ws_app = WebSocketWSGI(self.handler_func)
        return ws_app(environ, start_response)

# Create the WebSocket app
websocket_app_with_protocol = WebSocketAppWithProtocol(ws_handler)

# Create Flask app once
flask_app = create_app()

def composite_app(environ, start_response):
    """Composite WSGI: WebSocket BEFORE Flask"""
    path = environ.get('PATH_INFO', '')
    method = environ.get('REQUEST_METHOD', 'GET')
    
    # Debug logging for all requests
    print(f"🔍 WSGI Route: {method} {path}", flush=True)
    
    # Direct healthz handling (bypass Flask routing issues)
    if path == '/healthz':
        print("❤️ Direct healthz response", flush=True)
        start_response('200 OK', [('Content-Type', 'text/plain')])
        return [b'ok']
    
    if path == '/ws/twilio-media':
        print("📞 Routing to EventLet WebSocketWSGI", flush=True)
        return websocket_app_with_protocol(environ, start_response)
    
    # All other routes go to Flask
    print(f"🌐 Routing to Flask app: {path}", flush=True)
    try:
        return flask_app.wsgi_app(environ, start_response)
    except Exception as e:
        print(f"❌ Flask app error for {path}: {e}", flush=True)
        raise

app = composite_app

print("✅ EventLet Composite WSGI ready")
print("📞 /ws/twilio-media → EventLet WebSocketWSGI with audio.twilio.com")
print("🌐 All other routes → Flask app")