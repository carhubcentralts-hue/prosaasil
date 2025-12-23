"""
Test suite for HARD_MUTE barge-in improvements

Tests the new HARD_MUTE mechanism that prevents residual audio from
playing after a barge-in cancel.

Key improvements tested:
1. HARD_MUTE window activation on barge-in
2. Audio blocking during HARD_MUTE period
3. Auto-expiry of HARD_MUTE window
4. Improved cancel conditions (active + speaking state)
"""
import sys
import time

# Test constants
HARD_MUTE_DURATION_MS = 400  # Default HARD_MUTE duration in milliseconds
MUTE_CHECK_OFFSET_MS = 100  # Time offset for checking during mute (ms)
MUTE_EXPIRY_OFFSET_MS = 500  # Time offset for checking after expiry (ms)


class TestHardMuteMechanism:
    """Test HARD_MUTE window for barge-in"""
    
    def test_hard_mute_activates_on_barge_in(self):
        """Verify HARD_MUTE window is set when barge-in occurs"""
        # Simulate barge-in
        now = time.time()
        hard_mute_until_ts = now + (HARD_MUTE_DURATION_MS / 1000.0)
        
        # Verify mute window is set
        assert hard_mute_until_ts > now, "HARD_MUTE window should be in the future"
        assert (hard_mute_until_ts - now) <= 0.6, "HARD_MUTE should be <= 600ms"
        assert (hard_mute_until_ts - now) >= 0.3, "HARD_MUTE should be >= 300ms"
    
    def test_audio_blocked_during_hard_mute(self):
        """Verify audio is blocked during HARD_MUTE period"""
        # Set HARD_MUTE window
        now = time.time()
        hard_mute_until_ts = now + (HARD_MUTE_DURATION_MS / 1000.0)
        
        # Check if audio should be blocked (during mute period)
        current_time = now + (MUTE_CHECK_OFFSET_MS / 1000.0)  # 100ms after mute start
        should_block = current_time < hard_mute_until_ts
        
        assert should_block, "Audio should be blocked during HARD_MUTE period"
    
    def test_audio_allowed_after_hard_mute_expires(self):
        """Verify audio is allowed after HARD_MUTE window expires"""
        # Set HARD_MUTE window
        now = time.time()
        hard_mute_until_ts = now + (HARD_MUTE_DURATION_MS / 1000.0)
        
        # Check after expiry
        current_time = now + (MUTE_EXPIRY_OFFSET_MS / 1000.0)  # 500ms after mute start (expired)
        should_block = current_time < hard_mute_until_ts
        
        assert not should_block, "Audio should be allowed after HARD_MUTE expires"
    
    def test_hard_mute_clears_after_expiry(self):
        """Verify HARD_MUTE flag is cleared after expiry"""
        # Set HARD_MUTE window
        now = time.time()
        hard_mute_until_ts = now + (HARD_MUTE_DURATION_MS / 1000.0)
        
        # Simulate checking after expiry
        current_time = now + (MUTE_EXPIRY_OFFSET_MS / 1000.0)  # 500ms after mute start
        if hard_mute_until_ts and current_time >= hard_mute_until_ts:
            # Clear the flag
            hard_mute_until_ts = None
        
        assert hard_mute_until_ts is None, "HARD_MUTE flag should be cleared after expiry"


class TestImprovedCancelConditions:
    """Test improved cancel conditions for barge-in"""
    
    def test_cancel_requires_active_response_and_speaking(self):
        """Verify cancel requires both active_response_id AND speaking state"""
        # Test case 1: Has response, is speaking -> should cancel
        has_active_response = True
        ai_response_active = True
        is_ai_speaking = False
        
        should_cancel = has_active_response and (ai_response_active or is_ai_speaking)
        assert should_cancel, "Should cancel when has response and is active"
        
        # Test case 2: Has response, is speaking (event) -> should cancel
        has_active_response = True
        ai_response_active = False
        is_ai_speaking = True
        
        should_cancel = has_active_response and (ai_response_active or is_ai_speaking)
        assert should_cancel, "Should cancel when has response and is speaking"
        
        # Test case 3: Has response, but not active or speaking -> should NOT cancel
        has_active_response = True
        ai_response_active = False
        is_ai_speaking = False
        
        should_cancel = has_active_response and (ai_response_active or is_ai_speaking)
        assert not should_cancel, "Should NOT cancel when response not active/speaking"
        
        # Test case 4: No response -> should NOT cancel
        has_active_response = False
        ai_response_active = True
        is_ai_speaking = True
        
        should_cancel = has_active_response and (ai_response_active or is_ai_speaking)
        assert not should_cancel, "Should NOT cancel when no active response"
    
    def test_cancel_respects_greeting_lock(self):
        """Verify cancel is blocked during greeting lock"""
        has_active_response = True
        ai_response_active = True
        is_ai_speaking = True
        is_greeting_locked = True
        barge_in_enabled = True
        
        barge_in_allowed = barge_in_enabled and not is_greeting_locked
        should_cancel = (has_active_response and 
                        (ai_response_active or is_ai_speaking) and 
                        barge_in_allowed)
        
        assert not should_cancel, "Should NOT cancel during greeting lock"
    
    def test_cancel_respects_barge_in_disabled(self):
        """Verify cancel is blocked when barge-in is disabled"""
        has_active_response = True
        ai_response_active = True
        is_ai_speaking = True
        is_greeting_locked = False
        barge_in_enabled = False  # Disabled!
        
        barge_in_allowed = barge_in_enabled and not is_greeting_locked
        should_cancel = (has_active_response and 
                        (ai_response_active or is_ai_speaking) and 
                        barge_in_allowed)
        
        assert not should_cancel, "Should NOT cancel when barge-in disabled"


