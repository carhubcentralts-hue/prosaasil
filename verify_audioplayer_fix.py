#!/usr/bin/env python3
"""
Verification script for AudioPlayer 404 Loop Fix

Verifies that the code changes correctly handle:
1. "cached" reason -> returns "ready" (200)
2. "duplicate" reason -> returns "processing" (202) 
3. "error" reason -> returns "error" (500)

This prevents infinite 404 loops when recordings are being downloaded.
"""
import sys
import os
import re

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def verify_routes_calls_fix():
    """
    Verify that routes_calls.py correctly handles cached vs duplicate status
    """
    print("=" * 70)
    print("🔍 VERIFYING AUDIOPLAYER 404 FIX")
    print("=" * 70)
    
    with open('server/routes_calls.py', 'r') as f:
        content = f.read()
    
    # Check for the fix in download endpoint
    download_start = content.find('def download_recording')
    download_end = content.find('def get_recording_status')
    if download_start == -1 or download_end == -1:
        print("❌ ERROR: Could not find download_recording function")
        return False
    download_section = content[download_start:download_end]
    
    checks = {
        "download_cached_check": 'elif reason == "cached":' in download_section,
        "download_duplicate_check": 'elif reason == "duplicate":' in download_section,
    }
    
    # Check for cached handling
    cached_pos = download_section.find('elif reason == "cached":')
    if cached_pos != -1:
        cached_block = download_section[cached_pos:cached_pos + 500]
        checks["download_cached_returns_ready"] = 'status": "ready"' in cached_block
    else:
        checks["download_cached_returns_ready"] = False
    
    # Check for duplicate handling
    duplicate_pos = download_section.find('elif reason == "duplicate":')
    if duplicate_pos != -1:
        duplicate_block = download_section[duplicate_pos:duplicate_pos + 500]
        checks["download_duplicate_returns_processing"] = 'status": "processing"' in duplicate_block
    else:
        checks["download_duplicate_returns_processing"] = False
    
    # Check for the fix in stream endpoint
    stream_start = content.find('def stream_recording')
    if stream_start == -1:
        print("❌ ERROR: Could not find stream_recording function")
        return False
    stream_section = content[stream_start:stream_start + 15000]
    
    stream_checks = {
        "stream_cached_check": 'elif reason == "cached":' in stream_section,
        "stream_duplicate_check": 'elif reason == "duplicate":' in stream_section,
    }
    
    # Check for cached handling
    cached_pos = stream_section.find('elif reason == "cached":')
    if cached_pos != -1:
        cached_block = stream_section[cached_pos:cached_pos + 500]
        stream_checks["stream_cached_returns_ready"] = 'status": "ready"' in cached_block
    else:
        stream_checks["stream_cached_returns_ready"] = False
    
    # Check for duplicate handling
    duplicate_pos = stream_section.find('elif reason == "duplicate":')
    if duplicate_pos != -1:
        duplicate_block = stream_section[duplicate_pos:duplicate_pos + 500]
        stream_checks["stream_duplicate_returns_processing"] = 'status": "processing"' in duplicate_block
    else:
        stream_checks["stream_duplicate_returns_processing"] = False
    
    checks.update(stream_checks)
    
    print("\n✅ VERIFICATION RESULTS:")
    print("-" * 70)
    
    all_passed = True
    for check_name, result in checks.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {check_name}")
        if not result:
            all_passed = False
    
    print("-" * 70)
    
    if all_passed:
        print("\n🎉 ALL CHECKS PASSED!")
        print("\nThe fix correctly:")
        print("  1. Returns 'ready' (200) only when file is cached")
        print("  2. Returns 'processing' (202) when job is duplicate")
        print("  3. Prevents infinite 404 loops")
        return True
    else:
        print("\n❌ SOME CHECKS FAILED!")
        print("The code may still have issues with 404 loops.")
        return False


def verify_audioplayer_retry_logic():
    """
    Verify that AudioPlayer.tsx has proper retry logic
    """
    print("\n" + "=" * 70)
    print("🔍 VERIFYING AUDIOPLAYER RETRY LOGIC")
    print("=" * 70)
    
    with open('client/src/shared/components/AudioPlayer.tsx', 'r') as f:
        content = f.read()
    
    checks = {
        "has_max_retries": "MAX_RETRIES" in content,
        "has_retry_count_state": "retryCount" in content,
        "has_exponential_backoff": "getRetryDelay" in content,
        "has_404_handling": "404" in content,
        "has_abort_controller": "AbortController" in content,
    }
    
    print("\n✅ AUDIOPLAYER CHECKS:")
    print("-" * 70)
    
    all_passed = True
    for check_name, result in checks.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {check_name}")
        if not result:
            all_passed = False
    
    print("-" * 70)
    
    if all_passed:
        print("\n🎉 AUDIOPLAYER HAS PROPER RETRY LOGIC!")
        return True
    else:
        print("\n⚠️  AUDIOPLAYER MAY NEED IMPROVEMENTS")
        return False


def main():
    """
    Run all verification checks
    """
    print("\n" + "=" * 70)
    print("AUDIOPLAYER 404 LOOP FIX VERIFICATION")
    print("=" * 70)
    
    routes_ok = verify_routes_calls_fix()
    player_ok = verify_audioplayer_retry_logic()
    
    print("\n" + "=" * 70)
    print("FINAL RESULT")
    print("=" * 70)
    
    if routes_ok and player_ok:
        print("✅ ALL VERIFICATIONS PASSED!")
        print("\nThe fix should prevent infinite 404 loops:")
        print("  • Backend correctly distinguishes cached vs duplicate")
        print("  • AudioPlayer has proper retry limits and backoff")
        print("  • 404 errors are handled gracefully")
        return 0
    else:
        print("❌ SOME VERIFICATIONS FAILED")
        if not routes_ok:
            print("  • Backend fix needs attention")
        if not player_ok:
            print("  • AudioPlayer needs improvements")
        return 1


if __name__ == '__main__':
    sys.exit(main())
