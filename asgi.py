#!/usr/bin/env python3
"""
ASGI Application for Cloud Run WebSocket Support
Uses Starlette for WebSocket + Flask WSGI wrapper
BUILD 68: TTS fix - Google Cloud credentials multi-env support
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import asyncio
import json
import logging
import threading
from queue import Queue, Empty
from asgiref.wsgi import WsgiToAsgi
from starlette.applications import Starlette
from starlette.routing import Mount, WebSocketRoute, Route
from starlette.websockets import WebSocket
from starlette.responses import PlainTextResponse
from starlette.requests import Request

# STARTUP LOGGING - TO STDOUT
print("=" * 80, flush=True)
print("🚀 ASGI BUILD 68 LOADING - TTS FIX", flush=True)
print("=" * 80, flush=True)

# Import Flask app directly from factory (no EventLet dependency)
from server.app_factory import create_app

log = logging.getLogger("twilio_ws")
flask_app = create_app()

print("=" * 80, flush=True)
print("✅ ASGI BUILD 68 READY - TTS + WebSocket", flush=True)
print("=" * 80, flush=True)

async def ws_http_probe(request: Request):
    """Return 426 Upgrade Required for non-WebSocket requests"""
    return PlainTextResponse("Upgrade Required", status_code=426)

class SyncWebSocketWrapper:
    """
    Makes async Starlette WebSocket work with sync MediaStreamHandler
    Uses queues to bridge async/sync boundary
    """
    def __init__(self):
        self.recv_queue = Queue(maxsize=500)  # async → sync (max 500 frames ~10s of audio)
        self.send_queue = Queue(maxsize=500)  # sync → async (max 500 frames)
        self.running = True
        
    def receive(self):
        """Sync receive - blocks until message available"""
        try:
            msg = self.recv_queue.get(timeout=30)  # 30s timeout
            if msg is None:  # EOF signal
                return None
            return msg
        except Empty:
            return None
    
    def send(self, data):
        """Sync send - puts in queue for async sender"""
        if self.running:
            self.send_queue.put(data)
    
    def stop(self):
        """Stop wrapper"""
        self.running = False
        self.recv_queue.put(None)  # Signal EOF

async def ws_twilio_media(websocket: WebSocket):
    """
    WebSocket handler for Twilio Media Streams
    Bridges async Starlette WS to sync MediaStreamHandler
    """
    # Log connection attempt
    print(f"📞 WebSocket connection attempt: headers={dict(websocket.headers)}", flush=True)
    log.info(f"📞 WebSocket connection attempt: headers={dict(websocket.headers)}")
    
    # Accept with Twilio subprotocol
    try:
        await websocket.accept(subprotocol="audio.twilio.com")
        print("✅ WebSocket accepted with subprotocol: audio.twilio.com", flush=True)
        log.info("✅ WebSocket accepted with subprotocol: audio.twilio.com")
    except Exception as e:
        print(f"❌ WebSocket accept failed: {e}", flush=True)
        log.error(f"❌ WebSocket accept failed: {e}")
        raise
    
    print("📞 WebSocket connected: /ws/twilio-media", flush=True)
    log.info("📞 WebSocket connected: /ws/twilio-media")
    
    # Create sync wrapper
    ws_wrapper = SyncWebSocketWrapper()
    handler_thread = None
    
    try:
        # Import MediaStreamHandler
        from server.media_ws_ai import MediaStreamHandler
        
        # Task 1: Receive from Starlette WS → put in queue for sync handler
        async def receive_loop():
            try:
                print("🔧 receive_loop started", flush=True)
                while ws_wrapper.running:
                    try:
                        msg = await websocket.receive_json()
                        print(f"📨 Received: {msg.get('event', 'unknown')}", flush=True)
                        ws_wrapper.recv_queue.put(json.dumps(msg))
                    except json.JSONDecodeError:
                        # Non-JSON frames - consume text to keep loop alive
                        try:
                            _ = await websocket.receive_text()
                        except Exception:
                            pass
                        continue
                    except Exception as e:
                        print(f"❌ Receive error: {e}", flush=True)
                        log.error(f"Receive error: {e}")
                        break
            finally:
                print("🔧 receive_loop ended", flush=True)
                ws_wrapper.stop()
        
        # Task 2: Get from queue → send to Starlette WS
        async def send_loop():
            try:
                print("🔧 send_loop started", flush=True)
                while ws_wrapper.running:
                    # Non-blocking check for messages
                    try:
                        data = await asyncio.get_event_loop().run_in_executor(
                            None, ws_wrapper.send_queue.get, True, 0.1  # 100ms timeout
                        )
                        if data is None:
                            break
                        if isinstance(data, str):
                            await websocket.send_text(data)
                        else:
                            await websocket.send_bytes(data)
                    except Empty:
                        await asyncio.sleep(0.01)  # Yield to other tasks
                    except Exception as e:
                        print(f"❌ Send error: {e}", flush=True)
                        log.error(f"Send error: {e}")
                        break
            except Exception:
                pass
            finally:
                print("🔧 send_loop ended", flush=True)
        
        # Task 3: MediaStreamHandler in background thread (starts AFTER loops)
        def run_handler():
            try:
                print("🔧 Creating MediaStreamHandler...", flush=True)
                handler = MediaStreamHandler(ws_wrapper)
                print("🔧 Starting MediaStreamHandler.run()...", flush=True)
                handler.run()
                print("✅ MediaStreamHandler completed", flush=True)
                log.info("✅ MediaStreamHandler completed")
            except Exception as e:
                print(f"❌ MediaStreamHandler error: {e}", flush=True)
                import traceback
                traceback.print_exc()
                log.exception(f"❌ MediaStreamHandler error: {e}")
            finally:
                ws_wrapper.stop()
        
        # Start loops and handler together
        async def run_all():
            # Start async loops
            loops_task = asyncio.gather(
                receive_loop(),
                send_loop(),
                return_exceptions=True
            )
            
            # Give loops time to start
            await asyncio.sleep(0.1)
            
            # Now start handler thread
            handler_thread = threading.Thread(target=run_handler, daemon=True)
            handler_thread.start()
            print("✅ MediaStreamHandler thread started", flush=True)
            log.info("✅ MediaStreamHandler thread started")
            
            # Wait for loops to finish
            await loops_task
            
            # Wait for handler thread to finish (with timeout)
            await asyncio.get_event_loop().run_in_executor(
                None, handler_thread.join, 5  # 5s timeout
            )
        
        await run_all()
        
    except Exception as e:
        log.exception(f"WebSocket error: {e}")
    finally:
        ws_wrapper.stop()
        try:
            await websocket.close()
        except Exception:
            pass
        log.info("📞 WebSocket closed")

# ASGI Application with Starlette
# Order matters: WS routes BEFORE Mount to prevent SPA from catching them
asgi_app = Starlette(routes=[
    # Block non-WebSocket GET requests (return 426 instead of HTML)
    Route("/ws/twilio-media", ws_http_probe, methods=["GET"]),
    Route("/ws/twilio-media/", ws_http_probe, methods=["GET"]),
    # WebSocket routes (with and without trailing slash)
    WebSocketRoute("/ws/twilio-media", ws_twilio_media),
    WebSocketRoute("/ws/twilio-media/", ws_twilio_media),
    # Flask/SPA mount (fallback for everything else)
    Mount("/", app=WsgiToAsgi(flask_app)),
])
