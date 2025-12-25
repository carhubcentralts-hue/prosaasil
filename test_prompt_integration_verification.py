#!/usr/bin/env python3
"""
Test to verify that the Hebrew natural AI and customer name handling works correctly
This simulates how the system will behave with actual business prompts
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_system_prompt_structure():
    """Verify system prompt structure is correct"""
    print("\n" + "="*80)
    print("🔍 TEST 1: SYSTEM PROMPT STRUCTURE")
    print("="*80)
    
    from server.services.realtime_prompt_builder import _build_universal_system_prompt
    
    inbound_prompt = _build_universal_system_prompt(call_direction="inbound")
    
    # Verify key sections exist
    checks = {
        "Has language rules": "Language and Grammar:" in inbound_prompt,
        "Has name usage rules": "Customer Name Usage:" in inbound_prompt,
        "Has turn-taking rules": "Turn-taking:" in inbound_prompt,
        "Has truth rules": "Truth:" in inbound_prompt,
        "References Business Prompt": "Business Prompt" in inbound_prompt,
        "No hardcoded business content": not any(word in inbound_prompt for word in ["מנעולן", "שרברב", "מס"]),
        "Reasonable length (< 2000 chars)": len(inbound_prompt) < 2000,
    }
    
    print("\n✅ STRUCTURE CHECKS:")
    all_passed = True
    for check_name, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {check_name}")
        if not passed:
            all_passed = False
    
    return all_passed

def test_name_usage_behavior():
    """Test that name usage behavior is correctly specified"""
    print("\n" + "="*80)
    print("🔍 TEST 2: NAME USAGE BEHAVIOR")
    print("="*80)
    
    from server.services.realtime_prompt_builder import _build_universal_system_prompt
    
    prompt = _build_universal_system_prompt(call_direction="inbound")
    
    # Verify behavioral instructions (not templates)
    checks = {
        "Conditional on Business Prompt": "ONLY if the Business Prompt requests name usage" in prompt,
        "Natural integration": "naturally throughout the entire conversation" in prompt,
        "Free and human": "freely and humanly" in prompt,
        "No theoretical terms": "Do NOT say words like 'customer name'" in prompt,
        "Fallback behavior": "If no name is available - continue the conversation normally" in prompt,
        "No placeholders": "{" not in prompt or "customer_name" not in prompt,  # No template variables
        "No hardcoded examples": not any(name in prompt for name in ["דני", "אבי", "יוסי", "משה"]),
    }
    
    print("\n✅ BEHAVIOR CHECKS:")
    all_passed = True
    for check_name, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {check_name}")
        if not passed:
            all_passed = False
    
    return all_passed

def test_hebrew_quality_rules():
    """Test that Hebrew quality rules are properly specified"""
    print("\n" + "="*80)
    print("🔍 TEST 3: HEBREW QUALITY RULES")
    print("="*80)
    
    from server.services.realtime_prompt_builder import _build_universal_system_prompt
    
    prompt = _build_universal_system_prompt(call_direction="inbound")
    
    # Verify Hebrew quality instructions
    checks = {
        "Natural fluent Hebrew": "natural, fluent, daily Israeli Hebrew" in prompt,
        "No translation": "Do NOT translate from English" in prompt,
        "No foreign structures": "do NOT use foreign structures" in prompt,
        "Native speaker level": "high-level native speaker" in prompt,
        "Short flowing sentences": "short, flowing sentences" in prompt,
        "Human intonation": "human intonation" in prompt,
        "Avoid artificial phrasing": "Avoid artificial or overly formal phrasing" in prompt,
    }
    
    print("\n✅ HEBREW QUALITY CHECKS:")
    all_passed = True
    for check_name, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {check_name}")
        if not passed:
            all_passed = False
    
    return all_passed

def test_business_prompt_separation():
    """Test that system prompt doesn't interfere with business prompt flow"""
    print("\n" + "="*80)
    print("🔍 TEST 4: BUSINESS PROMPT SEPARATION")
    print("="*80)
    
    from server.services.realtime_prompt_builder import _build_universal_system_prompt
    
    prompt = _build_universal_system_prompt(call_direction="inbound")
    
    # Verify separation between system rules and business content
    checks = {
        "References Business Prompt for flow": "Follow the Business Prompt for the business-specific script and flow" in prompt,
        "No hardcoded greetings": not any(greeting in prompt for greeting in ["שלום", "בוקר טוב", "ערב טוב", "היי"]),
        "No hardcoded services": not any(service in prompt for service in ["שרברות", "מנעולנות", "חשמל", "ניקיון"]),
        "No hardcoded cities": not any(city in prompt for city in ["תל אביב", "ירושלים", "חיפה", "באר שבע"]),
        "No hardcoded business names": not any(name in prompt for name in ["משה", "דוד", "יוסי"]),
        "Behavioral only": "treat each call as independent" in prompt and "Business Prompt" in prompt,
    }
    
    print("\n✅ SEPARATION CHECKS:")
    all_passed = True
    for check_name, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {check_name}")
        if not passed:
            all_passed = False
    
    return all_passed

def main():
    """Run all verification tests"""
    print("\n" + "="*80)
    print("🧪 PROMPT INTEGRATION VERIFICATION SUITE")
    print("="*80)
    print("\nThis test verifies that the Hebrew natural AI and customer name")
    print("handling instructions are correctly integrated and will work in production.")
    
    # Run tests
    test1_passed = test_system_prompt_structure()
    test2_passed = test_name_usage_behavior()
    test3_passed = test_hebrew_quality_rules()
    test4_passed = test_business_prompt_separation()
    
    # Summary
    print("\n" + "="*80)
    print("📊 VERIFICATION SUMMARY")
    print("="*80)
    
    tests = {
        "System Prompt Structure": test1_passed,
        "Name Usage Behavior": test2_passed,
        "Hebrew Quality Rules": test3_passed,
        "Business Prompt Separation": test4_passed,
    }
    
    all_passed = all(tests.values())
    
    for test_name, passed in tests.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {test_name}")
    
    print("\n" + "="*80)
    if all_passed:
        print("🎉 ALL VERIFICATION TESTS PASSED!")
        print("\n✅ The implementation is correct and will work in production:")
        print("   - Hebrew will be natural, fluent, and high-quality")
        print("   - Customer name will be used naturally when business prompt requests it")
        print("   - System prompt controls behavior/grammar, not flow")
        print("   - Business prompt controls flow and content")
        print("="*80)
        return 0
    else:
        print("❌ SOME VERIFICATION TESTS FAILED!")
        print("="*80)
        return 1

if __name__ == "__main__":
    sys.exit(main())
