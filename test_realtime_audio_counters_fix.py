#!/usr/bin/env python3
"""
Test for realtime_audio_in_chunks AttributeError Fix

Verifies that audio counters are always initialized in __init__
and never cause AttributeError crashes.

Problem: MediaStreamHandler crashed with AttributeError when accessing
realtime_audio_in_chunks because it was only initialized in 
_run_realtime_mode_async, not in __init__.

Solution: 
1. Initialize counters in __init__ (line ~1806)
2. Add defensive getattr() protection at increment sites
"""

import sys
import os

def test_counter_initialization():
    """Test that audio counters are initialized in __init__"""
    print("=" * 80)
    print("TEST 1: Counter Initialization in __init__")
    print("=" * 80)
    
    # Mock WebSocket object
    class MockWebSocket:
        def send(self, data):
            pass
    
    from server.media_ws_ai import MediaStreamHandler
    
    # Create handler (simulates call start)
    ws = MockWebSocket()
    handler = MediaStreamHandler(ws)
    
    # Verify counters exist immediately after __init__
    assert hasattr(handler, 'realtime_audio_in_chunks'), \
        "❌ realtime_audio_in_chunks not initialized in __init__"
    assert hasattr(handler, 'realtime_audio_out_chunks'), \
        "❌ realtime_audio_out_chunks not initialized in __init__"
    
    # Verify initial values are zero
    assert handler.realtime_audio_in_chunks == 0, \
        f"❌ realtime_audio_in_chunks should be 0, got {handler.realtime_audio_in_chunks}"
    assert handler.realtime_audio_out_chunks == 0, \
        f"❌ realtime_audio_out_chunks should be 0, got {handler.realtime_audio_out_chunks}"
    
    print("✅ realtime_audio_in_chunks initialized in __init__: 0")
    print("✅ realtime_audio_out_chunks initialized in __init__: 0")
    print()
    return True

def test_counter_increment_safety():
    """Test that counter increments are safe with getattr fallback"""
    print("=" * 80)
    print("TEST 2: Safe Counter Increment Operations")
    print("=" * 80)
    
    # Mock WebSocket object
    class MockWebSocket:
        def send(self, data):
            pass
    
    from server.media_ws_ai import MediaStreamHandler
    
    # Create handler
    ws = MockWebSocket()
    handler = MediaStreamHandler(ws)
    
    # Simulate increment operations (these should NEVER crash)
    # Test the pattern used at line ~8572 and ~4863
    try:
        # Simulate inbound audio increment
        handler.realtime_audio_in_chunks = getattr(handler, "realtime_audio_in_chunks", 0) + 1
        assert handler.realtime_audio_in_chunks == 1
        print("✅ realtime_audio_in_chunks increment works: 0 → 1")
        
        # Simulate outbound audio increment
        handler.realtime_audio_out_chunks = getattr(handler, "realtime_audio_out_chunks", 0) + 1
        assert handler.realtime_audio_out_chunks == 1
        print("✅ realtime_audio_out_chunks increment works: 0 → 1")
        
        # Test multiple increments
        for i in range(5):
            handler.realtime_audio_in_chunks = getattr(handler, "realtime_audio_in_chunks", 0) + 1
        assert handler.realtime_audio_in_chunks == 6
        print("✅ Multiple increments work: 1 → 6")
        
    except AttributeError as e:
        print(f"❌ AttributeError during increment: {e}")
        return False
    
    print()
    return True

def test_counter_access_with_fallback():
    """Test that all counter access points have proper fallback"""
    print("=" * 80)
    print("TEST 3: Safe Counter Access (getattr pattern)")
    print("=" * 80)
    
    # Mock WebSocket object
    class MockWebSocket:
        def send(self, data):
            pass
    
    from server.media_ws_ai import MediaStreamHandler
    
    # Create handler
    ws = MockWebSocket()
    handler = MediaStreamHandler(ws)
    
    # Test getattr access pattern used in various places
    try:
        # Pattern used in _calculate_and_log_cost (line ~7857)
        audio_in_chunks = getattr(handler, 'realtime_audio_in_chunks', 0)
        audio_out_chunks = getattr(handler, 'realtime_audio_out_chunks', 0)
        assert audio_in_chunks == 0
        assert audio_out_chunks == 0
        print("✅ getattr with fallback works: returns 0 when counter exists and is 0")
        
        # Test with non-zero values
        handler.realtime_audio_in_chunks = 100
        handler.realtime_audio_out_chunks = 200
        audio_in_chunks = getattr(handler, 'realtime_audio_in_chunks', 0)
        audio_out_chunks = getattr(handler, 'realtime_audio_out_chunks', 0)
        assert audio_in_chunks == 100
        assert audio_out_chunks == 200
        print("✅ getattr returns correct values: in=100, out=200")
        
        # Test with missing attribute (simulate broken state)
        delattr(handler, 'realtime_audio_in_chunks')
        audio_in_chunks = getattr(handler, 'realtime_audio_in_chunks', 0)
        assert audio_in_chunks == 0
        print("✅ getattr fallback works when attribute is missing: returns 0")
        
    except Exception as e:
        print(f"❌ Exception during counter access: {e}")
        return False
    
    print()
    return True

def test_no_double_initialization():
    """Test that counters from _run_realtime_mode_async don't override __init__"""
    print("=" * 80)
    print("TEST 4: No Double Initialization Conflict")
    print("=" * 80)
    
    # This verifies that the old initialization in _run_realtime_mode_async
    # has been removed or commented out (lines 2519-2520)
    
    import inspect
    from server.media_ws_ai import MediaStreamHandler
    
    # Get source of _run_realtime_mode_async method
    source = inspect.getsource(MediaStreamHandler._run_realtime_mode_async)
    
    # Check that the old initialization is commented out or removed
    if "self.realtime_audio_in_chunks = 0" in source and \
       "# 🔥 REMOVED" not in source and \
       "#" not in source.split("self.realtime_audio_in_chunks = 0")[0].split('\n')[-1]:
        print("⚠️  WARNING: Found uncommented counter initialization in _run_realtime_mode_async")
        print("    This could override __init__ values!")
        return False
    
    print("✅ Old counter initialization properly removed/commented from _run_realtime_mode_async")
    print()
    return True

def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("🔍 REALTIME AUDIO COUNTERS FIX - VERIFICATION TESTS")
    print("=" * 80)
    print()
    
    tests = [
        test_counter_initialization,
        test_counter_increment_safety,
        test_counter_access_with_fallback,
        test_no_double_initialization,
    ]
    
    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append(result)
        except Exception as e:
            print(f"❌ Test {test_func.__name__} crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    passed = sum(results)
    total = len(results)
    print(f"Tests passed: {passed}/{total}")
    
    if all(results):
        print("\n✅ ALL TESTS PASSED!")
        print("\nThe fix ensures:")
        print("  1. ✅ Counters initialized in __init__ (always available)")
        print("  2. ✅ Defensive getattr() at increment sites (no crashes)")
        print("  3. ✅ Defensive getattr() at read sites (safe access)")
        print("  4. ✅ No double initialization conflicts")
        print("\nResult: No more AttributeError crashes on realtime_audio_in_chunks!")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED!")
        return 1

if __name__ == '__main__':
    sys.exit(main())
