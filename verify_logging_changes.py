#!/usr/bin/env python3
"""
Simple test to verify DEBUG flag defaults
"""
import os
import sys

print("\n" + "="*80)
print("Verifying DEBUG flag defaults in source files")
print("="*80)

# Check logging_setup.py
with open('server/logging_setup.py', 'r') as f:
    content = f.read()
    if 'DEBUG = os.getenv("DEBUG", "1") == "1"' in content:
        print("✓ logging_setup.py: DEBUG defaults to '1' (production mode)")
    else:
        print("✗ logging_setup.py: DEBUG flag incorrect")

# Check media_ws_ai.py
with open('server/media_ws_ai.py', 'r') as f:
    content = f.read()
    if 'DEBUG = os.getenv("DEBUG", "1") == "1"' in content:
        print("✓ media_ws_ai.py: DEBUG defaults to '1' (production mode)")
    else:
        print("✗ media_ws_ai.py: DEBUG flag incorrect")

# Check for twilio.http_client logging
with open('server/logging_setup.py', 'r') as f:
    content = f.read()
    if 'logging.getLogger("twilio.http_client").setLevel(logging.ERROR)' in content:
        print("✓ logging_setup.py: twilio.http_client set to ERROR in production")
    else:
        print("✗ logging_setup.py: twilio.http_client not set correctly")

# Check that verbose logs were converted to logger.debug()
verbose_checks = [
    ('[AUDIO_DELTA]', 'logger.debug(f"[AUDIO_DELTA]'),
    ('[PIPELINE STATUS]', 'logger.debug('),
    ('[FRAME_METRICS]', 'logger.debug(f"[FRAME_METRICS]'),
    ('[STT_RAW]', 'logger.debug(f"[STT_RAW]'),
    ('[BARGE-IN DEBUG]', 'logger.debug(f"[BARGE-IN DEBUG]'),
    ('WS_KEEPALIVE', 'logger.debug(f"WS_KEEPALIVE'),
]

print("\nChecking converted verbose logs in media_ws_ai.py:")
with open('server/media_ws_ai.py', 'r') as f:
    content = f.read()
    for log_name, expected_pattern in verbose_checks:
        if expected_pattern in content:
            print(f"✓ {log_name} converted to logger.debug()")
        else:
            print(f"⚠ {log_name} may not be fully converted")

# Check openai_realtime_client.py
print("\nChecking openai_realtime_client.py:")
with open('server/services/openai_realtime_client.py', 'r') as f:
    content = f.read()
    if 'logger.debug(' in content and 'got audio chunk from OpenAI' in content:
        print("✓ Audio chunk logs converted to logger.debug()")
    else:
        print("⚠ Audio chunk logs may not be converted")

# Check for [CALL_START] and [CALL_END] logs
print("\nChecking [CALL_START] and [CALL_END] logs:")
with open('server/media_ws_ai.py', 'r') as f:
    content = f.read()
    if 'logger.warning(f"[CALL_START] call_sid=' in content:
        print("✓ [CALL_START] log added with WARNING level")
    else:
        print("⚠ [CALL_START] log not found")
    
    if 'logger.warning(f"[CALL_END] call_sid=' in content:
        print("✓ [CALL_END] log added with WARNING level")
    else:
        print("⚠ [CALL_END] log not found")

print("\n" + "="*80)
print("Verification completed!")
print("="*80)
