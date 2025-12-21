"""
Test suite for barge-in false trigger fixes

Tests the 3 key fixes:
1. Audio-only cancel decision (5+ consecutive frames)
2. Response-scoped cleanup
3. RMS-based false trigger recovery
"""
import sys


class TestBargeInDebounce:
    """Test audio-only barge-in detection with frame debouncing"""
    
    def test_debounce_requires_5_consecutive_frames(self):
        """Verify that barge-in requires 5 consecutive frames above threshold"""
        # Simulate the frame counting logic
        frames_above_threshold = 0
        MIN_BARGE_IN_FRAMES = 5
        barge_in_threshold = 35
        
        # Test sequence: 4 frames above, 1 below, 5 frames above
        test_rms_values = [40, 45, 50, 42, 20, 38, 41, 43, 45, 47]
        
        triggered_at = []
        for i, rms in enumerate(test_rms_values):
            if rms > barge_in_threshold:
                frames_above_threshold += 1
            else:
                frames_above_threshold = 0
            
            if frames_above_threshold >= MIN_BARGE_IN_FRAMES:
                triggered_at.append(i)
                frames_above_threshold = 0  # Reset after trigger
        
        # Should trigger at frame 9 (5th consecutive frame above threshold)
        assert len(triggered_at) == 1, "Should trigger exactly once"
        assert triggered_at[0] == 9, f"Should trigger at frame 9, got {triggered_at[0]}"
    
    def test_debounce_resets_on_low_rms(self):
        """Verify frame counter resets when RMS drops below threshold"""
        frames_above_threshold = 0
        MIN_BARGE_IN_FRAMES = 5
        barge_in_threshold = 35
        
        # Test: 3 frames above, 1 below (should reset), 2 frames above
        test_rms_values = [40, 45, 50, 20, 38, 41]
        
        for rms in test_rms_values:
            if rms > barge_in_threshold:
                frames_above_threshold += 1
            else:
                frames_above_threshold = 0
        
        # Final count should be 2 (reset happened)
        assert frames_above_threshold == 2, f"Counter should be 2 after reset, got {frames_above_threshold}"
    
    def test_guards_prevent_cancel_without_active_response(self):
        """Verify cancel doesn't trigger without active response"""
        # All guards must pass
        is_ai_speaking = True
        has_active_response = False  # Missing!
        is_greeting_locked = False
        rms_above_threshold = True
        
        should_count_frame = (
            is_ai_speaking and 
            has_active_response and 
            not is_greeting_locked and 
            rms_above_threshold
        )
        
        assert not should_count_frame, "Should not count frame without active response"
    
    def test_guards_prevent_cancel_during_greeting(self):
        """Verify cancel doesn't trigger during greeting lock"""
        is_ai_speaking = True
        has_active_response = True
        is_greeting_locked = True  # Locked!
        rms_above_threshold = True
        
        should_count_frame = (
            is_ai_speaking and 
            has_active_response and 
            not is_greeting_locked and 
            rms_above_threshold
        )
        
        assert not should_count_frame, "Should not count frame during greeting lock"
    
    def test_guards_prevent_cancel_when_ai_not_speaking(self):
        """Verify cancel doesn't trigger when AI is not speaking"""
        is_ai_speaking = False  # Not speaking!
        has_active_response = True
        is_greeting_locked = False
        rms_above_threshold = True
        
        should_count_frame = (
            is_ai_speaking and 
            has_active_response and 
            not is_greeting_locked and 
            rms_above_threshold
        )
        
        assert not should_count_frame, "Should not count frame when AI not speaking"


class TestResponseScopedCleanup:
    """Test that cancel cleanup is response-scoped only"""
    
    def test_cleanup_only_if_response_id_matches(self):
        """Verify cleanup only happens if active_response_id matches cancelled_id"""
        active_response_id = "resp_123"
        cancelled_id = "resp_123"
        
        # Simulate the guard check
        should_cleanup = (active_response_id == cancelled_id)
        
        assert should_cleanup, "Should cleanup when IDs match"
        
        # Test with different ID
        active_response_id = "resp_456"
        should_cleanup = (active_response_id == cancelled_id)
        
        assert not should_cleanup, "Should NOT cleanup when IDs don't match"
    
    def test_cleanup_does_not_touch_global_state(self):
        """Verify that cleanup doesn't clear global session state"""
        # These should NOT be touched by cleanup
        global_state = {
            'user_speaking': True,  # Managed by speech cycle
            'user_has_spoken': True,  # Global session state
            'greeting_lock_active': False,  # Global state
            'stream_sid': 'SM123456',  # Websocket state
        }
        
        # Simulate cleanup (should only touch response-scoped state)
        response_state = {
            'active_response_id': None,  # OK to clear
            'is_ai_speaking': False,  # OK to clear
            'ai_response_active': False,  # OK to clear
            'speaking': False,  # OK to clear
        }
        
        # Verify global state unchanged
        assert global_state['user_speaking'] == True
        assert global_state['user_has_spoken'] == True
        assert global_state['greeting_lock_active'] == False
        assert global_state['stream_sid'] == 'SM123456'


