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
    
    🔥 FIX: Conditional subprotocol negotiation to prevent Twilio error 31924
    """
    # 🔥 CRITICAL: Log at the VERY TOP before any operations - use BOTH print and logger
    print(f"[REALTIME] WS handler ENTERED: path=/ws/twilio-media", flush=True)
    print(f"[REALTIME] Query params: {websocket.scope.get('query_string')}", flush=True)
    twilio_log.info("[REALTIME] WS handler ENTERED: path=/ws/twilio-media")
    twilio_log.info(f"[REALTIME] Query params: {websocket.scope.get('query_string')}")
    
    # 🔥 FIX: Conditional subprotocol acceptance - only if Twilio requested one
    try:
        # Get requested subprotocols from headers
        headers_dict = dict(websocket.headers)
        requested_subprotocols = headers_dict.get(b'sec-websocket-protocol', b'').decode('utf-8')
        requested_list = [s.strip() for s in requested_subprotocols.split(',') if s.strip()]
        
        # Log what Twilio requested for debugging
        print(f"[WS-HANDSHAKE] Requested subprotocols: {requested_list}", flush=True)
        twilio_log.info(f"[WS-HANDSHAKE] Requested subprotocols: {requested_list}")
        
        # Decide how to accept
        if not requested_list:
            # Twilio sent no subprotocol - accept without one
            print("[REALTIME] About to accept WebSocket WITHOUT subprotocol...", flush=True)
            await websocket.accept()
            print("[REALTIME] WebSocket accepted without subprotocol", flush=True)
            twilio_log.info("[REALTIME] WebSocket accepted without subprotocol")
        elif 'audio.twilio.com' in requested_list:
            # Twilio requested audio.twilio.com - accept with it
            print("[REALTIME] About to accept WebSocket WITH subprotocol: audio.twilio.com...", flush=True)
            await websocket.accept(subprotocol="audio.twilio.com")
            print("[REALTIME] WebSocket accepted with subprotocol: audio.twilio.com", flush=True)
            twilio_log.info("[REALTIME] WebSocket accepted with subprotocol: audio.twilio.com")
        else:
            # Unknown subprotocol requested - reject
            print(f"[WS] Unknown subprotocol from client – rejecting: {requested_list}", flush=True)
            twilio_log.warning(f"[WS] Unknown subprotocol from client – rejecting: {requested_list}")
            await websocket.close(code=1002, reason="Unsupported subprotocol")
            return
            
    except Exception as e:
        print(f"[REALTIME] WebSocket accept FAILED: {e}", flush=True)
        twilio_log.exception(f"[REALTIME] WebSocket accept failed: {e}")
        raise
    
    print("[REALTIME] WebSocket connected: /ws/twilio-media", flush=True)
    twilio_log.info("[REALTIME] WebSocket connected: /ws/twilio-media")
    
    # Create sync wrapper
    print("[REALTIME] Creating SyncWebSocketWrapper...", flush=True)
    twilio_log.info("[REALTIME] Creating SyncWebSocketWrapper...")
    ws_wrapper = SyncWebSocketWrapper()
    handler_thread = None
    
    # 🔥 FIX: START event watchdog to close ghost sessions
    start_event_received = asyncio.Event()
    ghost_session_closed = False
    
    print("[REALTIME] SyncWebSocketWrapper created - about to enter try block", flush=True)
    
    try:
        print("[REALTIME] INSIDE try block - importing MediaStreamHandler...", flush=True)
        twilio_log.info("[REALTIME] Importing MediaStreamHandler...")
        # Import MediaStreamHandler
        from server.media_ws_ai import MediaStreamHandler
        print("[REALTIME] MediaStreamHandler imported successfully!", flush=True)
        twilio_log.info("[REALTIME] MediaStreamHandler imported successfully")
        
        # Task 1: Receive from Starlette WS → put in queue for sync handler
        async def receive_loop():
            nonlocal ghost_session_closed
            msg_count = 0
            try:
                print("[REALTIME] receive_loop: STARTED", flush=True)
                twilio_log.info("[WS] receive_loop started")
                while ws_wrapper.running and not ghost_session_closed:
                    try:
                        msg = await websocket.receive_json()
                        msg_count += 1
                        event_type = msg.get("event", "unknown")
                        if event_type == "start":
                            print("[WS] START EVENT RECEIVED!", flush=True)
                            twilio_log.info(f"[WS] START EVENT RECEIVED! Forwarding to handler")
                            start_event_received.set()  # Signal that START was received
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
                print("[REALTIME] send_loop: STARTED", flush=True)
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
        
        # Task 3: START event watchdog - closes ghost sessions after 3 seconds
        async def start_watchdog():
            """
            🔥 FIX: Ghost session protection
            Closes WebSocket if no START event is received within 3 seconds
            """
            nonlocal ghost_session_closed
            try:
                # Wait up to 3 seconds for START event
                await asyncio.wait_for(start_event_received.wait(), timeout=3.0)
                # START received - no action needed
                twilio_log.info("[WS] START watchdog: START event received in time")
            except asyncio.TimeoutError:
                # No START event after 3 seconds - close as ghost session
                ghost_session_closed = True
                print("[WS] No START event – closing ghost session", flush=True)
                twilio_log.warning("[WS] No START event after 3s – closing ghost session")
                ws_wrapper.stop()
                try:
                    await websocket.close(code=1000, reason="No START event")
                except Exception:
                    pass
        
        # Task 4: MediaStreamHandler in background thread
        def run_handler():
            try:
                print("[REALTIME] run_handler: STARTED - Getting Flask app...", flush=True)
                twilio_log.info("[REALTIME] run_handler: STARTED - Getting Flask app...")
                _ = get_flask_app()
                print("[REALTIME] run_handler: Flask app ready - Creating MediaStreamHandler...", flush=True)
                twilio_log.info("[REALTIME] run_handler: Flask app ready - Creating MediaStreamHandler...")
                handler = MediaStreamHandler(ws_wrapper)
                print("[REALTIME] run_handler: MediaStreamHandler created - About to call handler.run()...", flush=True)
                twilio_log.info("[REALTIME] run_handler: MediaStreamHandler created - Starting handler.run()...")
                handler.run()
                print("[REALTIME] run_handler: handler.run() completed normally", flush=True)
                twilio_log.info("[REALTIME] run_handler: handler.run() completed normally")
            except Exception as e:
                twilio_log.exception(f"[REALTIME] MediaStreamHandler error: {e}")
                import traceback
                twilio_log.error(f"[REALTIME] Full traceback:\n{traceback.format_exc()}")
            finally:
                twilio_log.info("[REALTIME] run_handler: CLEANUP - stopping wrapper")
                ws_wrapper.stop()
        
        # Start loops and handler together
        async def run_all():
            nonlocal handler_thread
            print("[REALTIME] run_all: STARTING async loops and handler thread...", flush=True)
            twilio_log.info("[REALTIME] run_all: STARTING async loops and handler thread...")
            # Start async loops and watchdog
            print("[REALTIME] run_all: Creating asyncio.gather for receive_loop, send_loop, and watchdog...", flush=True)
            loops_task = asyncio.gather(
                receive_loop(),
                send_loop(),
                start_watchdog(),  # 🔥 FIX: Add START event watchdog
                return_exceptions=True
            )
            print("[REALTIME] run_all: Async loops and watchdog started - sleeping 0.1s...", flush=True)
            
            # Give loops time to start
            await asyncio.sleep(0.1)
            
            # Now start handler thread
            print("[REALTIME] run_all: Creating and starting handler thread...", flush=True)
            twilio_log.info("[REALTIME] run_all: Creating and starting handler thread...")
            handler_thread = threading.Thread(target=run_handler, daemon=True)
            handler_thread.start()
            print("[REALTIME] run_all: Handler thread STARTED - waiting for loops to finish...", flush=True)
            twilio_log.info("[REALTIME] run_all: Handler thread started - waiting for loops...")
            
            # Wait for loops to finish
            await loops_task
            twilio_log.info("[REALTIME] run_all: Async loops finished - waiting for handler thread...")
            
            # Wait for handler thread to finish
            await asyncio.get_event_loop().run_in_executor(
                None, handler_thread.join, 15
            )
            twilio_log.info("[REALTIME] run_all: Handler thread joined - all tasks complete")
        
        print("[REALTIME] About to call run_all()...", flush=True)
        twilio_log.info("[REALTIME] About to call run_all()...")
        await run_all()
        print("[REALTIME] run_all() completed - handler finished", flush=True)
        twilio_log.info("[REALTIME] run_all() completed")
        
    except Exception as e:
        print(f"[REALTIME] EXCEPTION in ws_twilio_media: {e}", flush=True)
        twilio_log.exception(f"[REALTIME] WebSocket error in ws_twilio_media: {e}")
        import traceback
        print(f"[REALTIME] Full traceback:\n{traceback.format_exc()}", flush=True)
        twilio_log.error(f"[REALTIME] Full traceback:\n{traceback.format_exc()}")
    finally:
        print("[REALTIME] FINALLY block - stopping wrapper and closing websocket", flush=True)
        twilio_log.info("[REALTIME] FINALLY block - stopping wrapper and closing websocket")
        ws_wrapper.stop()
        try:
            await websocket.close()
            twilio_log.info("[REALTIME] WebSocket closed successfully")
        except Exception as e:
            twilio_log.error(f"[REALTIME] Error closing websocket: {e}")
        twilio_log.info("[REALTIME] WebSocket handler EXITED")

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
