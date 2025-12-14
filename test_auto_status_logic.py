#!/usr/bin/env python3
"""
Unit tests for auto-status service logic
Tests the keyword matching and status validation WITHOUT database
"""
import sys
import os

# Add the project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_auto_status_keyword_matching():
    """
    Test keyword matching logic
    
    Note: This test uses the private _map_from_keywords method to test
    keyword matching in isolation without database dependencies.
    In production code, always use the public suggest_status() method.
    """
    print("=" * 80)
    print("TEST: Auto-Status Keyword Matching")
    print("=" * 80)
    print()
    
    from server.services.lead_auto_status_service import get_auto_status_service
    
    service = get_auto_status_service()
    
    # Simulate a business with specific statuses
    valid_statuses = {
        'new', 'interested', 'not_relevant', 'follow_up', 'no_answer', 'qualified'
    }
    
    test_cases = [
        # (summary, expected_status_or_none, description)
        ("לא מעוניין בשירות", "not_relevant", "Not interested - Hebrew"),
        ("not interested, stop calling", "not_relevant", "Not interested - English"),
        ("כן מעוניין, תשלחו פרטים", "interested", "Interested - Hebrew"),
        ("yes, sounds interesting", "interested", "Interested - English"),
        ("תחזרו בשבוע הבא", "follow_up", "Follow up - Hebrew"),
        ("call back next week", "follow_up", "Follow up - English"),
        ("אין מענה", "no_answer", "No answer - Hebrew"),
        ("no answer, voicemail", "no_answer", "No answer - English"),
        ("קבענו פגישה למחר", "qualified", "Appointment set - Hebrew"),
        ("appointment scheduled", "qualified", "Appointment set - English"),
        ("יכול להיות מעניין", "interested", "Maybe interested - Hebrew"),
    ]
    
    passed = 0
    failed = 0
    
    for summary, expected, description in test_cases:
        result = service._map_from_keywords(summary, valid_statuses)
        
        if result == expected:
            print(f"✅ {description}")
            print(f"   Summary: '{summary}'")
            print(f"   Expected: {expected}, Got: {result}")
            passed += 1
        else:
            print(f"❌ {description}")
            print(f"   Summary: '{summary}'")
            print(f"   Expected: {expected}, Got: {result}")
            failed += 1
        print()
    
    print(f"Results: {passed} passed, {failed} failed")
    print()
    
    return failed == 0


def test_status_validation():
    """Test that service only returns statuses that exist"""
    print("=" * 80)
    print("TEST: Status Validation")
    print("=" * 80)
    print()
    
    from server.services.lead_auto_status_service import get_auto_status_service
    
    service = get_auto_status_service()
    
    # Simulate a business with LIMITED statuses (no 'interested')
    valid_statuses = {'new', 'contacted', 'not_relevant'}
    
    # Summary that would normally suggest 'interested'
    summary = "כן מעוניין, נשמע מעניין"
    
    result = service._map_from_keywords(summary, valid_statuses)
    
    print(f"Business statuses: {valid_statuses}")
    print(f"Summary: '{summary}'")
    print(f"Result: {result}")
    print()
    
    if result is None or result in valid_statuses:
        print("✅ PASS: Service did NOT return invalid status")
        print("   Only returns statuses that exist for business")
        return True
    else:
        print(f"❌ FAIL: Service returned invalid status '{result}'")
        print("   Should return None or a status from valid_statuses")
        return False


def test_negation_handling():
    """Test that 'לא מעוניין' is not matched as 'מעוניין'"""
    print("=" * 80)
    print("TEST: Negation Handling (Critical)")
    print("=" * 80)
    print()
    
    from server.services.lead_auto_status_service import get_auto_status_service
    
    service = get_auto_status_service()
    
    valid_statuses = {'new', 'interested', 'not_relevant'}
    
    test_cases = [
        ("לא מעוניין בשירות", "not_relevant", "Should detect NOT interested"),
        ("לא מעוניין בכלל", "not_relevant", "Should detect NOT interested"),
        ("כן מעוניין", "interested", "Should detect interested"),
        ("מעוניין לשמוע", "interested", "Should detect interested"),
    ]
    
    passed = 0
    failed = 0
    
    for summary, expected, description in test_cases:
        result = service._map_from_keywords(summary, valid_statuses)
        
        if result == expected:
            print(f"✅ {description}")
            print(f"   Summary: '{summary}' → {result}")
            passed += 1
        else:
            print(f"❌ {description}")
            print(f"   Summary: '{summary}'")
            print(f"   Expected: {expected}, Got: {result}")
            failed += 1
        print()
    
    print(f"Results: {passed} passed, {failed} failed")
    print()
    
    return failed == 0


def test_priority_tie_breaking():
    """Test priority-based tie breaking"""
    print("=" * 80)
    print("TEST: Priority Tie-Breaking")
    print("=" * 80)
    print()
    
    from server.services.lead_auto_status_service import get_auto_status_service
    
    service = get_auto_status_service()
    
    valid_statuses = {'new', 'interested', 'qualified', 'follow_up'}
    
    # Summary with both 'interested' and 'appointment' keywords
    # Appointment has higher priority (1) than interested (2)
    summary = "כן מעוניין וקבענו פגישה למחר"
    
    result = service._map_from_keywords(summary, valid_statuses)
    
    print(f"Summary: '{summary}'")
    print(f"Result: {result}")
    print()
    
    if result == 'qualified':
        print("✅ PASS: Appointment (priority 1) wins over interested (priority 2)")
        return True
    else:
        print(f"❌ FAIL: Expected 'qualified' (appointment), got '{result}'")
        return False


def main():
    print()
    print("╔" + "=" * 78 + "╗")
    print("║" + "  Auto-Status Service Unit Tests".center(78) + "║")
    print("╚" + "=" * 78 + "╝")
    print()
    
    tests = [
        ("Keyword Matching", test_auto_status_keyword_matching),
        ("Status Validation", test_status_validation),
        ("Negation Handling", test_negation_handling),
        ("Priority Tie-Breaking", test_priority_tie_breaking),
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
        return 0
    else:
        print(f"❌ {total - passed_count} TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
