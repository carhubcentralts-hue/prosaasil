"""
Test for recording worker slot acquisition fix

This test verifies the critical fix:
- API no longer acquires slots (prevents stuck slots)
- Worker acquires slots at start and releases in finally
- Guarantees slot release even if worker crashes

Key changes tested:
1. routes_calls.py: download_recording() and stream_recording() don't call try_acquire_slot()
2. tasks_recording.py: Worker acquires slot before processing, releases in finally
3. Frontend: Reduced MAX_RETRIES from 10 to 5
"""
import sys
import os
import re

def test_api_no_slot_acquisition():
    """Test that API endpoints DO NOT acquire slots"""
    print("✓ Testing API endpoints don't acquire slots...")
    
    with open('server/routes_calls.py', 'r') as f:
        content = f.read()
    
    # Find download_recording function
    download_func_match = re.search(
        r'def download_recording\(call_sid\):(.*?)(?=\ndef |\Z)',
        content,
        re.DOTALL
    )
    assert download_func_match, "download_recording function not found"
    download_func = download_func_match.group(1)
    
    # Verify it does NOT call try_acquire_slot
    assert 'try_acquire_slot' not in download_func, \
        "❌ download_recording should NOT call try_acquire_slot (causes stuck slots)"
    
    # Verify it does NOT call release_slot (since it doesn't acquire)
    assert 'release_slot(business_id, call_sid)' not in download_func, \
        "❌ download_recording should NOT release slots (API doesn't acquire them)"
    
    # Verify it DOES call enqueue_recording_download_only
    assert 'enqueue_recording_download_only' in download_func, \
        "download_recording should enqueue jobs to worker"
    
    print("  ✅ download_recording correctly enqueues without acquiring slots")
    
    # Find stream_recording function
    stream_func_match = re.search(
        r'def stream_recording\(call_sid\):(.*?)(?=\ndef |\Z)',
        content,
        re.DOTALL
    )
    assert stream_func_match, "stream_recording function not found"
    stream_func = stream_func_match.group(1)
    
    # Verify it does NOT call try_acquire_slot
    assert 'try_acquire_slot' not in stream_func, \
        "❌ stream_recording should NOT call try_acquire_slot (causes stuck slots)"
    
    # Verify it does NOT call release_slot
    assert 'release_slot(business_id, call_sid)' not in stream_func, \
        "❌ stream_recording should NOT release slots (API doesn't acquire them)"
    
    # Verify it DOES call enqueue_recording_download_only
    assert 'enqueue_recording_download_only' in stream_func, \
        "stream_recording should enqueue jobs to worker"
    
    print("  ✅ stream_recording correctly enqueues without acquiring slots")

def test_worker_acquires_slots():
    """Test that worker acquires slots at start"""
    print("\n✓ Testing worker acquires slots...")
    
    with open('server/tasks_recording.py', 'r') as f:
        content = f.read()
    
    # Find the start_recording_worker function
    worker_match = re.search(
        r'def start_recording_worker\(app\):(.*?)(?=\ndef |\Z)',
        content,
        re.DOTALL
    )
    assert worker_match, "start_recording_worker function not found"
    worker_func = worker_match.group(1)
    
    # Verify worker imports try_acquire_slot
    assert 'from server.recording_semaphore import try_acquire_slot' in worker_func, \
        "Worker should import try_acquire_slot"
    
    # Verify worker acquires slot for download_only jobs
    assert 'try_acquire_slot(business_id, call_sid)' in worker_func, \
        "Worker should call try_acquire_slot"
    
    # Verify slot_acquired flag exists
    assert 'slot_acquired = False' in worker_func or 'slot_acquired' in content[:worker_match.start()], \
        "Worker should track slot_acquired flag"
    
    print("  ✅ Worker correctly acquires slots")

def test_worker_releases_slots_in_finally():
    """Test that worker ALWAYS releases slots in finally block"""
    print("\n✓ Testing worker releases slots in finally...")
    
    with open('server/tasks_recording.py', 'r') as f:
        content = f.read()
    
    # Find the start_recording_worker function
    worker_match = re.search(
        r'def start_recording_worker\(app\):(.*?)(?=\ndef |\Z)',
        content,
        re.DOTALL
    )
    assert worker_match, "start_recording_worker function not found"
    worker_func = worker_match.group(1)
    
    # Check for finally block
    assert 'finally:' in worker_func, "Worker should have finally block"
    
    # Find the finally block
    finally_match = re.search(r'finally:(.*?)(?=\n\s{0,12}[^ ]|\Z)', worker_func, re.DOTALL)
    assert finally_match, "Finally block not found"
    finally_block = finally_match.group(1)
    
    # Verify finally block releases slot
    assert 'release_slot' in finally_block, \
        "Finally block should call release_slot"
    
    # Verify it checks slot_acquired flag
    assert 'slot_acquired' in finally_block, \
        "Finally block should check slot_acquired flag"
    
    # Verify it imports release_slot
    assert 'from server.recording_semaphore import release_slot' in worker_func, \
        "Worker should import release_slot in finally block"
    
    print("  ✅ Worker correctly releases slots in finally (guaranteed cleanup)")

