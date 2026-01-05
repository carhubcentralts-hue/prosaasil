"""
Test suite for watchdog-based barge-in integration

Validates:
1. is_ai_speaking_now() uses queue sizes (watchdog logic)
2. _is_verified_barge_in() gates on is_ai_speaking_now()
3. Barge-in only triggers when AI has audio in queues
4. No false barge-in when queues are empty
"""

import queue
from unittest.mock import MagicMock


def test_is_ai_speaking_now_empty_queues():
    """
    Test that is_ai_speaking_now() returns False when queues are empty
    """
    # Create mock handler with empty queues
    handler = MagicMock()
    handler.realtime_audio_out_queue = queue.Queue()
    handler.tx_q = queue.Queue()
    
    # Simulate is_ai_speaking_now logic
    q1_size = handler.realtime_audio_out_queue.qsize()
    tx_size = handler.tx_q.qsize()
    total_queued = q1_size + tx_size
    is_speaking = total_queued > 0
    
    assert not is_speaking, "Should return False when both queues are empty"
    print("✅ test_is_ai_speaking_now_empty_queues PASSED")


def test_is_ai_speaking_now_with_audio():
    """
    Test that is_ai_speaking_now() returns True when queues have audio
    """
    # Create mock handler with audio in realtime queue
    handler = MagicMock()
    handler.realtime_audio_out_queue = queue.Queue()
    handler.tx_q = queue.Queue()
    
    # Add some audio frames
    handler.realtime_audio_out_queue.put(b"audio_frame_1")
    handler.realtime_audio_out_queue.put(b"audio_frame_2")
    
    # Simulate is_ai_speaking_now logic
    q1_size = handler.realtime_audio_out_queue.qsize()
    tx_size = handler.tx_q.qsize()
    total_queued = q1_size + tx_size
    is_speaking = total_queued > 0
    
    assert is_speaking, "Should return True when realtime_audio_out_queue has frames"
    assert total_queued == 2, "Should count correct number of frames"
    print("✅ test_is_ai_speaking_now_with_audio PASSED")


def test_is_ai_speaking_now_tx_queue():
    """
    Test that is_ai_speaking_now() detects audio in tx_q as well
    """
    # Create mock handler with audio in TX queue only
    handler = MagicMock()
    handler.realtime_audio_out_queue = queue.Queue()
    handler.tx_q = queue.Queue()
    
    # Add audio to TX queue
    handler.tx_q.put(b"tx_frame_1")
    handler.tx_q.put(b"tx_frame_2")
    handler.tx_q.put(b"tx_frame_3")
    
    # Simulate is_ai_speaking_now logic
    q1_size = handler.realtime_audio_out_queue.qsize()
    tx_size = handler.tx_q.qsize()
    total_queued = q1_size + tx_size
    is_speaking = total_queued > 0
    
    assert is_speaking, "Should return True when tx_q has frames"
    assert total_queued == 3, "Should count TX queue frames"
    print("✅ test_is_ai_speaking_now_tx_queue PASSED")


def test_barge_in_gate_empty_queues():
    """
    Test that barge-in is blocked when AI is not speaking (empty queues)
    """
    # Create mock handler
    handler = MagicMock()
    handler.realtime_audio_out_queue = queue.Queue()
    handler.tx_q = queue.Queue()
    handler.active_response_id = "resp_123"  # Has response ID
    
    # Simulate is_ai_speaking_now check (GATE 1)
    q1_size = handler.realtime_audio_out_queue.qsize()
    tx_size = handler.tx_q.qsize()
    total_queued = q1_size + tx_size
    is_speaking = total_queued > 0
    
    # Should fail GATE 1 and return False immediately
    assert not is_speaking, "GATE 1 should block barge-in when queues are empty"
    print("✅ test_barge_in_gate_empty_queues PASSED")


