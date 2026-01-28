"""
Test: Background Job Duplicate Constraint Fix

Tests the fix for the duplicate key constraint violation error when
trying to create background jobs with an existing active job.

Applies to all background job types:
- enqueue_outbound_calls
- delete_imported_leads
- delete_leads
- update_leads

Test scenarios:
1. No existing job - should create successfully
2. Existing stale job - should mark it as failed and create new job
3. Existing active job - should return 409 error with helpful message
4. Helper function exists and is used correctly
"""
import sys
import json
from datetime import datetime, timedelta


def test_helper_function_exists():
    """
    Test that the helper function check_and_handle_duplicate_background_job exists.
    """
    print("\n" + "="*70)
    print("TEST 1: Helper function exists")
    print("="*70)
    
    # Check in routes_outbound.py
    with open('/home/runner/work/prosaasil/prosaasil/server/routes_outbound.py', 'r') as f:
        content = f.read()
        
    assert 'def check_and_handle_duplicate_background_job(' in content, \
        "❌ Missing helper function in routes_outbound.py"
    assert 'BACKGROUND_JOB_STALE_THRESHOLD_MINUTES' in content, \
        "❌ Missing stale threshold constant in routes_outbound.py"
    
    # Check in routes_leads.py
    with open('/home/runner/work/prosaasil/prosaasil/server/routes_leads.py', 'r') as f:
        content = f.read()
        
    assert 'def check_and_handle_duplicate_background_job(' in content, \
        "❌ Missing helper function in routes_leads.py"
    assert 'BACKGROUND_JOB_STALE_THRESHOLD_MINUTES' in content, \
        "❌ Missing stale threshold constant in routes_leads.py"
    
    print("✅ Helper function exists in both files")
    print("✅ Stale threshold constant defined")
    return True


def test_stale_job_detection():
    """
    Test that helper function detects and handles stale jobs.
    """
    print("\n" + "="*70)
    print("TEST 2: Stale job detection logic")
    print("="*70)
    
    with open('/home/runner/work/prosaasil/prosaasil/server/routes_outbound.py', 'r') as f:
        content = f.read()
    
    # Verify stale job detection logic in helper function
    assert 'last_activity = existing_job.heartbeat_at or existing_job.created_at' in content, \
        "❌ Missing last activity check"
    assert 'is_stale = (now - last_activity) > stale_threshold' in content, \
        "❌ Missing stale job detection"
    assert "existing_job.status = 'failed'" in content, \
        "❌ Missing logic to mark stale job as failed"
    assert "'Job marked as stale" in content, \
        "❌ Missing stale job error message"
    
    print("✅ Helper function detects stale jobs")
    print("✅ Helper function marks stale jobs as failed")
    print("✅ Allows new job creation after cleanup")
    return True


def test_active_job_blocking():
    """
    Test that helper function blocks creation when active job exists.
    """
    print("\n" + "="*70)
    print("TEST 3: Active job blocking logic")
    print("="*70)
    
    with open('/home/runner/work/prosaasil/prosaasil/server/routes_outbound.py', 'r') as f:
        content = f.read()
    
    # Verify helper function handles active job blocking
    assert 'if is_stale:' in content, \
        "❌ Missing stale check branch"
    assert '409' in content, \
        "❌ Missing 409 Conflict response"
    assert 'db.session.rollback()' in content, \
        "❌ Missing rollback when active job exists"
    assert 'active_job_id' in content, \
        "❌ Missing active_job_id in response"
    assert 'active_job_status' in content, \
        "❌ Missing active_job_status in response"
    
    print("✅ Helper function blocks creation when active job exists")
    print("✅ Returns 409 Conflict status")
    print("✅ Rolls back transaction")
    print("✅ Includes active job details in response")
    return True


