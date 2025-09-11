#!/usr/bin/env python3

# CRITICAL: EventLet monkey patch MUST be first, before any other imports
import eventlet
eventlet.monkey_patch()

# Environment setup AFTER monkey patching
import os, sys, traceback, signal, json, time
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Enhanced stability configuration for Replit
os.environ.update({
    'EVENTLET_NO_GREENDNS': '1',
    'EVENTLET_HUB': 'poll',
    'PYTHONUNBUFFERED': '1',
    'GEVENT_SUPPORT': '1'
})

# Add signal handling for graceful shutdown
def signal_handler(sig, frame):
    print(f"🛑 Received signal {sig}, shutting down gracefully...")
    sys.exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

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
        traceback.print_exc()

class WebSocketAppWithProtocol:
    """WebSocket WSGI app that handles Twilio subprotocol"""
    
    def __init__(self, handler_func):
        self.handler_func = handler_func
    
    def __call__(self, environ, start_response):
        # Check for Twilio subprotocol
        raw = environ.get('HTTP_SEC_WEBSOCKET_PROTOCOL', '') or ''
        protocols = [p.strip() for p in raw.split(',') if p.strip()]
        wants_twilio = any(p.lower() == 'audio.twilio.com' for p in protocols)

        if wants_twilio:
            print("🎯 Twilio subprotocol requested", flush=True)
            
            # Wrapper for start_response that adds subprotocol
            def twilio_start_response(status, headers, exc_info=None):
                if status == '101 Switching Protocols':
                    headers = list(headers)
                    headers.append(('Sec-WebSocket-Protocol', 'audio.twilio.com'))
                    headers.append(('Upgrade', 'websocket'))
                    headers.append(('Connection', 'Upgrade'))
                    print("✅ Added Twilio subprotocol to handshake", flush=True)
                return start_response(status, headers, exc_info)
            
            # Use EventLet with custom start_response
            ws_app = WebSocketWSGI(self.handler_func)
            return ws_app(environ, twilio_start_response)
        
        # Default WebSocket without subprotocol
        ws_app = WebSocketWSGI(self.handler_func)
        return ws_app(environ, start_response)

# Create WebSocket app and Flask app
websocket_app_with_protocol = WebSocketAppWithProtocol(ws_handler)

# Create Flask app once with proper application context
flask_app = create_app()

def _init_app_context():
    """Initialize Flask app context for eventlet compatibility"""
    try:
        with flask_app.app_context():
            # Pre-warm any application context dependent operations
            pass
        print("✅ Flask app context initialized successfully")
    except Exception as e:
        print(f"⚠️ App context init warning: {e}")
        # Continue anyway, context will be created on first request

_init_app_context()

def _is_websocket_request(environ):
    """Check if this is a WebSocket upgrade request"""
    connection = environ.get('HTTP_CONNECTION', '').lower()
    upgrade = environ.get('HTTP_UPGRADE', '').lower()
    return 'upgrade' in connection and upgrade == 'websocket'

def app(environ, start_response):
    """Main WSGI application - routes WebSocket to EventLet, HTTP to Flask"""
    path = environ.get('PATH_INFO', '')
    method = environ.get('REQUEST_METHOD', 'GET')
    
    # Debug logging for all requests
    print(f"🔍 WSGI Route: {method} {path}", flush=True)
    
    # Enhanced healthz handling with more info
    if path == '/healthz':
        print("❤️ Direct healthz response", flush=True)
        health_data = {
            'status': 'ok',
            'timestamp': int(time.time()),
            'pid': os.getpid(),
            'memory_info': 'available'
        }
        response_text = f"ok - {health_data}"
        start_response('200 OK', [
            ('Content-Type', 'text/plain'),
            ('Cache-Control', 'no-cache'),
            ('X-Health-Check', 'wsgi-direct')
        ])
        return [response_text.encode('utf-8')]
    
    # Fast webhook responses (avoid Flask overhead)
    if path in (
        '/webhook/stream_status', '/webhook/stream_status/',
        '/webhook/stream_ended', '/webhook/stream_ended/'
    ):
        print(f"⚡ Fast 204 for {path}", flush=True)
        start_response('204 No Content', [
            ('Content-Type', 'text/plain'),
            ('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0'),
            ('Pragma', 'no-cache'),
        ])
        return [b'']

    # Fast TwiML response for incoming calls
    if path in ('/webhook/incoming_call', '/webhook/incoming_call/'):
        print(f"⚡ Fast TwiML for {path}", flush=True)
        scheme = (environ.get('HTTP_X_FORWARDED_PROTO') or 'https').split(',')[0].strip()
        host = (environ.get('HTTP_X_FORWARDED_HOST') or environ.get('HTTP_HOST')).split(',')[0].strip()
        base = f"{scheme}://{host}"
        twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Connect action="{base}/webhook/stream_ended">
    <Stream url="wss://{host}/ws/twilio-media" statusCallback="{base}/webhook/stream_status">
      <Parameter name="CallSid" value="{{CALL_SID}}"/>
    </Stream>
  </Connect>
</Response>'''
        start_response('200 OK', [
            ('Content-Type', 'application/xml; charset=utf-8'),
            ('Cache-Control', 'no-store, no-cache, must-revalidate'),
            ('Pragma', 'no-cache'),
        ])
        return [twiml.encode('utf-8')]

    # Fast call status response
    if path in ('/webhook/call_status', '/webhook/call_status/'):
        print(f"⚡ Fast 204 for {path}", flush=True)
        start_response('204 No Content', [
            ('Content-Type', 'text/plain'),
            ('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0'),
            ('Pragma', 'no-cache'),
        ])
        return [b'']
    
    # Route WebSocket requests to EventLet
    if path in ('/ws/twilio-media', '/ws/twilio-media/') and _is_websocket_request(environ):
        print("📞 Routing WebSocket to EventLet", flush=True)
        return websocket_app_with_protocol(environ, start_response)
    
    # All other requests (including HTTP to WebSocket paths) go to Flask
    print(f"🌐 Routing to Flask app: {path}", flush=True)
    try:
        return flask_app(environ, start_response)
    except Exception as e:
        print(f"❌ Flask app error for {path}: {e}", flush=True)
        traceback.print_exc()
        
        # Return proper error response
        try:
            error_response = json.dumps({
                'error': 'Internal server error',
                'path': path,
                'message': str(e)
            })
            start_response('500 Internal Server Error', [
                ('Content-Type', 'application/json'),
                ('Cache-Control', 'no-cache')
            ])
            return [error_response.encode('utf-8')]
        except:
            # Fallback error response
            start_response('500 Internal Server Error', [('Content-Type', 'text/plain')])
            return [b'Internal Server Error']

# WSGI application is exported as 'app' for gunicorn
# No need for additional assignment - the function is already named 'app'

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    print(f"[WSGI] starting on 0.0.0.0:{port}", flush=True)
    flask_app.run(host="0.0.0.0", port=port, debug=False)

print("✅ EventLet Composite WSGI ready")
print("📞 /ws/twilio-media → EventLet WebSocketWSGI with audio.twilio.com")
print("🌐 All other routes → Flask app")