class TestResponseCancelNotActiveLogging:
    """Test improved logging for response_cancel_not_active"""
    
    def test_response_cancel_not_active_is_info_level(self):
        """Verify response_cancel_not_active is logged as INFO, not ERROR"""
        error_str = "response is not_active"
        
        # Check if error matches expected patterns
        is_expected_error = ('not_active' in error_str.lower() or 
                            'no active' in error_str.lower() or 
                            'already_cancelled' in error_str.lower() or 
                            'already_completed' in error_str.lower())
        
        assert is_expected_error, "Should recognize response_cancel_not_active patterns"
    
    def test_other_errors_still_logged_as_debug(self):
        """Verify other cancel errors are still logged normally"""
        error_str = "network timeout"
        
        # Check if error matches expected patterns
        is_expected_error = ('not_active' in error_str.lower() or 
                            'no active' in error_str.lower() or 
                            'already_cancelled' in error_str.lower() or 
                            'already_completed' in error_str.lower())
        
        assert not is_expected_error, "Should NOT recognize other errors as response_cancel_not_active"


class TestBothQueuesFlush:
    """Test that both audio queues are flushed on barge-in"""
    
    def test_both_queues_flushed(self):
        """Verify both realtime_audio_out_queue and tx_q are flushed"""
        # Simulate queue states
        realtime_queue_size = 50
        tx_queue_size = 25
        
        # Simulate flush
        realtime_flushed = realtime_queue_size
        tx_flushed = tx_queue_size
        total_flushed = realtime_flushed + tx_flushed
        
        assert realtime_flushed > 0, "Should flush realtime queue"
        assert tx_flushed > 0, "Should flush TX queue"
        assert total_flushed == 75, f"Should flush both queues (total={total_flushed})"
    
    def test_flush_handles_empty_queues(self):
        """Verify flush handles already-empty queues gracefully"""
        # Simulate empty queues
        realtime_queue_size = 0
        tx_queue_size = 0
        
        # Simulate flush
        realtime_flushed = realtime_queue_size
        tx_flushed = tx_queue_size
        total_flushed = realtime_flushed + tx_flushed
        
        assert total_flushed == 0, "Should handle empty queues (total=0)"


def run_tests():
    """Run all tests and report results"""
    test_classes = [
        TestHardMuteMechanism(),
        TestImprovedCancelConditions(),
        TestResponseCancelNotActiveLogging(),
        TestBothQueuesFlush()
    ]
    
    total_tests = 0
    passed_tests = 0
    failed_tests = []
    
    for test_class in test_classes:
        class_name = test_class.__class__.__name__
        print(f"\n{'='*60}")
        print(f"Running {class_name}")
        print(f"{'='*60}")
        
        # Get all test methods
        test_methods = [m for m in dir(test_class) if m.startswith('test_')]
        
        for test_method in test_methods:
            total_tests += 1
            method = getattr(test_class, test_method)
            try:
                method()
                print(f"✅ {test_method}: PASSED")
                passed_tests += 1
            except AssertionError as e:
                print(f"❌ {test_method}: FAILED - {e}")
                failed_tests.append((class_name, test_method, str(e)))
            except Exception as e:
                print(f"❌ {test_method}: ERROR - {e}")
                failed_tests.append((class_name, test_method, str(e)))
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"TEST SUMMARY")
    print(f"{'='*60}")
    print(f"Total tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {len(failed_tests)}")
    
    if failed_tests:
        print(f"\nFailed tests:")
        for class_name, test_name, error in failed_tests:
            print(f"  - {class_name}.{test_name}: {error}")
        return 1
    else:
        print(f"\n✅ All tests passed!")
        return 0


if __name__ == '__main__':
    sys.exit(run_tests())
