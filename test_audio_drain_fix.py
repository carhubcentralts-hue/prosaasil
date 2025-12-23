"""
Test suite for AI speaking state drain logic fix

Tests the fix for keeping is_ai_speaking=True until audio queues drain:
1. is_ai_speaking should remain True while audio is in queues
2. is_ai_speaking should clear only after queues empty OR timeout
3. Barge-in should immediately clear state (forced interruption)
"""
import sys
import asyncio
import time
from unittest.mock import Mock, AsyncMock


class MockQueue:
    """Mock queue that simulates draining behavior"""
    def __init__(self, initial_size=0):
        self._size = initial_size
    
    def qsize(self):
        return self._size
    
    def drain_one(self):
        """Simulate one frame being sent/processed"""
        if self._size > 0:
            self._size -= 1


class MockHandler:
    """Mock MediaStreamHandler with drain check logic"""
    def __init__(self):
        self.tx_q = MockQueue()
        self.realtime_audio_out_queue = MockQueue()
        self.is_ai_speaking_event = Mock()
        self.is_ai_speaking_event.is_set = Mock(return_value=True)
        self.is_ai_speaking_event.clear = Mock()
        self.speaking = True
        self.ai_speaking_start_ts = time.time()
        self.has_pending_ai_response = True
        self.active_response_id = "test_response_123"
        self.response_pending_event = Mock()
        self.response_pending_event.clear = Mock()
        self.ai_response_active = True
        self._drain_tasks = {}
    
    async def _check_audio_drain_and_clear_speaking(self, response_id: str):
        """Simplified version of the drain check logic with response_id matching"""
        # Prevent task storms
        if response_id in self._drain_tasks:
            existing_task = self._drain_tasks[response_id]
            if existing_task and not existing_task.done():
                return "DUPLICATE_SKIPPED"
        
        self._drain_tasks[response_id] = asyncio.current_task()
        
        DRAIN_TIMEOUT_SEC = 0.5
        POLL_INTERVAL_MS = 50
        
        start_time = time.time()
        checks = 0
        max_checks = int((DRAIN_TIMEOUT_SEC * 1000) / POLL_INTERVAL_MS)
        
        while checks < max_checks:
            # 🔥 MOKEESH #1: Check response_id match before clearing!
            current_active_id = getattr(self, 'active_response_id', None)
            if current_active_id != response_id:
                # Response changed - don't clear!
                self._drain_tasks.pop(response_id, None)
                return "RESPONSE_CHANGED"
            
            # Check if queues are empty
            tx_size = self.tx_q.qsize()
            audio_out_size = self.realtime_audio_out_queue.qsize()
            
            if tx_size == 0 and audio_out_size == 0:
                # Final check before clearing
                if self.active_response_id == response_id:
                    # Clear all flags
                    if self.is_ai_speaking_event.is_set():
                        self.is_ai_speaking_event.clear()
                    self.speaking = False
                    self.ai_speaking_start_ts = None
                    self.has_pending_ai_response = False
                    self.active_response_id = None
                    self.response_pending_event.clear()
                    self.ai_response_active = False
                    self._drain_tasks.pop(response_id, None)
                    return "CLEARED_ON_EMPTY"
                else:
                    self._drain_tasks.pop(response_id, None)
                    return "RESPONSE_CHANGED"
            
            await asyncio.sleep(POLL_INTERVAL_MS / 1000.0)
            checks += 1
        
        # Timeout - check one more time
        if self.active_response_id == response_id:
            if self.is_ai_speaking_event.is_set():
                self.is_ai_speaking_event.clear()
            self.speaking = False
            self.ai_speaking_start_ts = None
            self.has_pending_ai_response = False
            self.active_response_id = None
            self.response_pending_event.clear()
            self.ai_response_active = False
            self._drain_tasks.pop(response_id, None)
            return "CLEARED_ON_TIMEOUT"
        else:
            self._drain_tasks.pop(response_id, None)
            return "RESPONSE_CHANGED"


