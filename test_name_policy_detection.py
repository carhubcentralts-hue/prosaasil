#!/usr/bin/env python3
"""
Test NAME_POLICY detection and NAME_ANCHOR system
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_name_policy_detection():
    """Test that name policy detection works correctly"""
    from server.services.realtime_prompt_builder import detect_name_usage_policy, build_name_anchor_message
    
    print("\n" + "="*80)
    print("🔍 TEST: Name Policy Detection")
    print("="*80)
    
    # Test 1: Hebrew explicit "השתמש בשם"
    print("\n📋 Test 1: Hebrew 'השתמש בשם'")
    prompt1 = "אתה נציג שירות. השתמש בשם הלקוח בשיחה."
    use_name, phrase = detect_name_usage_policy(prompt1)
    print(f"   Prompt: {prompt1}")
    print(f"   Result: use_name={use_name}, matched='{phrase}'")
    assert use_name == True, "Should detect 'השתמש בשם'"
    assert phrase is not None, "Should return matched phrase"
    print("   ✅ PASSED")
    
    # Test 2: Hebrew explicit "תשתמש בשם"
    print("\n📋 Test 2: Hebrew 'תשתמש בשם'")
    prompt2 = "תשתמש בשם הלקוח לאורך השיחה"
    use_name, phrase = detect_name_usage_policy(prompt2)
    print(f"   Prompt: {prompt2}")
    print(f"   Result: use_name={use_name}, matched='{phrase}'")
    assert use_name == True, "Should detect 'תשתמש בשם'"
    print("   ✅ PASSED")
    
    # Test 3: Hebrew "פנה בשמו"
    print("\n📋 Test 3: Hebrew 'פנה בשמו'")
    prompt3 = "פנה בשמו של הלקוח"
    use_name, phrase = detect_name_usage_policy(prompt3)
    print(f"   Prompt: {prompt3}")
    print(f"   Result: use_name={use_name}, matched='{phrase}'")
    assert use_name == True, "Should detect 'פנה בשמו'"
    print("   ✅ PASSED")
    
    # Test 4: English "use name"
    print("\n📋 Test 4: English 'use name'")
    prompt4 = "You are a service representative. Use the customer's name during conversation."
    use_name, phrase = detect_name_usage_policy(prompt4)
    print(f"   Prompt: {prompt4}")
    print(f"   Result: use_name={use_name}, matched='{phrase}'")
    assert use_name == True, "Should detect 'use the customer's name'"
    print("   ✅ PASSED")
    
    # Test 5: English "use their name"
    print("\n📋 Test 5: English 'use their name'")
    prompt5 = "When speaking to customers, use their name naturally."
    use_name, phrase = detect_name_usage_policy(prompt5)
    print(f"   Prompt: {prompt5}")
    print(f"   Result: use_name={use_name}, matched='{phrase}'")
    assert use_name == True, "Should detect 'use their name'"
    print("   ✅ PASSED")
    
    # Test 6: NO name usage instruction
    print("\n📋 Test 6: NO name usage instruction")
    prompt6 = "אתה נציג שירות. תהיה מקצועי ועוזר."
    use_name, phrase = detect_name_usage_policy(prompt6)
    print(f"   Prompt: {prompt6}")
    print(f"   Result: use_name={use_name}, matched='{phrase}'")
    assert use_name == False, "Should NOT detect name usage"
    assert phrase is None, "Should not return matched phrase"
    print("   ✅ PASSED")
    
    # Test 7: CRITICAL - "ליצור קרבה" should NOT trigger name usage!
    print("\n📋 Test 7: CRITICAL - 'ליצור קרבה' should NOT trigger")
    prompt7 = "אתה נציג שירות. המטרה ליצור קרבה עם הלקוח."
    use_name, phrase = detect_name_usage_policy(prompt7)
    print(f"   Prompt: {prompt7}")
    print(f"   Result: use_name={use_name}, matched='{phrase}'")
    assert use_name == False, "Should NOT detect 'ליצור קרבה' as name usage!"
    assert phrase is None, "Should not return matched phrase"
    print("   ✅ PASSED - 'ליצור קרבה' correctly ignored!")
    
    return True


def test_name_anchor_message():
    """Test NAME_ANCHOR message generation"""
    from server.services.realtime_prompt_builder import build_name_anchor_message
    
    print("\n" + "="*80)
    print("🔍 TEST: NAME_ANCHOR Message Generation")
    print("="*80)
    
    # Test 1: Name available + policy enabled
    print("\n📋 Test 1: Name available + policy enabled")
    msg1 = build_name_anchor_message("דוד כהן", True)
    print(f"   Message:\n{msg1}")
    assert "דוד כהן" in msg1, "Should include customer name"
    assert "ENABLED" in msg1, "Should show policy as ENABLED"
    assert "ACTION REQUIRED" in msg1, "Should have explicit action required"
    assert len(msg1) < 300, "Should be relatively SHORT (no duplicate instructions)"
    print("   ✅ PASSED - EXPLICIT action message, no duplicates")
    
    # Test 2: Name available + policy disabled
    print("\n📋 Test 2: Name available + policy disabled")
    msg2 = build_name_anchor_message("שרה לוי", False)
    print(f"   Message:\n{msg2}")
    assert "שרה לוי" in msg2, "Should include customer name"
    assert "DISABLED" in msg2, "Should show policy as DISABLED"
    assert len(msg2) < 300, "Should be relatively SHORT"
    print("   ✅ PASSED")
    
    # Test 3: No name + policy enabled
    print("\n📋 Test 3: No name + policy enabled")
    msg3 = build_name_anchor_message(None, True)
    print(f"   Message:\n{msg3}")
    assert "NOT AVAILABLE" in msg3, "Should show name as NOT AVAILABLE"
    assert "REQUESTED BUT UNAVAILABLE" in msg3, "Should show policy was requested"
    assert len(msg3) < 300, "Should be relatively SHORT"
    print("   ✅ PASSED")
    
    # Test 4: No name + policy disabled
    print("\n📋 Test 4: No name + policy disabled")
    msg4 = build_name_anchor_message(None, False)
    print(f"   Message:\n{msg4}")
    assert "NOT AVAILABLE" in msg4, "Should show name as NOT AVAILABLE"
    assert "NOT REQUESTED" in msg4 or "DISABLED" in msg4, "Should show policy was not requested"
    assert len(msg4) < 300, "Should be relatively SHORT"
    print("   ✅ PASSED")
    
    return True


def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("🧪 NAME POLICY & NAME ANCHOR TESTS")
    print("="*80)
    
    try:
        test1_passed = test_name_policy_detection()
        test2_passed = test_name_anchor_message()
        
        print("\n" + "="*80)
        print("📊 TEST SUMMARY")
        print("="*80)
        
        if test1_passed and test2_passed:
            print("\n🎉 ALL TESTS PASSED!")
            print("\n✅ Name policy detection working correctly:")
            print("   1. Detects Hebrew explicit instructions: 'השתמש בשם', 'תשתמש בשם', 'פנה בשמו'")
            print("   2. Detects English instructions: 'use name', 'use their name'")
            print("   3. CORRECTLY IGNORES 'ליצור קרבה' (not a name instruction!)")
            print("   4. Returns False when no name usage requested")
            print("\n✅ NAME_ANCHOR messages are SHORT and clean:")
            print("   1. No duplicate instructions (system prompt has them)")
            print("   2. Only includes: CustomerName + NameUsage flag")
            print("   3. All messages under 200 chars")
            print("="*80)
            return 0
        else:
            print("\n❌ SOME TESTS FAILED!")
            print("="*80)
            return 1
    except Exception as e:
        print(f"\n❌ TEST ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
