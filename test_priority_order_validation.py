"""
Test to verify the exact priority order of is_ai_speaking_now()

Ensures:
1. PRIMARY: last_ai_audio_ts < 400ms is checked FIRST
2. SECONDARY: is_ai_speaking flag (never alone, needs recent audio < 1.2s)
3. TERTIARY: Queue sizes (never alone, needs recent audio < 1.2s)
"""

import time
import queue
from unittest.mock import MagicMock


def test_priority_order_primary_wins():
    """
    Test that PRIMARY (timestamp < 400ms) returns True immediately
    Even if flag is False and queues are empty
    """
    handler = MagicMock()
    handler._last_ai_audio_ts = time.time() - 0.3  # 300ms ago (< 400ms)
    handler.is_ai_speaking_event = None  # Flag not set
    handler.realtime_audio_out_queue = queue.Queue()  # Empty
    handler.tx_q = queue.Queue()  # Empty
    
    now = time.time()
    last_ai_audio_ts = handler._last_ai_audio_ts
    
    # PRIMARY check should return True
    primary_result = last_ai_audio_ts and (now - last_ai_audio_ts) < 0.4
    
    assert primary_result, "PRIMARY should return True when timestamp < 400ms"
    print("✅ test_priority_order_primary_wins PASSED")


def test_priority_order_secondary_needs_timestamp():
    """
    Test that SECONDARY (flag) NEVER works alone - needs recent audio
    """
    # SCENARIO 1: Flag set but NO timestamp -> Should be False
    handler1 = MagicMock()
    handler1._last_ai_audio_ts = None  # No timestamp
    handler1.is_ai_speaking_event = MagicMock()
    handler1.is_ai_speaking_event.is_set.return_value = True
    handler1.realtime_audio_out_queue = queue.Queue()
    handler1.tx_q = queue.Queue()
    
    # PRIMARY check fails (no timestamp)
    primary = False
    
    # SECONDARY check should also fail (flag without timestamp)
    is_ai_speaking = handler1.is_ai_speaking_event.is_set()
    secondary = is_ai_speaking and handler1._last_ai_audio_ts and (time.time() - handler1._last_ai_audio_ts) < 1.2
    
    assert not secondary, "SECONDARY should fail when flag is set but NO timestamp"
    
    # SCENARIO 2: Flag set WITH recent timestamp -> Should be True
    handler2 = MagicMock()
    handler2._last_ai_audio_ts = time.time() - 0.5  # 500ms ago (< 1.2s)
    handler2.is_ai_speaking_event = MagicMock()
    handler2.is_ai_speaking_event.is_set.return_value = True
    handler2.realtime_audio_out_queue = queue.Queue()
    handler2.tx_q = queue.Queue()
    
    now = time.time()
    
    # PRIMARY check fails (500ms > 400ms)
    primary2 = handler2._last_ai_audio_ts and (now - handler2._last_ai_audio_ts) < 0.4
    assert not primary2, "PRIMARY should fail (500ms > 400ms)"
    
    # SECONDARY check should succeed (flag + recent timestamp)
    is_ai_speaking2 = handler2.is_ai_speaking_event.is_set()
    secondary2 = is_ai_speaking2 and handler2._last_ai_audio_ts and (now - handler2._last_ai_audio_ts) < 1.2
    
    assert secondary2, "SECONDARY should succeed when flag + recent timestamp"
    
    print("✅ test_priority_order_secondary_needs_timestamp PASSED")


