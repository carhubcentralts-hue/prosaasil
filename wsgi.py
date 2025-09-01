#!/usr/bin/env python3
"""
Hebrew AI Call Center - eventlet Composite WSGI
שלב 2: סדר טעינה נכון - eventlet monkey_patch ראשון!
"""
import os
# שלב 7: NixOS compatibility - set hub before eventlet import
os.environ['EVENTLET_NO_GREENDNS'] = '1'
os.environ['EVENTLET_HUB'] = 'poll'

import eventlet
eventlet.monkey_patch()

def create_websocket_handler():
    """EventLet WebSocket handler עם subprotocol נכון לTwilio"""
    def websocket_app(environ, start_response):
        """WebSocket handler עם audio.twilio.com subprotocol"""
        print("📞 EventLet WebSocket handler called!", flush=True)
        
        try:
            # Import here after monkey_patch
            from server.media_ws_ai import MediaStreamHandler
            
            # Get WebSocket from eventlet environ
            ws = environ['wsgi.websocket']
            print(f"✅ WebSocket connection established: {ws}", flush=True)
            
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
    """שלב 3: Composite WSGI - WebSocket לפני Flask"""
    from eventlet.websocket import WebSocketWSGI
    from server.app_factory import create_app
    
    # Create Flask app
    flask_app = create_app()
    
    # Create WebSocket WSGI with correct subprotocol
    websocket_handler = create_websocket_handler()
    websocket_wsgi = WebSocketWSGI(websocket_handler)
    
    def composite_app(environ, start_response):
        """Composite WSGI - בודק PATH_INFO ומנתב"""
        path = environ.get('PATH_INFO', '')
        print(f"🔍 WSGI Request: {path}", flush=True)
        
        # WebSocket route - עובר ל-EventLet
        if path == '/ws/twilio-media':
            print("📞 Routing to EventLet WebSocket with audio.twilio.com", flush=True)
            return websocket_wsgi(environ, start_response)
        
        # כל השאר - עובר ל-Flask
        print(f"🌐 Routing to Flask: {path}", flush=True)
        return flask_app.wsgi_app(environ, start_response)
    
    return composite_app

# יצוא סופי - composite_app (לא Flask!)
app = create_composite_wsgi()

print("✅ EventLet Composite WSGI created:")
print("   📞 /ws/twilio-media → EventLet WebSocketWSGI with audio.twilio.com")
print("   🌐 All other routes → Flask app")
print("   🔧 Worker: eventlet (Twilio compatible)")
print("🚀 Ready for Twilio Media Streams!")

if __name__ == '__main__':
    print("⚠️ Use Gunicorn with eventlet worker for production:")
    print("   python -m gunicorn -w 1 -k eventlet -b 0.0.0.0:5000 wsgi:app")
    # For testing only - not production!
    import eventlet.wsgi
    import os
    port = int(os.environ.get('PORT', 5000))
    eventlet.wsgi.server(eventlet.listen(('0.0.0.0', port)), app)