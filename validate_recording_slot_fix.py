"""
Code validation for recording slot release fix.

Verifies that the critical bug fix is in place by checking:
1. enqueue_recording_download_only returns bool
2. API endpoints check the return value
3. API endpoints call release_slot when enqueue returns False
"""

import os
import re


def check_enqueue_returns_bool():
    """Verify enqueue_recording_download_only has return statements"""
    filepath = "server/tasks_recording.py"
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Find the function
    func_pattern = r'def enqueue_recording_download_only\([^)]+\):(.*?)(?=\ndef |\Z)'
    match = re.search(func_pattern, content, re.DOTALL)
    
    if not match:
        raise AssertionError("Could not find enqueue_recording_download_only function")
    
    func_body = match.group(1)
    
    # Check for "return False" statements
    if 'return False' not in func_body:
        raise AssertionError("enqueue_recording_download_only should return False for dedup cases")
    
    # Check for "return True" statement
    if 'return True' not in func_body:
        raise AssertionError("enqueue_recording_download_only should return True when enqueued")
    
    print("✅ enqueue_recording_download_only returns bool (True/False)")


def check_api_handles_return_value():
    """Verify API endpoints check enqueue return value and release slot"""
    filepath = "server/routes_calls.py"
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Look for pattern: job_enqueued = enqueue_recording_download_only(
    if 'job_enqueued = enqueue_recording_download_only(' not in content:
        raise AssertionError("API should capture return value from enqueue_recording_download_only")
    
    # Look for pattern: if not job_enqueued:
    if 'if not job_enqueued:' not in content:
        raise AssertionError("API should check if job was enqueued")
    
    # Look for pattern: release_slot(business_id, call_sid) after if not job_enqueued
    # This ensures slot is released when job not enqueued
    pattern = r'if not job_enqueued:.*?release_slot\(business_id, call_sid\)'
    if not re.search(pattern, content, re.DOTALL):
        raise AssertionError("API should release slot when job not enqueued")
    
    print("✅ API endpoints check enqueue return value and release slot")


def check_recording_sid_passed():
    """Verify recording_sid is passed through the flow"""
    tasks_file = "server/tasks_recording.py"
    routes_file = "server/routes_calls.py"
    
    with open(tasks_file, 'r') as f:
        tasks_content = f.read()
    
    with open(routes_file, 'r') as f:
        routes_content = f.read()
    
    # Check function signature accepts recording_sid
    if 'def enqueue_recording_download_only(call_sid, recording_url, business_id, from_number="", to_number="", retry_count=0, recording_sid=None)' not in tasks_content:
        raise AssertionError("enqueue_recording_download_only should accept recording_sid parameter")
    
    # Check API passes recording_sid
    if 'recording_sid=call.recording_sid' not in routes_content:
        raise AssertionError("API should pass recording_sid from CallLog")
    
    # Check job dict includes recording_sid
    if '"recording_sid": recording_sid' not in tasks_content:
        raise AssertionError("Job dict should include recording_sid")
    
    # Check worker extracts recording_sid from job
    if 'recording_sid = job.get("recording_sid")' not in tasks_content:
        raise AssertionError("Worker should extract recording_sid from job")
    
    print("✅ recording_sid is passed through entire flow")


def check_diagnostic_logs():
    """Verify diagnostic logs are added"""
    filepath = "server/tasks_recording.py"
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Check for the 4 critical diagnostic logs
    required_logs = [
        "[DOWNLOAD_START]",
        "[DOWNLOAD_OK]",
        "[DOWNLOAD_FAIL]",
        "[RECORDING_SLOT_RELEASED]"
    ]
    
    for log_tag in required_logs:
        if log_tag not in content:
            raise AssertionError(f"Missing diagnostic log: {log_tag}")
    
    # Verify DOWNLOAD_START includes both call_sid and recording_sid
    if 'call_sid=' not in content or 'recording_sid=' not in content:
        raise AssertionError("DOWNLOAD_START log should include both call_sid and recording_sid")
    
    # Verify DOWNLOAD_OK includes size and duration
    if 'size=' not in content or 'duration=' not in content:
        raise AssertionError("DOWNLOAD_OK log should include size and duration")
    
    # Verify RECORDING_SLOT_RELEASED includes active_after and queue_len_after
    if 'active_after=' not in content or 'queue_len_after=' not in content:
        raise AssertionError("RECORDING_SLOT_RELEASED log should include active_after and queue_len_after")
    
    print("✅ All diagnostic logs present with correct fields")


def main():
    """Run all validation checks"""
    print("="*60)
    print("Recording Slot Release Fix - Code Validation")
    print("="*60)
    print()
    
    tests = [
        ("enqueue returns bool", check_enqueue_returns_bool),
        ("API handles return value", check_api_handles_return_value),
        ("recording_sid passed through flow", check_recording_sid_passed),
        ("diagnostic logs present", check_diagnostic_logs),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"❌ FAIL [{test_name}]: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ ERROR [{test_name}]: {e}")
            failed += 1
    
    print()
    print("="*60)
    print(f"Results: {passed} passed, {failed} failed")
    print("="*60)
    
    if failed > 0:
        print("\n⚠️  Some validations failed. Please review the code.")
        return 1
    else:
        print("\n✅ All validations passed! The fix is correctly implemented.")
        return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
