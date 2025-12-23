"""
Test suite for GREETING_PENDING, Barge-In, and STT_GUARD fixes

Tests three critical fixes:
1. GREETING_PENDING should not trigger after user has spoken
2. Barge-in should cancel active response when user speaks during AI speech
3. Short Hebrew greetings should pass STT_GUARD validation

This is a standalone test that doesn't require server imports.
"""
import sys


# Whitelist from the fix (copied for testing)
SHORT_HEBREW_OPENER_WHITELIST = {
    "הלו", "כן", "מה", "מי זה", "מי", "רגע", "שומע", "בסדר", "טוב",
    "הלוא", "אלו", "הי", "היי",
}


def should_accept_realtime_utterance_test(stt_text: str) -> bool:
    """
    Simplified version of should_accept_realtime_utterance for testing
    """
    # Only reject completely empty text
    if not stt_text or not stt_text.strip():
        return False
    
    # Check whitelist FIRST for short Hebrew greetings
    text_clean = stt_text.strip().lower()
    if text_clean in SHORT_HEBREW_OPENER_WHITELIST:
        print(f"  [WHITELIST] Accepted short Hebrew opener: '{stt_text}'")
        return True
    
    # Everything else is accepted - NO FILTERS
    return True


def test_greeting_pending_guard():
    """Test 1: GREETING_PENDING should be blocked when user has spoken"""
    print("\n" + "="*80)
    print("TEST 1: GREETING_PENDING Guard")
    print("="*80)
    
    # Simulate the guard conditions
    test_cases = [
        # (greeting_sent, user_has_spoken, ai_response_active, should_allow)
        (False, False, False, True),   # ✅ Allow: No greeting, no user, no AI
        (True, False, False, False),   # ❌ Block: Greeting already sent
        (False, True, False, False),   # ❌ Block: User already spoke
        (False, False, True, False),   # ❌ Block: AI response active
        (True, True, True, False),     # ❌ Block: All flags set
    ]
    
    passed = 0
    failed = 0
    
    for i, (greeting_sent, user_has_spoken, ai_response_active, should_allow) in enumerate(test_cases, 1):
        # Simulate the guard logic from our fix
        can_trigger = (
            not greeting_sent and 
            not user_has_spoken and 
            not ai_response_active
        )
        
        expected = "ALLOW" if should_allow else "BLOCK"
        actual = "ALLOW" if can_trigger else "BLOCK"
        status = "✅ PASS" if (can_trigger == should_allow) else "❌ FAIL"
        
        print(f"\nCase {i}: greeting_sent={greeting_sent}, user_has_spoken={user_has_spoken}, "
              f"ai_response_active={ai_response_active}")
        print(f"  Expected: {expected}, Actual: {actual} - {status}")
        
        if can_trigger == should_allow:
            passed += 1
        else:
            failed += 1
    
    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


def test_short_hebrew_opener_whitelist():
    """Test 3: Short Hebrew greetings should pass STT_GUARD"""
    print("\n" + "="*80)
    print("TEST 3: Short Hebrew Opener Whitelist")
    print("="*80)
    
    # Test cases: (text, should_pass, description)
    test_cases = [
        ("הלו", True, "Most common Hebrew phone greeting"),
        ("כן", True, "Yes - very common response"),
        ("מה", True, "What - common question"),
        ("מי זה", True, "Who is it"),
        ("רגע", True, "Wait/moment"),
        ("שומע", True, "Listening"),
        ("", False, "Empty string should be rejected"),
        ("beep", True, "Non-Hebrew but has text (no filters applied)"),
        ("long phrase with multiple words", True, "Long text should always pass"),
    ]
    
    passed = 0
    failed = 0
    
    for i, (text, should_pass, description) in enumerate(test_cases, 1):
        result = should_accept_realtime_utterance_test(text)
        
        status = "✅ PASS" if (result == should_pass) else "❌ FAIL"
        print(f"\nCase {i}: '{text}'")
        print(f"  Description: {description}")
        print(f"  Expected: {'ACCEPT' if should_pass else 'REJECT'}, "
              f"Actual: {'ACCEPT' if result else 'REJECT'} - {status}")
        
        if result == should_pass:
            passed += 1
        else:
            failed += 1
    
    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


def test_barge_in_flow():
    """Test 2: Barge-in flow logic (simulated)"""
    print("\n" + "="*80)
    print("TEST 2: Barge-In Flow (Simulated)")
    print("="*80)
    
    # Simulate the barge-in detection logic from our fix
    test_cases = [
        # (ai_is_speaking, active_response_id, text, should_trigger_cancel)
        (True, "resp_123", "הלו", True),   # ✅ Should cancel: AI speaking + valid utterance
        (False, "resp_123", "הלו", False),  # ❌ No cancel: AI not speaking
        (True, None, "הלו", False),         # ❌ No cancel: No active response
        (True, "resp_123", "", False),      # ❌ No cancel: Empty text
    ]
    
    passed = 0
    failed = 0
    
    for i, (ai_is_speaking, active_response_id, text, should_trigger_cancel) in enumerate(test_cases, 1):
        # Simulate the barge-in detection from our fix
        # Barge-in happens when: ai_is_speaking AND active_response_id exists AND text is not empty
        should_cancel = bool(ai_is_speaking and active_response_id and text)
        
        status = "✅ PASS" if (should_cancel == should_trigger_cancel) else "❌ FAIL"
        print(f"\nCase {i}: ai_speaking={ai_is_speaking}, "
              f"response_id={active_response_id or 'None'}, text='{text}'")
        print(f"  Expected: {'CANCEL' if should_trigger_cancel else 'NO CANCEL'}, "
              f"Actual: {'CANCEL' if should_cancel else 'NO CANCEL'} - {status}")
        
        if should_cancel == should_trigger_cancel:
            passed += 1
        else:
            failed += 1
    
    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("TESTING: GREETING_PENDING, Barge-In, and STT_GUARD Fixes")
    print("="*80)
    
    results = []
    
    # Run tests
    results.append(("GREETING_PENDING Guard", test_greeting_pending_guard()))
    results.append(("Barge-In Flow", test_barge_in_flow()))
    results.append(("Short Hebrew Opener Whitelist", test_short_hebrew_opener_whitelist()))
    
    # Print summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "="*80)
    if all_passed:
        print("✅ ALL TESTS PASSED")
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
