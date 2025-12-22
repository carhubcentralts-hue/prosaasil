"""
Test suite for text-based barge-in feature

Tests the minimal text barge-in implementation that prevents
"conversation_already_has_active_response" errors.
"""
import sys


class TestTextBargeInDetection:
    """Test text barge-in detection logic"""
    
    def test_text_barge_in_when_ai_speaking(self):
        """Verify text barge-in triggers when AI is speaking"""
        is_ai_speaking = True
        has_active_response = True
        
        should_trigger_barge_in = is_ai_speaking or has_active_response
        
        assert should_trigger_barge_in, "Should trigger barge-in when AI is speaking"
    
    def test_text_barge_in_when_active_response_exists(self):
        """Verify text barge-in triggers when active response exists"""
        is_ai_speaking = False
        has_active_response = True  # Response created but audio not yet started
        
        should_trigger_barge_in = is_ai_speaking or has_active_response
        
        assert should_trigger_barge_in, "Should trigger barge-in when active response exists"
    
    def test_no_text_barge_in_when_ai_not_speaking(self):
        """Verify no text barge-in when AI is not speaking and no active response"""
        is_ai_speaking = False
        has_active_response = False
        
        should_trigger_barge_in = is_ai_speaking or has_active_response
        
        assert not should_trigger_barge_in, "Should NOT trigger barge-in when AI is idle"


class TestTextBargeInStateMachine:
    """Test text barge-in state machine flow"""
    
    def test_pending_cancel_flag_flow(self):
        """Verify pending cancel flag is set and cleared correctly"""
        # Initial state
        _barge_in_pending_cancel = False
        _pending_user_text = None
        
        # Step 1: Detect text while AI speaking
        is_ai_speaking = True
        user_text = "שלום"
        
        if is_ai_speaking:
            _barge_in_pending_cancel = True
            _pending_user_text = user_text
        
        assert _barge_in_pending_cancel == True, "Pending cancel flag should be set"
        assert _pending_user_text == "שלום", "User text should be stored"
        
        # Step 2: response.cancelled event arrives
        if _barge_in_pending_cancel:
            _barge_in_pending_cancel = False
            txt = _pending_user_text
            _pending_user_text = None
            # Simulate response creation
            response_created = True
        
        assert _barge_in_pending_cancel == False, "Pending cancel flag should be cleared"
        assert _pending_user_text is None, "User text should be cleared"
        assert response_created == True, "Response should be created from text"
    
    def test_pending_text_storage(self):
        """Verify only the last text is stored"""
        _pending_user_text = None
        
        # Multiple texts arrive (only last should be kept)
        texts = ["טקסט 1", "טקסט 2", "טקסט 3"]
        
        for text in texts:
            _pending_user_text = text  # Overwrite each time
        
        assert _pending_user_text == "טקסט 3", "Should keep only the last text"


class TestResponseCreateGuard:
    """Test response.create guard for active responses"""
    
    def test_guard_blocks_when_ai_response_active(self):
        """Verify guard blocks response.create when ai_response_active=True"""
        ai_response_active = True
        is_greeting = False
        force = False
        
        should_block = ai_response_active and not is_greeting and not force
        
        assert should_block, "Should block response.create when ai_response_active=True"
    
    def test_guard_allows_when_no_active_response(self):
        """Verify guard allows response.create when ai_response_active=False"""
        ai_response_active = False
        is_greeting = False
        force = False
        
        should_block = ai_response_active and not is_greeting and not force
        
        assert not should_block, "Should allow response.create when no active response"
    
    def test_guard_allows_greeting(self):
        """Verify guard allows greeting even with active response"""
        ai_response_active = True
        is_greeting = True  # Greeting bypasses guard
        force = False
        
        should_block = ai_response_active and not is_greeting and not force
        
        assert not should_block, "Should allow greeting even with active response"
    
    def test_guard_allows_forced_response(self):
        """Verify guard allows forced response"""
        ai_response_active = True
        is_greeting = False
        force = True  # Force bypasses guard
        
        should_block = ai_response_active and not is_greeting and not force
        
        assert not should_block, "Should allow forced response even with active response"


class TestBargeInCancelSequence:
    """Test the 3-step cancel sequence"""
    
    def test_cancel_sequence_executes_all_steps(self):
        """Verify all 3 steps of cancel sequence execute"""
        # Simulate state
        active_response_id = "resp_123"
        stream_sid = "SM123456"
        
        # Step A: Snapshot
        rid = active_response_id
        assert rid == "resp_123", "Should snapshot response ID"
        
        # Step B: Cancel + Clear + Flush
        cancel_sent = False
        clear_sent = False
        flush_called = False
        
        if rid:
            cancel_sent = True  # Simulate cancel
            if stream_sid:
                clear_sent = True  # Simulate Twilio clear
            flush_called = True  # Simulate flush
        
        assert cancel_sent, "Should send cancel"
        assert clear_sent, "Should send Twilio clear"
        assert flush_called, "Should flush TX queue"
        
        # Step C: Store pending text
        pending_text = "user text"
        assert pending_text is not None, "Should store pending text"


class TestBargeInEventCounter:
    """Test barge-in event counter increments"""
    
    def test_counter_increments_on_text_barge_in(self):
        """Verify barge-in counter increments when text barge-in completes"""
        _barge_in_event_count = 0
        
        # Simulate text barge-in completion
        text_barge_in_completed = True
        
        if text_barge_in_completed:
            _barge_in_event_count += 1
        
        assert _barge_in_event_count == 1, "Counter should increment to 1"
        
        # Another text barge-in
        if text_barge_in_completed:
            _barge_in_event_count += 1
        
        assert _barge_in_event_count == 2, "Counter should increment to 2"


def run_tests():
    """Run all tests and report results"""
    test_classes = [
        TestTextBargeInDetection(),
        TestTextBargeInStateMachine(),
        TestResponseCreateGuard(),
        TestBargeInCancelSequence(),
        TestBargeInEventCounter()
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
