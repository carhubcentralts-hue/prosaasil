#!/usr/bin/env python3
"""
ASGI Application for Cloud Run WebSocket Support
Uses Starlette for WebSocket + Flask WSGI wrapper
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import asyncio
import json
import logging
from asgiref.wsgi import WsgiToAsgi
from starlette.applications import Starlette
from starlette.routing import Mount, WebSocketRoute
from starlette.websockets import WebSocket

# Import Flask app directly from factory (no EventLet dependency)
from server.app_factory import create_app

log = logging.getLogger("twilio_ws")
flask_app = create_app()

# Wrapper to make Starlette WebSocket work with sync MediaStreamHandler
class AsyncToSyncWebSocketAdapter:
    """Adapter that makes async Starlette WebSocket look sync to MediaStreamHandler"""
    def __init__(self, starlette_ws: WebSocket):
        self.ws = starlette_ws
        self.receive_queue = asyncio.Queue()
        self.send_queue = asyncio.Queue()
        self._running = True
        
    async def _receive_loop(self):
        """Background task: read from async WS, put in queue for sync consumer"""
        try:
            while self._running:
                try:
                    msg = await self.ws.receive_json()
                    await self.receive_queue.put(json.dumps(msg))
                except Exception as e:
                    log.error(f"Receive error: {e}")
                    break
        finally:
            await self.receive_queue.put(None)  # Signal EOF
            
    async def _send_loop(self):
        """Background task: read from queue, send to async WS"""
        try:
            while self._running:
                data = await self.send_queue.get()
                if data is None:
                    break
                try:
                    if isinstance(data, str):
                        await self.ws.send_text(data)
                    else:
                        await self.ws.send_bytes(data)
                except Exception as e:
                    log.error(f"Send error: {e}")
                    break
        except Exception:
            pass
    
    def receive(self):
        """Sync receive for MediaStreamHandler"""
        # Block until message available
        loop = asyncio.new_event_loop()
        try:
            msg = loop.run_until_complete(self.receive_queue.get())
            return msg
        finally:
            loop.close()
    
    def send(self, data):
        """Sync send for MediaStreamHandler"""
        # Schedule send
        try:
            asyncio.create_task(self.send_queue.put(data))
        except RuntimeError:
            # No event loop, create one
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(self.send_queue.put(data))
            finally:
                loop.close()
    
    def stop(self):
        """Stop adapter"""
        self._running = False

async def ws_twilio_media(websocket: WebSocket):
    """
    WebSocket handler for Twilio Media Streams
    Runs MediaStreamHandler in background thread
    """
    # Accept with Twilio subprotocol
    await websocket.accept(subprotocol="audio.twilio.com")
    
    call_sid = None
    log.info("📞 WebSocket connected: /ws/twilio-media")
    
    try:
        # Import handler
        from server.media_ws_ai import MediaStreamHandler
        
        # Create adapter
        adapter = AsyncToSyncWebSocketAdapter(websocket)
        
        # Start background tasks for adapter
        receive_task = asyncio.create_task(adapter._receive_loop())
        send_task = asyncio.create_task(adapter._send_loop())
        
        # Run MediaStreamHandler in thread
        handler = MediaStreamHandler(adapter)
        
        def run_handler():
            try:
                handler.run()
            except Exception as e:
                log.exception(f"Handler error: {e}")
        
        # Start handler in background thread
        import threading
        handler_thread = threading.Thread(target=run_handler, daemon=True)
        handler_thread.start()
        
        # Wait for handler thread to finish
        await asyncio.get_event_loop().run_in_executor(None, handler_thread.join)
        
        # Stop adapter
        adapter.stop()
        
        # Cancel background tasks
        receive_task.cancel()
        send_task.cancel()
        
    except Exception as e:
        log.exception(f"WebSocket error: {e}")
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
        log.info(f"📞 WebSocket closed call={call_sid}")

# ASGI Application with Starlette
asgi_app = Starlette(routes=[
    WebSocketRoute("/ws/twilio-media", ws_twilio_media),
    Mount("/", app=WsgiToAsgi(flask_app)),
])
