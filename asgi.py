#!/usr/bin/env python3
"""
ASGI Application for Cloud Run WebSocket Support
Uses Starlette for WebSocket + Flask WSGI wrapper
BUILD 85: Google STT Fix + Conversation Memory + Auto Leads
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Mark that we're running under ASGI
os.environ['ASGI_SERVER'] = '1'

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

# BUILD 168.2: Minimal startup logging
log = logging.getLogger("asgi")

# GCP credentials setup (silent unless error)
gcp_creds = os.getenv('GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON') or os.getenv('GOOGLE_APPLICATION_CREDENTIALS', '')
if gcp_creds and gcp_creds.startswith('{'):
    try:
        creds_data = json.loads(gcp_creds)
        credentials_path = '/tmp/gcp_credentials.json'
        with open(credentials_path, 'w') as f:
            json.dump(creds_data, f)
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
    except Exception as e:
        log.error(f"GCP credentials setup failed: {e}")

# Lazy Flask app creation
twilio_log = logging.getLogger("twilio_ws")
flask_app = None

def get_flask_app():
    """Lazy Flask app creation - only when needed"""
    global flask_app
    if flask_app is None:
        from server.app_factory import create_app
        flask_app = create_app()
    return flask_app

# Background warmup
def _warmup_flask():
    import time
    time.sleep(0.5)
    _ = get_flask_app()

warmup_thread = threading.Thread(target=_warmup_flask, daemon=True)
warmup_thread.start()

async def ws_http_probe(request: Request):
    """Return 426 Upgrade Required for non-WebSocket requests"""
    return PlainTextResponse("Upgrade Required", status_code=426)

async def healthz_immediate(request: Request):
    """Immediate health check - no Flask required"""
    return PlainTextResponse("ok", status_code=200)

class SyncWebSocketWrapper:
    """
    Makes async Starlette WebSocket work with sync MediaStreamHandler
    Uses queues to bridge async/sync boundary
    """
    def __init__(self):
        self.recv_queue = Queue(maxsize=500)  # async → sync (max 500 frames ~10s of audio)
        self.send_queue = Queue(maxsize=600)  # sync → async (max 600 frames ~12s buffer - handles AI latency)
        self.running = True
        
    def receive(self):
        """Sync receive - blocks until message available"""
        try:
            msg = self.recv_queue.get(timeout=120)
            if msg is None:
                return None
            return msg
        except Empty:
            return None
    
    def send(self, data):
        """Sync send - puts in queue for async sender with timeout"""
        if self.running:
            try:
                self.send_queue.put(data, timeout=2.0)
            except:
                pass  # Drop frame if queue is full
    
    def stop(self):
        """Stop wrapper"""
        self.running = False
        self.recv_queue.put(None)  # Signal EOF

async def ws_twilio_media(websocket: WebSocket):
    """
    WebSocket handler for Twilio Media Streams
    Bridges async Starlette WS to sync MediaStreamHandler
    """
    # Accept with Twilio subprotocol
    try:
        await websocket.accept(subprotocol="audio.twilio.com")
    except Exception as e:
        twilio_log.error(f"WebSocket accept failed: {e}")
        raise
    
    twilio_log.info("WebSocket connected: /ws/twilio-media")
    
    # Create sync wrapper
    ws_wrapper = SyncWebSocketWrapper()
    handler_thread = None
    
    try:
        # Import MediaStreamHandler
        from server.media_ws_ai import MediaStreamHandler
        
        # Task 1: Receive from Starlette WS → put in queue for sync handler
        async def receive_loop():
            msg_count = 0
            try:
                twilio_log.info("[WS] receive_loop started")
                while ws_wrapper.running:
                    try:
                        msg = await websocket.receive_json()
                        msg_count += 1
                        event_type = msg.get("event", "unknown")
                        if event_type == "start":
                            twilio_log.info(f"[WS] START event received! Forwarding to handler")
                        ws_wrapper.recv_queue.put(json.dumps(msg))
                    except json.JSONDecodeError:
                        try:
                            _ = await websocket.receive_text()
                        except Exception:
                            pass
                        continue
                    except Exception as e:
                        twilio_log.error(f"[WS] Receive error after {msg_count} msgs: {e}")
                        break
            finally:
                twilio_log.info(f"[WS] receive_loop ended after {msg_count} messages")
                ws_wrapper.stop()
        
        # Task 2: Get from queue → send to Starlette WS
        async def send_loop():
            try:
                error_count = 0
                max_errors = 10
                
                while ws_wrapper.running and error_count < max_errors:
                    try:
                        data = await asyncio.get_event_loop().run_in_executor(
                            None, ws_wrapper.send_queue.get, True, 0.5
                        )
                        if data is None:
                            break
                        
                        try:
                            if isinstance(data, str):
                                await websocket.send_text(data)
                            else:
                                await websocket.send_bytes(data)
                            error_count = 0
                        except Exception as send_err:
                            error_count += 1
                            if error_count >= max_errors:
                                break
                            await asyncio.sleep(0.05)
                            
                    except Empty:
                        await asyncio.sleep(0.01)
                    except Exception as e:
                        error_count += 1
                        twilio_log.error(f"Send loop error: {e}")
                        if error_count >= max_errors:
                            break
                        await asyncio.sleep(0.05)
            except Exception as fatal:
                twilio_log.error(f"Fatal send_loop error: {fatal}")
            finally:
                ws_wrapper.stop()
        
        # Task 3: MediaStreamHandler in background thread
        def run_handler():
            try:
                twilio_log.info("[WS] run_handler: Getting Flask app...")
                _ = get_flask_app()
                twilio_log.info("[WS] run_handler: Creating MediaStreamHandler...")
                handler = MediaStreamHandler(ws_wrapper)
                twilio_log.info("[WS] run_handler: Starting handler.run()...")
                handler.run()
                twilio_log.info("[WS] run_handler: handler.run() completed normally")
            except Exception as e:
                twilio_log.error(f"[WS] MediaStreamHandler error: {e}")
                import traceback
                twilio_log.error(traceback.format_exc())
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
            
            # Wait for loops to finish
            await loops_task
            
            # Wait for handler thread to finish
            await asyncio.get_event_loop().run_in_executor(
                None, handler_thread.join, 15
            )
        
        await run_all()
        
    except Exception as e:
        twilio_log.exception(f"WebSocket error: {e}")
    finally:
        ws_wrapper.stop()
        try:
            await websocket.close()
        except Exception:
            pass
        twilio_log.info("WebSocket closed")

# Lazy ASGI wrapper to defer Flask app creation
class LazyASGIWrapper:
    """Wraps Flask app creation to defer until first request"""
    def __init__(self, app_getter):
        self.app_getter = app_getter
        self._asgi_app = None
    
    async def __call__(self, scope, receive, send):
        if self._asgi_app is None:
            flask_app = self.app_getter()
            self._asgi_app = WsgiToAsgi(flask_app)
        await self._asgi_app(scope, receive, send)

# ASGI Application with Starlette
# Order matters: Health checks FIRST, then WS, then Flask mount
app = Starlette(routes=[
    # 🚀 CRITICAL: Immediate health check for Cloud Run (no Flask required!)
    Route("/healthz", healthz_immediate, methods=["GET"]),
    Route("/health", healthz_immediate, methods=["GET"]),
    # Block non-WebSocket GET requests (return 426 instead of HTML)
    Route("/ws/twilio-media", ws_http_probe, methods=["GET"]),
    Route("/ws/twilio-media/", ws_http_probe, methods=["GET"]),
    # WebSocket routes (with and without trailing slash)
    WebSocketRoute("/ws/twilio-media", ws_twilio_media),
    WebSocketRoute("/ws/twilio-media/", ws_twilio_media),
    # Flask/SPA mount (fallback for everything else) - LAZY!
    Mount("/", app=LazyASGIWrapper(get_flask_app)),
])

# ✅ Alias for compatibility
asgi_app = app
