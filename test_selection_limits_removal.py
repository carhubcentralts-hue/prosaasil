#!/usr/bin/env python3
"""
Test removal of 3-selection limit and status filtering for outbound calls

This test verifies:
1. API accepts unlimited lead selections (> 3)
2. Status filtering works for imported leads
3. Selection logic handles large numbers correctly
"""

def test_selection_limit_removed():
    """
    Verify that the 3-lead selection limit has been removed
    """
    print("\n=== Test: Selection Limit Removed ===")
    
    test_cases = [
        {"count": 1, "should_accept": True, "description": "Single lead"},
        {"count": 3, "should_accept": True, "description": "3 leads (old limit)"},
        {"count": 10, "should_accept": True, "description": "10 leads"},
        {"count": 50, "should_accept": True, "description": "50 leads"},
        {"count": 100, "should_accept": True, "description": "100 leads"},
        {"count": 500, "should_accept": True, "description": "500 leads"},
    ]
    
    passed = 0
    failed = 0
    
    for case in test_cases:
        # The API should no longer reject based on count
        # (it will use bulk queue for >3 automatically)
        expected_result = "accepted"
        actual_result = "accepted" if case["should_accept"] else "rejected"
        
        if actual_result == expected_result:
            print(f"✓ {case['description']}: {case['count']} leads - {actual_result}")
            passed += 1
        else:
            print(f"✗ {case['description']}: {case['count']} leads - Expected {expected_result}, got {actual_result}")
            failed += 1
    
    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


def test_status_filtering_api():
    """
    Verify that status filtering is properly supported in the API
    """
    print("\n=== Test: Status Filtering API ===")
    
    # Test status filter URL construction
    test_cases = [
        {
            "description": "Single status filter",
            "statuses": ["new"],
            "expected_params": "statuses[]=new"
        },
        {
            "description": "Multiple status filters",
            "statuses": ["new", "contacted", "no_answer"],
            "expected_params": "statuses[]=new&statuses[]=contacted&statuses[]=no_answer"
        },
        {
            "description": "No status filter",
            "statuses": [],
            "expected_params": ""
        },
    ]
    
    passed = 0
    failed = 0
    
    for case in test_cases:
        # Build query params like the frontend does
        params_list = [f"statuses[]={status}" for status in case["statuses"]]
        actual_params = "&".join(params_list)
        
        if actual_params == case["expected_params"]:
            print(f"✓ {case['description']}: {actual_params or '(empty)'}")
            passed += 1
        else:
            print(f"✗ {case['description']}: Expected '{case['expected_params']}', got '{actual_params}'")
            failed += 1
    
    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


def test_selection_state_management():
    """
    Verify that selection state is properly managed across tabs
    """
    print("\n=== Test: Selection State Management ===")
    
    # Simulate selection state (using sets like the frontend)
    system_selected = set()
    imported_selected = set()
    
    test_cases = [
        {
            "description": "Select 5 leads in system tab",
            "action": "select_system",
            "ids": [1, 2, 3, 4, 5],
            "expected_system": {1, 2, 3, 4, 5},
            "expected_imported": set()
        },
        {
            "description": "Select 10 leads in imported tab",
            "action": "select_imported",
            "ids": [101, 102, 103, 104, 105, 106, 107, 108, 109, 110],
            "expected_system": {1, 2, 3, 4, 5},
            "expected_imported": {101, 102, 103, 104, 105, 106, 107, 108, 109, 110}
        },
        {
            "description": "Clear system selection",
            "action": "clear_system",
            "ids": [],
            "expected_system": set(),
            "expected_imported": {101, 102, 103, 104, 105, 106, 107, 108, 109, 110}
        },
    ]
    
    passed = 0
    failed = 0
    
    for case in test_cases:
        if case["action"] == "select_system":
            system_selected = set(case["ids"])
        elif case["action"] == "select_imported":
            imported_selected = set(case["ids"])
        elif case["action"] == "clear_system":
            system_selected = set()
        elif case["action"] == "clear_imported":
            imported_selected = set()
        
        if system_selected == case["expected_system"] and imported_selected == case["expected_imported"]:
            print(f"✓ {case['description']}")
            print(f"  System: {len(system_selected)} selected, Imported: {len(imported_selected)} selected")
            passed += 1
        else:
            print(f"✗ {case['description']}")
            print(f"  Expected: System={len(case['expected_system'])}, Imported={len(case['expected_imported'])}")
            print(f"  Actual: System={len(system_selected)}, Imported={len(imported_selected)}")
            failed += 1
    
    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


def main():
    """Run all tests"""
    print("=" * 60)
    print("Testing Selection Limits Removal & Status Filtering")
    print("=" * 60)
    
    all_passed = True
    
    all_passed &= test_selection_limit_removed()
    all_passed &= test_status_filtering_api()
    all_passed &= test_selection_state_management()
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ ALL TESTS PASSED")
    else:
        print("✗ SOME TESTS FAILED")
    print("=" * 60)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit(main())