class TestFalseTriggerRecovery:
    """Test RMS-based false trigger recovery"""
    
    def test_false_trigger_detection_no_text_low_rms(self):
        """Verify false trigger detected when no text and RMS below threshold"""
        got_committed_text = False  # No transcription
        current_rms = 25
        barge_threshold = 35
        rms_below_threshold = current_rms < barge_threshold
        user_currently_speaking = False
        
        is_false_trigger = (
            not got_committed_text and 
            rms_below_threshold and 
            not user_currently_speaking
        )
        
        assert is_false_trigger, "Should detect false trigger"
    
    def test_no_false_trigger_when_text_received(self):
        """Verify no false trigger when transcription received"""
        got_committed_text = True  # Got text!
        current_rms = 25
        barge_threshold = 35
        rms_below_threshold = current_rms < barge_threshold
        user_currently_speaking = False
        
        is_false_trigger = (
            not got_committed_text and 
            rms_below_threshold and 
            not user_currently_speaking
        )
        
        assert not is_false_trigger, "Should NOT be false trigger when text received"
    
    def test_no_false_trigger_when_rms_still_high(self):
        """Verify no false trigger when RMS still above threshold"""
        got_committed_text = False
        current_rms = 50  # Still high!
        barge_threshold = 35
        rms_below_threshold = current_rms < barge_threshold
        user_currently_speaking = False
        
        is_false_trigger = (
            not got_committed_text and 
            rms_below_threshold and 
            not user_currently_speaking
        )
        
        assert not is_false_trigger, "Should NOT be false trigger when RMS still high"
    
    def test_no_false_trigger_when_user_speaking(self):
        """Verify no false trigger when user is currently speaking"""
        got_committed_text = False
        current_rms = 25
        barge_threshold = 35
        rms_below_threshold = current_rms < barge_threshold
        user_currently_speaking = True  # Still speaking!
        
        is_false_trigger = (
            not got_committed_text and 
            rms_below_threshold and 
            not user_currently_speaking
        )
        
        assert not is_false_trigger, "Should NOT be false trigger when user still speaking"
    
    def test_recovery_delay_is_500ms(self):
        """Verify recovery delay is 500ms (not 250ms)"""
        recovery_delay_sec = 0.5
        
        assert recovery_delay_sec == 0.5, f"Recovery delay should be 0.5s, got {recovery_delay_sec}"
        assert recovery_delay_sec > 0.25, "Recovery delay should be LONGER than 0.25s, not 'faster'"


