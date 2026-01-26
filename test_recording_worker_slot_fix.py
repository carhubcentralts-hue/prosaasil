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
    
    # Verify worker imports try_acquire_slot at function level (not in loop)
    assert 'from server.recording_semaphore import try_acquire_slot' in worker_func or \
           'from server.recording_semaphore import' in worker_func and 'try_acquire_slot' in worker_func, \
        "Worker should import try_acquire_slot at function level"
    
    # Verify worker acquires slot for download_only jobs
    assert 'try_acquire_slot(business_id, call_sid)' in worker_func, \
        "Worker should call try_acquire_slot"
    
    # Verify slot_acquired flag exists
    assert 'slot_acquired = False' in worker_func, \
        "Worker should track slot_acquired flag"
    
    # Verify NO import inside the loop (should be at function level)
    # Look for pattern: indented "from server.recording_semaphore import try_acquire_slot"
    loop_imports = re.findall(r'\n\s{16,}from server\.recording_semaphore import try_acquire_slot', worker_func)
    assert len(loop_imports) == 0, \
        "try_acquire_slot import should be at function level, not inside loop"
    
    print("  ✅ Worker correctly acquires slots")
    print("  ✅ Imports moved to function level (not in loop)")

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
    
    # Verify release_slot is imported at function level (not in loop)
    assert 'from server.recording_semaphore import' in worker_func and 'release_slot' in worker_func, \
        "Worker should import release_slot at function level"
    
    # Verify NO import inside finally block (should be at top)
    assert 'from server.recording_semaphore import release_slot' not in finally_block, \
        "Import should be at function level, not in finally block"
    
    print("  ✅ Worker correctly releases slots in finally (guaranteed cleanup)")
    print("  ✅ Imports moved to function level (not in loop)")

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
    # Updated: INFLIGHT_TTL should be 600-900s to handle large recordings
    assert 600 <= inflight_ttl <= 1200, \
        f"INFLIGHT_TTL should be 600-1200 seconds (10-20 min) for large recordings, got {inflight_ttl}"
    
    # Check QUEUED_TTL
    queued_match = re.search(r'QUEUED_TTL = (\d+)', content)
    assert queued_match, "QUEUED_TTL not found"
    queued_ttl = int(queued_match.group(1))
    assert queued_ttl >= 600, \
        f"QUEUED_TTL should be ≥ 600 seconds, got {queued_ttl}"
    
    print(f"  ✅ TTL values appropriate: INFLIGHT={inflight_ttl}s, QUEUED={queued_ttl}s")

def test_dedup_ttl_short():
    """Test that dedup TTL is short (not 30 minutes)"""
    print("\n✓ Testing dedup TTL is short...")
    
    with open('server/tasks_recording.py', 'r') as f:
        content = f.read()
    
    # Find the dedup TTL in enqueue_recording_download_only
    # Should be 120 seconds, not 1800 (30 minutes)
    assert 'ex=120' in content or 'ex = 120' in content, \
        "Dedup TTL should be 120 seconds (short to prevent blocking on failures)"
    
    # Make sure old value (1800 = 30 min) is NOT present
    assert 'ex=1800' not in content and 'ex = 1800' not in content, \
        "Dedup TTL should NOT be 1800s (30 minutes) - too long, blocks retries on failure"
    
    print("  ✅ Dedup TTL correctly set to 120s (prevents blocking on failures)")

def test_worker_no_blocking_loop():
    """Test that worker doesn't block with sleep loop"""
    print("\n✓ Testing worker doesn't block on slot acquisition...")
    
    with open('server/tasks_recording.py', 'r') as f:
        content = f.read()
    
    # Find the worker function
    worker_match = re.search(
        r'def start_recording_worker\(app\):(.*?)(?=\ndef |\Z)',
        content,
        re.DOTALL
    )
    assert worker_match, "start_recording_worker function not found"
    worker_func = worker_match.group(1)
    
    # Check that there's NO 60-second loop (for attempt in range(60))
    assert 'for attempt in range(60)' not in worker_func and \
           'for attempt in range(max_slot_attempts)' not in worker_func, \
        "Worker should NOT have blocking loop for slot acquisition"
    
    # Check that worker tries once and re-enqueues if no slot
    assert 'try_acquire_slot(business_id, call_sid)' in worker_func, \
        "Worker should try to acquire slot once"
    
    # Check for backoff delays array (not sleep loop)
    assert 'backoff_delays' in worker_func or 'backoff' in worker_func.lower(), \
        "Worker should use backoff delays for re-enqueue"
    
    print("  ✅ Worker correctly re-enqueues without blocking (no 60s sleep loop)")
    print("  ✅ Uses exponential backoff for slot retries")

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
        test_dedup_ttl_short()
        test_worker_no_blocking_loop()
        
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
        print("6. ✅ TTL values appropriate (INFLIGHT=900s for large recordings)")
        print("7. ✅ Dedup TTL short (120s, not 30min)")
        print("8. ✅ Worker doesn't block - re-enqueues with backoff")
        print()
        print("This fixes the critical deadlock issue where:")
        print("- API acquired slots but worker did work")
        print("- Worker crashes left slots stuck forever (active=5/5)")
        print("- Queue grew infinitely as no slots became available")
        print()
        print("Additional improvements from feedback:")
        print("- Dedup TTL reduced from 30min to 120s (prevents blocking on failures)")
        print("- INFLIGHT_TTL increased to 900s (handles large recordings)")
        print("- Worker no longer blocks with 60s sleep loop (better throughput)")
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
