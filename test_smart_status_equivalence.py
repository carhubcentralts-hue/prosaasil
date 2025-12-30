#!/usr/bin/env python3
"""
Test Suite: Smart Status Equivalence and Change Prevention
Tests the new logic that prevents unnecessary status changes
"""
import sys
import os

# Add the project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_status_family_classification():
    """Test that statuses are correctly classified into families"""
    print("=" * 80)
    print("TEST: Status Family Classification")
    print("=" * 80)
    print()
    
    from server.services.lead_auto_status_service import get_auto_status_service
    
    service = get_auto_status_service()
    
    test_cases = [
        # (status_name, expected_family, description)
        ("no_answer", "NO_ANSWER", "English no_answer"),
        ("no_answer_2", "NO_ANSWER", "English no_answer with number"),
        ("אין מענה", "NO_ANSWER", "Hebrew no answer"),
        ("אין מענה 3", "NO_ANSWER", "Hebrew no answer with number"),
        ("busy", "NO_ANSWER", "Busy status"),
        ("קו תפוס", "NO_ANSWER", "Hebrew busy"),
        ("interested", "INTERESTED", "English interested"),
        ("מעוניין", "INTERESTED", "Hebrew interested"),
        ("qualified", "QUALIFIED", "English qualified"),
        ("appointment", "QUALIFIED", "Appointment status"),
        ("פגישה", "QUALIFIED", "Hebrew meeting"),
        ("not_relevant", "NOT_RELEVANT", "English not relevant"),
        ("לא רלוונטי", "NOT_RELEVANT", "Hebrew not relevant"),
        ("follow_up", "FOLLOW_UP", "English follow up"),
        ("חזרה", "FOLLOW_UP", "Hebrew callback"),
        ("contacted", "CONTACTED", "English contacted"),
        ("נוצר קשר", "CONTACTED", "Hebrew contacted"),
        ("new", "NEW", "New lead"),
        ("חדש", "NEW", "Hebrew new"),
    ]
    
    passed = 0
    failed = 0
    
    for status_name, expected_family, description in test_cases:
        family = service._get_status_family(status_name)
        
        if family == expected_family:
            print(f"✅ {description:<40} → {family}")
            passed += 1
        else:
            print(f"❌ {description:<40} → {family} (expected {expected_family})")
            failed += 1
    
    print()
    print(f"Results: {passed} passed, {failed} failed")
    print()
    
    return failed == 0


def test_status_progression_scores():
    """Test that statuses have correct progression scores"""
    print("=" * 80)
    print("TEST: Status Progression Scores")
    print("=" * 80)
    print()
    
    from server.services.lead_auto_status_service import get_auto_status_service
    
    service = get_auto_status_service()
    
    # Define expected ordering (lower score = earlier in funnel)
    test_sequence = [
        ("new", 0, "New lead"),
        ("no_answer", 1, "No answer"),
        ("attempting", 2, "Attempting"),
        ("contacted", 3, "Contacted"),
        ("not_relevant", 3, "Not relevant (negative outcome)"),
        ("follow_up", 4, "Follow up"),
        ("interested", 5, "Interested"),
        ("qualified", 6, "Qualified"),
    ]
    
    print("Status progression scores (higher = more advanced):")
    print()
    
    passed = 0
    failed = 0
    prev_score = -1
    
    for status_name, expected_score, description in test_sequence:
        score = service._get_status_progression_score(status_name)
        
        # Check exact score
        if score == expected_score:
            print(f"✅ {description:<40} score={score}")
            passed += 1
        else:
            print(f"❌ {description:<40} score={score} (expected {expected_score})")
            failed += 1
    
    print()
    print(f"Results: {passed} passed, {failed} failed")
    print()
    
    return failed == 0


