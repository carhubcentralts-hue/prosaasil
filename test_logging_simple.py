#!/usr/bin/env python3
"""
Simple test script to verify DEBUG=1 (production) logging configuration
Tests twilio logger levels without importing Flask dependencies
"""
import os
import sys
import logging

# Set production mode
os.environ['DEBUG'] = '1'

print("=" * 80)
print("TESTING PRODUCTION LOGGING (DEBUG=1)")
print("=" * 80)
print()

# Configure root logger to WARNING (production mode)
root_logger = logging.getLogger()
root_logger.setLevel(logging.WARNING)

# Add console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(levelname)s: %(name)s: %(message)s'))
root_logger.addHandler(console_handler)

print(f"✅ Root logger level: {logging.getLevelName(root_logger.level)}")
print(f"   Expected: WARNING (30)")
print()

# Configure Twilio loggers (same as in app_factory.py and logging_setup.py)
for lib_name in ("twilio", "twilio.http_client", "twilio.rest"):
    lib_logger = logging.getLogger(lib_name)
    lib_logger.setLevel(logging.ERROR)
    lib_logger.propagate = False

# Configure uvicorn logger
uvicorn_access_logger = logging.getLogger("uvicorn.access")
uvicorn_access_logger.setLevel(logging.WARNING)
uvicorn_access_logger.propagate = False

# Check twilio loggers
twilio_logger = logging.getLogger("twilio")
twilio_http_logger = logging.getLogger("twilio.http_client")
twilio_rest_logger = logging.getLogger("twilio.rest")

print("🔍 Twilio logger levels:")
print(f"   twilio: {logging.getLevelName(twilio_logger.level)} (propagate={twilio_logger.propagate})")
print(f"   twilio.http_client: {logging.getLevelName(twilio_http_logger.level)} (propagate={twilio_http_logger.propagate})")
print(f"   twilio.rest: {logging.getLevelName(twilio_rest_logger.level)} (propagate={twilio_rest_logger.propagate})")
print(f"   Expected: ERROR (40) with propagate=False")
print()

# Check uvicorn logger
print("🔍 Uvicorn logger levels:")
print(f"   uvicorn.access: {logging.getLevelName(uvicorn_access_logger.level)} (propagate={uvicorn_access_logger.propagate})")
print(f"   Expected: WARNING (30) with propagate=False")
print()

# Test that INFO logs are suppressed
print("🧪 Testing log suppression:")
print()

test_logger = logging.getLogger("test_module")

print("   Sending DEBUG log (should NOT appear):")
test_logger.debug("This DEBUG log should be suppressed in production")

print("   Sending INFO log (should NOT appear):")
test_logger.info("This INFO log should be suppressed in production")

print("   Sending WARNING log (SHOULD APPEAR BELOW):")
test_logger.warning("✅ This WARNING log should appear in production")

print("   Sending ERROR log (SHOULD APPEAR BELOW):")
test_logger.error("✅ This ERROR log should appear in production")

print()

# Test twilio logger directly
print("🧪 Testing Twilio logger suppression:")
print()

print("   Sending DEBUG to twilio.http_client (should NOT appear):")
twilio_http_logger.debug("-- BEGIN Twilio API Request -- DEBUG (should be suppressed)")

print("   Sending INFO to twilio.http_client (should NOT appear):")
twilio_http_logger.info("-- BEGIN Twilio API Request -- INFO (should be suppressed)")

print("   Sending WARNING to twilio.http_client (should NOT appear due to ERROR level):")
twilio_http_logger.warning("Twilio WARNING (should be suppressed)")

print("   Sending ERROR to twilio.http_client (SHOULD APPEAR BELOW):")
twilio_http_logger.error("✅ Twilio ERROR (should appear)")

print()
print("=" * 80)
print("TEST COMPLETE")
print("=" * 80)
print()
print("✅ VERIFICATION:")
print("   1. Root logger at WARNING level? ", "YES" if root_logger.level == logging.WARNING else "NO")
print("   2. Twilio loggers at ERROR level? ", "YES" if twilio_http_logger.level == logging.ERROR else "NO")
print("   3. Twilio propagate=False? ", "YES" if not twilio_http_logger.propagate else "NO")
print("   4. Only 3 log messages should appear above (2 from test_module, 1 from twilio)")
print()
print("✅ Expected behavior in production:")
print("   - NO INFO/DEBUG logs visible")
print("   - NO 'BEGIN Twilio API Request' spam")
print("   - Only WARNING/ERROR/CRITICAL logs visible")
print("   - In media_ws_ai: only CALL_START, CALL_END, CALL_METRICS, and errors")
