#!/usr/bin/env python3
print("🔍 Testing Hebrew services import...")

try:
    from server.services.gcp_stt_stream import GcpHebrewStreamer
    print("✅ GcpHebrewStreamer imported successfully")
    stt_ok = True
except ImportError as e:
    print(f"❌ GcpHebrewStreamer import failed: {e}")
    stt_ok = False

try:
    from server.services.gcp_tts_live import generate_hebrew_response
    print("✅ generate_hebrew_response imported successfully")
    tts_ok = True
except ImportError as e:
    print(f"❌ generate_hebrew_response import failed: {e}")
    tts_ok = False

HEBREW_REALTIME_ENABLED = stt_ok and tts_ok
print(f"🎯 HEBREW_REALTIME_ENABLED = {HEBREW_REALTIME_ENABLED}")

if HEBREW_REALTIME_ENABLED:
    print("✅ All Hebrew services available - AI mode should work!")
else:
    print("❌ Hebrew services not available - AI mode will be silent!")
    print("🔧 Need to fix the imports or credentials")
