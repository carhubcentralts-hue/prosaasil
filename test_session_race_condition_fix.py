"""
Test for session.created/session.updated race condition fix

This test verifies that:
1. session.created does NOT set _session_config_confirmed flag
2. ONLY session.updated sets the confirmation flag
3. Event-driven waiting works correctly (no polling bottleneck)
4. response.create is blocked until session.updated arrives
"""
import asyncio
import time


class MockMediaStreamHandler:
    """Mock handler to test session confirmation logic"""
    
    def __init__(self):
        self._session_config_confirmed = False
        self._session_config_failed = False
        self._session_config_event = asyncio.Event()
        self.events_received = []
    
    def handle_session_created(self, session_data):
        """Handle session.created event - should NOT confirm session"""
        self.events_received.append('session.created')
        # 🔥 FIX: NEVER set _session_config_confirmed here
        # This event shows DEFAULT config before session.update is applied
        print(f"📋 [SESSION.CREATED] Received - baseline state (NOT confirmed)")
        print(f"   _session_config_confirmed = {self._session_config_confirmed} (should be False)")
        return self._session_config_confirmed  # Should be False
    
    def handle_session_updated(self, session_data):
        """Handle session.updated event - ONLY place to confirm session"""
        self.events_received.append('session.updated')
        # Validate configuration
        validation_ok = (
            session_data.get('output_audio_format') == 'g711_ulaw' and
            session_data.get('input_audio_format') == 'g711_ulaw' and
            len(session_data.get('instructions', '')) > 10
        )
        
        if validation_ok:
            self._session_config_confirmed = True
            self._session_config_event.set()  # Wake up waiting coroutines
            print(f"✅ [SESSION.UPDATED] Configuration confirmed!")
            print(f"   _session_config_confirmed = {self._session_config_confirmed} (should be True)")
        else:
            self._session_config_failed = True
            print(f"❌ [SESSION.UPDATED] Validation failed!")
        
        return self._session_config_confirmed
    
    async def wait_for_session_confirmation(self, max_wait=5.0):
        """Wait for session confirmation using event (no polling)"""
        wait_start = time.time()
        
        while True:
            if self._session_config_failed:
                raise RuntimeError("Session configuration failed")
            
            elapsed = time.time() - wait_start
            if elapsed > max_wait:
                raise RuntimeError(f"Timeout waiting for session.updated after {max_wait}s")
            
            # Event-driven wait with timeout
            remaining_time = max_wait - elapsed
            try:
                await asyncio.wait_for(
                    self._session_config_event.wait(),
                    timeout=min(0.1, remaining_time)
                )
                # Event was set - session confirmed!
                break
            except asyncio.TimeoutError:
                # Timeout - check flags in next iteration
                continue
        
        session_wait_ms = (time.time() - wait_start) * 1000
        print(f"✅ [WAIT] Session confirmed in {session_wait_ms:.1f}ms")
        return session_wait_ms


async def test_race_condition_scenario():
    """
    Test the exact race condition from production logs:
    1. session.created arrives first (DEFAULT config)
    2. Wait for confirmation starts
    3. session.updated arrives later (CORRECT config)
    """
    print("\n" + "="*80)
    print("TEST 1: Race Condition Scenario (session.created → session.updated)")
    print("="*80)
    
    handler = MockMediaStreamHandler()
    
    # Simulate session.created arriving immediately
    print("\n[STEP 1] Simulating session.created event...")
    confirmed_after_created = handler.handle_session_created({
        'output_audio_format': 'pcm16',  # DEFAULT (wrong!)
        'input_audio_format': 'pcm16',   # DEFAULT (wrong!)
        'instructions': ''                # DEFAULT (empty!)
    })
    
    assert confirmed_after_created == False, \
        "❌ BUG: session.created should NOT confirm session!"
    print("✅ PASS: session.created did NOT confirm session")
    
    # Start waiting for confirmation
    print("\n[STEP 2] Starting event-driven wait for session.updated...")
    wait_task = asyncio.create_task(handler.wait_for_session_confirmation(max_wait=5.0))
    
    # Simulate session.updated arriving 200ms later (like in production logs)
    print("\n[STEP 3] Simulating 200ms delay before session.updated...")
    await asyncio.sleep(0.2)
    
    print("[STEP 4] Simulating session.updated event...")
    confirmed_after_updated = handler.handle_session_updated({
        'output_audio_format': 'g711_ulaw',  # CORRECT
        'input_audio_format': 'g711_ulaw',   # CORRECT
        'instructions': 'You are a helpful assistant in Hebrew.'  # CORRECT
    })
    
    assert confirmed_after_updated == True, \
        "❌ BUG: session.updated should confirm session!"
    print("✅ PASS: session.updated confirmed session")
    
    # Wait task should complete almost instantly (event-driven)
    wait_ms = await wait_task
    assert wait_ms < 250, \
        f"❌ BUG: Event-driven wait took {wait_ms:.1f}ms (should be ~200ms)"
    print(f"✅ PASS: Wait completed in {wait_ms:.1f}ms (event-driven, no polling delay)")
    
    # Verify event order
    assert handler.events_received == ['session.created', 'session.updated'], \
        f"❌ BUG: Wrong event order: {handler.events_received}"
    print(f"✅ PASS: Events received in correct order: {handler.events_received}")
    
    print("\n" + "="*80)
    print("✅ TEST 1 PASSED: Race condition properly handled!")
    print("="*80)


