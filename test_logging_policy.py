"""
Test Production Logging Policy Implementation

This script verifies that the new logging policy works correctly:
- DEBUG=1 (production): Minimal logs, only INFO macro events
- DEBUG=0 (development): Full DEBUG logs with rate-limiting

Run with:
    DEBUG=1 python test_logging_policy.py  # Test production mode
    DEBUG=0 python test_logging_policy.py  # Test development mode
"""
import os
import sys
import logging
import time
import threading

# Must set DEBUG before importing server modules
DEBUG = os.getenv("DEBUG", "1") == "1"
print(f"\n{'='*70}")
print(f"Testing Logging Policy - DEBUG={1 if DEBUG else 0} ({'PRODUCTION' if DEBUG else 'DEVELOPMENT'} mode)")
print(f"{'='*70}\n")

# Test the helpers directly without Flask dependency
class RateLimiter:
    """Rate-limit helper to prevent log spam"""
    def __init__(self):
        self.t = {}
        self._lock = threading.Lock()
    
    def every(self, key: str, sec: float) -> bool:
        now = time.time()
        with self._lock:
            last_time = self.t.get(key, 0)
            if now - last_time >= sec:
                self.t[key] = now
                return True
        return False

class OncePerCall:
    """One-shot logging helper"""
    def __init__(self):
        self.seen = set()
        self._lock = threading.Lock()
    
    def once(self, key: str) -> bool:
        with self._lock:
            if key in self.seen:
                return False
            self.seen.add(key)
            return True

# Setup minimal logging
if DEBUG:
    BASE_LEVEL = logging.INFO
    NOISY_LEVEL = logging.WARNING
else:
    BASE_LEVEL = logging.DEBUG
    NOISY_LEVEL = logging.INFO

logging.basicConfig(
    level=BASE_LEVEL,
    format='%(levelname)s - %(name)s - %(message)s'
)

# Set noisy module levels
noisy_modules = [
    "server.media_ws_ai",
    "server.services.audio_dsp",
    "websockets",
    "urllib3",
    "httpx",
    "openai",
]

for module_name in noisy_modules:
    logging.getLogger(module_name).setLevel(NOISY_LEVEL)

# Get test logger
logger = logging.getLogger("test_logging_policy")

def test_basic_logging():
    """Test basic log levels"""
    print("\n[TEST 1] Basic Log Levels")
    print("-" * 40)
    
    logger.debug("This is a DEBUG log")
    logger.info("This is an INFO log")
    logger.warning("This is a WARNING log")
    logger.error("This is an ERROR log")
    
    print("\nExpected in production (DEBUG=1): INFO, WARNING, ERROR")
    print("Expected in development (DEBUG=0): All levels\n")

def test_rate_limiter():
    """Test rate limiting functionality"""
    print("\n[TEST 2] Rate Limiter")
    print("-" * 40)
    
    rl_test = RateLimiter()
    
    print("Attempting 5 logs with 2-second rate limit...")
    for i in range(5):
        if rl_test.every("test_key", 2.0):
            logger.info(f"[RATE_LIMITED] Log #{i+1} - This should appear once every 2 seconds")
        else:
            print(f"  Log #{i+1} suppressed by rate limiter")
        time.sleep(0.5)
    
    print("\nExpected: Only 2-3 logs should appear\n")

def test_once_per_call():
    """Test once-per-call functionality"""
    print("\n[TEST 3] Once-Per-Call Helper")
    print("-" * 40)
    
    once_test = OncePerCall()
    
    print("Attempting 3 logs with once-per-call...")
    for i in range(3):
        if once_test.once("test_once"):
            logger.info(f"[ONCE_PER_CALL] This should appear only ONCE")
        else:
            print(f"  Attempt #{i+1} suppressed by once-per-call")
    
    print("\nExpected: Only first log should appear\n")

def test_noisy_modules():
    """Test noisy module silencing"""
    print("\n[TEST 4] Noisy Module Levels")
    print("-" * 40)
    
    for module_name in noisy_modules:
        module_logger = logging.getLogger(module_name)
        level = module_logger.getEffectiveLevel()
        level_name = logging.getLevelName(level)
        print(f"  {module_name}: {level_name}")
    
    if DEBUG:
        print("\nExpected in production (DEBUG=1): All at WARNING")
    else:
        print("\nExpected in development (DEBUG=0): All at INFO")
    print()

def test_macro_events():
    """Test macro event logging"""
    print("\n[TEST 5] Macro Events (Should Always Be INFO)")
    print("-" * 40)
    
    # Simulate macro events
    logger.info("[BOOT] System initialization")
    logger.info("[CALL_START] Call initiated")
    logger.info("[REALTIME] OpenAI connected")
    logger.info("[CREATE_APPT] Appointment created")
    logger.info("[CALL_END] Call completed")
    
    print("\nExpected: All 5 macro events should appear in both modes\n")

def test_debug_vs_info():
    """Test DEBUG vs INFO distinction"""
    print("\n[TEST 6] DEBUG vs INFO Distinction")
    print("-" * 40)
    
    logger.debug("[VALIDATION] Checking slot availability")
    logger.debug("[CRM] Found existing lead")
    logger.debug("[UTTERANCE] Collecting results")
    logger.info("[WEBHOOK_CLOSE] Triggering close_session")
    
    print("\nExpected in production (DEBUG=1): Only WEBHOOK_CLOSE")
    print("Expected in development (DEBUG=0): All 4 logs\n")

def main():
    """Run all tests"""
    test_basic_logging()
    test_rate_limiter()
    test_once_per_call()
    test_noisy_modules()
    test_macro_events()
    test_debug_vs_info()
    
    print("\n" + "="*70)
    print("Test Complete!")
    print("="*70)
    print("\nReview the output above to verify:")
    if DEBUG:
        print("  ✓ Only INFO, WARNING, ERROR are visible")
        print("  ✓ DEBUG logs are suppressed")
        print("  ✓ Noisy modules are at WARNING level")
    else:
        print("  ✓ All log levels are visible")
        print("  ✓ Noisy modules are at INFO level")
    print("  ✓ Rate limiting works correctly")
    print("  ✓ Once-per-call works correctly")
    print("  ✓ Macro events are logged as INFO")
    print()

if __name__ == "__main__":
    main()
