#!/usr/bin/env python3
"""
ASGI Application Wrapper for Cloud Run WebSocket Support
Wraps Flask WSGI app with WebSocket handling
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import after path setup
from asgiref.wsgi import WsgiToAsgi
from wsgi import flask_app, ws_handler
import asyncio

# Wrap Flask WSGI app to ASGI
app = WsgiToAsgi(flask_app)

# Add WebSocket route handler
async def websocket_application(scope, receive, send):
    """Handle WebSocket connections"""
    if scope['type'] == 'websocket' and scope['path'] in ('/ws/twilio-media', '/ws/twilio-media/'):
        await handle_websocket(scope, receive, send)
    elif scope['type'] == 'http':
        # Pass HTTP requests to Flask
        await app(scope, receive, send)
    else:
        # Reject other connection types
        await send({
            'type': 'websocket.close',
            'code': 1000,
        })

async def handle_websocket(scope, receive, send):
    """WebSocket connection handler for Twilio Media Streams"""
    # Accept the WebSocket connection
    await send({
        'type': 'websocket.accept',
        'subprotocol': 'audio.twilio.com',  # Twilio subprotocol
    })
    
    print(f"📞 WebSocket connected: {scope['path']}", flush=True)
    
    # Create a synchronous WebSocket wrapper for MediaStreamHandler
    import threading
    import queue
    
    class ASGISyncWebSocket:
        """Wrapper that converts ASGI WebSocket to sync interface for MediaStreamHandler"""
        def __init__(self, scope, receive, send):
            self.scope = scope
            self._receive = receive
            self._send = send
            self.receive_queue = queue.Queue()
            self.send_queue = queue.Queue()
            self.running = True
            self.loop = asyncio.get_event_loop()
            
        def send(self, data):
            """Sync send - queues data for async sending"""
            self.send_queue.put(data)
            
        def recv(self):
            """Sync receive - blocks until data available"""
            return self.receive_queue.get(timeout=30)
            
        async def _async_receiver(self):
            """Async task to receive WebSocket messages"""
            try:
                while self.running:
                    message = await self._receive()
                    if message['type'] == 'websocket.receive':
                        data = message.get('text') or message.get('bytes')
                        if data:
                            self.receive_queue.put(data)
                    elif message['type'] == 'websocket.disconnect':
                        self.running = False
                        break
            except Exception as e:
                print(f"❌ Async receiver error: {e}")
                self.running = False
                
        async def _async_sender(self):
            """Async task to send WebSocket messages"""
            try:
                while self.running:
                    try:
                        data = self.send_queue.get(timeout=0.1)
                        if isinstance(data, str):
                            await self._send({
                                'type': 'websocket.send',
                                'text': data,
                            })
                        else:
                            await self._send({
                                'type': 'websocket.send',
                                'bytes': data,
                            })
                    except queue.Empty:
                        await asyncio.sleep(0.01)
            except Exception as e:
                print(f"❌ Async sender error: {e}")
                self.running = False
    
    ws = ASGISyncWebSocket(scope, receive, send)
    
    # Start async tasks for send/receive
    receive_task = asyncio.create_task(ws._async_receiver())
    send_task = asyncio.create_task(ws._async_sender())
    
    try:
        # Run MediaStreamHandler in a thread
        from server.media_ws_ai import MediaStreamHandler
        handler = MediaStreamHandler(ws)
        
        # Run handler in thread pool
        await asyncio.to_thread(handler.run)
        
    except Exception as e:
        print(f"❌ WebSocket handler error: {e}", flush=True)
        import traceback
        traceback.print_exc()
    finally:
        ws.running = False
        receive_task.cancel()
        send_task.cancel()
        
        try:
            await send({
                'type': 'websocket.close',
                'code': 1000,
            })
        except:
            pass

# Export the application
app = websocket_application
