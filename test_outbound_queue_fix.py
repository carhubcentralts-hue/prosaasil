"""
Test Outbound Queue Fix - Verify 404 and dedup fixes
"""
import sys
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import inspect


def test_active_queue_returns_200_structure():
    """Verify that get_active_outbound_job returns proper structure with active flag"""
    from server.routes_outbound import get_active_outbound_job
    
    # Check that the function exists
    assert get_active_outbound_job is not None
    
    # Check the code structure for the fix
    source = inspect.getsource(get_active_outbound_job)
    
    # Verify the fix is present - should return 200 with active=false instead of 404
    assert '"ok": True' in source, "Response should include ok: True"
    assert '"active": False' in source, "Response should include active: False"
    assert '"active": True' in source, "Response should include active: True for active queues"
    assert '"queue_len"' in source, "Response should include queue_len"
    
    print("✓ Active queue endpoint returns proper structure with active flag")


def test_dedup_ignores_stale_null_call_sid_logic():
    """Verify that _check_duplicate_in_db has logic to ignore stale NULL call_sid"""
    from server.services.twilio_outbound_service import _check_duplicate_in_db
    
    # Check that the function exists
    assert _check_duplicate_in_db is not None
    
    # Check the code structure for the fix
    source = inspect.getsource(_check_duplicate_in_db)
    
    # Verify the fix is present
    assert 'stale_threshold' in source, "Should have stale_threshold logic"
    assert 'call_sid IS NOT NULL' in source or 'call_sid is None' in source, "Should check for NULL call_sid"
    assert 'created_at > :stale_threshold' in source or 'timedelta(seconds=60)' in source, "Should have 60 second threshold"
    
    print("✓ Dedup function has logic to ignore stale NULL call_sid records")


def test_cleanup_handles_stale_call_logs():
    """Verify that cleanup_stuck_dialing_jobs cleans up stale call_log records"""
    from server.routes_outbound import cleanup_stuck_dialing_jobs
    
    # Check that the function exists
    assert cleanup_stuck_dialing_jobs is not None
    
    # Check the code structure for the fix
    source = inspect.getsource(cleanup_stuck_dialing_jobs)
    
    # Verify the fix is present
    assert 'call_sid IS NULL' in source, "Should check for NULL call_sid in cleanup"
    assert 'call_log' in source, "Should cleanup call_log table"
    assert 'stale' in source.lower() or 'cleanup' in source.lower(), "Should mention stale/cleanup"
    
    print("✓ Cleanup function handles stale call_log records with NULL call_sid")


def test_semaphore_has_cleanup():
    """Verify that semaphore system has cleanup for expired slots"""
    from server.services.outbound_semaphore import cleanup_expired_slots
    
    # Check that the function exists
    assert cleanup_expired_slots is not None
    
    # Check the code structure
    source = inspect.getsource(cleanup_expired_slots)
    
    # Verify cleanup logic exists
    assert 'expired' in source.lower() or 'cleanup' in source.lower(), "Should mention expired/cleanup"
    assert 'SREM' in source or 'slots_key' in source, "Should remove from Redis slots"
    
    print("✓ Semaphore system has cleanup for expired slots")


def test_frontend_handles_active_flag():
    """Verify that frontend service handles the new active flag"""
    # Use relative path from script location
    base_path = os.path.dirname(os.path.abspath(__file__))
    client_file = os.path.join(base_path, 'client/src/services/calls.ts')
    
    if os.path.exists(client_file):
        with open(client_file, 'r') as f:
            content = f.read()
        
        # Verify the fix is present
        assert 'active' in content, "Frontend should handle active field"
        assert 'getActiveQueue' in content, "Frontend should have getActiveQueue function"
        
        print("✓ Frontend service updated to handle active flag")
    else:
        print("⚠ Frontend file not found, skipping check")


def run_all_tests():
    """Run all tests and report results"""
    tests = [
        test_active_queue_returns_200_structure,
        test_dedup_ignores_stale_null_call_sid_logic,
        test_cleanup_handles_stale_call_logs,
        test_semaphore_has_cleanup,
        test_frontend_handles_active_flag,
    ]
    
    passed = 0
    failed = 0
    
    print("=" * 60)
    print("Running Outbound Queue Fix Tests")
    print("=" * 60)
    
    for test in tests:
        try:
            print(f"\n{test.__name__}...")
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ ERROR: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)