def test_frontend_reduced_retries():
    """Test that frontend reduced MAX_RETRIES"""
    print("\n✓ Testing frontend retry reduction...")
    
    with open('client/src/shared/components/AudioPlayer.tsx', 'r') as f:
        content = f.read()
    
    # Find MAX_RETRIES constant
    max_retries_match = re.search(r'const MAX_RETRIES = (\d+);', content)
    assert max_retries_match, "MAX_RETRIES constant not found"
    
    max_retries = int(max_retries_match.group(1))
    assert max_retries <= 5, f"MAX_RETRIES should be ≤ 5, got {max_retries}"
    
    print(f"  ✅ Frontend MAX_RETRIES correctly set to {max_retries}")

def test_frontend_stops_on_failed():
    """Test that frontend stops polling on 'failed' status"""
    print("\n✓ Testing frontend stops on failed status...")
    
    with open('client/src/shared/components/AudioPlayer.tsx', 'r') as f:
        content = f.read()
    
    # Check for failed status check
    assert "data.status === 'failed'" in content, \
        "Frontend should check for 'failed' status"
    
    # Check that it throws error (stops polling)
    assert "throw new Error" in content, \
        "Frontend should stop polling on failed status"
    
    print("  ✅ Frontend correctly stops polling on failed status")

def test_frontend_validates_blob():
    """Test that frontend validates blob before creating URL"""
    print("\n✓ Testing frontend blob validation...")
    
    with open('client/src/shared/components/AudioPlayer.tsx', 'r') as f:
        content = f.read()
    
    # Check for blob size validation
    assert 'blob.size' in content, \
        "Frontend should validate blob size"
    
    # Check for error on empty blob
    assert 'blob.size === 0' in content or 'blob.size == 0' in content, \
        "Frontend should check for empty blob"
    
    print("  ✅ Frontend correctly validates blob before creating URL")

def test_semaphore_ttl_values():
    """Test that TTL values are appropriate"""
    print("\n✓ Testing semaphore TTL values...")
    
    with open('server/recording_semaphore.py', 'r') as f:
        content = f.read()
    
    # Check INFLIGHT_TTL
    inflight_match = re.search(r'INFLIGHT_TTL = (\d+)', content)
    assert inflight_match, "INFLIGHT_TTL not found"
    inflight_ttl = int(inflight_match.group(1))
    assert 60 <= inflight_ttl <= 300, \
        f"INFLIGHT_TTL should be 60-300 seconds, got {inflight_ttl}"
    
    # Check QUEUED_TTL
    queued_match = re.search(r'QUEUED_TTL = (\d+)', content)
    assert queued_match, "QUEUED_TTL not found"
    queued_ttl = int(queued_match.group(1))
    assert queued_ttl >= 600, \
        f"QUEUED_TTL should be ≥ 600 seconds, got {queued_ttl}"
    
    print(f"  ✅ TTL values appropriate: INFLIGHT={inflight_ttl}s, QUEUED={queued_ttl}s")

def run_all_tests():
    """Run all tests"""
    print("=" * 70)
    print("RECORDING WORKER SLOT ACQUISITION FIX - VERIFICATION TESTS")
    print("=" * 70)
    print()
    
    try:
        test_api_no_slot_acquisition()
        test_worker_acquires_slots()
        test_worker_releases_slots_in_finally()
        test_frontend_reduced_retries()
        test_frontend_stops_on_failed()
        test_frontend_validates_blob()
        test_semaphore_ttl_values()
        
        print()
        print("=" * 70)
        print("✅ ALL TESTS PASSED")
        print("=" * 70)
        print()
        print("Summary of fixes:")
        print("1. ✅ API endpoints no longer acquire slots (prevents deadlock)")
        print("2. ✅ Worker acquires slots at start and releases in finally")
        print("3. ✅ Frontend reduced retries from 10 to 5")
        print("4. ✅ Frontend stops polling on 'failed' status")
        print("5. ✅ Frontend validates blob size before creating URL")
        print("6. ✅ TTL values appropriate for cleanup")
        print()
        print("This fixes the critical deadlock issue where:")
        print("- API acquired slots but worker did work")
        print("- Worker crashes left slots stuck forever (active=5/5)")
        print("- Queue grew infinitely as no slots became available")
        print()
        return True
        
    except AssertionError as e:
        print()
        print("=" * 70)
        print(f"❌ TEST FAILED: {e}")
        print("=" * 70)
        return False
    except Exception as e:
        print()
        print("=" * 70)
        print(f"❌ UNEXPECTED ERROR: {e}")
        print("=" * 70)
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
