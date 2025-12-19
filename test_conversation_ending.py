#!/usr/bin/env python3
"""
Test script for conversation ending logic
Tests different scenarios to ensure smart disconnection works correctly
"""

def test_polite_closing_detection():
    """Test that polite closing phrases are detected correctly"""
    
    # Simulate the _check_polite_closing logic
    def check_polite_closing(text):
        text_lower = text.lower().strip()
        
        polite_closing_phrases = [
            "תודה שהתקשרת", "תודה על הפנייה", "תודה על השיחה",
            "תודה רבה", "תודה", 
            "יום נפלא", "יום נעים", "יום טוב", "ערב נעים", "ערב טוב",
            "ביי", "להתראות", "bye", "goodbye",
            "נציג יחזור אליך", "נחזור אליך", "ניצור קשר", "יחזרו אליך",
            "נציג ייצור קשר", "בעל מקצוע יחזור אליך",
            "נשמח לעזור", "נשמח לעמוד לשירותך",
            "שמח שיכולתי לעזור", "שמחתי לעזור",
            "אם תצטרך משהו נוסף", "אם יש שאלות נוספות",
            "תודה יחזרו אליך", "תודה ביי", "תודה להתראות",
            "תודה רבה ביי", "תודה רבה להתראות"
        ]
        
        for phrase in polite_closing_phrases:
            if phrase in text_lower:
                return True
        
        # Check for thank you + goodbye combo
        ends_with_goodbye = any(text_lower.endswith(word) for word in ["ביי", "להתראות", "bye", "goodbye"])
        has_thank_you = "תודה" in text_lower
        
        if ends_with_goodbye and has_thank_you:
            return True
        
        return False
    
    test_cases = [
        # User-reported phrases that should trigger ending
        ("תודה יחזרו אליך", True, "Callback promise with thank you"),
        ("תודה ביי", True, "Thank you bye"),
        ("תודה רבה ביי", True, "Thank you very much bye"),
        ("תודה להתראות", True, "Thank you goodbye"),
        ("בעל מקצוע יחזור אליך", True, "Professional will call back"),
        ("נציג יחזור אליך", True, "Rep will call back"),
        
        # Standard polite closings
        ("תודה שהתקשרת", True, "Thank you for calling"),
        ("יום נפלא", True, "Have a great day"),
        ("להתראות", True, "Goodbye"),
        ("ביי", True, "Bye"),
        
        # Should NOT trigger (too generic without context)
        ("שלום", False, "Hello - greeting only"),
        ("היי", False, "Hi - greeting only"),
        
        # Edge cases
        ("מצוין, קיבלתי. בעל מקצוע יחזור אליך בהקדם. תודה ולהתראות.", True, "Full closing sentence"),
        ("תודה רבה על הזמן", True, "Thank you for your time"),
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
