#!/usr/bin/env python3
"""
Debug script to test what happens in AI mode
"""

import os
import time

# Set environment for AI mode
os.environ['WS_MODE'] = 'AI'
os.environ['HEBREW_REALTIME_ENABLED'] = 'true'

print("🎯 Testing AI mode configuration...")
print(f"WS_MODE = {os.getenv('WS_MODE')}")
print(f"HEBREW_REALTIME_ENABLED = {os.getenv('HEBREW_REALTIME_ENABLED')}")

try:
    from server.media_ws import HEBREW_REALTIME_ENABLED, MediaStreamHandler
    print(f"🔍 HEBREW_REALTIME_ENABLED in media_ws = {HEBREW_REALTIME_ENABLED}")
    
    # Test מה קורה כשמתחילים WebSocket handler
    print("🔧 Testing MediaStreamHandler creation...")
    
    # Dummy WebSocket object for testing
    class DummyWS:
        def receive(self):
            return None
            
    dummy_ws = DummyWS()
    handler = MediaStreamHandler(dummy_ws)
    
    print(f"✅ Handler created successfully")
    print(f"🔍 Handler has STT: {handler.stt is not None}")
    
except Exception as e:
    print(f"❌ Error in handler creation: {e}")
    import traceback
    traceback.print_exc()

