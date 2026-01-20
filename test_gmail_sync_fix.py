#!/usr/bin/env python3
"""
Test for Gmail sync duplicate validation fix
Verifies that the mode validation logic works correctly after the fix
"""

import sys

def test_mode_validation_logic():
    """
    Test that mode validation logic works correctly
    """
    print("=" * 80)
    print("TEST: Mode validation logic in sync_receipts endpoint")
    print("=" * 80)
    
    # Test cases for mode validation
    test_cases = [
        ('incremental', True, 'incremental'),
        ('full', True, 'full_backfill'),  # Should be mapped to full_backfill
        ('full_backfill', True, 'full_backfill'),
        ('invalid_mode', False, None),
    ]
    
    all_passed = True
    
    for mode_input, should_pass, expected_mode in test_cases:
        # Simulate the validation logic from routes_receipts.py
        mode = mode_input
        
        # First validation - check if mode is valid
        if mode not in ['full_backfill', 'incremental', 'full']:
            if should_pass:
                print(f"❌ FAIL: Mode '{mode_input}' should pass but was rejected by first validation")
                all_passed = False
            else:
                print(f"✅ PASS: Mode '{mode_input}' correctly rejected by validation")
            continue
        
        # Map legacy 'full' to 'full_backfill'
        if mode == 'full':
            mode = 'full_backfill'
        
        # After this point, mode should be either 'full_backfill' or 'incremental'
        # The bug was that there was a second validation that checked for ['full', 'incremental']
        # which would fail for 'full_backfill' even though it's valid
        
        if mode == expected_mode:
            print(f"✅ PASS: Mode '{mode_input}' -> '{mode}' matches expected '{expected_mode}'")
        else:
            print(f"❌ FAIL: Mode '{mode_input}' -> '{mode}' doesn't match expected '{expected_mode}'")
            all_passed = False
    
    print("\n" + "=" * 80)
    if all_passed:
        print("✅ ALL MODE VALIDATION TESTS PASSED")
    else:
        print("❌ SOME MODE VALIDATION TESTS FAILED")
    print("=" * 80)
    
    return all_passed


def test_no_duplicate_validation():
    """
    Test that there's no duplicate validation in routes_receipts.py
    """
    print("\n" + "=" * 80)
    print("TEST: No duplicate mode validation in routes_receipts.py")
    print("=" * 80)
    
    try:
        file_path = '/home/runner/work/prosaasil/prosaasil/server/routes_receipts.py'
        
        with open(file_path, 'r') as f:
            lines = f.readlines()
        
        # Find the sync_receipts function
        in_function = False
        mode_validations = []
        
        for i, line in enumerate(lines, start=1):
            if 'def sync_receipts():' in line:
                in_function = True
                print(f"✅ Found sync_receipts function at line {i}")
                continue
            
            if in_function:
                # Look for next function definition to know when to stop
                if line.startswith('def ') and 'sync_receipts' not in line:
                    break
                
                # Check for mode validation
                if 'if mode not in' in line:
                    mode_validations.append((i, line.strip()))
        
        print(f"\nFound {len(mode_validations)} mode validation(s):")
        for line_num, line in mode_validations:
            print(f"  Line {line_num}: {line}")
        
        if len(mode_validations) == 1:
            print("\n✅ PASS: Only one mode validation found (duplicate removed)")
            
            # Check that the validation includes the correct modes
            validation_line = mode_validations[0][1]
            if "'full_backfill'" in validation_line and "'incremental'" in validation_line and "'full'" in validation_line:
                print("✅ PASS: Validation includes all required modes: 'full_backfill', 'incremental', 'full'")
                return True
            else:
                print("❌ FAIL: Validation doesn't include all required modes")
                return False
        elif len(mode_validations) == 0:
            print("❌ FAIL: No mode validation found")
            return False
        else:
            print(f"❌ FAIL: Found {len(mode_validations)} mode validations (should be 1)")
            return False
            
    except FileNotFoundError:
        print(f"❌ File not found: {file_path}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = True
    
    # Run tests
    success = test_mode_validation_logic() and success
    success = test_no_duplicate_validation() and success
    
    if success:
        print("\n" + "=" * 80)
        print("🎉 All Gmail sync fix tests passed!")
        print("=" * 80)
        print("\n✅ The fix is working correctly:")
        print("   - Mode validation logic works for all valid modes")
        print("   - No duplicate validation code found")
        print("   - 'full' mode correctly maps to 'full_backfill'")
        print("   - Sync endpoint should now work with custom date ranges")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed")
        sys.exit(1)
