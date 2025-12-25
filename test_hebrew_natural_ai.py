#!/usr/bin/env python3
"""
Test script for verifying Hebrew natural AI and customer name handling features

Tests:
1. Hebrew naturalness rules are present in system prompt
2. Customer name rules are present in system prompt
3. Rules are behavioral (no hardcoded names)
4. Both inbound and outbound prompts have the rules
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_hebrew_naturalness():
    """Test Hebrew naturalness rules in system prompt"""
    print("\n" + "="*80)
    print("🔵 TEST 1: HEBREW NATURALNESS RULES")
    print("="*80)
    
    from server.services.realtime_prompt_builder import _build_universal_system_prompt
    
    # Test inbound
    inbound_prompt = _build_universal_system_prompt(call_direction="inbound")
    
    # Check for key Hebrew rules (English instructions, Hebrew output)
    checks = {
        "Language section header": "Language and Grammar:" in inbound_prompt,
        "Natural Israeli Hebrew": "natural, fluent, daily Israeli Hebrew" in inbound_prompt,
        "Don't translate": "Do NOT translate from English" in inbound_prompt,
        "Native speaker quality": "high-level native speaker" in inbound_prompt,
        "Short flowing sentences": "short, flowing sentences" in inbound_prompt,
        "Avoid artificial phrasing": "Avoid artificial or overly formal phrasing" in inbound_prompt,
    }
    
    print("\n✅ HEBREW NATURALNESS CHECKS:")
    all_passed = True
    for check_name, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {check_name}")
        if not passed:
            all_passed = False
    
    print(f"\n📏 Prompt length: {len(inbound_prompt)} chars")
    
    return all_passed

def test_customer_name_rules():
    """Test customer name handling rules in system prompt"""
    print("\n" + "="*80)
    print("🔵 TEST 2: CUSTOMER NAME RULES")
    print("="*80)
    
    from server.services.realtime_prompt_builder import _build_universal_system_prompt
    
    # Test outbound
    outbound_prompt = _build_universal_system_prompt(call_direction="outbound")
    
    # Check for key name rules (English instructions)
    checks = {
        "Name usage section": "Customer Name Usage:" in outbound_prompt,
        "Only if prompt requests": "ONLY if the Business Prompt requests name usage" in outbound_prompt,
        "Natural usage": "Use the name naturally throughout the entire conversation" in outbound_prompt,
        "Free and human integration": "freely and humanly" in outbound_prompt,
        "No theoretical phrasing": "Do NOT say words like 'customer name'" in outbound_prompt,
        "Don't ask for name": "Do NOT ask what the name is and do NOT invent a name" in outbound_prompt,
        "Continue without name": "If no name is available - continue the conversation normally" in outbound_prompt,
    }
    
    print("\n✅ CUSTOMER NAME HANDLING CHECKS:")
    all_passed = True
    for check_name, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {check_name}")
        if not passed:
            all_passed = False
    
    print(f"\n📏 Prompt length: {len(outbound_prompt)} chars")
    
    return all_passed

def test_no_hardcoded_content():
    """Test that system prompt has no hardcoded business content"""
    print("\n" + "="*80)
    print("🔵 TEST 3: NO HARDCODED BUSINESS CONTENT")
    print("="*80)
    
    from server.services.realtime_prompt_builder import _build_universal_system_prompt
    
    prompt = _build_universal_system_prompt(call_direction="inbound")
    
    # These should NOT be in the system prompt (they're business-specific)
    forbidden_content = [
        "מנעולן",  # Locksmith
        "שרברב",  # Plumber
        "מס",     # Tax
        "רופא",   # Doctor
        "דני",    # Name example
        "אבי",    # Name example
        "ירושלים", # City
        "תל אביב", # City
    ]
    
    print("\n✅ NO HARDCODED BUSINESS CONTENT CHECKS:")
    all_passed = True
    for content in forbidden_content:
        found = content in prompt
        status = "❌" if found else "✅"
        print(f"  {status} Does NOT contain '{content}'")
        if found:
            all_passed = False
    
    return all_passed

def test_both_directions():
    """Test that both inbound and outbound have the new rules"""
    print("\n" + "="*80)
    print("🔵 TEST 4: BOTH DIRECTIONS HAVE RULES")
    print("="*80)
    
    from server.services.realtime_prompt_builder import _build_universal_system_prompt
    
    inbound = _build_universal_system_prompt(call_direction="inbound")
    outbound = _build_universal_system_prompt(call_direction="outbound")
    
    # Both should have the core rules (English instructions)
    inbound_has_hebrew = "Language and Grammar:" in inbound
    inbound_has_name = "Customer Name Usage:" in inbound
    outbound_has_hebrew = "Language and Grammar:" in outbound
    outbound_has_name = "Customer Name Usage:" in outbound
    
    print("\n✅ RULES IN BOTH DIRECTIONS:")
    print(f"  {'✅' if inbound_has_hebrew else '❌'} Inbound has Hebrew rules")
    print(f"  {'✅' if inbound_has_name else '❌'} Inbound has name rules")
    print(f"  {'✅' if outbound_has_hebrew else '❌'} Outbound has Hebrew rules")
    print(f"  {'✅' if outbound_has_name else '❌'} Outbound has name rules")
    
    # Check direction-specific content
    inbound_specific = "Inbound rules:" in inbound
    outbound_specific = "Outbound rules:" in outbound
    
    print(f"  {'✅' if inbound_specific else '❌'} Inbound has direction-specific rules")
    print(f"  {'✅' if outbound_specific else '❌'} Outbound has direction-specific rules")
    
    all_passed = inbound_has_hebrew and inbound_has_name and outbound_has_hebrew and outbound_has_name and inbound_specific and outbound_specific
    
    return all_passed

def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("🧪 HEBREW NATURAL AI + CUSTOMER NAME HANDLING TEST SUITE")
    print("="*80)
    
    # Run tests
    test1_passed = test_hebrew_naturalness()
    test2_passed = test_customer_name_rules()
    test3_passed = test_no_hardcoded_content()
    test4_passed = test_both_directions()
    
    # Summary
    print("\n" + "="*80)
    print("📊 TEST SUMMARY")
    print("="*80)
    
    tests = {
        "Hebrew Naturalness Rules": test1_passed,
        "Customer Name Rules": test2_passed,
        "No Hardcoded Content": test3_passed,
        "Both Directions": test4_passed,
    }
    
    all_passed = all(tests.values())
    
    for test_name, passed in tests.items():
        status = "✅" if passed else "❌"
        print(f"  {status} {test_name}")
    
    print("\n" + "="*80)
    if all_passed:
        print("🎉 ALL TESTS PASSED!")
        print("="*80)
        return 0
    else:
        print("❌ SOME TESTS FAILED!")
        print("="*80)
        return 1

if __name__ == "__main__":
    sys.exit(main())