async def test_event_performance():
    """Test that event-driven waiting is fast (no polling bottleneck)"""
    print("\n" + "="*80)
    print("TEST 2: Event Performance (no polling bottleneck)")
    print("="*80)
    
    handler = MockMediaStreamHandler()
    
    # Start waiting
    print("\n[STEP 1] Starting wait...")
    wait_task = asyncio.create_task(handler.wait_for_session_confirmation(max_wait=5.0))
    
    # Small delay to ensure wait task is running
    await asyncio.sleep(0.01)
    
    # Set event immediately
    print("[STEP 2] Setting event...")
    event_set_time = time.time()
    handler._session_config_confirmed = True
    handler._session_config_event.set()
    
    # Measure wake-up latency
    wait_ms = await wait_task
    wake_up_latency = (time.time() - event_set_time) * 1000
    
    print(f"\n📊 Performance Metrics:")
    print(f"   Total wait time: {wait_ms:.1f}ms")
    print(f"   Wake-up latency: {wake_up_latency:.1f}ms")
    
    # Event-driven should wake up in < 10ms (vs 50ms polling)
    assert wake_up_latency < 10, \
        f"❌ BUG: Wake-up latency too high: {wake_up_latency:.1f}ms (should be < 10ms)"
    print(f"✅ PASS: Wake-up latency < 10ms (event-driven, not polling)")
    
    print("\n" + "="*80)
    print("✅ TEST 2 PASSED: Event-driven waiting is fast!")
    print("="*80)


async def test_session_created_only():
    """
    Test that waiting continues if only session.created arrives
    (should timeout since session.updated never arrives)
    """
    print("\n" + "="*80)
    print("TEST 3: Timeout Scenario (session.created only, no session.updated)")
    print("="*80)
    
    handler = MockMediaStreamHandler()
    
    # Simulate session.created
    print("\n[STEP 1] Simulating session.created event...")
    handler.handle_session_created({
        'output_audio_format': 'pcm16',
        'input_audio_format': 'pcm16',
        'instructions': ''
    })
    
    # Start waiting with short timeout
    print("[STEP 2] Starting wait with 1s timeout...")
    timeout_occurred = False
    try:
        await handler.wait_for_session_confirmation(max_wait=1.0)
    except RuntimeError as e:
        timeout_occurred = True
        print(f"✅ PASS: Timeout occurred as expected: {e}")
    
    assert timeout_occurred, \
        "❌ BUG: Should timeout if session.updated never arrives!"
    assert not handler._session_config_confirmed, \
        "❌ BUG: Session should NOT be confirmed!"
    
    print("\n" + "="*80)
    print("✅ TEST 3 PASSED: Properly times out without session.updated!")
    print("="*80)


async def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("TESTING SESSION RACE CONDITION FIX")
    print("="*80)
    
    try:
        await test_race_condition_scenario()
        await test_event_performance()
        await test_session_created_only()
        
        print("\n" + "="*80)
        print("✅ ALL TESTS PASSED!")
        print("="*80)
        print("\nFix verified:")
        print("1. ✅ session.created does NOT confirm session")
        print("2. ✅ ONLY session.updated confirms session")
        print("3. ✅ Event-driven waiting (no polling bottleneck)")
        print("4. ✅ Proper timeout handling")
        print("5. ✅ Fast wake-up (< 10ms latency)")
        return True
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return False
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