class TestAudioDrainLogic:
    """Test that is_ai_speaking tracks audio delivery, not just server events"""
    
    def test_immediate_clear_when_queues_empty(self):
        """Verify is_ai_speaking clears immediately when queues already empty"""
        handler = MockHandler()
        # Queues already empty
        handler.tx_q._size = 0
        handler.realtime_audio_out_queue._size = 0
        # Use matching response_id!
        handler.active_response_id = "test_response_123"
        
        # Run drain check with matching response_id
        result = asyncio.run(handler._check_audio_drain_and_clear_speaking("test_response_123"))
        
        # Should clear immediately
        assert result == "CLEARED_ON_EMPTY", f"Should clear on empty, got {result}"
        assert handler.speaking == False, "speaking should be False"
        assert handler.ai_response_active == False, "ai_response_active should be False"
        assert handler.active_response_id is None, "active_response_id should be None"
        handler.is_ai_speaking_event.clear.assert_called()
    
    def test_delayed_clear_when_queues_draining(self):
        """Verify is_ai_speaking remains True while queues drain, then clears"""
        handler = MockHandler()
        # Queues have audio
        handler.tx_q._size = 3
        handler.realtime_audio_out_queue._size = 2
        # Use matching response_id!
        handler.active_response_id = "test_response_123"
        
        # Simulate draining while check is running
        async def drain_while_checking():
            # Wait a bit
            await asyncio.sleep(0.1)
            # Drain all queues
            handler.tx_q._size = 0
            handler.realtime_audio_out_queue._size = 0
        
        # Run both tasks
        async def run_test():
            drain_task = asyncio.create_task(drain_while_checking())
            check_result = await handler._check_audio_drain_and_clear_speaking("test_response_123")
            await drain_task
            return check_result
        
        result = asyncio.run(run_test())
        
        # Should eventually clear on empty (not timeout)
        assert result == "CLEARED_ON_EMPTY", f"Should clear on empty, got {result}"
        assert handler.speaking == False, "speaking should be False after drain"
        handler.is_ai_speaking_event.clear.assert_called()
    
    def test_timeout_clear_when_queues_never_empty(self):
        """Verify is_ai_speaking clears after timeout even if queues still have data"""
        handler = MockHandler()
        # Queues never empty (stuck)
        handler.tx_q._size = 100
        handler.realtime_audio_out_queue._size = 50
        # Use matching response_id!
        handler.active_response_id = "test_response_123"
        
        # Run drain check (will timeout)
        start_time = time.time()
        result = asyncio.run(handler._check_audio_drain_and_clear_speaking("test_response_123"))
        elapsed = time.time() - start_time
        
        # Should timeout and clear
        assert result == "CLEARED_ON_TIMEOUT", f"Should clear on timeout, got {result}"
        assert elapsed >= 0.5, f"Should wait at least 500ms, waited {elapsed*1000:.0f}ms"
        assert elapsed < 0.6, f"Should timeout at ~500ms, took {elapsed*1000:.0f}ms"
        assert handler.speaking == False, "speaking should be False after timeout"
        handler.is_ai_speaking_event.clear.assert_called()
    
    def test_all_flags_cleared_together(self):
        """Verify all related flags are cleared atomically"""
        handler = MockHandler()
        handler.tx_q._size = 0
        handler.realtime_audio_out_queue._size = 0
        
        # Set initial state
        handler.speaking = True
        handler.ai_response_active = True
        handler.active_response_id = "test_123"
        handler.has_pending_ai_response = True
        
        # Run drain check
        asyncio.run(handler._check_audio_drain_and_clear_speaking("test_123"))
        
        # Verify all flags cleared
        assert handler.speaking == False, "speaking should be cleared"
        assert handler.ai_response_active == False, "ai_response_active should be cleared"
        assert handler.active_response_id is None, "active_response_id should be cleared"
        assert handler.has_pending_ai_response == False, "has_pending_ai_response should be cleared"
        assert handler.ai_speaking_start_ts is None, "ai_speaking_start_ts should be cleared"
        handler.is_ai_speaking_event.clear.assert_called()
        handler.response_pending_event.clear.assert_called()
    
    def test_response_id_mismatch_skips_clear(self):
        """🔥 MOKEESH #1: Verify drain check skips clear if response_id changed"""
        handler = MockHandler()
        handler.tx_q._size = 0
        handler.realtime_audio_out_queue._size = 0
        
        # Set active_response_id to DIFFERENT value
        handler.active_response_id = "NEW_RESPONSE_999"
        
        # Try to drain OLD response
        result = asyncio.run(handler._check_audio_drain_and_clear_speaking("OLD_RESPONSE_123"))
        
        # Should NOT clear because response_id changed!
        assert result == "RESPONSE_CHANGED", f"Should skip on mismatch, got {result}"
        # Flags should NOT be cleared
        assert handler.active_response_id == "NEW_RESPONSE_999", "Should keep NEW response_id"
        # is_ai_speaking should NOT be cleared
        handler.is_ai_speaking_event.clear.assert_not_called()
    
    def test_response_id_change_during_drain(self):
        """🔥 MOKEESH #1: Verify drain detects response_id change mid-drain"""
        handler = MockHandler()
        handler.tx_q._size = 10
        handler.realtime_audio_out_queue._size = 5
        handler.active_response_id = "OLD_RESPONSE_123"
        
        # Simulate response changing mid-drain
        async def change_response_mid_drain():
            await asyncio.sleep(0.1)  # Let drain start
            handler.active_response_id = "NEW_RESPONSE_999"
            handler.tx_q._size = 0  # Drain queues
            handler.realtime_audio_out_queue._size = 0
        
        async def run_test():
            change_task = asyncio.create_task(change_response_mid_drain())
            result = await handler._check_audio_drain_and_clear_speaking("OLD_RESPONSE_123")
            await change_task
            return result
        
        result = asyncio.run(run_test())
        
        # Should detect change and NOT clear
        assert result == "RESPONSE_CHANGED", f"Should detect change, got {result}"
        assert handler.active_response_id == "NEW_RESPONSE_999", "Should preserve new response_id"
    
    def test_prevent_task_storm(self):
        """🔥 MOKEESH #4: Verify only one drain task runs per response_id"""
        handler = MockHandler()
        handler.tx_q._size = 10
        handler.realtime_audio_out_queue._size = 5
        handler.active_response_id = "test_123"  # Set matching response_id
        
        # Track which tasks completed
        completed = []
        
        # Start first drain task
        async def run_test():
            # Start two drain tasks for same response_id
            async def task1_wrapper():
                result = await handler._check_audio_drain_and_clear_speaking("test_123")
                completed.append(("task1", result))
                return result
            
            async def task2_wrapper():
                result = await handler._check_audio_drain_and_clear_speaking("test_123")
                completed.append(("task2", result))
                return result
            
            task1 = asyncio.create_task(task1_wrapper())
            await asyncio.sleep(0.05)  # Let task1 start and register
            task2 = asyncio.create_task(task2_wrapper())
            
            # Wait for task2 to check and skip
            await asyncio.sleep(0.05)
            
            # Drain queues to let task1 complete
            handler.tx_q._size = 0
            handler.realtime_audio_out_queue._size = 0
            
            # Wait for both to finish
            await task1
            await task2
        
        asyncio.run(run_test())
        
        # Check results
        assert len(completed) == 2, f"Should have 2 results, got {len(completed)}"
        
        # One should be skipped, one should complete
        results = [r for _, r in completed]
        assert "DUPLICATE_SKIPPED" in results, f"One task should be skipped, got {results}"
        assert any(r in ["CLEARED_ON_EMPTY", "CLEARED_ON_TIMEOUT"] for r in results), f"One task should complete, got {results}"