def test_no_answer_progression_detection():
    """Test detection of valid no-answer progression"""
    print("=" * 80)
    print("TEST: No-Answer Progression Detection")
    print("=" * 80)
    print()
    
    from server.services.lead_auto_status_service import get_auto_status_service
    
    service = get_auto_status_service()
    
    test_cases = [
        # (current, suggested, is_valid_progression, description)
        ("no_answer", "no_answer_2", True, "no_answer → no_answer_2"),
        ("no_answer_2", "no_answer_3", True, "no_answer_2 → no_answer_3"),
        ("אין מענה", "אין מענה 2", True, "Hebrew: אין מענה → אין מענה 2"),
        ("no_answer_2", "no_answer", False, "no_answer_2 → no_answer (backward)"),
        ("no_answer", "no_answer", False, "no_answer → no_answer (same)"),
        ("no_answer", "busy", False, "no_answer → busy (different type)"),
        ("interested", "no_answer_2", False, "interested → no_answer_2 (not in family)"),
    ]
    
    passed = 0
    failed = 0
    
    for current, suggested, expected, description in test_cases:
        result = service._is_no_answer_progression(current, suggested)
        
        if result == expected:
            icon = "✅" if expected else "⭕"
            print(f"{icon} {description:<50} is_progression={result}")
            passed += 1
        else:
            print(f"❌ {description:<50} is_progression={result} (expected {expected})")
            failed += 1
    
    print()
    print(f"Results: {passed} passed, {failed} failed")
    print()
    
    return failed == 0


def test_should_change_status_decisions():
    """Test the core decision logic for status changes"""
    print("=" * 80)
    print("TEST: Should Change Status Decisions")
    print("=" * 80)
    print()
    
    from server.services.lead_auto_status_service import get_auto_status_service
    
    service = get_auto_status_service()
    
    # Use tenant_id=999 (test tenant)
    test_tenant = 999
    
    test_cases = [
        # (current_status, suggested_status, should_change, description)
        # Basic cases
        (None, "new", True, "No current status → assign first status"),
        ("interested", None, False, "No suggested status → don't change"),
        ("interested", "interested", False, "Same status → don't change"),
        
        # Progression cases
        ("new", "interested", True, "Upgrade: new → interested"),
        ("interested", "qualified", True, "Upgrade: interested → qualified"),
        ("attempting", "contacted", True, "Upgrade: attempting → contacted"),
        
        # Downgrade prevention
        ("qualified", "interested", False, "Prevent downgrade: qualified → interested"),
        ("interested", "contacted", False, "Prevent downgrade: interested → contacted"),
        ("contacted", "attempting", False, "Prevent downgrade: contacted → attempting"),
        
        # Same family - no change
        ("interested", "מעוניין", False, "Same family INTERESTED - don't change"),
        ("contacted", "נוצר קשר", False, "Same family CONTACTED - don't change"),
        
        # No-answer progression - allowed
        ("no_answer", "no_answer_2", True, "Valid no-answer progression"),
        ("no_answer_2", "no_answer_3", True, "Valid no-answer progression 2→3"),
        
        # No-answer same level - not allowed
        ("no_answer", "busy", False, "Same NO_ANSWER family without progression"),
        ("no_answer_2", "no_answer_2", False, "Same exact status"),
        
        # NOT_RELEVANT override - special case
        ("qualified", "not_relevant", True, "NOT_RELEVANT overrides even qualified"),
        ("interested", "not_relevant", True, "NOT_RELEVANT overrides interested"),
    ]
    
    passed = 0
    failed = 0
    
    for current, suggested, expected, description in test_cases:
        should_change, reason = service.should_change_status(current, suggested, test_tenant)
        
        if should_change == expected:
            icon = "✅" if expected else "⭕"
            print(f"{icon} {description:<55} → {should_change}")
            print(f"   Reason: {reason}")
            passed += 1
        else:
            print(f"❌ {description:<55} → {should_change} (expected {expected})")
            print(f"   Reason: {reason}")
            failed += 1
        print()
    
    print(f"Results: {passed} passed, {failed} failed")
    print()
    
    return failed == 0


