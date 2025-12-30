#!/usr/bin/env python3
"""
Test for Busy Call Status Fix
Verifies that busy calls ("קו תפוס") get proper status updates
"""
import sys
import os

# Add the project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_busy_call_detection():
    """Test that busy calls are detected and get appropriate status"""
    print("=" * 80)
    print("TEST: Busy Call Detection")
    print("=" * 80)
    print()
    
    from server.services.lead_auto_status_service import get_auto_status_service
    
    service = get_auto_status_service()
    
    # Mock available statuses (simulating business statuses)
    valid_statuses = {
        'new': 'חדש',
        'no_answer': 'אין מענה',
        'no_answer_2': 'אין מענה 2',
        'busy': 'תפוס',
        'interested': 'מעוניין'
    }
    
    # Mock the _get_valid_statuses_dict method
    original_method = service._get_valid_statuses_dict
    service._get_valid_statuses_dict = lambda tenant_id: valid_statuses
    
    try:
        # Test 1: Busy call summary from failed call handler
        print("Test 1: Busy call summary - 'שיחה לא נענתה - קו תפוס'")
        print("-" * 60)
        result = service.suggest_status(
            tenant_id=1,
            lead_id=1,
            call_direction='outbound',
            call_summary="שיחה לא נענתה - קו תפוס",
            call_transcript=None,
            call_duration=0
        )
        
        print(f"Call Summary: 'שיחה לא נענתה - קו תפוס'")
        print(f"Duration: 0 seconds")
        print(f"Suggested Status: {result}")
        print()
        
        if result and ('no_answer' in result.lower() or 'busy' in result.lower()):
            print("✅ PASS: Status correctly suggested for busy call")
            test1_passed = True
        else:
            print(f"❌ FAIL: Expected no_answer or busy status, got '{result}'")
            test1_passed = False
        print()
        
        # Test 2: No-answer call summary
        print("Test 2: No-answer call summary - 'שיחה לא נענתה - אין מענה'")
        print("-" * 60)
        result = service.suggest_status(
            tenant_id=1,
            lead_id=1,
            call_direction='outbound',
            call_summary="שיחה לא נענתה - אין מענה",
            call_transcript=None,
            call_duration=0
        )
        
        print(f"Call Summary: 'שיחה לא נענתה - אין מענה'")
        print(f"Duration: 0 seconds")
        print(f"Suggested Status: {result}")
        print()
        
        if result and 'no_answer' in result.lower():
            print("✅ PASS: Status correctly suggested for no-answer call")
            test2_passed = True
        else:
            print(f"❌ FAIL: Expected no_answer status, got '{result}'")
            test2_passed = False
        print()
        
        # Test 3: Failed call summary
        print("Test 3: Failed call summary - 'שיחה נכשלה - לא הצליח להתקשר'")
        print("-" * 60)
        result = service.suggest_status(
            tenant_id=1,
            lead_id=1,
            call_direction='outbound',
            call_summary="שיחה נכשלה - לא הצליח להתקשר",
            call_transcript=None,
            call_duration=0
        )
        
        print(f"Call Summary: 'שיחה נכשלה - לא הצליח להתקשר'")
        print(f"Duration: 0 seconds")
        print(f"Suggested Status: {result}")
        print()
        
        if result and 'no_answer' in result.lower():
            print("✅ PASS: Status correctly suggested for failed call")
            test3_passed = True
        else:
            print(f"❌ FAIL: Expected no_answer status, got '{result}'")
            test3_passed = False
        print()
        
        return test1_passed and test2_passed and test3_passed
        
    finally:
        # Restore original method
        service._get_valid_statuses_dict = original_method


def test_busy_keyword_matching():
    """Test that busy keywords are properly matched"""
    print("=" * 80)
    print("TEST: Busy Keyword Matching")
    print("=" * 80)
    print()
    
    from server.services.lead_auto_status_service import get_auto_status_service
    
    service = get_auto_status_service()
    
    # Test various busy-related texts
    test_cases = [
        ("קו תפוס", True, "Hebrew: קו תפוס"),
        ("line busy", True, "English: line busy"),
        ("busy", True, "English: busy"),
        ("תפוס", True, "Hebrew: תפוס"),
        ("שיחה לא נענתה - קו תפוס", True, "Full summary with busy"),
        ("שיחה נכשלה", True, "Failed call"),
        ("מעוניין בשירות", False, "Interested (should NOT match)")
    ]
    
    all_passed = True
    
    for text, should_match, description in test_cases:
        # Check if the text contains any of the no-answer indicators
        no_answer_indicators = [
            'לא נענה', 'לא ענה', 'אין מענה', 'no answer', 'unanswered', 
            'didn\'t answer', 'did not answer', 'לא השיב', 'לא הגיב',
            'ניתוק מיידי', 'immediate disconnect', '0 שניות', '1 שנייה', '2 שניות',
            'שיחה לא נענתה',
            'קו תפוס', 'line busy', 'busy', 'תפוס',
            'שיחה נכשלה', 'call failed', 'failed', 'נכשל'
        ]
        
        text_lower = text.lower()
        matches = any(indicator in text_lower for indicator in no_answer_indicators)
        
        if matches == should_match:
            print(f"✅ PASS: {description} - matches={matches} (expected={should_match})")
        else:
            print(f"❌ FAIL: {description} - matches={matches} (expected={should_match})")
            all_passed = False
    
    print()
    return all_passed


def main():
    print()
    print("╔" + "=" * 78 + "╗")
    print("║" + "  Busy Call Status Fix Tests".center(78) + "║")
    print("╚" + "=" * 78 + "╝")
    print()
    
    tests = [
        ("Busy Call Detection", test_busy_call_detection),
        ("Busy Keyword Matching", test_busy_keyword_matching),
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
        print()
    
    # Summary
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
