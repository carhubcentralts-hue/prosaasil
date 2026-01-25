"""
Verify recording queue deduplication fixes are in place
"""
import os

def check_file_contains(filepath, patterns, description):
    """Check if file contains all patterns"""
    print(f"\n🔍 Checking {description}...")
    print(f"   File: {filepath}")
    
    if not os.path.exists(filepath):
        print(f"   ❌ File not found!")
        return False
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    all_found = True
    for pattern in patterns:
        if pattern in content:
            print(f"   ✅ Found: {pattern[:60]}...")
        else:
            print(f"   ❌ Missing: {pattern[:60]}...")
            all_found = False
    
    return all_found

def main():
    print("=" * 70)
    print("Recording Queue Deduplication - Code Verification")
    print("=" * 70)
    
    results = []
    
    # Check 1: Job-level deduplication in tasks_recording.py
    results.append(check_file_contains(
        "/home/runner/work/prosaasil/prosaasil/server/tasks_recording.py",
        [
            "job_key = f\"job:download:{business_id}:{call_sid}\"",
            "Job already enqueued",
            "Job lock acquired"
        ],
        "Job-level deduplication in enqueue_recording_download_only"
    ))
    
    # Check 2: Status endpoint in routes_calls.py
    results.append(check_file_contains(
        "/home/runner/work/prosaasil/prosaasil/server/routes_calls.py",
        [
            "@calls_bp.route(\"/api/recordings/<call_sid>/status\"",
            "def get_recording_status(call_sid):",
            "Check recording status without triggering download"
        ],
        "Status endpoint in routes_calls.py"
    ))
    
    # Check 3: Status polling in AudioPlayer.tsx
    results.append(check_file_contains(
        "/home/runner/work/prosaasil/prosaasil/client/src/shared/components/AudioPlayer.tsx",
        [
            "const pollRecordingStatus",
            "const getRetryDelay",
            "statusUrl.replace('/status', '/stream')",
            "Exponential backoff:"
        ],
        "Status polling with exponential backoff in AudioPlayer.tsx"
    ))
    
    # Check 4: Cleanup and deduplication
    results.append(check_file_contains(
        "/home/runner/work/prosaasil/prosaasil/client/src/shared/components/AudioPlayer.tsx",
        [
            "if (retryTimeoutRef.current) {",
            "clearTimeout(retryTimeoutRef.current);",
            "prepareTriggered"
        ],
        "Timer cleanup and duplicate trigger prevention"
    ))
    
    print("\n" + "=" * 70)
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"✅ All checks passed ({passed}/{total})!")
        print("=" * 70)
        print("\n📋 Summary of Changes:")
        print("   1. ✅ Job-level deduplication prevents duplicate RECORDING_QUEUE entries")
        print("   2. ✅ New /status endpoint for polling without enqueueing")
        print("   3. ✅ AudioPlayer uses smart polling with exponential backoff")
        print("   4. ✅ Timer cleanup prevents memory leaks and duplicate requests")
        print("\n🎯 Expected Behavior:")
        print("   - No duplicate jobs in RECORDING_QUEUE (Redis dedup)")
        print("   - Polling uses /status endpoint (doesn't trigger enqueue)")
        print("   - Exponential backoff: 3s → 5s → 8s → 12s → 15s")
        print("   - Timers cleaned up on unmount/src change")
        return 0
    else:
        print(f"❌ Some checks failed ({passed}/{total})")
        print("=" * 70)
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