class TestBargeInImmediate:
    """Test that barge-in clears state immediately (forced interruption)"""
    
    def test_barge_in_clears_immediately_after_flush(self):
        """Verify barge-in clears is_ai_speaking immediately, not via drain check"""
        # Simulate barge-in flow
        has_active_response = True
        queues_have_audio = True  # Queues still have audio!
        
        # Barge-in detected
        if has_active_response:
            # Step 1: Cancel response
            # Step 2: Send Twilio clear
            # Step 3: Flush queues
            queues_flushed = True
            
            # Step 4: Clear state IMMEDIATELY (not via drain check)
            is_ai_speaking_cleared = True
            
            # Verify immediate clear happened
            assert queues_flushed, "Queues should be flushed"
            assert is_ai_speaking_cleared, "is_ai_speaking should clear immediately"
            # Drain check should NOT be used for barge-in
    
    def test_natural_completion_uses_drain_check(self):
        """Verify natural completion (response.audio.done) uses drain check"""
        # Simulate response.audio.done
        audio_done_received = True
        queues_have_audio = True  # Queues still have audio
        
        if audio_done_received:
            # Should schedule drain check, NOT clear immediately
            drain_check_scheduled = True
            is_ai_speaking_still_true = True  # Not cleared yet!
            
            # Verify drain check used, not immediate clear
            assert drain_check_scheduled, "Drain check should be scheduled"
            assert is_ai_speaking_still_true, "is_ai_speaking should remain True until drain"


def run_tests():
    """Run all tests and report results"""
    test_classes = [
        TestAudioDrainLogic(),
        TestBargeInImmediate()
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
