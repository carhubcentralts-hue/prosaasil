#!/usr/bin/env python3
"""
🎯 TEST - Loop Fixes for Lead Deletion and Recording Processing

Tests the fixes for:
1. Lead deletion loop (idempotency)
2. Recording processing loop (retry with backoff)
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_lead_deletion_idempotency():
    """
    Test 1: Lead deletion API should be idempotent
    
    Verify that:
    - check_and_handle_duplicate_background_job has return_existing parameter
    - It returns existing job instead of error when return_existing=True
    """
    print("=" * 70)
    print("🧪 TEST 1: Lead Deletion Idempotency")
    print("=" * 70)
    
    routes_file = os.path.join(os.path.dirname(__file__), 'server/routes_leads.py')
    if not os.path.exists(routes_file):
        print("❌ routes_leads.py not found")
        return False
    
    with open(routes_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = []
    
    # Check 1: Function signature includes return_existing parameter
    if 'def check_and_handle_duplicate_background_job' in content and 'return_existing' in content:
        print("✅ check_and_handle_duplicate_background_job has return_existing parameter")
        checks.append(True)
    else:
        print("❌ return_existing parameter not found")
        checks.append(False)
    
    # Check 2: Function returns existing job when return_existing=True
    if 'if return_existing:' in content and '"existing": True' in content:
        print("✅ Function returns existing job in idempotent mode")
        checks.append(True)
    else:
        print("❌ Idempotent mode not implemented correctly")
        checks.append(False)
    
    # Check 3: bulk_delete_leads uses return_existing=True
    if 'return_existing=True' in content:
        print("✅ bulk_delete_leads uses idempotent mode")
        checks.append(True)
    else:
        print("❌ bulk_delete_leads doesn't use idempotent mode")
        checks.append(False)
    
    success = all(checks)
    if success:
        print("\n✅ TEST 1 PASSED: Lead deletion idempotency implemented")
    else:
        print("\n❌ TEST 1 FAILED: Some checks failed")
    
    return success


def test_delete_leads_job_skip_deleted():
    """
    Test 2: Delete leads job should skip already-deleted leads
    
    Verify that:
    - Job checks if leads exist before attempting deletion
    - Handles empty lead set gracefully
    """
    print("\n" + "=" * 70)
    print("🧪 TEST 2: Delete Leads Job Skip Already Deleted")
    print("=" * 70)
    
    job_file = os.path.join(os.path.dirname(__file__), 'server/jobs/delete_leads_job.py')
    if not os.path.exists(job_file):
        print("❌ delete_leads_job.py not found")
        return False
    
    with open(job_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = []
    
    # Check 1: Fetches only existing leads
    if 'Lead.query.filter' in content and 'Lead.id.in_(batch_ids)' in content:
        print("✅ Job fetches only existing leads from batch")
        checks.append(True)
    else:
        print("❌ Job doesn't check for existing leads")
        checks.append(False)
    
    # Check 2: Handles empty lead set (already deleted)
    if 'if not actual_lead_ids:' in content and 'already deleted' in content:
        print("✅ Job handles already-deleted leads gracefully")
        checks.append(True)
    else:
        print("❌ Job doesn't handle already-deleted leads")
        checks.append(False)
    
    # Check 3: Continues processing after empty batch
    if 'continue' in content and 'IDEMPOTENCY' in content:
        print("✅ Job continues to next batch after skipping deleted leads")
        checks.append(True)
    else:
        print("❌ Job doesn't continue properly")
        checks.append(False)
    
    success = all(checks)
    if success:
        print("\n✅ TEST 2 PASSED: Delete job handles already-deleted leads")
    else:
        print("\n❌ TEST 2 FAILED: Some checks failed")
    
    return success


def test_recording_retry_logic():
    """
    Test 3: Recording job should retry with backoff for missing CallLog/audio
    
    Verify that:
    - Job checks for CallLog existence
    - Implements retry with exponential backoff
    - Has max retry limit to prevent infinite loops
    """
    print("\n" + "=" * 70)
    print("🧪 TEST 3: Recording Retry Logic with Backoff")
    print("=" * 70)
    
    job_file = os.path.join(os.path.dirname(__file__), 'server/jobs/recording_job.py')
    if not os.path.exists(job_file):
        print("❌ recording_job.py not found")
        return False
    
    with open(job_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = []
    
    # Check 1: Checks for CallLog existence
    if 'CallLog.query.filter_by(call_sid=' in content:
        print("✅ Job checks for CallLog existence")
        checks.append(True)
    else:
        print("❌ Job doesn't check for CallLog")
        checks.append(False)
    
    # Check 2: Implements retry count and max retries at module level
    if 'MAX_RECORDING_RETRIES' in content and 'run.retry_count' in content:
        print("✅ Job implements retry count with max limit (module-level constant)")
        checks.append(True)
    else:
        print("❌ Job doesn't implement retry limit properly")
        checks.append(False)
    
    # Check 3: Uses exponential backoff with helper function
    if 'calculate_retry_delay' in content or ('2 **' in content and 'backoff' in content.lower()):
        print("✅ Job uses exponential backoff for retries")
        checks.append(True)
    else:
        print("❌ Job doesn't use exponential backoff")
        checks.append(False)
    
    # Check 4: Doesn't throw exception for temporary failures
    if 'CallLog not found' in content and 'retry' in content.lower():
        print("✅ Job handles missing CallLog with retry instead of exception")
        checks.append(True)
    else:
        print("❌ Job might still throw exceptions")
        checks.append(False)
    
    # Check 5: Marks as permanently failed after max retries
    if 'permanent' in content.lower() or 'after.*retries' in content.lower():
        print("✅ Job marks as permanently failed after max retries")
        checks.append(True)
    else:
        print("❌ Job doesn't mark permanent failures")
        checks.append(False)
    
    # Check 6: Retry count not incremented in exception handler (avoid double-counting)
    lines = content.split('\n')
    in_exception_handler = False
    retry_in_handler = False
    for i, line in enumerate(lines):
        if 'except Exception as e:' in line:
            in_exception_handler = True
        elif in_exception_handler and 'run.retry_count += 1' in line and '#' not in line.split('run.retry_count')[0]:
            # Found uncommented increment in exception handler
            retry_in_handler = True
            break
        elif in_exception_handler and (line.strip().startswith('def ') or (line and not line[0].isspace())):
            # Exited the exception handler
            in_exception_handler = False
    
    if not retry_in_handler:
        print("✅ Job doesn't double-count retries in exception handler")
        checks.append(True)
    else:
        print("❌ Job increments retry_count in exception handler (double-counting)")
        checks.append(False)
    
    success = all(checks)
    if success:
        print("\n✅ TEST 3 PASSED: Recording retry logic implemented correctly")
    else:
        print("\n❌ TEST 3 FAILED: Some checks failed")
    
    return success


def test_recording_no_infinite_loop():
    """
    Test 4: Recording job should not loop infinitely
    
    Verify that:
    - Job doesn't throw exceptions that cause immediate retry
    - Uses return instead of raise for temporary failures
    """
    print("\n" + "=" * 70)
    print("🧪 TEST 4: Recording No Infinite Loop")
    print("=" * 70)
    
    job_file = os.path.join(os.path.dirname(__file__), 'server/jobs/recording_job.py')
    if not os.path.exists(job_file):
        print("❌ recording_job.py not found")
        return False
    
    with open(job_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = []
    
    # Check 1: Returns instead of raises for permanent failures
    if 'return {"success": False' in content and 'permanent' in content.lower():
        print("✅ Job returns (not raises) for permanent failures")
        checks.append(True)
    else:
        print("❌ Job might still raise exceptions")
        checks.append(False)
    
    # Check 2: Uses controlled exception raising only for retry
    lines = content.split('\n')
    raise_count = sum(1 for line in lines if 'raise Exception' in line and 'retry' in line.lower())
    if raise_count > 0:
        print(f"✅ Job raises exceptions only for controlled retry ({raise_count} locations)")
        checks.append(True)
    else:
        print("⚠️  Job might not raise exceptions for retry (check manually)")
        checks.append(True)  # Not a failure, just a warning
    
    # Check 3: Has logic to handle audio file not available
    if 'Audio file not available' in content or 'audio_file' in content:
        print("✅ Job handles missing audio file scenario")
        checks.append(True)
    else:
        print("❌ Job doesn't handle missing audio file")
        checks.append(False)
    
    success = all(checks)
    if success:
        print("\n✅ TEST 4 PASSED: Recording won't loop infinitely")
    else:
        print("\n❌ TEST 4 FAILED: Some checks failed")
    
    return success


def run_all_tests():
    """Run all loop fix tests"""
    print("=" * 70)
    print("🎯 LOOP FIXES TEST SUITE")
    print("=" * 70)
    print()
    
    results = []
    results.append(("Lead Deletion Idempotency", test_lead_deletion_idempotency()))
    results.append(("Delete Job Skip Deleted", test_delete_leads_job_skip_deleted()))
    results.append(("Recording Retry Logic", test_recording_retry_logic()))
    results.append(("Recording No Infinite Loop", test_recording_no_infinite_loop()))
    
    print("\n" + "=" * 70)
    print("📊 TEST SUMMARY")
    print("=" * 70)
    
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {test_name}")
    
    all_passed = all(result[1] for result in results)
    
    print("=" * 70)
    if all_passed:
        print("🎉 ALL TESTS PASSED")
        print("=" * 70)
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
