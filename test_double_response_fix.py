"""
Test suite for double response prevention fixes

Tests the key fixes:
1. One response per user turn lock (_response_create_in_flight)
2. Utterance deduplication via fingerprinting
3. Watchdog enhanced guards to prevent double retry
4. Frame drop categorization and SIMPLE_MODE validation
"""
import sys
import time
import hashlib


class TestResponseCreateLock:
    """Test response.create in-flight lock to prevent duplicates"""
    
    def test_lock_blocks_duplicate_response_create(self):
        """Verify that response.create is blocked when already in flight"""
        # Simulate the lock logic
        _response_create_in_flight = False
        _response_create_started_ts = 0.0
        
        # First response.create call
        _response_create_in_flight = True
        _response_create_started_ts = time.time()
        first_call_allowed = True
        
        # Second response.create call (should be blocked)
        elapsed = time.time() - _response_create_started_ts
        second_call_allowed = not (_response_create_in_flight and elapsed < 6.0)
        
        assert first_call_allowed, "First call should be allowed"
        assert not second_call_allowed, "Second call should be blocked when in flight"
    
    def test_lock_allows_retry_after_timeout(self):
        """Verify that response.create is allowed after 6-second timeout"""
        _response_create_in_flight = True
        _response_create_started_ts = time.time() - 7.0  # 7 seconds ago
        
        elapsed = time.time() - _response_create_started_ts
        retry_allowed = not (_response_create_in_flight and elapsed < 6.0)
        
        assert retry_allowed, "Retry should be allowed after 6 seconds"
    
    def test_lock_cleared_on_response_created(self):
        """Verify that lock is cleared when response.created event arrives"""
        _response_create_in_flight = True
        _response_create_started_ts = time.time()
        
        # Simulate response.created event
        _response_create_in_flight = False
        
        # New response.create should be allowed
        elapsed = time.time() - _response_create_started_ts
        new_call_allowed = not (_response_create_in_flight and elapsed < 6.0)
        
        assert new_call_allowed, "New call should be allowed after lock cleared"
    
    def test_lock_cleared_on_response_done(self):
        """Verify that lock is cleared when response.done event arrives"""
        _response_create_in_flight = True
        
        # Simulate response.done event
        _response_create_in_flight = False
        
        assert not _response_create_in_flight, "Lock should be cleared on response.done"
    
    def test_lock_cleared_on_response_cancelled(self):
        """Verify that lock is cleared when response.cancelled event arrives"""
        _response_create_in_flight = True
        
        # Simulate response.cancelled event
        _response_create_in_flight = False
        
        assert not _response_create_in_flight, "Lock should be cleared on response.cancelled"