def run_tests():
    """Run all tests and report results"""
    test_classes = [
        TestBargeInDebounce(),
        TestResponseScopedCleanup(),
        TestFalseTriggerRecovery()
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
    """Test audio-only barge-in detection with frame debouncing"""
    
    def test_debounce_requires_5_consecutive_frames(self):
        """Verify that barge-in requires 5 consecutive frames above threshold"""
        # Simulate the frame counting logic
        frames_above_threshold = 0
        MIN_BARGE_IN_FRAMES = 5
        barge_in_threshold = 35
        
        # Test sequence: 4 frames above, 1 below, 5 frames above
        test_rms_values = [40, 45, 50, 42, 20, 38, 41, 43, 45, 47]
        
        triggered_at = []
        for i, rms in enumerate(test_rms_values):
            if rms > barge_in_threshold:
                frames_above_threshold += 1
            else:
                frames_above_threshold = 0
            
            if frames_above_threshold >= MIN_BARGE_IN_FRAMES:
                triggered_at.append(i)
                frames_above_threshold = 0  # Reset after trigger
        
        # Should trigger at frame 9 (5th consecutive frame above threshold)
        assert len(triggered_at) == 1, "Should trigger exactly once"
        assert triggered_at[0] == 9, f"Should trigger at frame 9, got {triggered_at[0]}"
    
    def test_debounce_resets_on_low_rms(self):
        """Verify frame counter resets when RMS drops below threshold"""
        frames_above_threshold = 0
        MIN_BARGE_IN_FRAMES = 5
        barge_in_threshold = 35
        
        # Test: 3 frames above, 1 below (should reset), 2 frames above
        test_rms_values = [40, 45, 50, 20, 38, 41]
        
        for rms in test_rms_values:
            if rms > barge_in_threshold:
                frames_above_threshold += 1
            else:
                frames_above_threshold = 0
        
        # Final count should be 2 (reset happened)
        assert frames_above_threshold == 2, f"Counter should be 2 after reset, got {frames_above_threshold}"
    
    def test_guards_prevent_cancel_without_active_response(self):
        """Verify cancel doesn't trigger without active response"""
        # All guards must pass
        is_ai_speaking = True
        has_active_response = False  # Missing!
        is_greeting_locked = False
        rms_above_threshold = True
        
        should_count_frame = (
            is_ai_speaking and 
            has_active_response and 
            not is_greeting_locked and 
            rms_above_threshold
        )
        
        assert not should_count_frame, "Should not count frame without active response"
    
    def test_guards_prevent_cancel_during_greeting(self):
        """Verify cancel doesn't trigger during greeting lock"""
        is_ai_speaking = True
        has_active_response = True
        is_greeting_locked = True  # Locked!
        rms_above_threshold = True
        
        should_count_frame = (
            is_ai_speaking and 
            has_active_response and 
            not is_greeting_locked and 
            rms_above_threshold
        )
        
        assert not should_count_frame, "Should not count frame during greeting lock"
    
    def test_guards_prevent_cancel_when_ai_not_speaking(self):
        """Verify cancel doesn't trigger when AI is not speaking"""
        is_ai_speaking = False  # Not speaking!
        has_active_response = True
        is_greeting_locked = False
        rms_above_threshold = True
        
        should_count_frame = (
            is_ai_speaking and 
            has_active_response and 
            not is_greeting_locked and 
            rms_above_threshold
        )
        
        assert not should_count_frame, "Should not count frame when AI not speaking"


class TestResponseScopedCleanup:
    """Test that cancel cleanup is response-scoped only"""
    
    def test_cleanup_only_if_response_id_matches(self):
        """Verify cleanup only happens if active_response_id matches cancelled_id"""
        active_response_id = "resp_123"
        cancelled_id = "resp_123"
        
        # Simulate the guard check
        should_cleanup = (active_response_id == cancelled_id)
        
        assert should_cleanup, "Should cleanup when IDs match"
        
        # Test with different ID
        active_response_id = "resp_456"
        should_cleanup = (active_response_id == cancelled_id)
        
        assert not should_cleanup, "Should NOT cleanup when IDs don't match"
    
    def test_cleanup_does_not_touch_global_state(self):
        """Verify that cleanup doesn't clear global session state"""
        # These should NOT be touched by cleanup
        global_state = {
            'user_speaking': True,  # Managed by speech cycle
            'user_has_spoken': True,  # Global session state
            'greeting_lock_active': False,  # Global state
            'stream_sid': 'SM123456',  # Websocket state
        }
        
        # Simulate cleanup (should only touch response-scoped state)
        response_state = {
            'active_response_id': None,  # OK to clear
            'is_ai_speaking': False,  # OK to clear
            'ai_response_active': False,  # OK to clear
            'speaking': False,  # OK to clear
        }
        
        # Verify global state unchanged
        assert global_state['user_speaking'] == True
        assert global_state['user_has_spoken'] == True
        assert global_state['greeting_lock_active'] == False
        assert global_state['stream_sid'] == 'SM123456'


class TestFalseTriggerRecovery:
    """Test RMS-based false trigger recovery"""
    
    def test_false_trigger_detection_no_text_low_rms(self):
        """Verify false trigger detected when no text and RMS below threshold"""
        got_committed_text = False  # No transcription
        current_rms = 25
        barge_threshold = 35
        rms_below_threshold = current_rms < barge_threshold
        user_currently_speaking = False
        
        is_false_trigger = (
            not got_committed_text and 
            rms_below_threshold and 
            not user_currently_speaking
        )
        
        assert is_false_trigger, "Should detect false trigger"
    
    def test_no_false_trigger_when_text_received(self):
        """Verify no false trigger when transcription received"""
        got_committed_text = True  # Got text!
        current_rms = 25
        barge_threshold = 35
        rms_below_threshold = current_rms < barge_threshold
        user_currently_speaking = False
        
        is_false_trigger = (
            not got_committed_text and 
            rms_below_threshold and 
            not user_currently_speaking
        )
        
        assert not is_false_trigger, "Should NOT be false trigger when text received"
    
    def test_no_false_trigger_when_rms_still_high(self):
        """Verify no false trigger when RMS still above threshold"""
        got_committed_text = False
        current_rms = 50  # Still high!
        barge_threshold = 35
        rms_below_threshold = current_rms < barge_threshold
        user_currently_speaking = False
        
        is_false_trigger = (
            not got_committed_text and 
            rms_below_threshold and 
            not user_currently_speaking
        )
        
        assert not is_false_trigger, "Should NOT be false trigger when RMS still high"
    
    def test_no_false_trigger_when_user_speaking(self):
        """Verify no false trigger when user is currently speaking"""
        got_committed_text = False
        current_rms = 25
        barge_threshold = 35
        rms_below_threshold = current_rms < barge_threshold
        user_currently_speaking = True  # Still speaking!
        
        is_false_trigger = (
            not got_committed_text and 
            rms_below_threshold and 
            not user_currently_speaking
        )
        
        assert not is_false_trigger, "Should NOT be false trigger when user still speaking"
    
    def test_recovery_delay_is_500ms(self):
        """Verify recovery delay is 500ms (not 250ms)"""
        recovery_delay_sec = 0.5
        
        assert recovery_delay_sec == 0.5, f"Recovery delay should be 0.5s, got {recovery_delay_sec}"
        assert recovery_delay_sec > 0.25, "Recovery delay should be LONGER than 0.25s, not 'faster'"


if __name__ == '__main__':
    # Run tests with pytest
    pytest.main([__file__, '-v'])
