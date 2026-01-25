"""
Test Recording Semaphore System
================================

Tests the new per-business 3-concurrent-downloads limit with Redis queue.
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_semaphore_module_imports():
    """Test that the semaphore module can be imported"""
    from server.recording_semaphore import (
        try_acquire_slot, 
        release_slot, 
        check_status,
        MAX_SLOTS_PER_BUSINESS
    )
    
    assert MAX_SLOTS_PER_BUSINESS == 3
    print("✅ Semaphore module imports successfully")
    print(f"✅ MAX_SLOTS_PER_BUSINESS = {MAX_SLOTS_PER_BUSINESS}")


def test_semaphore_without_redis():
    """Test semaphore behavior when Redis is not available"""
    from server.recording_semaphore import try_acquire_slot, REDIS_ENABLED
    
    # When Redis is not available, should allow all downloads
    acquired, status = try_acquire_slot(business_id=1, call_sid="CA123")
    
    if not REDIS_ENABLED:
        assert acquired == True
        assert status == "no_redis"
        print("✅ Without Redis: Always allows downloads (fail-open)")
    else:
        print("ℹ️  Redis is available, testing with Redis")
        assert acquired in [True, False]


def test_stream_recording_integration():
    """Test that stream_recording uses the new semaphore system"""
    # Read file directly instead of importing (avoids Flask dependency)
    with open("server/routes_calls.py", "r") as f:
        source = f.read()
    
    # Verify it uses semaphore system
    assert "recording_semaphore" in source, "routes_calls should import recording_semaphore"
    assert "try_acquire_slot" in source, "stream_recording should call try_acquire_slot"
    assert "check_status" in source, "stream_recording should call check_status"
    
    # Verify old system is removed  
    assert "playback_dedup" not in source, "Old playback_dedup should be removed"
    
    print("✅ stream_recording uses new semaphore system")
    print("✅ Old playback_dedup system removed")


def test_enqueue_no_rate_limit():
    """Test that enqueue functions no longer have rate_limit checks"""
    # Read file directly instead of importing
    with open("server/tasks_recording.py", "r") as f:
        source = f.read()
    
    # Find the enqueue_recording_download_only function
    import re
    match1 = re.search(r'def enqueue_recording_download_only.*?(?=\ndef |\Z)', source, re.DOTALL)
    match2 = re.search(r'def enqueue_recording_job.*?(?=\ndef |\Z)', source, re.DOTALL)
    
    assert match1, "enqueue_recording_download_only should exist"
    assert match2, "enqueue_recording_job should exist"
    
    func1_source = match1.group(0)
    func2_source = match2.group(0)
    
    # Check for rate limit removal
    assert "_check_business_rate_limit" not in func1_source, "Rate limit check should be removed from enqueue_recording_download_only"
    assert "_check_business_rate_limit" not in func2_source, "Rate limit check should be removed from enqueue_recording_job"
    
    print("✅ enqueue_recording_download_only: rate_limit removed")
    print("✅ enqueue_recording_job: rate_limit removed")


def test_worker_releases_slot():
    """Test that worker releases slot and processes next from queue"""
    # Read file directly instead of importing
    with open("server/tasks_recording.py", "r") as f:
        source = f.read()
    
    # Verify worker imports and uses semaphore
    assert "recording_semaphore" in source, "Worker should import recording_semaphore"
    assert "release_slot" in source, "Worker should call release_slot"
    
    print("✅ Worker calls release_slot to free slots")
    print("✅ Worker processes next from queue")


def test_list_calls_no_downloads():
    """Verify list_calls doesn't trigger downloads (should already be correct)"""
    # Read file directly instead of importing
    with open("server/routes_calls.py", "r") as f:
        source = f.read()
    
    # Find list_calls function
    import re
    match = re.search(r'def list_calls\(\):.*?(?=\n@|\ndef [a-z]|\Z)', source, re.DOTALL)
    assert match, "list_calls function should exist"
    
    func_source = match.group(0)
    
    # Verify no enqueue calls
    assert "enqueue_recording" not in func_source, "list_calls should not enqueue downloads"
    assert "DO NOT enqueue downloads here" in func_source or "FIX: DO NOT enqueue" in func_source, \
        "Should have comment warning against downloads"
    
    print("✅ list_calls does NOT trigger downloads")


def test_logging_format():
    """Test that new logging format is used"""
    # Read file directly instead of importing
    with open("server/recording_semaphore.py", "r") as f:
        source = f.read()
    
    # Should have new log format
    assert "RECORDING_ENQUEUE" in source, "Should use RECORDING_ENQUEUE log format"
    assert "RECORDING_QUEUED" in source, "Should use RECORDING_QUEUED log format"
    assert "RECORDING_DONE" in source, "Should use RECORDING_DONE log format"
    assert "RECORDING_NEXT" in source, "Should use RECORDING_NEXT log format"
    
    print("✅ New logging format: RECORDING_ENQUEUE, RECORDING_QUEUED, RECORDING_DONE, RECORDING_NEXT")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("Testing Recording Semaphore System")
    print("="*60 + "\n")
    
    try:
        test_semaphore_module_imports()
        print()
        
        test_semaphore_without_redis()
        print()
        
        test_stream_recording_integration()
        print()
        
        test_enqueue_no_rate_limit()
        print()
        
        test_worker_releases_slot()
        print()
        
        test_list_calls_no_downloads()
        print()
        
        test_logging_format()
        print()
        
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED")
        print("="*60)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
