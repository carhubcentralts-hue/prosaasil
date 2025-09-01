#!/usr/bin/env python3
"""
Simple WebSocket test script for debugging Twilio connection
"""
import asyncio
import websockets
import json

async def test_websocket_connection():
    uri = "wss://ai-crmd.replit.app/ws/twilio-media"
    
    headers = {
        'Sec-WebSocket-Protocol': 'audio.twilio.com'
    }
    
    print(f"🔗 Connecting to: {uri}")
    print(f"📋 Headers: {headers}")
    
    try:
        async with websockets.connect(uri, extra_headers=headers, timeout=10) as websocket:
            print("✅ WebSocket connection established!")
            
            # Send a test message like Twilio would
            test_message = {
                "event": "connected",
                "protocol": "audio.twilio.com",
                "version": "1.0.0"
            }
            
            await websocket.send(json.dumps(test_message))
            print(f"📤 Sent: {test_message}")
            
            # Wait for response
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                print(f"📥 Received: {response}")
            except asyncio.TimeoutError:
                print("⏰ No response within 5 seconds (may be normal)")
            
            print("✅ WebSocket test completed successfully")
            
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"❌ WebSocket handshake failed: {e}")
        print(f"   Status code: {e.status_code}")
        if hasattr(e, 'headers'):
            print(f"   Response headers: {e.headers}")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print(f"   Error type: {type(e).__name__}")

if __name__ == "__main__":
    asyncio.run(test_websocket_connection())