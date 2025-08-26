"""
WebSocket Server עם websockets library - תחליף לFlask-Sock
"""
import asyncio
import websockets
import json
import base64
import time
import os
# from .media_ws import MediaStreamHandler  # Will implement directly here

class TwilioWebSocketHandler:
    def __init__(self, websocket):
        self.websocket = websocket
        # Direct implementation instead of MediaStreamHandler
        
    async def handle_connection(self):
        """Handle Twilio WebSocket connection"""
        print(f"🚨 WEBSOCKET_CONNECTED: Native websockets at {time.time()}")
        
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    event_type = data.get("event")
                    
                    if event_type == "start":
                        stream_sid = data["start"]["streamSid"]
                        print(f"🚨 WEBSOCKET_START: {stream_sid}")
                        
                    elif event_type == "media":
                        print(f"🚨 MEDIA_FRAME_RECEIVED: Processing...")
                        # Process media frame
                        await self.process_media(data["media"])
                        
                    elif event_type == "stop":
                        print(f"🚨 WEBSOCKET_STOP")
                        break
                        
                except json.JSONDecodeError:
                    print("❌ Invalid JSON received")
                    continue
                    
        except websockets.exceptions.ConnectionClosed:
            print("🔒 WebSocket connection closed")
        except Exception as e:
            print(f"❌ WebSocket error: {e}")
            
    async def process_media(self, media_data):
        """Process media frame - Hebrew STT + AI + TTS"""
        try:
            # Get the base64 payload
            b64_payload = media_data["payload"]
            
            # Convert to audio data
            import audioop
            mulaw_data = base64.b64decode(b64_payload)
            pcm16_data = audioop.ulaw2lin(mulaw_data, 2)
            
            print(f"🚨 AUDIO_PROCESSED: {len(pcm16_data)} bytes")
            
            # TODO: Send to Hebrew STT
            # TODO: Generate AI response
            # TODO: Convert to Hebrew TTS
            # TODO: Send back to Twilio
            
            return True
            
        except Exception as e:
            print(f"❌ Media processing error: {e}")
            return False

async def twilio_websocket_handler(websocket, path):
    """Main WebSocket handler for Twilio Media Streams"""
    if path == "/ws/twilio-media" or path == "/ws/twilio-media/":
        handler = TwilioWebSocketHandler(websocket)
        await handler.handle_connection()
    else:
        print(f"❌ Invalid WebSocket path: {path}")

def start_websocket_server(host="0.0.0.0", port=8765):
    """Start the WebSocket server"""
    print(f"🚀 Starting WebSocket server on {host}:{port}")
    
    return websockets.serve(
        twilio_websocket_handler,
        host,
        port,
        subprotocols=[]
    )