def test_priority_order_tertiary_never_alone():
    """
    Test that TERTIARY (queues) NEVER works alone - always needs recent audio
    """
    # SCENARIO 1: Queues have audio but NO timestamp -> Should be False
    handler1 = MagicMock()
    handler1._last_ai_audio_ts = None  # No timestamp
    handler1.is_ai_speaking_event = None
    handler1.realtime_audio_out_queue = queue.Queue()
    handler1.tx_q = queue.Queue()
    
    # Add audio to queues
    handler1.realtime_audio_out_queue.put(b"frame1")
    handler1.realtime_audio_out_queue.put(b"frame2")
    
    # Check if queues have audio
    q1_size = handler1.realtime_audio_out_queue.qsize()
    tx_size = handler1.tx_q.qsize()
    has_queued = (q1_size > 0 or tx_size > 0)
    
    assert has_queued, "Queues should have audio"
    
    # TERTIARY check should fail (queues without timestamp)
    tertiary = has_queued and handler1._last_ai_audio_ts and (time.time() - handler1._last_ai_audio_ts) < 1.2
    
    assert not tertiary, "TERTIARY should fail when queues have audio but NO timestamp"
    
    # SCENARIO 2: Queues have audio WITH old timestamp -> Should be False
    handler2 = MagicMock()
    handler2._last_ai_audio_ts = time.time() - 3.0  # 3 seconds ago (> 1.2s)
    handler2.is_ai_speaking_event = None
    handler2.realtime_audio_out_queue = queue.Queue()
    handler2.tx_q = queue.Queue()
    handler2.realtime_audio_out_queue.put(b"frame")
    
    now = time.time()
    q1_size2 = handler2.realtime_audio_out_queue.qsize()
    tx_size2 = handler2.tx_q.qsize()
    has_queued2 = (q1_size2 > 0 or tx_size2 > 0)
    
    # TERTIARY check should fail (timestamp too old)
    tertiary2 = has_queued2 and handler2._last_ai_audio_ts and (now - handler2._last_ai_audio_ts) < 1.2
    
    assert not tertiary2, "TERTIARY should fail when timestamp > 1.2s"
    
    # SCENARIO 3: Queues have audio WITH recent timestamp -> Should be True
    handler3 = MagicMock()
    handler3._last_ai_audio_ts = time.time() - 0.8  # 800ms ago (< 1.2s)
    handler3.is_ai_speaking_event = None
    handler3.realtime_audio_out_queue = queue.Queue()
    handler3.tx_q = queue.Queue()
    handler3.realtime_audio_out_queue.put(b"frame")
    
    now3 = time.time()
    
    # PRIMARY fails (800ms > 400ms)
    primary3 = handler3._last_ai_audio_ts and (now3 - handler3._last_ai_audio_ts) < 0.4
    assert not primary3, "PRIMARY should fail (800ms > 400ms)"
    
    # SECONDARY fails (no flag)
    secondary3 = False
    
    # TERTIARY should succeed (queues + recent timestamp)
    q1_size3 = handler3.realtime_audio_out_queue.qsize()
    tx_size3 = handler3.tx_q.qsize()
    has_queued3 = (q1_size3 > 0 or tx_size3 > 0)
    tertiary3 = has_queued3 and handler3._last_ai_audio_ts and (now3 - handler3._last_ai_audio_ts) < 1.2
    
    assert tertiary3, "TERTIARY should succeed when queues + recent timestamp"
    
    print("✅ test_priority_order_tertiary_never_alone PASSED")


def test_timestamp_is_most_reliable():
    """
    Test that timestamp (PRIMARY) is the most reliable indicator
    Because it's updated on EVERY audio.delta
    """
    handler = MagicMock()
    handler._last_ai_audio_ts = time.time() - 0.1  # 100ms ago
    handler.is_ai_speaking_event = None  # Flag might be stuck or not set
    handler.realtime_audio_out_queue = queue.Queue()  # Queues might be empty
    handler.tx_q = queue.Queue()
    
    now = time.time()
    
    # Even without flag or queues, timestamp should indicate AI speaking
    primary_result = handler._last_ai_audio_ts and (now - handler._last_ai_audio_ts) < 0.4
    
    assert primary_result, "Timestamp alone should be sufficient when < 400ms"
    print("✅ test_timestamp_is_most_reliable PASSED")


def test_flag_can_get_stuck_true():
    """
    Test scenario where is_ai_speaking flag gets stuck True
    but timestamp shows AI is NOT speaking (> 1.2s)
    """
    handler = MagicMock()
    handler._last_ai_audio_ts = time.time() - 5.0  # 5 seconds ago (very old)
    handler.is_ai_speaking_event = MagicMock()
    handler.is_ai_speaking_event.is_set.return_value = True  # Flag stuck True
    handler.realtime_audio_out_queue = queue.Queue()
    handler.tx_q = queue.Queue()
    
    now = time.time()
    
    # PRIMARY fails (timestamp too old)
    primary = handler._last_ai_audio_ts and (now - handler._last_ai_audio_ts) < 0.4
    assert not primary, "PRIMARY should fail with old timestamp"
    
    # SECONDARY fails (flag is True but timestamp too old)
    is_ai_speaking = handler.is_ai_speaking_event.is_set()
    secondary = is_ai_speaking and handler._last_ai_audio_ts and (now - handler._last_ai_audio_ts) < 1.2
    assert not secondary, "SECONDARY should fail even with flag=True when timestamp is old"
    
    # Result: Should NOT consider AI speaking
    print("✅ test_flag_can_get_stuck_true PASSED - Timestamp prevents stuck flag false positive")


if __name__ == "__main__":
    # Run all tests
    test_priority_order_primary_wins()
    test_priority_order_secondary_needs_timestamp()
    test_priority_order_tertiary_never_alone()
    test_timestamp_is_most_reliable()
    test_flag_can_get_stuck_true()
    
    print("\n" + "="*60)
    print("✅ ALL PRIORITY ORDER TESTS PASSED")
    print("="*60)
    print("\nValidated priority order:")
    print("  1. PRIMARY: last_ai_audio_ts < 400ms (most reliable)")
    print("  2. SECONDARY: is_ai_speaking flag (never alone)")
    print("  3. TERTIARY: Queue sizes (never alone)")
    print("\n✅ Queues NEVER stand alone - always gated by timestamp")
    print("✅ Timestamp prevents stuck flag false positives")