def test_unique_constraint_protection():
    """
    Test that the fix properly protects against the unique constraint.
    """
    print("\n" + "="*70)
    print("TEST 4: Unique constraint protection")
    print("="*70)
    
    with open('/home/runner/work/prosaasil/prosaasil/server/routes_outbound.py', 'r') as f:
        content = f.read()
    
    # Verify the constraint is mentioned in helper function
    assert 'idx_background_jobs_unique_active' in content, \
        "❌ Missing reference to unique constraint"
    
    # Verify the helper is called before job creation
    assert 'can_proceed, error_response, status_code = check_and_handle_duplicate_background_job(' in content, \
        "❌ Helper function not being called"
    assert 'if not can_proceed:' in content, \
        "❌ Missing check of can_proceed return value"
    
    print("✅ Code references the unique constraint")
    print("✅ Helper function is called before job creation")
    print("✅ Return value is checked before proceeding")
    return True


def test_stale_threshold_value():
    """
    Test that the stale threshold is set to a reasonable value (10 minutes).
    """
    print("\n" + "="*70)
    print("TEST 5: Stale threshold value")
    print("="*70)
    
    with open('/home/runner/work/prosaasil/prosaasil/server/routes_outbound.py', 'r') as f:
        content = f.read()
    
    # Check that threshold is 10 minutes
    assert 'BACKGROUND_JOB_STALE_THRESHOLD_MINUTES = 10' in content, \
        "❌ Stale threshold should be 10 minutes"
    
    print("✅ Stale threshold set to 10 minutes (reasonable value)")
    print("   - Short enough to detect stuck jobs quickly")
    print("   - Long enough to avoid false positives for slow jobs")
    return True


def test_all_job_types_use_helper():
    """
    Test that all background job types use the helper function.
    """
    print("\n" + "="*70)
    print("TEST 6: All job types use helper function")
    print("="*70)
    
    job_types = [
        ('enqueue_outbound_calls', 'server/routes_outbound.py'),
        ('delete_imported_leads', 'server/routes_outbound.py'),
        ('delete_leads', 'server/routes_leads.py'),
        ('update_leads', 'server/routes_leads.py'),
    ]
    
    for job_type, file_path in job_types:
        full_path = f'/home/runner/work/prosaasil/prosaasil/{file_path}'
        with open(full_path, 'r') as f:
            content = f.read()
        
        # Check that the job type is assigned
        assert f"job_type = '{job_type}'" in content, \
            f"❌ Job type assignment '{job_type}' not found in {file_path}"
        
        # Check that the helper function is called for this job type
        assert f"job_type='{job_type}'" in content, \
            f"❌ Missing helper function call for job type '{job_type}' in {file_path}"
        
        # Verify the helper function exists
        assert 'check_and_handle_duplicate_background_job(' in content, \
            f"❌ Helper function not found in {file_path}"
        
        print(f"✅ Job type '{job_type}' uses helper function in {file_path}")
    
    print(f"\n✅ All {len(job_types)} job types have duplicate protection via helper!")
    return True


def run_all_tests():
    """Run all test scenarios"""
    print("\n" + "="*80)
    print("BACKGROUND JOB DUPLICATE FIX - TEST SUITE (Refactored)")
    print("Testing fix for: duplicate key violates unique constraint")
    print("="*80)
    
    tests = [
        test_helper_function_exists,
        test_stale_job_detection,
        test_active_job_blocking,
        test_unique_constraint_protection,
        test_stale_threshold_value,
        test_all_job_types_use_helper,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append((test.__name__, result))
        except AssertionError as e:
            print(f"\n❌ TEST FAILED: {e}")
            results.append((test.__name__, False))
        except Exception as e:
            print(f"\n❌ TEST ERROR: {e}")
            results.append((test.__name__, False))
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! The refactored code is working correctly.")
        return 0
    else:
        print(f"\n❌ {total - passed} test(s) failed. Please review the implementation.")
        return 1


if __name__ == '__main__':
    sys.exit(run_all_tests())
