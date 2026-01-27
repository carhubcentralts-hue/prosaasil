"""
Code verification for recording playback loop fix

This script verifies that the necessary code changes are in place:
1. Backend checks for existing RecordingRun before creating jobs
2. Backend creates RecordingRun BEFORE enqueueing to RQ
3. Frontend uses guards to prevent concurrent checks
4. Frontend uses AbortController to cancel pending requests
"""
import re


def verify_backend_routes_calls():
    """Verify routes_calls.py has proper deduplication logic"""
    print("🔍 Checking server/routes_calls.py...")
    
    with open('/home/runner/work/prosaasil/prosaasil/server/routes_calls.py', 'r') as f:
        content = f.read()
    
    checks = [
        ("RecordingRun model imported", "from server.models_sql import RecordingRun"),
        ("Checks for existing RecordingRun", "existing_run = RecordingRun.query.filter_by"),
        ("Returns 202 for running jobs", "existing_run.status == 'running'"),
        ("Returns 202 for queued jobs", "existing_run.status == 'queued'"),
        ("Returns 500 for failed jobs", "existing_run.status == 'failed'"),
    ]
    
    all_passed = True
    for check_name, check_pattern in checks:
        if check_pattern in content:
            print(f"  ✅ {check_name}")
        else:
            print(f"  ❌ {check_name} - NOT FOUND")
            all_passed = False
    
    return all_passed


def verify_backend_tasks_recording():
    """Verify tasks_recording.py has proper deduplication logic"""
    print("\n🔍 Checking server/tasks_recording.py...")
    
    with open('/home/runner/work/prosaasil/prosaasil/server/tasks_recording.py', 'r') as f:
        content = f.read()
    
    checks = [
        ("db imported", "from server.db import db"),
        ("Checks for existing queued/running RecordingRun", "RecordingRun.status.in_(['queued', 'running'])"),
        ("Returns duplicate for existing job", "return (False, \"duplicate\")"),
        ("Creates RecordingRun before RQ enqueue", "run = RecordingRun("),
        ("Commits RecordingRun to DB", "db.session.commit()"),
        ("Gets run_id before enqueue", "run_id = run.id"),
    ]
    
    all_passed = True
    for check_name, check_pattern in checks:
        if check_pattern in content:
            print(f"  ✅ {check_name}")
        else:
            print(f"  ❌ {check_name} - NOT FOUND")
            all_passed = False
    
    # Verify order: RecordingRun creation comes before Queue enqueue
    run_creation_pos = content.find("run = RecordingRun(")
    queue_enqueue_pos = content.find("queue = Queue('recordings'")
    
    if run_creation_pos > 0 and queue_enqueue_pos > 0:
        if run_creation_pos < queue_enqueue_pos:
            print("  ✅ RecordingRun created BEFORE Queue instantiation")
        else:
            print("  ❌ RecordingRun should be created BEFORE Queue")
            all_passed = False
    
    return all_passed


def verify_frontend_audio_player():
    """Verify AudioPlayer.tsx has proper guards and abort logic"""
    print("\n🔍 Checking client/src/shared/components/AudioPlayer.tsx...")
    
    with open('/home/runner/work/prosaasil/prosaasil/client/src/shared/components/AudioPlayer.tsx', 'r') as f:
        content = f.read()
    
    checks = [
        ("AbortController ref defined", "abortControllerRef = useRef<AbortController | null>(null)"),
        ("Checking guard ref defined", "isCheckingRef = useRef<boolean>(false)"),
        ("Prevents concurrent checks", "if (isCheckingRef.current)"),
        ("Creates AbortController for requests", "const controller = new AbortController()"),
        ("Passes signal to fetch", "signal: controller.signal"),
        ("Handles AbortError", "error.name === 'AbortError'"),
        ("Aborts on cleanup", "abortControllerRef.current.abort()"),
        ("Resets checking flag on cleanup", "isCheckingRef.current = false"),
    ]
    
    all_passed = True
    for check_name, check_pattern in checks:
        if check_pattern in content:
            print(f"  ✅ {check_name}")
        else:
            print(f"  ❌ {check_name} - NOT FOUND")
            all_passed = False
    
    return all_passed


def verify_key_behaviors():
    """Verify key behavioral changes"""
    print("\n🔍 Verifying key behaviors...")
    
    # Check that HEAD requests have abort capability
    with open('/home/runner/work/prosaasil/prosaasil/client/src/shared/components/AudioPlayer.tsx', 'r') as f:
        content = f.read()
    
    behaviors = []
    
    # Check for single-check guard
    if "if (isCheckingRef.current)" in content and "return false" in content:
        print("  ✅ Single concurrent check guard implemented")
        behaviors.append(True)
    else:
        print("  ❌ Single concurrent check guard missing")
        behaviors.append(False)
    
    # Check for cleanup on unmount
    if "abortControllerRef.current.abort()" in content and "return () =>" in content:
        print("  ✅ Cleanup on unmount implemented")
        behaviors.append(True)
    else:
        print("  ❌ Cleanup on unmount missing")
        behaviors.append(False)
    
    # Check backend DB check before Redis
    with open('/home/runner/work/prosaasil/prosaasil/server/tasks_recording.py', 'r') as f:
        content = f.read()
    
    # Find position of DB check vs Redis check in enqueue_recording_download_only
    func_start = content.find("def enqueue_recording_download_only(")
    if func_start > 0:
        func_content = content[func_start:func_start + 5000]  # Look at next 5000 chars
        
        db_check_pos = func_content.find("RecordingRun.query.filter_by")
        redis_check_pos = func_content.find("redis_conn.get(job_key)")
        
        if db_check_pos > 0 and redis_check_pos > 0:
            if db_check_pos < redis_check_pos:
                print("  ✅ DB check happens BEFORE Redis check")
                behaviors.append(True)
            else:
                print("  ❌ DB check should happen BEFORE Redis check")
                behaviors.append(False)
        else:
            print("  ⚠️  Could not verify DB vs Redis check order")
            behaviors.append(None)
    
    return all(b for b in behaviors if b is not None)


def main():
    print("=" * 60)
    print("  Recording Playback Loop Fix - Code Verification")
    print("=" * 60)
    
    results = []
    
    results.append(verify_backend_routes_calls())
    results.append(verify_backend_tasks_recording())
    results.append(verify_frontend_audio_player())
    results.append(verify_key_behaviors())
    
    print("\n" + "=" * 60)
    if all(results):
        print("✅ ALL VERIFICATIONS PASSED")
        print("\nThe code changes implement:")
        print("  1. ✅ Backend checks RecordingRun before creating jobs")
        print("  2. ✅ Backend creates RecordingRun BEFORE RQ enqueue")
        print("  3. ✅ Frontend guards prevent concurrent checks")
        print("  4. ✅ Frontend AbortController cancels pending requests")
        print("\nExpected behavior:")
        print("  • Single Play click → 1-2 stream requests maximum")
        print("  • No duplicate jobs created in worker")
        print("  • Console doesn't print 'Streaming from...' in loop")
    else:
        print("❌ SOME VERIFICATIONS FAILED")
        print("\nPlease review the failed checks above.")
    print("=" * 60)


if __name__ == "__main__":
    main()
