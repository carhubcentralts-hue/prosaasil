#!/usr/bin/env python3
"""
Test script for conversation ending logic
Tests different scenarios to ensure smart disconnection works correctly
"""

def test_polite_closing_detection():
    """Test that polite closing phrases are detected correctly"""
    
    # Simulate the STRICT _check_polite_closing logic (only ביי/להתראות!)
    def check_polite_closing(text):
        text_lower = text.lower().strip()
        
        # Ignore list
        ignore_phrases = ["היי כבי", "היי ביי", "הי כבי", "הי ביי"]
        for ignore in ignore_phrases:
            if ignore in text_lower:
                return False
        
        # Filter greetings
        greeting_words = ["היי", "הי", "שלום וברכה", "בוקר טוב", "צהריים טובים", "ערב טוב"]
        for greeting in greeting_words:
            if greeting in text_lower and "ביי" not in text_lower and "להתראות" not in text_lower:
                return False
        
        # ✅ ONLY explicit goodbye words trigger disconnection!
        explicit_goodbye_words = ["ביי", "להתראות", "bye", "goodbye"]
        
        has_explicit_goodbye = any(word in text_lower for word in explicit_goodbye_words)
        
        return has_explicit_goodbye
    
    test_cases = [
        # ✅ SHOULD trigger - has explicit ביי/להתראות
        ("תודה ביי", True, "Thank you bye - HAS explicit goodbye"),
        ("תודה רבה ביי", True, "Thank you very much bye - HAS explicit goodbye"),
        ("תודה להתראות", True, "Thank you goodbye - HAS explicit goodbye"),
        ("להתראות", True, "Goodbye - explicit"),
        ("ביי", True, "Bye - explicit"),
        ("מצוין, קיבלתי. בעל מקצוע יחזור אליך בהקדם. תודה ולהתראות.", True, "Full closing with להתראות"),
        ("נציג יחזור אליך ביי", True, "Callback promise WITH bye"),
        ("יום נפלא ביי", True, "Have a great day WITH bye"),
        ("bye", True, "English bye"),
        ("goodbye", True, "English goodbye"),
        
        # ❌ Should NOT trigger - NO explicit ביי/להתראות
        ("תודה יחזרו אליך", False, "Callback promise WITHOUT bye - should NOT disconnect"),
        ("בעל מקצוע יחזור אליך", False, "Professional will call back WITHOUT bye - should NOT disconnect"),
        ("נציג יחזור אליך", False, "Rep will call back WITHOUT bye - should NOT disconnect"),
        ("תודה שהתקשרת", False, "Thank you for calling WITHOUT bye - should NOT disconnect"),
        ("יום נפלא", False, "Have a great day WITHOUT bye - should NOT disconnect"),
        ("תודה רבה על הזמן", False, "Thank you for your time WITHOUT bye - should NOT disconnect"),
        ("תודה", False, "Just thank you - should NOT disconnect"),
        ("שלום", False, "Hello - greeting only"),
        ("היי", False, "Hi - greeting only"),
        
        # Edge cases - ignore patterns
        ("היי ביי", False, "Ignore pattern - sounds like bye but isn't"),
        ("היי כבי", False, "Ignore pattern - sounds like bye but isn't"),
    ]
    
    print("🧪 Testing polite closing detection...\n")
    
    passed = 0
    failed = 0
    
    for text, expected, description in test_cases:
        result = check_polite_closing(text)
        status = "✅ PASS" if result == expected else "❌ FAIL"
        
        if result == expected:
            passed += 1
        else:
            failed += 1
        
        print(f"{status}: '{text}'")
        print(f"       Description: {description}")
        print(f"       Expected: {expected}, Got: {result}")
        print()
    
    print(f"\n📊 Results: {passed} passed, {failed} failed out of {len(test_cases)} tests")
    return failed == 0


def test_smart_ending_logic():
    """Test that smart ending logic works correctly for different scenarios"""
    
    print("\n🧪 Testing smart ending scenarios...\n")
    
    scenarios = [
        {
            "name": "User said goodbye + AI polite closing",
            "user_said_goodbye": True,
            "user_messages": 3,
            "ai_polite_closing": True,
            "expected_hangup": True,
            "reason": "User explicitly ended conversation"
        },
        {
            "name": "AI polite closing after 2+ exchanges (smart ending)",
            "user_said_goodbye": False,
            "user_messages": 3,
            "ai_polite_closing": True,
            "expected_hangup": True,
            "reason": "AI smart ending after meaningful conversation"
        },
        {
            "name": "AI polite closing but only 1 user message",
            "user_said_goodbye": False,
            "user_messages": 1,
            "ai_polite_closing": True,
            "expected_hangup": False,
            "reason": "Conversation too short for smart ending"
        },
        {
            "name": "No AI polite closing, user didn't say goodbye",
            "user_said_goodbye": False,
            "user_messages": 5,
            "ai_polite_closing": False,
            "expected_hangup": False,
            "reason": "No ending signal detected"
        },
        {
            "name": "AI polite closing after lead captured",
            "user_said_goodbye": False,
            "user_messages": 4,
            "ai_polite_closing": True,
            "lead_captured": True,
            "expected_hangup": True,
            "reason": "Lead captured and AI ended politely"
        },
    ]
    
    passed = 0
    failed = 0
    
    for scenario in scenarios:
        # Simulate the smart ending logic
        user_said_goodbye = scenario.get("user_said_goodbye", False)
        user_messages = scenario.get("user_messages", 0)
        ai_polite_closing = scenario.get("ai_polite_closing", False)
        has_meaningful_conversation = user_messages >= 2
        
        # Apply the logic
        should_hangup = False
        if user_said_goodbye or (ai_polite_closing and has_meaningful_conversation):
            should_hangup = True
        
        expected = scenario["expected_hangup"]
        status = "✅ PASS" if should_hangup == expected else "❌ FAIL"
        
        if should_hangup == expected:
            passed += 1
        else:
            failed += 1
        
        print(f"{status}: {scenario['name']}")
        print(f"       user_said_goodbye={user_said_goodbye}, user_messages={user_messages}")
        print(f"       ai_polite_closing={ai_polite_closing}")
        print(f"       Expected hangup: {expected}, Got: {should_hangup}")
        print(f"       Reason: {scenario['reason']}")
        print()
    
    print(f"\n📊 Results: {passed} passed, {failed} failed out of {len(scenarios)} tests")
    return failed == 0


if __name__ == "__main__":
    print("=" * 70)
    print("CONVERSATION ENDING LOGIC TESTS")
    print("=" * 70)
    
    test1_passed = test_polite_closing_detection()
    test2_passed = test_smart_ending_logic()
    
    print("\n" + "=" * 70)
    if test1_passed and test2_passed:
        print("✅ ALL TESTS PASSED!")
    else:
        print("❌ SOME TESTS FAILED")
    print("=" * 70)
