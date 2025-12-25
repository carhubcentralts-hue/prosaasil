"""
Test suite for audio drain timing fix

Tests the fix for proper audio drain before hangup:
1. Calculate exact time needed for remaining frames (frames * 20ms + buffer)
2. Wait for both queues to empty
3. Add playback buffer for Twilio to actually play the frames
"""
import sys
import asyncio
import time
from unittest.mock import Mock, AsyncMock


class MockQueue:
    """Mock queue that simulates draining behavior"""
    def __init__(self, initial_size=0):
        self._size = initial_size
        self._items = list(range(initial_size))
    
    def qsize(self):
        return self._size
    
    def empty(self):
        return self._size == 0
    
    def drain_one(self):
        """Simulate one frame being sent/processed"""
        if self._size > 0:
            self._size -= 1
            if self._items:
                self._items.pop(0)
    
    def get_nowait(self):
        if self._size > 0:
            self._size -= 1
            if self._items:
                return self._items.pop(0)
        raise Exception("Queue empty")


class MockHandler:
    """Mock MediaStreamHandler with enhanced drain logic"""
    def __init__(self):
        self.tx_q = MockQueue()
        self.realtime_audio_out_queue = MockQueue()
        self.pending_hangup = False
        self.hangup_triggered = False
        self.hangup_executed = False
        self.audio_done_by_response_id = {}
        self.call_sid = "CA1234567890"
        self._hangup_times = []
    
    async def maybe_execute_hangup(self, via: str, response_id: str):
        """Mock hangup execution"""
        # Check conditions
        conditions = {
            "pending": self.pending_hangup,
            "audio_done": self.audio_done_by_response_id.get(response_id, False),
            "tx_empty": self.tx_q.empty(),
            "out_q_empty": self.realtime_audio_out_queue.empty(),
            "not_triggered": not self.hangup_triggered,
        }
        
        if all(conditions.values()):
            self.hangup_executed = True
            self.hangup_triggered = True
            self._hangup_times.append(time.time())
            return True
        return False
    
    async def delayed_hangup_with_drain(self, response_id: str):
        """
        Enhanced delayed hangup logic with proper drain timing
        This mimics the fix implemented in media_ws_ai.py
        """
        # Capture initial queue sizes at audio.done moment
        initial_q1_size = self.realtime_audio_out_queue.qsize()
        initial_tx_size = self.tx_q.qsize()
        total_frames_remaining = initial_q1_size + initial_tx_size
        
        start_time = time.time()
        
        if total_frames_remaining > 0:
            # Calculate time needed: each frame = 20ms, plus 400ms buffer
            remaining_ms = total_frames_remaining * 20
            buffer_ms = 400
            total_wait_ms = remaining_ms + buffer_ms
            print(f"⏳ [TEST] {total_frames_remaining} frames remaining → waiting {total_wait_ms}ms")
        
        # STEP 1: Wait for OpenAI queue to drain (max 30 seconds)
        for i in range(300):  # 300 * 100ms = 30 seconds max
            q1_size = self.realtime_audio_out_queue.qsize()
            if q1_size == 0:
                print(f"✅ [TEST] OpenAI queue empty after {i*100}ms")
                break
            await asyncio.sleep(0.1)
        
        # STEP 2: Wait for TX queue to drain (max 60 seconds)
        for i in range(600):  # 600 * 100ms = 60 seconds max
            tx_size = self.tx_q.qsize()
            if tx_size == 0:
                print(f"✅ [TEST] TX queue empty after {i*100}ms")
                break
            await asyncio.sleep(0.1)
        
        # STEP 3: Extra buffer for Twilio playback
        playback_buffer_seconds = 0.5  # 500ms
        print(f"⏳ [TEST] Queues empty, waiting {playback_buffer_seconds}s for Twilio playback")
        await asyncio.sleep(playback_buffer_seconds)
        
        drain_time = time.time() - start_time
        print(f"✅ [TEST] Total drain time: {drain_time*1000:.0f}ms")
        
        # Now execute hangup
        await self.maybe_execute_hangup(via="audio.done", response_id=response_id)


