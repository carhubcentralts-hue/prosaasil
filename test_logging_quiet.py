#!/usr/bin/env python3
"""
Test script to verify DEBUG=1 (production) logging is quiet
Should only show WARNING/ERROR/CRITICAL, no INFO/DEBUG spam
"""
import os
import sys
import logging

# Set production mode
os.environ['DEBUG'] = '1'

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 80)
print("TESTING PRODUCTION LOGGING (DEBUG=1)")
print("=" * 80)
print()

# Import logging_setup
from server.logging_setup import setup_logging

# Setup logging
root_logger = setup_logging()

print(f"✅ Root logger level: {logging.getLevelName(root_logger.level)}")
print(f"   Expected: WARNING (30)")
print()

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
uvicorn_access_logger = logging.getLogger("uvicorn.access")
print("🔍 Uvicorn logger levels:")
print(f"   uvicorn.access: {logging.getLevelName(uvicorn_access_logger.level)} (propagate={uvicorn_access_logger.propagate})")
print(f"   Expected: WARNING (30) with propagate=False")
print()

# Test that INFO logs are suppressed
print("🧪 Testing log suppression:")
print()

test_logger = logging.getLogger("test_module")

print("   Sending INFO log (should NOT appear):")
test_logger.info("This INFO log should be suppressed in production")

print("   Sending WARNING log (should appear):")
test_logger.warning("This WARNING log should appear in production")

print("   Sending ERROR log (should appear):")
test_logger.error("This ERROR log should appear in production")

print()

# Test twilio logger directly
print("🧪 Testing Twilio logger suppression:")
print()

print("   Sending INFO to twilio.http_client (should NOT appear):")
twilio_http_logger.info("-- BEGIN Twilio API Request -- (should be suppressed)")

print("   Sending WARNING to twilio.http_client (should NOT appear due to ERROR level):")
twilio_http_logger.warning("Twilio WARNING (should be suppressed)")

print("   Sending ERROR to twilio.http_client (should appear):")
twilio_http_logger.error("Twilio ERROR (should appear)")

print()
print("=" * 80)
print("TEST COMPLETE")
print("=" * 80)
print()
print("✅ Expected output:")
print("   - Root logger at WARNING level")
print("   - Twilio loggers at ERROR level with propagate=False")
print("   - NO INFO logs visible")
print("   - Only WARNING and ERROR logs visible")
print("   - NO 'BEGIN Twilio API Request' spam")
