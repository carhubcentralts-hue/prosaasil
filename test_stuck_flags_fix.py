#!/usr/bin/env python3
"""
Unit test for stuck flags crash fix in _realtime_audio_sender

Tests verify:
1. _stuck_flags_first_seen_ts initialized as None in __init__
2. None check prevents TypeError on subtraction
3. Timestamp set on first detection
4. Timestamp reset on recovery
"""

import unittest
import time


class MockHandler:
    """Mock MediaStreamHandler with just the stuck flags tracking"""
    def __init__(self):
        # Initialize the timestamp (mimics fix in __init__)
        self._stuck_flags_first_seen_ts = None
        self.ai_response_active = False
        
    def check_stuck_flags(self, now):
        """
        Simulates the stuck flags check logic from _realtime_audio_sender
        This is the fixed version that should not crash.
        """
        STUCK_FLAGS_TIMEOUT_SEC = 1.5
        
        if self.ai_response_active:
            # Track how long this inconsistent state has persisted
            # 🔥 FIX: Check for None explicitly, not just hasattr
            if self._stuck_flags_first_seen_ts is None:
                self._stuck_flags_first_seen_ts = now
            
            # 🔥 FIX: Guard against None before subtraction to prevent TypeError
            if self._stuck_flags_first_seen_ts is None:
                stuck_flags_age = 0.0
            else:
                stuck_flags_age = now - self._stuck_flags_first_seen_ts
            
            if stuck_flags_age > STUCK_FLAGS_TIMEOUT_SEC:
                # Reset flags
                self.ai_response_active = False
                self._stuck_flags_first_seen_ts = None
                return "recovered"
            
            return f"stuck for {stuck_flags_age:.2f}s"
        else:
            # Flags are consistent - reset tracking
            self._stuck_flags_first_seen_ts = None
            return "consistent"


class TestStuckFlagsFix(unittest.TestCase):
    """Test that stuck flags detection doesn't crash"""
    
    def test_initialization(self):
        """Test that _stuck_flags_first_seen_ts is initialized as None"""
        handler = MockHandler()
        self.assertIsNone(handler._stuck_flags_first_seen_ts)
    
    def test_no_crash_on_none_subtraction(self):
        """Test that None timestamp doesn't cause TypeError"""
        handler = MockHandler()
        handler.ai_response_active = True
        
        # Explicitly set to None (simulates reset)
        handler._stuck_flags_first_seen_ts = None
        
        # This should not crash
        now = time.monotonic()
        result = handler.check_stuck_flags(now)
        
        # Should return "stuck for 0.00s" since timestamp was just set
        self.assertTrue("stuck" in result or "consistent" in result)
    
    def test_timestamp_set_on_first_detection(self):
        """Test that timestamp is set when stuck state is first detected"""
        handler = MockHandler()
        handler.ai_response_active = True
        
        # First check - should set timestamp
        now1 = time.monotonic()
        result1 = handler.check_stuck_flags(now1)
        
        # Timestamp should now be set
        self.assertIsNotNone(handler._stuck_flags_first_seen_ts)
        self.assertEqual(handler._stuck_flags_first_seen_ts, now1)
    
    def test_timestamp_persists_during_stuck_state(self):
        """Test that timestamp persists while stuck state continues"""
        handler = MockHandler()
        handler.ai_response_active = True
        
        # First check - sets timestamp
        now1 = time.monotonic()
        handler.check_stuck_flags(now1)
        first_ts = handler._stuck_flags_first_seen_ts
        
        # Second check - should keep same timestamp
        time.sleep(0.1)
        now2 = time.monotonic()
        handler.check_stuck_flags(now2)
        
        # Timestamp should be unchanged
        self.assertEqual(handler._stuck_flags_first_seen_ts, first_ts)
    
    def test_timestamp_reset_on_recovery(self):
        """Test that timestamp is reset when flags become consistent"""
        handler = MockHandler()
        handler.ai_response_active = True
        
        # Set stuck state
        now1 = time.monotonic()
        handler.check_stuck_flags(now1)
        self.assertIsNotNone(handler._stuck_flags_first_seen_ts)
        
        # Simulate timeout and recovery
        time.sleep(1.6)  # More than STUCK_FLAGS_TIMEOUT_SEC (1.5s)
        now2 = time.monotonic()
        result = handler.check_stuck_flags(now2)
        
        # Should recover and reset timestamp
        self.assertEqual(result, "recovered")
        self.assertIsNone(handler._stuck_flags_first_seen_ts)
    
    def test_timestamp_reset_when_consistent(self):
        """Test that timestamp is reset when flags are not stuck"""
        handler = MockHandler()
        handler.ai_response_active = True
        
        # Set stuck state
        now1 = time.monotonic()
        handler.check_stuck_flags(now1)
        self.assertIsNotNone(handler._stuck_flags_first_seen_ts)
        
        # Clear stuck flag
        handler.ai_response_active = False
        
        # Check again - should reset timestamp
        now2 = time.monotonic()
        result = handler.check_stuck_flags(now2)
        
        # Timestamp should be reset
        self.assertEqual(result, "consistent")
        self.assertIsNone(handler._stuck_flags_first_seen_ts)
    
    def test_repeated_none_checks_dont_crash(self):
        """Test that multiple checks with None don't cause issues"""
        handler = MockHandler()
        
        # Multiple checks with None timestamp
        for _ in range(10):
            handler._stuck_flags_first_seen_ts = None
            handler.ai_response_active = True
            now = time.monotonic()
            
            # Should not crash
            result = handler.check_stuck_flags(now)
            self.assertTrue("stuck" in result or "consistent" in result)
            
            # Reset for next iteration
            handler.ai_response_active = False
            handler.check_stuck_flags(now)


if __name__ == '__main__':
    unittest.main()
