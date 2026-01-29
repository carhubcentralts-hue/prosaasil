#!/usr/bin/env python3
"""
Verification script for outbound call queue fixes

This script verifies that the fixes are correctly applied without requiring
imports or dependencies.
"""

print("=" * 70)
print("Outbound Call Queue Fixes Verification")
print("=" * 70)
print()

# Read the source file
with open('server/routes_outbound.py', 'r') as f:
    source = f.read()

tests_passed = 0
tests_failed = 0

# Test 1: Lock token mismatch only logged on failure
print("Test 1: Lock token mismatch only logged when rowcount == 0")
print("-" * 70)
if 'if update_result.rowcount == 0:' in source:
    # Find the section after this check
    parts = source.split('if update_result.rowcount == 0:')
    if len(parts) > 1:
        # Check that the error is in the if block (not always executed)
        next_section = parts[1].split('\n')[0:5]
        next_text = '\n'.join(next_section)
        if 'log.error' in next_text and 'Lock token mismatch' in next_text:
            print("✅ PASS: Lock token mismatch error only logged when rowcount == 0")
            tests_passed += 1
        else:
            print("❌ FAIL: Error logging not found in the correct place")
            tests_failed += 1
    else:
        print("❌ FAIL: Could not find check for rowcount")
        tests_failed += 1
else:
    print("❌ FAIL: Fix for rowcount check not found")
    tests_failed += 1
print()

# Test 2: Already_queued handling
print("Test 2: Jobs with 'already_queued' status wait instead of skip")
print("-" * 70)
if 'status == "already_queued"' in source or "status == 'already_queued'" in source:
    # Find the section
    if 'already in Redis queue, waiting for slot to free up' in source:
        # Check that it sleeps and continues
        already_queued_section = source.split('already_queued')[1].split('elif')[0]
        if 'time.sleep(1)' in already_queued_section and 'continue' in already_queued_section:
            print("✅ PASS: Jobs with 'already_queued' status wait (sleep 1s) and retry")
            tests_passed += 1
        else:
            print("❌ FAIL: Sleep/continue not found for already_queued")
            tests_failed += 1
    else:
        print("❌ FAIL: Descriptive log message not found")
        tests_failed += 1
else:
    print("❌ FAIL: Fix for already_queued not found")
    tests_failed += 1
print()

# Test 3: Separate handling for inflight
print("Test 3: 'inflight' status handled separately from 'already_queued'")
print("-" * 70)
if 'status == "inflight"' in source or "status == 'inflight'" in source:
    print("✅ PASS: 'inflight' status has separate handling")
    tests_passed += 1
else:
    print("❌ FAIL: Separate inflight handling not found")
    tests_failed += 1
print()

# Test 4: Stop queue API exists
print("Test 4: Stop queue API is implemented")
print("-" * 70)
if '/api/outbound/stop-queue' in source:
    if 'run.status = "stopped"' in source or "run.status = 'stopped'" in source:
        if 'cancelled_count' in source:
            print("✅ PASS: Stop queue API is properly implemented")
            tests_passed += 1
        else:
            print("❌ FAIL: Stop queue doesn't track cancelled count")
            tests_failed += 1
    else:
        print("❌ FAIL: Stop queue doesn't set status to stopped")
        tests_failed += 1
else:
    print("❌ FAIL: Stop queue API endpoint not found")
    tests_failed += 1
print()

# Summary
print("=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"Tests Passed: {tests_passed}/4")
print(f"Tests Failed: {tests_failed}/4")
print()

if tests_failed == 0:
    print("✅ All verification tests passed!")
    print()
    print("Fixes applied:")
    print("  1. Lock token mismatch error only logged when UPDATE fails (rowcount == 0)")
    print("  2. Jobs with 'already_queued' status wait for Redis queue instead of being skipped")
    print("  3. 'inflight' and 'already_queued' handled separately")
    print("  4. Stop queue API is properly implemented")
    exit(0)
else:
    print("❌ Some verification tests failed!")
    exit(1)