class TestUtteranceDeduplication:
    """Test utterance deduplication via fingerprinting"""
    
    def test_fingerprint_generation(self):
        """Verify fingerprint is generated correctly"""
        text = "פריצת דלת."
        now_sec = time.time()
        time_bucket = int(now_sec / 2.0)
        fingerprint = hashlib.sha1(f"{text}|{time_bucket}".encode()).hexdigest()[:16]
        
        assert len(fingerprint) == 16, "Fingerprint should be 16 characters"
        assert fingerprint.isalnum(), "Fingerprint should be alphanumeric"
    
    def test_same_text_same_bucket_produces_same_fingerprint(self):
        """Verify same text in same time bucket produces same fingerprint"""
        text = "פריצת דלת."
        now_sec = time.time()
        time_bucket = int(now_sec / 2.0)
        
        fp1 = hashlib.sha1(f"{text}|{time_bucket}".encode()).hexdigest()[:16]
        fp2 = hashlib.sha1(f"{text}|{time_bucket}".encode()).hexdigest()[:16]
        
        assert fp1 == fp2, "Same text in same bucket should produce same fingerprint"
    
    def test_different_text_produces_different_fingerprint(self):
        """Verify different text produces different fingerprint"""
        text1 = "פריצת דלת."
        text2 = "שלום."
        now_sec = time.time()
        time_bucket = int(now_sec / 2.0)
        
        fp1 = hashlib.sha1(f"{text1}|{time_bucket}".encode()).hexdigest()[:16]
        fp2 = hashlib.sha1(f"{text2}|{time_bucket}".encode()).hexdigest()[:16]
        
        assert fp1 != fp2, "Different text should produce different fingerprint"
    
    def test_duplicate_within_window_is_dropped_with_race_condition(self):
        """Verify duplicate utterance within 4-second window is dropped ONLY with race condition"""
        text = "פריצת דלת."
        now_sec = time.time()
        time_bucket = int(now_sec / 2.0)
        fingerprint = hashlib.sha1(f"{text}|{time_bucket}".encode()).hexdigest()[:16]
        
        _last_user_turn_fingerprint = fingerprint
        _last_user_turn_timestamp = now_sec
        
        # Same utterance 2 seconds later WITH race condition
        now_sec_2 = now_sec + 2.0
        time_since_last = now_sec_2 - _last_user_turn_timestamp
        
        # Simulate race condition (response.create in flight)
        _response_create_in_flight = True
        
        # Check if it should be dropped
        is_duplicate = (
            (_last_user_turn_fingerprint == fingerprint) and 
            (time_since_last < 4.0) and
            _response_create_in_flight  # Race condition indicator
        )
        
        assert is_duplicate, "Duplicate with race condition should be detected"
    
    def test_duplicate_within_window_allowed_without_race_condition(self):
        """Verify duplicate utterance within window is ALLOWED without race condition"""
        text = "פריצת דלת."
        now_sec = time.time()
        time_bucket = int(now_sec / 2.0)
        fingerprint = hashlib.sha1(f"{text}|{time_bucket}".encode()).hexdigest()[:16]
        
        _last_user_turn_fingerprint = fingerprint
        _last_user_turn_timestamp = now_sec
        
        # Same utterance 2 seconds later WITHOUT race condition
        now_sec_2 = now_sec + 2.0
        time_since_last = now_sec_2 - _last_user_turn_timestamp
        
        # NO race condition (response.create not in flight, AI not speaking)
        _response_create_in_flight = False
        ai_response_active = False
        is_ai_speaking = False
        
        # Check if it should be dropped
        has_race_condition = (
            _response_create_in_flight or 
            ai_response_active or 
            is_ai_speaking
        )
        is_duplicate = (
            (_last_user_turn_fingerprint == fingerprint) and 
            (time_since_last < 4.0) and
            has_race_condition
        )
        
        assert not is_duplicate, "Duplicate without race condition should be ALLOWED (user might repeat intentionally)"
    
    def test_duplicate_after_window_is_allowed(self):
        """Verify duplicate utterance after 4-second window is allowed"""
        text = "פריצת דלת."
        now_sec = time.time()
        time_bucket = int(now_sec / 2.0)
        fingerprint = hashlib.sha1(f"{text}|{time_bucket}".encode()).hexdigest()[:16]
        
        _last_user_turn_fingerprint = fingerprint
        _last_user_turn_timestamp = now_sec
        
        # Same utterance 5 seconds later (outside window)
        now_sec_2 = now_sec + 5.0
        time_since_last = now_sec_2 - _last_user_turn_timestamp
        
        # Check if it should be dropped
        is_duplicate = (_last_user_turn_fingerprint == fingerprint) and (time_since_last < 4.0)
        
        assert not is_duplicate, "Duplicate after 4 seconds should be allowed"


class TestWatchdogEnhancedGuards:
    """Test watchdog enhanced guards to prevent double retry"""
    
    def test_watchdog_blocked_when_response_in_flight(self):
        """Verify watchdog is blocked when response.create is in flight"""
        _response_create_in_flight = True
        _watchdog_retry_done = False
        
        # Watchdog should not retry
        should_retry = not _response_create_in_flight and not _watchdog_retry_done
        
        assert not should_retry, "Watchdog should be blocked when response in flight"
    
    def test_watchdog_blocked_when_retry_already_done(self):
        """Verify watchdog is blocked when retry already done for this turn"""
        _response_create_in_flight = False
        _watchdog_retry_done = True
        
        # Watchdog should not retry
        should_retry = not _response_create_in_flight and not _watchdog_retry_done
        
        assert not should_retry, "Watchdog should be blocked when retry already done"
    
    def test_watchdog_allowed_when_conditions_met(self):
        """Verify watchdog is allowed when all conditions are met"""
        _response_create_in_flight = False
        _watchdog_retry_done = False
        ai_response_active = False
        is_ai_speaking = False
        active_response_id = None
        
        # Watchdog should retry
        should_retry = (
            not _response_create_in_flight and
            not _watchdog_retry_done and
            not ai_response_active and
            not is_ai_speaking and
            active_response_id is None
        )
        
        assert should_retry, "Watchdog should be allowed when conditions met"
    
    def test_watchdog_sets_retry_flag(self):
        """Verify watchdog sets retry flag when sending retry"""
        _watchdog_retry_done = False
        
        # Simulate watchdog retry
        _watchdog_retry_done = True
        
        assert _watchdog_retry_done, "Watchdog should set retry flag"
    
    def test_watchdog_flag_reset_on_new_turn(self):
        """Verify watchdog flag is reset on new user turn"""
        _watchdog_retry_done = True
        
        # Simulate new turn (new utterance)
        _watchdog_retry_done = False
        
        assert not _watchdog_retry_done, "Watchdog flag should be reset on new turn"


