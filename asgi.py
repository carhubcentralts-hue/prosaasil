#!/usr/bin/env python3
"""
ASGI Application for Cloud Run WebSocket Support
Uses Starlette for WebSocket + Flask WSGI wrapper
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from asgiref.wsgi import WsgiToAsgi
from starlette.applications import Starlette
from starlette.routing import Mount, WebSocketRoute
from starlette.websockets import WebSocket

from wsgi import flask_app  # Flask WSGI app

async def ws_twilio_media(websocket: WebSocket):
    """
    WebSocket handler for Twilio Media Streams
    Accept connection and consume frames to keep connection alive
    """
    # חובה לקבל את החיבור עם הsubprotocol של Twilio:
    await websocket.accept(subprotocol="audio.twilio.com")
    
    print("📞 WebSocket connected: /ws/twilio-media", flush=True)
    
    try:
        # Import handler
        from server.media_ws_ai import MediaStreamHandler
        
        # Create wrapper for sync handler
        class StarletteWebSocketWrapper:
            def __init__(self, ws):
                self.ws = ws
                self._loop = None
                
            def send(self, data):
                """Sync send - schedule in event loop"""
                import asyncio
                if isinstance(data, str):
                    asyncio.create_task(self.ws.send_text(data))
                else:
                    asyncio.create_task(self.ws.send_bytes(data))
                    
            def recv(self):
                """Sync recv - not ideal but MediaStreamHandler expects it"""
                import asyncio
                # This won't work well - MediaStreamHandler needs refactoring for async
                # For now, just keep connection alive
                return None
        
        # Keep connection alive - consume Twilio frames
        while True:
            # Twilio שולחת frames כ-JSON (media/start, media/stop, media, mark, close)
            try:
                msg = await websocket.receive_json()
                event = msg.get("event", "")
                
                # Log events for debugging
                if event in ("start", "stop", "connected"):
                    print(f"📞 Twilio event: {event}", flush=True)
                
                # כאן לפחות "לצרוך" את ההודעות כדי שהחיבור לא ייסגר מייד
                # TODO: קרא ל-STT pipeline בזמן אמת כאן
                
            except Exception as e:
                print(f"❌ WebSocket receive error: {e}", flush=True)
                break
                
    except Exception as e:
        print(f"❌ WebSocket handler error: {e}", flush=True)
        import traceback
        traceback.print_exc()
    finally:
        try:
            await websocket.close()
        except:
            pass
        print("📞 WebSocket disconnected", flush=True)

# ASGI Application with Starlette
asgi_app = Starlette(routes=[
    WebSocketRoute("/ws/twilio-media", ws_twilio_media),  # WebSocket למדיה
    Mount("/", app=WsgiToAsgi(flask_app)),                # כל ה-HTTP של Flask
])