def test_real_world_scenarios():
    """Test realistic scenarios that would happen in production"""
    print("=" * 80)
    print("TEST: Real World Scenarios")
    print("=" * 80)
    print()
    
    from server.services.lead_auto_status_service import get_auto_status_service
    
    service = get_auto_status_service()
    test_tenant = 999
    
    scenarios = [
        {
            "name": "First call - no answer",
            "current": "new",
            "suggested": "no_answer",
            "should_change": True,
            "description": "New lead, first call didn't answer → change to no_answer"
        },
        {
            "name": "Second call - still no answer",
            "current": "no_answer",
            "suggested": "no_answer_2",
            "should_change": True,
            "description": "Lead already at no_answer, suggest progression → change to no_answer_2"
        },
        {
            "name": "Third call - still no answer",
            "current": "no_answer_2",
            "suggested": "no_answer_2",
            "should_change": False,
            "description": "Lead already at no_answer_2, suggest same → DON'T change (already correct!)"
        },
        {
            "name": "Lead answered - now interested",
            "current": "no_answer_2",
            "suggested": "interested",
            "should_change": True,
            "description": "Lead finally answered and is interested → upgrade to interested"
        },
        {
            "name": "Follow-up call - still interested",
            "current": "interested",
            "suggested": "interested",
            "should_change": False,
            "description": "Lead still interested after follow-up → DON'T change (already correct!)"
        },
        {
            "name": "Appointment set!",
            "current": "interested",
            "suggested": "qualified",
            "should_change": True,
            "description": "Lead was interested, now appointment set → upgrade to qualified"
        },
        {
            "name": "Lead says not interested",
            "current": "qualified",
            "suggested": "not_relevant",
            "should_change": True,
            "description": "Lead was qualified but now says not interested → change to not_relevant (override)"
        },
        {
            "name": "Already contacted, AI suggests contacted",
            "current": "contacted",
            "suggested": "contacted",
            "should_change": False,
            "description": "Lead already contacted, AI suggests same → DON'T change (already correct!)"
        },
    ]
    
    passed = 0
    failed = 0
    
    for idx, scenario in enumerate(scenarios, 1):
        print(f"Scenario {idx}: {scenario['name']}")
        print(f"  Current: {scenario['current']}")
        print(f"  Suggested: {scenario['suggested']}")
        print(f"  Description: {scenario['description']}")
        
        should_change, reason = service.should_change_status(
            scenario['current'], 
            scenario['suggested'], 
            test_tenant
        )
        
        if should_change == scenario['should_change']:
            icon = "✅" if should_change else "⏭️ "
            print(f"  {icon} CORRECT: should_change={should_change}")
            print(f"     Reason: {reason}")
            passed += 1
        else:
            print(f"  ❌ ERROR: should_change={should_change} (expected {scenario['should_change']})")
            print(f"     Reason: {reason}")
            failed += 1
        
        print()
    
    print(f"Results: {passed}/{len(scenarios)} scenarios passed")
    print()
    
    return failed == 0


def main():
    print()
    print("╔" + "=" * 78 + "╗")
    print("║" + "  Smart Status Equivalence - Test Suite".center(78) + "║")
    print("╚" + "=" * 78 + "╝")
    print()
    
    tests = [
        ("Status Family Classification", test_status_family_classification),
        ("Status Progression Scores", test_status_progression_scores),
        ("No-Answer Progression Detection", test_no_answer_progression_detection),
        ("Should Change Status Decisions", test_should_change_status_decisions),
        ("Real World Scenarios", test_real_world_scenarios),
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
        print()
        print("🎉 The smart status equivalence logic is working correctly!")
        print()
        print("Key features verified:")
        print("  ✅ Status family classification (NO_ANSWER, INTERESTED, etc.)")
        print("  ✅ Status progression scoring")
        print("  ✅ No-answer progression detection")
        print("  ✅ Smart status change decisions")
        print("  ✅ Prevention of unnecessary changes")
        print("  ✅ Prevention of downgrades")
        print("  ✅ Real-world scenario handling")
        return 0
    else:
        print(f"❌ {total - passed_count} TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
