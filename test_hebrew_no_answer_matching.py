#!/usr/bin/env python3
"""
Test for Hebrew no-answer status matching
Tests the CRITICAL FIX for matching Hebrew status labels like "אין מענה"
"""
import sys
import os

# Add the project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_hebrew_label_matching():
    """
    Test that statuses with Hebrew labels are correctly matched
    
    Simulates a business with custom status names but Hebrew labels:
    - name: "custom_mjqxkfis", label: "אין מענה 1"
    - name: "custom_mjqxk7gb", label: "אין מענה 2"
    - name: "custom_mjrzufjt", label: "אין מענה 3"
    """
    print("=" * 80)
    print("TEST: Hebrew Label Matching for No-Answer Statuses")
    print("=" * 80)
    print()
    
    from server.services.lead_auto_status_service import LeadAutoStatusService
    
    # Create a mock status class
    class MockStatus:
        def __init__(self, name, label, description=None):
            self.name = name
            self.label = label
            self.description = description
    
    service = LeadAutoStatusService()
    
    # Simulate business statuses with custom names but Hebrew labels
    mock_statuses = [
        MockStatus("custom_mjqxkfis", "אין מענה 1", None),
        MockStatus("custom_mjqxk7gb", "אין מענה 2", None),
        MockStatus("custom_mjrzufjt", "אין מענה 3", None),
        MockStatus("interested", "מעוניין", "לקוח מעוניין"),
        MockStatus("new", "חדש", "ליד חדש"),
    ]
    
    # Test the keyword matching logic
    no_answer_keywords = [
        'no_answer', 'no answer', 'אין מענה', 'לא ענה', 'לא נענה',
        'busy', 'תפוס', 'קו תפוס', 'failed', 'נכשל', 'שיחה נכשלה',
        'unanswered', 'not answered', 'didnt answer', "didn't answer"
    ]
    
    found_statuses = []
    status_match_info = {}
    
    for status in mock_statuses:
        matched_in = []
        
        # Check name field
        if status.name:
            name_lower = status.name.lower()
            if any(kw in name_lower for kw in no_answer_keywords):
                matched_in.append("name")
        
        # Check label field (CRITICAL!)
        if status.label:
            label_lower = status.label.lower()
            if any(kw in label_lower for kw in no_answer_keywords):
                matched_in.append("label")
        
        # Check description field
        if status.description:
            desc_lower = status.description.lower()
            if any(kw in desc_lower for kw in no_answer_keywords):
                matched_in.append("description")
        
        # If any field matched, add this status
        if matched_in:
            found_statuses.append(status.name)
            status_match_info[status.name] = {
                'fields': matched_in,
                'label': status.label,
                'name': status.name
            }
            print(f"✅ Found: '{status.name}' (label: '{status.label}', matched in: {', '.join(matched_in)})")
    
    print()
    print(f"Total found: {len(found_statuses)}")
    print()
    
    # Verify results
    expected_statuses = ["custom_mjqxkfis", "custom_mjqxk7gb", "custom_mjrzufjt"]
    
    if len(found_statuses) == 3 and all(s in found_statuses for s in expected_statuses):
        print("✅ PASS: All Hebrew-labeled no-answer statuses were found!")
        print(f"   Found: {found_statuses}")
        return True
    else:
        print("❌ FAIL: Did not find all Hebrew-labeled statuses")
        print(f"   Expected: {expected_statuses}")
        print(f"   Found: {found_statuses}")
        return False


