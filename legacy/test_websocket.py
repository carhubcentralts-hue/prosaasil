#!/usr/bin/env python3
"""
Simple WebSocket test without async
"""
import json
import socket

def test_websocket_simple():
    """Simple test to see if WebSocket endpoint responds"""
    try:
        print("🔗 Testing WebSocket endpoint availability")
        
        # Try to connect to see if endpoint exists
        import requests
        resp = requests.get("http://localhost:5000/ws/twilio-media", timeout=2)
        print(f"HTTP response: {resp.status_code}")
        
        # If we get 400, it means endpoint exists but expects WebSocket
        if resp.status_code == 400:
            print("✅ WebSocket endpoint exists (400 is expected for HTTP to WS endpoint)")
            print("🎯 Ready for Twilio Media Streams connections!")
            return True
        else:
            print(f"❌ Unexpected response: {resp.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False

if __name__ == "__main__":
    test_websocket_simple()