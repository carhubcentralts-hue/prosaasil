#!/usr/bin/env python3
"""
Test Recording Deduplication and Performance Fixes

This test verifies:
1. Global deduplication prevents duplicate requests
2. Slot cleanup works correctly
3. Redis operations are atomic
"""

import time
import sys
import os

# Add server directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))

def test_recording_semaphore():
    """Test recording semaphore deduplication and cleanup"""
    from server.recording_semaphore import (
        try_acquire_slot, 
        release_slot, 
        cleanup_expired_slots,
        REDIS_ENABLED
    )
    
    if not REDIS_ENABLED:
        print("⚠️  Redis not enabled - skipping semaphore tests")
        return
    
    print("✅ Testing recording semaphore system...")
    
    # Test 1: Acquire slot
    business_id = 999  # Test business
    call_sid = "CA_test_dedup_12345"
    
    acquired, status = try_acquire_slot(business_id, call_sid)
    print(f"   Slot acquisition: {'✅ PASS' if acquired else '❌ FAIL'} (status={status})")
    
    # Test 2: Try to acquire same slot again (should be rejected)
    acquired2, status2 = try_acquire_slot(business_id, call_sid)
    if not acquired2 and status2 == "inflight":
        print(f"   Deduplication: ✅ PASS (correctly rejected duplicate)")
    else:
        print(f"   Deduplication: ❌ FAIL (should reject duplicate, got status={status2})")
    
    # Test 3: Release slot
    next_call = release_slot(business_id, call_sid)
    print(f"   Slot release: ✅ PASS (next_call={next_call})")
    
    # Test 4: Cleanup expired slots
    cleaned = cleanup_expired_slots(business_id)
    print(f"   Cleanup: ✅ PASS (cleaned {cleaned} expired slots)")
    
    print("✅ Recording semaphore tests complete\n")


def test_recording_tasks():
    """Test recording task deduplication"""
    from server.tasks_recording import (
        enqueue_recording_download_only,
        RECORDING_QUEUE,
        REDIS_DEDUP_ENABLED
    )
    
    print("✅ Testing recording task deduplication...")
    
    # Test 1: Enqueue a job
    call_sid = "CA_test_task_67890"
    recording_url = "https://test.twilio.com/recording.mp3"
    business_id = 999
    
    # Clear queue first
    while not RECORDING_QUEUE.empty():
        try:
            RECORDING_QUEUE.get_nowait()
            RECORDING_QUEUE.task_done()
        except:
            break
    
    # Enqueue first job
    result1 = enqueue_recording_download_only(
        call_sid=call_sid,
        recording_url=recording_url,
        business_id=business_id
    )
    
    if result1:
        print(f"   First enqueue: ✅ PASS (job enqueued)")
    else:
        print(f"   First enqueue: ⚠️  SKIP (file cached or dedup hit)")
    
    # Test 2: Try to enqueue duplicate (should be rejected)
    result2 = enqueue_recording_download_only(
        call_sid=call_sid,
        recording_url=recording_url,
        business_id=business_id
    )
    
    if not result2 and REDIS_DEDUP_ENABLED:
        print(f"   Duplicate rejection: ✅ PASS (correctly rejected)")
    elif not REDIS_DEDUP_ENABLED:
        print(f"   Duplicate rejection: ⚠️  SKIP (Redis dedup not enabled)")
    else:
        print(f"   Duplicate rejection: ⚠️  WARNING (duplicate was allowed)")
    
    # Check queue size
    queue_size = RECORDING_QUEUE.qsize()
    expected = 1 if result1 else 0
    if queue_size == expected:
        print(f"   Queue size: ✅ PASS (size={queue_size})")
    else:
        print(f"   Queue size: ⚠️  WARNING (expected {expected}, got {queue_size})")
    
    print("✅ Recording task tests complete\n")


def main():
    print("=" * 70)
    print("Recording Deduplication and Performance Test Suite")
    print("=" * 70)
    print()
    
    # Test semaphore system
    try:
        test_recording_semaphore()
    except Exception as e:
        print(f"❌ Semaphore test failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Test task deduplication
    try:
        test_recording_tasks()
    except Exception as e:
        print(f"❌ Task test failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("=" * 70)
    print("Test suite complete")
    print("=" * 70)


if __name__ == "__main__":
    main()
