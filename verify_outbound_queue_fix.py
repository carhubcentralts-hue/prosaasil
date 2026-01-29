#!/usr/bin/env python3
"""
Verification script for Outbound Queue Fix
Checks that all required changes are in place without running imports
"""
import os
import sys


def check_file_contains(filepath, patterns, description):
    """Check if a file contains all the given patterns"""
    print(f"\n{description}")
    print(f"  File: {filepath}")
    
    if not os.path.exists(filepath):
        print(f"  ✗ File not found")
        return False
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    all_found = True
    for pattern in patterns:
        if pattern in content:
            print(f"  ✓ Found: {pattern[:60]}...")
        else:
            print(f"  ✗ Missing: {pattern[:60]}...")
            all_found = False
    
    return all_found


def main():
    print("=" * 70)
    print("Outbound Queue Fix Verification")
    print("=" * 70)
    
    # Use relative path from script location
    base_path = os.path.dirname(os.path.abspath(__file__))
    all_checks_passed = True
    
    # Check 1: Backend endpoint returns 200 with active flag
    check1 = check_file_contains(
        f'{base_path}/server/routes_outbound.py',
        [
            '"ok": True',
            '"active": False',
            '"active": True',
            '"queue_len"',
            'return jsonify({',
        ],
        "Check 1: Backend endpoint returns 200 with active flag"
    )
    all_checks_passed = all_checks_passed and check1
    
    # Check 2: Dedup ignores stale NULL call_sid
    check2 = check_file_contains(
        f'{base_path}/server/services/twilio_outbound_service.py',
        [
            'stale_threshold',
            'call_sid IS NOT NULL',
            'created_at > :stale_threshold',
            'timedelta(seconds=60)',
        ],
        "Check 2: Dedup ignores stale NULL call_sid"
    )
    all_checks_passed = all_checks_passed and check2
    
    # Check 3: Cleanup handles stale call_log records
    check3 = check_file_contains(
        f'{base_path}/server/routes_outbound.py',
        [
            'Cleanup stale call_log records',
            'call_sid IS NULL',
            'call_log',
            'result_stale_calls',
        ],
        "Check 3: Cleanup handles stale call_log records"
    )
    all_checks_passed = all_checks_passed and check3
    
    # Check 4: Frontend handles active flag
    check4 = check_file_contains(
        f'{base_path}/client/src/services/calls.ts',
        [
            'active',
            'getActiveQueue',
            'response.active',
        ],
        "Check 4: Frontend handles active flag"
    )
    all_checks_passed = all_checks_passed and check4
    
    # Check 5: Semaphore has cleanup logic
    check5 = check_file_contains(
        f'{base_path}/server/services/outbound_semaphore.py',
        [
            'cleanup_expired_slots',
            'SREM',
            'inflight_key',
        ],
        "Check 5: Semaphore has cleanup for expired slots"
    )
    all_checks_passed = all_checks_passed and check5
    
    print("\n" + "=" * 70)
    if all_checks_passed:
        print("✓ ALL CHECKS PASSED - Fixes are in place")
        print("=" * 70)
        return 0
    else:
        print("✗ SOME CHECKS FAILED - Review the output above")
        print("=" * 70)
        return 1


if __name__ == '__main__':
    sys.exit(main())
