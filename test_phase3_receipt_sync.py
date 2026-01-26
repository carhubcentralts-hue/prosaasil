"""Test Phase 3: Receipt Sync worker-only with cancel support"""
import inspect
import sys
import os

# Add server directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))


def test_no_thread_fallback_code():
    """Verify thread fallback code removed"""
    # Read source file directly
    with open('server/routes_receipts.py', 'r') as f:
        source = f.read()
    
    # Find sync_receipts function
    sync_receipts_start = source.find('def sync_receipts(')
    if sync_receipts_start == -1:
        raise AssertionError("Could not find sync_receipts function")
    
    # Get a reasonable chunk after the function definition
    sync_receipts_source = source[sync_receipts_start:sync_receipts_start + 10000]
    
    # Verify no threading code present
    assert 'threading.Thread' not in sync_receipts_source, "Thread class should not be in sync_receipts"
    assert 'thread.start()' not in sync_receipts_source, "thread.start() should not be in sync_receipts"
    assert 'run_sync_in_background' not in sync_receipts_source, "Background thread function should be removed"
    
    # Verify 503 error handling is present
    assert '503' in sync_receipts_source, "Should return 503 when worker not available"
    # Check for worker-related message (case insensitive)
    assert 'worker' in sync_receipts_source.lower(), "Should mention worker in error message"
    
    print("✓ Test passed: no_thread_fallback_code")


def test_cancel_heartbeat_check():
    """Test that heartbeat function checks for cancellation"""
    # Read source file directly
    with open('server/jobs/gmail_sync_job.py', 'r') as f:
        source = f.read()
    
    # Verify cancel checking in heartbeat
    assert 'cancel_requested' in source, "Should check cancel_requested flag"
    assert 'InterruptedError' in source or 'interrupted' in source.lower(), "Should handle cancellation"
    
    # Verify cancel check before sync
    assert source.count('cancel_requested') >= 2, "Should check cancel_requested in multiple places"
    
    print("✓ Test passed: cancel_heartbeat_check")


def test_cancel_endpoint_exists():
    """Test that cancel endpoint exists"""
    # Read source file directly
    with open('server/routes_receipts.py', 'r') as f:
        source = f.read()
    
    # Verify cancel endpoint is defined
    assert 'def cancel_receipt_sync' in source, "Cancel endpoint function should exist"
    assert '/api/receipts/sync/<int:run_id>/cancel' in source, "Cancel route should be defined"
    assert 'cancel_requested = True' in source, "Should set cancel_requested flag"
    assert 'cancelled_at' in source, "Should set cancelled_at timestamp"
    
    print("✓ Test passed: cancel_endpoint_exists")


def test_503_error_format():
    """Test that 503 error handling is correct"""
    # Read source file directly
    with open('server/routes_receipts.py', 'r') as f:
        source = f.read()
    
    # Find the 503 error return
    sync_receipts_start = source.find('def sync_receipts(')
    sync_receipts_source = source[sync_receipts_start:sync_receipts_start + 10000]
    
    # Verify 503 is returned with proper structure
    assert '503' in sync_receipts_source, "Should return 503 status code"
    assert '"success": False' in sync_receipts_source, "Should have success: False"
    assert '"error"' in sync_receipts_source, "Should have error field"
    
    print("✓ Test passed: 503_error_format")


def test_cancel_in_sync_job():
    """Test that sync job handles cancellation"""
    # Read source file directly
    with open('server/jobs/gmail_sync_job.py', 'r') as f:
        source = f.read()
    
    # Verify cancellation handling
    assert 'if sync_run.cancel_requested:' in source, "Should check cancel_requested"
    assert "status = 'cancelled'" in source, "Should set status to cancelled"
    assert '"cancelled": True' in source, "Should return cancelled in result"
    
    print("✓ Test passed: cancel_in_sync_job")


def test_no_else_block_in_sync():
    """Verify the else block was removed from sync_receipts"""
    # Read source file directly
    with open('server/routes_receipts.py', 'r') as f:
        lines = f.readlines()
    
    # Find sync_receipts function
    in_sync_receipts = False
    found_rq_check = False
    found_else_after_rq = False
    
    for i, line in enumerate(lines):
        if 'def sync_receipts(' in line:
            in_sync_receipts = True
        elif in_sync_receipts and 'def ' in line and 'sync_receipts' not in line:
            # Reached next function
            break
        elif in_sync_receipts:
            # Check for the RQ availability check
            if 'if not (use_rq and RQ_AVAILABLE and receipts_queue)' in line:
                found_rq_check = True
            # Make sure there's no else: block for threading fallback
            elif found_rq_check and line.strip().startswith('else:'):
                # Check if this else is related to the RQ check
                # by looking for threading code nearby
                next_lines = ''.join(lines[i:min(i+20, len(lines))])
                if 'threading' in next_lines or 'thread.start' in next_lines:
                    found_else_after_rq = True
    
    assert found_rq_check, "Should have RQ availability check"
    assert not found_else_after_rq, "Should NOT have else block with threading fallback"
    
    print("✓ Test passed: no_else_block_in_sync")


if __name__ == '__main__':
    """Run all tests"""
    print("=" * 60)
    print("Phase 3: Receipt Sync Worker-Only Tests")
    print("=" * 60)
    
    tests = [
        test_no_thread_fallback_code,
        test_cancel_heartbeat_check,
        test_cancel_endpoint_exists,
        test_503_error_format,
        test_cancel_in_sync_job,
        test_no_else_block_in_sync,
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            print(f"\n→ Running {test_func.__name__}...")
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"✗ FAILED: {test_func.__name__}")
            print(f"  Error: {e}")
            failed += 1
        except Exception as e:
            print(f"⚠ ERROR: {test_func.__name__}")
            print(f"  Error: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    if failed > 0:
        exit(1)

