#!/usr/bin/env python3
"""
Test WebSocket connection directly
"""
import websocket
import json
import time
import threading

def on_message(ws, message):
    print(f"📨 Received: {message}")

def on_error(ws, error):
    print(f"❌ WebSocket Error: {error}")

def on_close(ws, close_status_code, close_msg):
    print(f"🔒 WebSocket Closed: {close_status_code}, {close_msg}")

def on_open(ws):
    print("✅ WebSocket Connected!")
    
    # Send a test start message like Twilio would
    start_msg = {
        "event": "start",
        "start": {
            "streamSid": "MZ_test_stream",
            "callSid": "CA_test_call"
        }
    }
    
    print(f"📤 Sending start: {start_msg}")
    ws.send(json.dumps(start_msg))
    
    # Send a test media frame
    time.sleep(1)
    media_msg = {
        "event": "media",
        "media": {
            "payload": "uLaw8kHzMono"  # dummy payload
        }
    }
    
    print(f"📤 Sending media: {media_msg}")
    ws.send(json.dumps(media_msg))
    
    # Close after 3 seconds
    time.sleep(3)
    print("🔒 Closing connection...")
    ws.close()

if __name__ == "__main__":
    websocket.enableTrace(True)
    ws = websocket.WebSocketApp("wss://ai-crmd.replit.app/ws/twilio-media",
                              on_open=on_open,
                              on_message=on_message,
                              on_error=on_error,
                              on_close=on_close)
    
    print("🔗 Attempting WebSocket connection...")
    ws.run_forever()