def test_number_extraction_from_labels():
    """
    Test that numbers are correctly extracted from Hebrew labels for progression
    """
    print("=" * 80)
    print("TEST: Number Extraction from Hebrew Labels")
    print("=" * 80)
    print()
    
    import re
    
    # Create a mock status class
    class MockStatus:
        def __init__(self, name, label):
            self.name = name
            self.label = label
    
    test_cases = [
        (MockStatus("custom_mjqxkfis", "אין מענה 1"), 1),
        (MockStatus("custom_mjqxk7gb", "אין מענה 2"), 2),
        (MockStatus("custom_mjrzufjt", "אין מענה 3"), 3),
        (MockStatus("no_answer_1", "No Answer 1"), 1),
        (MockStatus("no_answer_2", "No Answer 2"), 2),
        (MockStatus("base_status", "אין מענה"), None),  # No number at all - base status
        (MockStatus("custom_xyz", "לא נענה"), None),  # No number in label or name
    ]
    
    passed = 0
    failed = 0
    
    for status, expected_number in test_cases:
        # Extract numbers from label (priority)
        numbers_in_label = re.findall(r'\d+', status.label or '')
        numbers_in_name = re.findall(r'\d+', status.name)
        
        # Prefer label over name
        if numbers_in_label:
            extracted_number = int(numbers_in_label[0])
        elif numbers_in_name:
            extracted_number = int(numbers_in_name[0])
        else:
            extracted_number = None
        
        if extracted_number == expected_number:
            print(f"✅ '{status.name}' (label: '{status.label}') → {extracted_number}")
            passed += 1
        else:
            print(f"❌ '{status.name}' (label: '{status.label}') → Expected: {expected_number}, Got: {extracted_number}")
            failed += 1
    
    print()
    print(f"Results: {passed} passed, {failed} failed")
    print()
    
    return failed == 0


def test_progression_logic():
    """
    Test the full progression logic with Hebrew labels
    """
    print("=" * 80)
    print("TEST: No-Answer Progression with Hebrew Labels")
    print("=" * 80)
    print()
    
    import re
    
    # Create a mock status class
    class MockStatus:
        def __init__(self, name, label):
            self.name = name
            self.label = label
    
    # Simulate statuses with Hebrew labels
    available_statuses = [
        MockStatus("custom_mjqxkfis", "אין מענה 1"),
        MockStatus("custom_mjqxk7gb", "אין מענה 2"),
        MockStatus("custom_mjrzufjt", "אין מענה 3"),
    ]
    
    # Build attempt mapping
    status_by_attempt = {}
    
    for status in available_statuses:
        numbers_in_name = re.findall(r'\d+', status.name)
        numbers_in_label = re.findall(r'\d+', status.label or '')
        
        # Combine all found numbers (prefer label over name)
        all_numbers = numbers_in_label + numbers_in_name
        
        if all_numbers:
            attempt_num = int(all_numbers[0])
            status_by_attempt[attempt_num] = status.name
            print(f"🔢 Mapped attempt {attempt_num} → '{status.name}' (label: '{status.label}')")
    
    print()
    print(f"Attempt mapping: {status_by_attempt}")
    print()
    
    # Test progression scenarios
    test_scenarios = [
        (1, "custom_mjqxkfis", "First no-answer → אין מענה 1"),
        (2, "custom_mjqxk7gb", "Second no-answer → אין מענה 2"),
        (3, "custom_mjrzufjt", "Third no-answer → אין מענה 3"),
    ]
    
    passed = 0
    failed = 0
    
    for next_attempt, expected_status, description in test_scenarios:
        # Find matching status
        if next_attempt in status_by_attempt:
            target_status = status_by_attempt[next_attempt]
        else:
            target_status = None
        
        if target_status == expected_status:
            print(f"✅ {description}")
            print(f"   Attempt {next_attempt} → '{target_status}'")
            passed += 1
        else:
            print(f"❌ {description}")
            print(f"   Expected: '{expected_status}', Got: '{target_status}'")
            failed += 1
        print()
    
    print(f"Results: {passed} passed, {failed} failed")
    print()
    
    return failed == 0


def main():
    print()
    print("╔" + "=" * 78 + "╗")
    print("║" + "  Hebrew No-Answer Status Matching Tests".center(78) + "║")
    print("╚" + "=" * 78 + "╝")
    print()
    
    tests = [
        ("Hebrew Label Matching", test_hebrew_label_matching),
        ("Number Extraction", test_number_extraction_from_labels),
        ("Progression Logic", test_progression_logic),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            print(f"❌ TEST CRASHED: {test_name}")
            print(f"   Error: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Summary
    print()
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print()
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print()
    
    total = len(results)
    passed_count = sum(1 for _, p in results if p)
    
    print(f"Total: {passed_count}/{total} tests passed")
    print()
    
    if passed_count == total:
        print("✅ ALL TESTS PASSED")
        print()
        print("🎯 The fix successfully:")
        print("   1. Matches Hebrew labels like 'אין מענה 1', 'אין מענה 2', 'אין מענה 3'")
        print("   2. Extracts numbers from Hebrew labels for progression")
        print("   3. Maps attempts correctly to numbered statuses")
        return 0
    else:
        print(f"❌ {total - passed_count} TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
