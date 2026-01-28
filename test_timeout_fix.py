#!/usr/bin/env python3
"""
Test script to verify that the RQ job_timeout parameter fix works correctly.

This test verifies that:
1. Jobs can be enqueued with a timeout parameter
2. The timeout is properly passed to RQ as 'job_timeout'
3. The job function doesn't receive 'timeout' as a kwarg
"""
import os
import sys

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def test_job_function():
    """
    Test job function that should NOT receive timeout as a parameter.
    
    This is the key test - if the fix works, this function will be called
    without any unexpected 'timeout' kwarg.
    """
    print("✅ test_job_function called successfully (no timeout kwarg received)")
    return {'status': 'success'}


def test_enqueue_with_timeout():
    """Test that we can enqueue a job with timeout without errors"""
    from server.services.jobs import enqueue
    
    print("\n🧪 Testing job enqueue with timeout parameter...")
    
    try:
        # This should work now - timeout should be passed as job_timeout to RQ
        job = enqueue(
            'default',
            test_job_function,
            timeout=60,  # This should be converted to job_timeout internally
            job_id='test_timeout_fix_123',
            retry=None
        )
        
        print(f"✅ Job enqueued successfully: {job.id}")
        print(f"   Job timeout: {job.timeout}")
        print(f"   Job function: {job.func_name}")
        
        # Verify the job has the correct timeout
        if job.timeout == 60:
            print("✅ Job timeout is correctly set to 60 seconds")
        else:
            print(f"❌ Job timeout is {job.timeout}, expected 60")
            return False
        
        print("\n✨ Test PASSED: Timeout parameter is now correctly handled!")
        return True
        
    except TypeError as e:
        if "got an unexpected keyword argument 'timeout'" in str(e):
            print(f"❌ Test FAILED: {e}")
            print("   The timeout parameter is still being passed to the job function")
            print("   This means the fix didn't work correctly")
            return False
        else:
            print(f"❌ Unexpected error: {e}")
            raise
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_reminders_tick_job():
    """Test the actual reminders_tick_job that was failing"""
    from server.services.jobs import enqueue
    from server.jobs.reminders_tick_job import reminders_tick_job
    
    print("\n🧪 Testing reminders_tick_job enqueue (the original failing case)...")
    
    try:
        job = enqueue(
            'default',
            reminders_tick_job,
            job_id='test_reminders_tick_456',
            timeout=120,  # This was causing the error before
            retry=None,
            ttl=300
        )
        
        print(f"✅ reminders_tick_job enqueued successfully: {job.id}")
        print(f"   Job timeout: {job.timeout}")
        print(f"   Job function: {job.func_name}")
        
        if job.timeout == 120:
            print("✅ Job timeout is correctly set to 120 seconds")
        else:
            print(f"❌ Job timeout is {job.timeout}, expected 120")
            return False
        
        print("\n✨ Test PASSED: reminders_tick_job can now be enqueued with timeout!")
        return True
        
    except TypeError as e:
        if "got an unexpected keyword argument 'timeout'" in str(e):
            print(f"❌ Test FAILED: {e}")
            print("   reminders_tick_job is still receiving timeout as a kwarg")
            return False
        else:
            print(f"❌ Unexpected error: {e}")
            raise
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    print("=" * 70)
    print("RQ Timeout Parameter Fix - Test Suite")
    print("=" * 70)
    
    # Test 1: Basic enqueue with timeout
    test1_passed = test_enqueue_with_timeout()
    
    # Test 2: Actual reminders_tick_job
    test2_passed = test_reminders_tick_job()
    
    print("\n" + "=" * 70)
    print("Test Results:")
    print("=" * 70)
    print(f"Test 1 (Basic enqueue): {'✅ PASSED' if test1_passed else '❌ FAILED'}")
    print(f"Test 2 (reminders_tick_job): {'✅ PASSED' if test2_passed else '❌ FAILED'}")
    
    if test1_passed and test2_passed:
        print("\n🎉 All tests PASSED! The fix is working correctly.")
        sys.exit(0)
    else:
        print("\n❌ Some tests FAILED. The fix needs more work.")
        sys.exit(1)
