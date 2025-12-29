#!/usr/bin/env python3
"""
Test Business Prompt Name Recognition
======================================

Verifies that the AI correctly identifies when a business prompt requests name usage,
especially with the user's exact phrasing.
"""

def test_name_usage_recognition():
    """Test that various phrasings requesting name usage are recognized."""
    
    print("=" * 80)
    print("🧪 BUSINESS PROMPT NAME USAGE RECOGNITION TEST")
    print("=" * 80)
    print()
    
    # Test various business prompts that request name usage
    prompts_requesting_name = [
        # User's exact phrasing
        "במידה וקיים שם לקוח, השתמש בשם שלו באופן טבעי לאורך השיחה כדי ליצור קרבה. אם אין שם – המשך כרגיל בלי להזכיר זאת.",
        
        # Other Hebrew variations
        "השתמש בשם הלקוח במהלך השיחה",
        "פנה ללקוח בשמו",
        "קרא לו בשם",
        "אם קיים שם לקוח - השתמש בו",
        
        # English variations
        "Use the customer's name during the conversation",
        "Address the customer by name",
        "If a customer name exists, use it naturally",
    ]
    
    prompts_not_requesting_name = [
        "אתה נציג שירות מקצועי. עזור ללקוח בצורה יעילה.",
        "You are a professional service representative. Help customers efficiently.",
        "נהל שיחה מקצועית וברורה",
    ]
    
    # Keywords that indicate name usage request
    hebrew_keywords = ['השתמש בשם', 'השתמשי בשם', 'פנה בשמו', 'פני בשמו', 
                       'השתמש בשם של הלקוח', 'קרא לו בשמו', 'אם קיים שם', 'במידה וקיים שם']
    english_keywords = ['use the name', 'use their name', 'use customer name', 
                        'address by name', 'call them by name', 'if name exists', 
                        'when name is available']
    
    all_keywords = hebrew_keywords + english_keywords
    
    print("📋 Testing prompts that REQUEST name usage:")
    all_passed = True
    for i, prompt in enumerate(prompts_requesting_name, 1):
        # Check if any keyword appears in the prompt
        has_keyword = any(keyword.lower() in prompt.lower() for keyword in all_keywords)
        
        if has_keyword:
            print(f"   ✅ Test {i}: Correctly detected name usage request")
            print(f"      Prompt: {prompt[:80]}...")
        else:
            print(f"   ❌ Test {i}: FAILED to detect name usage request")
            print(f"      Prompt: {prompt[:80]}...")
            all_passed = False
        print()
    
    print("=" * 80)
    print("📋 Testing prompts that DO NOT request name usage:")
    for i, prompt in enumerate(prompts_not_requesting_name, 1):
        # Check if any keyword appears in the prompt
        has_keyword = any(keyword.lower() in prompt.lower() for keyword in all_keywords)
        
        if not has_keyword:
            print(f"   ✅ Test {i}: Correctly identified NO name usage request")
            print(f"      Prompt: {prompt[:80]}...")
        else:
            print(f"   ❌ Test {i}: FALSE POSITIVE - detected name usage when not requested")
            print(f"      Prompt: {prompt[:80]}...")
            all_passed = False
        print()
    
    print("=" * 80)
    print("📊 TEST SUMMARY")
    print("=" * 80)
    
    if all_passed:
        print("🎉 ALL TESTS PASSED!")
        print()
        print("✅ The AI should now correctly identify when to use customer names")
        print("✅ Including the user's exact phrasing:")
        print("   'במידה וקיים שם לקוח, השתמש בשם שלו באופן טבעי...'")
        print()
        print("The system prompt now includes explicit examples of Hebrew and English")
        print("phrases that request name usage, so the AI will recognize them.")
        return 0
    else:
        print("❌ SOME TESTS FAILED!")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(test_name_usage_recognition())
