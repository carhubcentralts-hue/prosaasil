#!/usr/bin/env python3
"""
Test for auto-save customer name from conversation
Tests the new feature that detects and saves customer names during calls
"""

def test_name_detection_from_conversation():
    """Test that customer names are detected from conversation"""
    print("\n" + "="*80)
    print("🔍 TEST: Name Detection from Conversation")
    print("="*80)
    
    from server.services.realtime_prompt_builder import detect_name_from_conversation
    
    # Test Case 1: "אני [name]" pattern
    print(f"\n📋 Test 1: 'אני [name]' pattern")
    text1 = "שלום, אני דני"
    result1 = detect_name_from_conversation(text1)
    print(f"   Input: '{text1}'")
    print(f"   Detected: '{result1}'")
    assert result1 == "דני", f"Expected 'דני', got '{result1}'"
    print(f"   ✅ PASSED")
    
    # Test Case 2: "קוראים לי [name]" pattern
    print(f"\n📋 Test 2: 'קוראים לי [name]' pattern")
    text2 = "קוראים לי רונית"
    result2 = detect_name_from_conversation(text2)
    print(f"   Input: '{text2}'")
    print(f"   Detected: '{result2}'")
    assert result2 == "רונית", f"Expected 'רונית', got '{result2}'"
    print(f"   ✅ PASSED")
    
    # Test Case 3: "השם שלי [name]" pattern
    print(f"\n📋 Test 3: 'השם שלי [name]' pattern")
    text3 = "כן, השם שלי משה"
    result3 = detect_name_from_conversation(text3)
    print(f"   Input: '{text3}'")
    print(f"   Detected: '{result3}'")
    assert result3 == "משה", f"Expected 'משה', got '{result3}'"
    print(f"   ✅ PASSED")
    
    # Test Case 4: "שמי [name]" pattern
    print(f"\n📋 Test 4: 'שמי [name]' pattern")
    text4 = "שלום, שמי אבי"
    result4 = detect_name_from_conversation(text4)
    print(f"   Input: '{text4}'")
    print(f"   Detected: '{result4}'")
    assert result4 == "אבי", f"Expected 'אבי', got '{result4}'"
    print(f"   ✅ PASSED")
    
    # Test Case 5: No name (should return None)
    print(f"\n📋 Test 5: No name in text")
    text5 = "מה שלומך? אני רוצה לקבל מידע"
    result5 = detect_name_from_conversation(text5)
    print(f"   Input: '{text5}'")
    print(f"   Detected: '{result5}'")
    assert result5 is None, f"Expected None, got '{result5}'"
    print(f"   ✅ PASSED")
    
    # Test Case 6: Common word that's not a name (should filter out)
    print(f"\n📋 Test 6: Filter out common words")
    text6 = "אני כן רוצה"
    result6 = detect_name_from_conversation(text6)
    print(f"   Input: '{text6}'")
    print(f"   Detected: '{result6}'")
    assert result6 is None, f"Expected None (filtered 'כן'), got '{result6}'"
    print(f"   ✅ PASSED")
    
    # Test Case 7: Multiple names in one text (should get first)
    print(f"\n📋 Test 7: Multiple names - take first")
    text7 = "אני דני וקוראים לי גם דניאל"
    result7 = detect_name_from_conversation(text7)
    print(f"   Input: '{text7}'")
    print(f"   Detected: '{result7}'")
    assert result7 == "דני", f"Expected 'דני' (first match), got '{result7}'"
    print(f"   ✅ PASSED")
    
    print("\n" + "="*80)
    print("✅ ALL TESTS PASSED: Name detection works correctly")
    print("="*80)
    print("\n💡 How it works:")
    print("   1. Customer says their name during call")
    print("   2. System detects name using patterns")
    print("   3. Lead record is updated automatically")
    print("   4. Works for both inbound and outbound calls")

if __name__ == "__main__":
    test_name_detection_from_conversation()