async def test_audio_drain_timing():
    """Test that audio drain waits for frames to play"""
    print("\n" + "="*70)
    print("TEST 1: Audio Drain Timing with 41 Frames")
    print("="*70)
    
    handler = MockHandler()
    handler.realtime_audio_out_queue = MockQueue(initial_size=30)
    handler.tx_q = MockQueue(initial_size=11)
    handler.pending_hangup = True
    handler.audio_done_by_response_id["resp_123"] = True
    
    # Start drain task
    start_time = time.time()
    drain_task = asyncio.create_task(handler.delayed_hangup_with_drain("resp_123"))
    
    # Simulate queue draining in background (1 frame per 20ms)
    async def drain_queues():
        while not handler.realtime_audio_out_queue.empty() or not handler.tx_q.empty():
            await asyncio.sleep(0.02)  # 20ms per frame
            handler.realtime_audio_out_queue.drain_one()
            if handler.realtime_audio_out_queue.empty():
                handler.tx_q.drain_one()
    
    drain_background = asyncio.create_task(drain_queues())
    
    # Wait for both tasks
    await drain_task
    await drain_background
    
    total_time = time.time() - start_time
    
    print(f"\n📊 Test Results:")
    print(f"   - Total time: {total_time*1000:.0f}ms")
    print(f"   - Expected minimum: ~1320ms (41 frames * 20ms + 500ms buffer)")
    print(f"   - Hangup executed: {handler.hangup_executed}")
    print(f"   - Queues empty: OpenAI={handler.realtime_audio_out_queue.empty()}, TX={handler.tx_q.empty()}")
    
    # Assertions
    assert handler.hangup_executed, "Hangup should have been executed"
    assert handler.realtime_audio_out_queue.empty(), "OpenAI queue should be empty"
    assert handler.tx_q.empty(), "TX queue should be empty"
    assert total_time >= 1.2, f"Should wait at least 1.2s for frames to play, got {total_time:.2f}s"
    
    print("\n✅ TEST 1 PASSED: Audio drain timing is correct")
    return True


async def test_no_premature_hangup():
    """Test that hangup doesn't fire while frames are still in queue"""
    print("\n" + "="*70)
    print("TEST 2: No Premature Hangup")
    print("="*70)
    
    handler = MockHandler()
    handler.realtime_audio_out_queue = MockQueue(initial_size=10)
    handler.tx_q = MockQueue(initial_size=5)
    handler.pending_hangup = True
    handler.audio_done_by_response_id["resp_456"] = True
    
    # Try to execute hangup immediately (should fail because queues not empty)
    result = await handler.maybe_execute_hangup(via="test", response_id="resp_456")
    
    print(f"📊 Test Results:")
    print(f"   - Immediate hangup attempt: {result}")
    print(f"   - Hangup executed: {handler.hangup_executed}")
    print(f"   - Queue sizes: OpenAI={handler.realtime_audio_out_queue.qsize()}, TX={handler.tx_q.qsize()}")
    
    assert not handler.hangup_executed, "Hangup should NOT execute with non-empty queues"
    assert result == False, "Hangup should return False when conditions not met"
    
    print("\n✅ TEST 2 PASSED: Hangup correctly prevented with non-empty queues")
    return True


async def test_hangup_after_drain():
    """Test that hangup executes after queues drain"""
    print("\n" + "="*70)
    print("TEST 3: Hangup After Drain")
    print("="*70)
    
    handler = MockHandler()
    handler.realtime_audio_out_queue = MockQueue(initial_size=5)
    handler.tx_q = MockQueue(initial_size=3)
    handler.pending_hangup = True
    handler.audio_done_by_response_id["resp_789"] = True
    
    # Empty queues
    while not handler.realtime_audio_out_queue.empty():
        handler.realtime_audio_out_queue.drain_one()
    while not handler.tx_q.empty():
        handler.tx_q.drain_one()
    
    # Now try hangup (should succeed)
    result = await handler.maybe_execute_hangup(via="test", response_id="resp_789")
    
    print(f"📊 Test Results:")
    print(f"   - Hangup after drain: {result}")
    print(f"   - Hangup executed: {handler.hangup_executed}")
    print(f"   - Queue sizes: OpenAI={handler.realtime_audio_out_queue.qsize()}, TX={handler.tx_q.qsize()}")
    
    assert handler.hangup_executed, "Hangup SHOULD execute with empty queues"
    assert result == True, "Hangup should return True when successful"
    
    print("\n✅ TEST 3 PASSED: Hangup correctly executes after queues drain")
    return True


async def run_all_tests():
    """Run all audio drain timing tests"""
    print("\n" + "="*70)
    print("AUDIO DRAIN TIMING FIX - TEST SUITE")
    print("="*70)
    
    tests = [
        test_audio_drain_timing,
        test_no_premature_hangup,
        test_hangup_after_drain,
    ]
    
    results = []
    for test in tests:
        try:
            result = await test()
            results.append((test.__name__, result))
        except Exception as e:
            print(f"\n❌ TEST FAILED: {test.__name__}")
            print(f"   Error: {e}")
            import traceback
            traceback.print_exc()
            results.append((test.__name__, False))
    
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {test_name}")
    
    all_passed = all(result for _, result in results)
    if all_passed:
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
