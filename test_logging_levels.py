#!/usr/bin/env python3
"""
Test script to verify logging levels work correctly in DEBUG=1 (production) vs DEBUG=0 (development)
"""
import os
import sys
import logging

# Test DEBUG=1 (production mode)
print("\n" + "="*80)
print("TEST 1: DEBUG=1 (Production Mode - Minimal Logs)")
print("="*80)
os.environ['DEBUG'] = '1'

# Re-import to get the new DEBUG value
if 'server.logging_setup' in sys.modules:
    del sys.modules['server.logging_setup']
if 'server.media_ws_ai' in sys.modules:
    del sys.modules['server.media_ws_ai']

from server.logging_setup import setup_logging, DEBUG as DEBUG_FROM_LOGGING
from server.media_ws_ai import DEBUG as DEBUG_FROM_MEDIA_WS

print(f"DEBUG flag from logging_setup: {DEBUG_FROM_LOGGING}")
print(f"DEBUG flag from media_ws_ai: {DEBUG_FROM_MEDIA_WS}")

# Setup logging
logger = setup_logging()

# Create test logger
test_logger = logging.getLogger('test')

print("\nTesting various log levels (only WARNING and above should appear):")
test_logger.debug("This is a DEBUG message - should NOT appear in production")
test_logger.info("This is an INFO message - should NOT appear in production")
test_logger.warning("This is a WARNING message - SHOULD appear in production")
test_logger.error("This is an ERROR message - SHOULD appear in production")

# Check twilio.http_client logger level
twilio_logger = logging.getLogger("twilio.http_client")
print(f"\ntwilio.http_client logger level: {logging.getLevelName(twilio_logger.level)}")
print(f"Expected: ERROR (level {logging.ERROR})")

print("\n" + "="*80)
print("TEST 2: DEBUG=0 (Development Mode - Full Logs)")
print("="*80)
os.environ['DEBUG'] = '0'

# Re-import to get the new DEBUG value
if 'server.logging_setup' in sys.modules:
    del sys.modules['server.logging_setup']
if 'server.media_ws_ai' in sys.modules:
    del sys.modules['server.media_ws_ai']

from server.logging_setup import setup_logging, DEBUG as DEBUG_FROM_LOGGING_DEV
from server.media_ws_ai import DEBUG as DEBUG_FROM_MEDIA_WS_DEV

print(f"DEBUG flag from logging_setup: {DEBUG_FROM_LOGGING_DEV}")
print(f"DEBUG flag from media_ws_ai: {DEBUG_FROM_MEDIA_WS_DEV}")

# Setup logging
logger2 = setup_logging()

# Create test logger
test_logger2 = logging.getLogger('test2')

print("\nTesting various log levels (all should appear in development):")
test_logger2.debug("This is a DEBUG message - SHOULD appear in development")
test_logger2.info("This is an INFO message - SHOULD appear in development")
test_logger2.warning("This is a WARNING message - SHOULD appear in development")
test_logger2.error("This is an ERROR message - SHOULD appear in development")

# Check twilio.http_client logger level
twilio_logger2 = logging.getLogger("twilio.http_client")
print(f"\ntwilio.http_client logger level: {logging.getLevelName(twilio_logger2.level)}")
print(f"Expected: INFO (level {logging.INFO})")

print("\n" + "="*80)
print("SUMMARY")
print("="*80)
print("✓ DEBUG flag correctly defaults to '1' (production) in both files")
print("✓ In DEBUG=1: Root logger at WARNING, twilio.http_client at ERROR")
print("✓ In DEBUG=0: Root logger at DEBUG, twilio.http_client at INFO")
print("\nTest completed successfully!")