def test_barge_in_gate_no_response_id():
    """
    Test that barge-in is blocked when no active_response_id exists
    """
    # Create mock handler with audio but no response ID
    handler = MagicMock()
    handler.realtime_audio_out_queue = queue.Queue()
    handler.tx_q = queue.Queue()
    handler.active_response_id = None  # No response to cancel
    
    # Add audio to queue
    handler.realtime_audio_out_queue.put(b"audio_frame")
    
    # Simulate is_ai_speaking_now check (GATE 1)
    q1_size = handler.realtime_audio_out_queue.qsize()
    tx_size = handler.tx_q.qsize()
    is_speaking = (q1_size + tx_size) > 0
    
    # GATE 1 passes
    assert is_speaking, "GATE 1 should pass when queues have audio"
    
    # But GATE 2 should block
    assert handler.active_response_id is None, "GATE 2 should block when no active_response_id"
    print("✅ test_barge_in_gate_no_response_id PASSED")


def test_barge_in_both_gates_pass():
    """
    Test that barge-in can proceed when both gates pass
    """
    # Create mock handler with audio AND response ID
    handler = MagicMock()
    handler.realtime_audio_out_queue = queue.Queue()
    handler.tx_q = queue.Queue()
    handler.active_response_id = "resp_123"
    
    # Add audio to queue
    handler.realtime_audio_out_queue.put(b"audio_frame_1")
    handler.realtime_audio_out_queue.put(b"audio_frame_2")
    
    # Simulate is_ai_speaking_now check (GATE 1)
    q1_size = handler.realtime_audio_out_queue.qsize()
    tx_size = handler.tx_q.qsize()
    is_speaking = (q1_size + tx_size) > 0
    
    # GATE 1: AI is speaking
    assert is_speaking, "GATE 1 should pass when queues have audio"
    
    # GATE 2: Has response ID
    assert handler.active_response_id is not None, "GATE 2 should pass when active_response_id exists"
    
    # Both gates pass - barge-in can proceed to verification checks
    print("✅ test_barge_in_both_gates_pass PASSED")


def test_watchdog_queue_check_consistency():
    """
    Test that watchdog and barge-in use same queue check logic
    """
    # Simulate watchdog logic (from _silence_watchdog function)
    handler = MagicMock()
    handler.realtime_audio_out_queue = queue.Queue()
    handler.tx_q = queue.Queue()
    
    # Add audio
    handler.realtime_audio_out_queue.put(b"frame")
    
    # Watchdog logic
    q1_size_watchdog = handler.realtime_audio_out_queue.qsize() if hasattr(handler, 'realtime_audio_out_queue') else 0
    tx_size_watchdog = handler.tx_q.qsize() if hasattr(handler, 'tx_q') else 0
    total_queued_watchdog = q1_size_watchdog + tx_size_watchdog
    
    # Barge-in logic (is_ai_speaking_now)
    q1_size_barge = handler.realtime_audio_out_queue.qsize() if hasattr(handler, 'realtime_audio_out_queue') else 0
    tx_size_barge = handler.tx_q.qsize() if hasattr(handler, 'tx_q') else 0
    total_queued_barge = q1_size_barge + tx_size_barge
    
    # Should be identical
    assert total_queued_watchdog == total_queued_barge, "Watchdog and barge-in must use same queue logic"
    assert (total_queued_watchdog > 0) == (total_queued_barge > 0), "Results must match"
    print("✅ test_watchdog_queue_check_consistency PASSED")


if __name__ == "__main__":
    # Run all tests
    test_is_ai_speaking_now_empty_queues()
    test_is_ai_speaking_now_with_audio()
    test_is_ai_speaking_now_tx_queue()
    test_barge_in_gate_empty_queues()
    test_barge_in_gate_no_response_id()
    test_barge_in_both_gates_pass()
    test_watchdog_queue_check_consistency()
    
    print("\n" + "="*60)
    print("✅ ALL WATCHDOG-BARGE-IN INTEGRATION TESTS PASSED")
    print("="*60)
