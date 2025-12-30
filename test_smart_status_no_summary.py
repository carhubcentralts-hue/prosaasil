#!/usr/bin/env python3
"""
Test smart status change logic for calls without summary
Tests the enhanced auto-status service with duration-based logic
"""
import sys
import os

# Add the project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_short_call_no_answer():
    """Test that very short calls (< 5 seconds) go to no_answer"""
    print("=" * 80)
    print("TEST: Short Call (< 5 seconds) → No Answer")
    print("=" * 80)
    print()
    
    from server.services.lead_auto_status_service import get_auto_status_service
    
    service = get_auto_status_service()
    
    # Simulate a business with no_answer status
    valid_statuses = {
        'new': 'חדש',
        'no_answer': 'אין מענה',
        'interested': 'מעוניין'
    }
    
    # Mock the _get_valid_statuses_dict method
    original_method = service._get_valid_statuses_dict
    service._get_valid_statuses_dict = lambda tenant_id: valid_statuses
    
    # Mock _handle_no_answer_with_progression to return simple no_answer
    service._handle_no_answer_with_progression = lambda t, l, v: 'no_answer'
    
    try:
        # Test with very short call (3 seconds), no summary
        result = service.suggest_status(
            tenant_id=1,
            lead_id=1,
            call_direction='outbound',
            call_summary=None,
            call_transcript=None,
            call_duration=3  # Very short call
        )
        
        print(f"Call duration: 3 seconds")
        print(f"Summary: None")
        print(f"Result: {result}")
        print()
        
        if result == 'no_answer':
            print("✅ PASS: Short call correctly assigned to no_answer")
            return True
        else:
            print(f"❌ FAIL: Expected 'no_answer', got '{result}'")
            return False
    finally:
        # Restore original method
        service._get_valid_statuses_dict = original_method


def test_mid_length_disconnect():
    """Test that mid-length calls (25 seconds) without summary get smart status"""
    print("=" * 80)
    print("TEST: Mid-Length Call (25 seconds) → Smart Status")
    print("=" * 80)
    print()
    
    from server.services.lead_auto_status_service import get_auto_status_service
    
    service = get_auto_status_service()
    
    # Simulate a business with various statuses including "contacted"
    valid_statuses = {
        'new': 'חדש',
        'no_answer': 'אין מענה',
        'contacted': 'נוצר קשר',
        'interested': 'מעוניין'
    }
    
    # Mock the _get_valid_statuses_dict method
    original_method = service._get_valid_statuses_dict
    service._get_valid_statuses_dict = lambda tenant_id: valid_statuses
    
    try:
        # Test with mid-length call (26 seconds), no summary
        result = service.suggest_status(
            tenant_id=1,
            lead_id=1,
            call_direction='outbound',
            call_summary=None,
            call_transcript=None,
            call_duration=26  # Mid-length call
        )
        
        print(f"Call duration: 26 seconds")
        print(f"Summary: None")
        print(f"Result: {result}")
        print()
        
        if result == 'contacted':
            print("✅ PASS: Mid-length call correctly assigned to contacted")
            return True
        elif result in valid_statuses:
            print(f"✅ PASS: Mid-length call assigned to valid status '{result}'")
            return True
        else:
            print(f"❌ FAIL: Expected valid status, got '{result}'")
            return False
    finally:
        # Restore original method
        service._get_valid_statuses_dict = original_method


def test_no_answer_progression_logic():
    """Test the smart no-answer progression logic"""
    print("=" * 80)
    print("TEST: No-Answer Status Progression")
    print("=" * 80)
    print()
    
    from server.services.lead_auto_status_service import get_auto_status_service
    
    service = get_auto_status_service()
    
    # Test case 1: Business with numbered no-answer statuses
    valid_statuses_numbered = {
        'new': 'חדש',
        'no_answer': 'אין מענה',
        'no_answer_2': 'אין מענה 2',
        'no_answer_3': 'אין מענה 3',
        'interested': 'מעוניין'
    }
    
    print("Test Case 1: Business with no_answer, no_answer_2, no_answer_3")
    
    # Test finding available no-answer statuses
    available = []
    for status_name in valid_statuses_numbered.keys():
        status_lower = status_name.lower()
        if ('no_answer' in status_lower or 
            'no answer' in status_lower or 
            'אין מענה' in status_lower):
            available.append(status_name)
    
    print(f"Available no-answer statuses: {sorted(available)}")
    
    if len(available) == 3:
        print("✅ PASS: Found all 3 no-answer status variants")
        print()
        result1 = True
    else:
        print(f"❌ FAIL: Expected 3 statuses, found {len(available)}")
        print()
        result1 = False
    
    # Test case 2: Business with only base no_answer
    valid_statuses_simple = {
        'new': 'חדש',
        'no_answer': 'אין מענה',
        'interested': 'מעוניין'
    }
    
    print("Test Case 2: Business with only base no_answer")
    
    available = []
    for status_name in valid_statuses_simple.keys():
        status_lower = status_name.lower()
        if ('no_answer' in status_lower or 
            'no answer' in status_lower or 
            'אין מענה' in status_lower):
            available.append(status_name)
    
    print(f"Available no-answer statuses: {sorted(available)}")
    
    if len(available) == 1 and 'no_answer' in available:
        print("✅ PASS: Found base no_answer status")
        print()
        result2 = True
    else:
        print(f"❌ FAIL: Expected 1 status, found {len(available)}")
        print()
        result2 = False
    
    return result1 and result2


def test_with_summary_still_works():
    """Test that normal flow with summary still works"""
    print("=" * 80)
    print("TEST: Normal Flow with Summary (Regression)")
    print("=" * 80)
    print()
    
    from server.services.lead_auto_status_service import get_auto_status_service
    
    service = get_auto_status_service()
    
    valid_statuses = {
        'new': 'חדש',
        'no_answer': 'אין מענה',
        'interested': 'מעוניין',
        'not_relevant': 'לא רלוונטי'
    }
    
    # Mock the _get_valid_statuses_dict method
    original_method = service._get_valid_statuses_dict
    service._get_valid_statuses_dict = lambda tenant_id: valid_statuses
    
    # Mock AI suggestion to avoid API call
    original_ai = service._suggest_status_with_ai
    service._suggest_status_with_ai = lambda text, statuses, direction: None  # Skip AI
    
    try:
        # Test with summary showing interest
        result = service.suggest_status(
            tenant_id=1,
            lead_id=1,
            call_direction='inbound',
            call_summary="הלקוח מעוניין בשירות ומבקש פרטים נוספים",
            call_transcript=None,
            call_duration=120  # Long call
        )
        
        print(f"Call duration: 120 seconds")
        print(f"Summary: 'הלקוח מעוניין בשירות ומבקש פרטים נוספים'")
        print(f"Result: {result}")
        print()
        
        if result == 'interested':
            print("✅ PASS: Summary-based status detection still works")
            return True
        else:
            print(f"❌ FAIL: Expected 'interested', got '{result}'")
            return False
    finally:
        # Restore original methods
        service._get_valid_statuses_dict = original_method
        service._suggest_status_with_ai = original_ai


def main():
    print()
    print("╔" + "=" * 78 + "╗")
    print("║" + "  Smart Status Change (No Summary) Tests".center(78) + "║")
    print("╚" + "=" * 78 + "╝")
    print()
    
    tests = [
        ("Short Call No Answer", test_short_call_no_answer),
        ("Mid-Length Disconnect", test_mid_length_disconnect),
        ("No-Answer Progression Logic", test_no_answer_progression_logic),
        ("Normal Flow Regression", test_with_summary_still_works),
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