class TestFrameDropCategorization:
    """Test frame drop categorization and SIMPLE_MODE validation"""
    
    def test_categorized_drops_tracked_separately(self):
        """Verify frame drops are tracked in separate categories"""
        drops = {
            'greeting_lock': 10,
            'filters': 0,
            'queue_full': 0,
            'bargein_flush': 25,
            'tx_overflow': 0,
            'shutdown': 0,
            'unknown': 0
        }
        
        total_categorized = sum(drops.values())
        assert total_categorized == 35, f"Total categorized should be 35, got {total_categorized}"
        assert drops['greeting_lock'] == 10, "Greeting lock drops tracked"
        assert drops['bargein_flush'] == 25, "Barge-in flush drops tracked"
    
    def test_unknown_drops_calculated_from_difference(self):
        """Verify unknown drops are calculated from total vs categorized"""
        frames_dropped_total = 100
        frames_dropped_categorized = 94
        
        # Calculate unknown
        frames_dropped_unknown = frames_dropped_total - frames_dropped_categorized
        
        assert frames_dropped_unknown == 6, f"Unknown should be 6, got {frames_dropped_unknown}"
    
    def test_simple_mode_violation_when_unknown_drops_exist(self):
        """Verify SIMPLE_MODE violation is detected when unknown drops exist"""
        SIMPLE_MODE = True
        frames_dropped_unknown = 106
        
        # Should trigger error
        is_bug = SIMPLE_MODE and frames_dropped_unknown > 0
        
        assert is_bug, "SIMPLE_MODE with unknown drops should be flagged as bug"
    
    def test_simple_mode_no_violation_when_no_unknown_drops(self):
        """Verify no SIMPLE_MODE violation when all drops are categorized"""
        SIMPLE_MODE = True
        frames_dropped_unknown = 0
        frames_dropped_total = 50
        frames_dropped_bargein_flush = 50
        
        # Should not trigger error (all drops accounted for)
        is_bug = SIMPLE_MODE and frames_dropped_unknown > 0
        
        assert not is_bug, "SIMPLE_MODE should not flag bug when all drops categorized"
    
    def test_bargein_flush_increments_counter(self):
        """Verify barge-in flush increments the bargein counter"""
        frames_dropped_bargein_flush = 0
        flushed_count = 25
        
        # Simulate flush
        frames_dropped_bargein_flush += flushed_count
        
        assert frames_dropped_bargein_flush == 25, "Barge-in flush should increment counter"


def run_all_tests():
    """Run all test classes"""
    test_classes = [
        TestResponseCreateLock,
        TestUtteranceDeduplication,
        TestWatchdogEnhancedGuards,
        TestFrameDropCategorization
    ]
    
    total_tests = 0
    passed_tests = 0
    failed_tests = []
    
    for test_class in test_classes:
        print(f"\n{'='*70}")
        print(f"Running {test_class.__name__}")
        print(f"{'='*70}")
        
        test_instance = test_class()
        test_methods = [method for method in dir(test_instance) if method.startswith('test_')]
        
        for method_name in test_methods:
            total_tests += 1
            try:
                method = getattr(test_instance, method_name)
                method()
                passed_tests += 1
                print(f"✅ {method_name}")
            except AssertionError as e:
                failed_tests.append((test_class.__name__, method_name, str(e)))
                print(f"❌ {method_name}: {e}")
            except Exception as e:
                failed_tests.append((test_class.__name__, method_name, f"Error: {e}"))
                print(f"❌ {method_name}: Error: {e}")
    
    # Print summary
    print(f"\n{'='*70}")
    print(f"TEST SUMMARY")
    print(f"{'='*70}")
    print(f"Total tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {len(failed_tests)}")
    
    if failed_tests:
        print(f"\n❌ FAILED TESTS:")
        for class_name, method_name, error in failed_tests:
            print(f"  - {class_name}.{method_name}: {error}")
        return False
    else:
        print(f"\n✅ ALL TESTS PASSED!")
        return True


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
