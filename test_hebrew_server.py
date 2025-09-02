#!/usr/bin/env python3
"""
Hebrew AI Server Test - Direct Flask + EventLet
"""
import eventlet
eventlet.monkey_patch()

import os
os.environ['EVENTLET_NO_GREENDNS'] = '1' 
os.environ['EVENTLET_HUB'] = 'poll'

from server.app_factory import create_app
from flask_sock import Sock

# Create Flask app
app = create_app()
sock = Sock(app)

@sock.route('/ws/twilio-media')
def ws_twilio_media(ws):
    """WebSocket handler for Twilio media streams"""
    print("📞 Twilio WebSocket connected!", flush=True)
    try:
        from server.media_ws_ai import MediaStreamHandler
        handler = MediaStreamHandler(ws)
        handler.run()
    except Exception as e:
        print(f"❌ WebSocket error: {e}", flush=True)
        import traceback
        traceback.print_exc()

@app.route('/healthz')
def healthz():
    return {"status": "ok", "message": "Hebrew AI Server Ready!"}

@app.route('/test-hebrew')
def test_hebrew():
    return {"message": "שרת עברית פועל!", "ai": "לאה מוכנה לעבודה"}

if __name__ == '__main__':
    print("🚀 Starting Hebrew AI Server on port 5000...")
    print("✅ EventLet hub:", eventlet.hubs.get_hub())
    print("✅ WebSocket ready for Twilio media")
    print("✅ Hebrew AI components loaded")
    
    # Start server
    try:
        import eventlet
        import eventlet.wsgi
        eventlet.wsgi.server(eventlet.listen(('0.0.0.0', 5000)), app)
    except KeyboardInterrupt:
        print("🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Server error: {e}")
        import traceback
        traceback.print_exc()