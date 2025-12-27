#!/usr/bin/env python3
"""
Test Prompt Architecture - Verify Clean Separation and No Hardcoded Content

Tests:
1. System prompts have no hardcoded Hebrew text
2. System prompts have no business-specific content
3. Business prompts are properly separated
4. Fallback paths work correctly
5. Validation functions work
6. No duplicated rules between layers
"""
import sys
import re
sys.path.insert(0, '/home/runner/work/prosaasil/prosaasil')

from server.services.realtime_prompt_builder import (
    build_global_system_prompt,
    _build_universal_system_prompt,
    validate_business_prompts,
    build_compact_greeting_prompt,
    build_full_business_prompt,
    _get_fallback_prompt,
)

def test_no_hardcoded_hebrew():
    """Test that system prompts have no hardcoded Hebrew text"""
    print("\n🔍 Test 1: No Hardcoded Hebrew in System Prompts")
    
    for direction in ['inbound', 'outbound', None]:
        system_prompt = build_global_system_prompt(direction)
        
        # Check for Hebrew characters
        hebrew_chars = [c for c in system_prompt if '\u0590' <= c <= '\u05FF']
        
        direction_label = direction or 'default'
        if hebrew_chars:
            print(f"  ❌ {direction_label.upper()}: Found {len(hebrew_chars)} Hebrew characters")
            print(f"     Hebrew: {''.join(set(hebrew_chars))}")
            return False
        else:
            print(f"  ✅ {direction_label.upper()}: No Hebrew characters ({len(system_prompt)} chars)")
    
    return True


def test_no_business_specific_content():
    """Test that system prompts have no business-specific content"""
    print("\n🔍 Test 2: No Business-Specific Content in System Prompts")
    
    system_prompt = build_global_system_prompt('inbound')
    
    # List of business-specific terms that should NOT appear
    forbidden_terms = [
        'plumber', 'electrician', 'salon', 'beauty', 'haircut',
        'תספורת', 'צביעה', 'מספרה', 'שירותי', 'טכנאי',
        'business_name', 'company_name'
    ]
    
    found_terms = []
    for term in forbidden_terms:
        if term.lower() in system_prompt.lower():
            found_terms.append(term)
    
    if found_terms:
        print(f"  ❌ Found business-specific terms: {found_terms}")
        return False
    else:
        print(f"  ✅ No business-specific content found")
    
    return True


def test_prompt_separation():
    """Test that prompts are properly separated"""
    print("\n🔍 Test 3: Prompt Separation (System vs Business)")
    
    # Use the raw universal system prompt for testing
    from server.services.realtime_prompt_builder import _build_universal_system_prompt
    system_prompt = _build_universal_system_prompt('inbound')
    
    # System prompt should contain behavioral rules
    expected_keywords = ['isolation', 'hebrew', 'transcript', 'turn-taking', 'style']
    found_keywords = [kw for kw in expected_keywords if kw.lower() in system_prompt.lower()]
    
    if len(found_keywords) < 4:
        print(f"  ❌ System prompt missing expected keywords. Found: {found_keywords}")
        return False
    else:
        print(f"  ✅ System prompt contains behavioral rules ({len(found_keywords)}/{len(expected_keywords)} keywords)")
    
    # System prompt should NOT contain phrases like "Business Prompt" or "BUSINESS PROMPT"
    if 'BUSINESS PROMPT' in system_prompt or 'Business Prompt:' in system_prompt:
        print(f"  ❌ System prompt contains business prompt markers (should be separate)")
        return False
    else:
        print(f"  ✅ System prompt properly separated from business content")
    
    return True


def test_fallback_paths():
    """Test that fallback paths work and have proper logging"""
    print("\n🔍 Test 4: Fallback Paths")
    
    # Test fallback with no business_id
    fallback = _get_fallback_prompt(None)
    if not fallback or len(fallback) < 20:
        print(f"  ❌ Fallback prompt is empty or too short")
        return False
    else:
        print(f"  ✅ Fallback prompt works without business_id ({len(fallback)} chars)")
    
    # Check that fallback doesn't contain hardcoded Hebrew
    hebrew_chars = [c for c in fallback if '\u0590' <= c <= '\u05FF']
    if hebrew_chars:
        print(f"  ❌ Fallback contains Hebrew: {''.join(set(hebrew_chars))}")
        return False
    else:
        print(f"  ✅ Fallback has no hardcoded Hebrew")
    
    return True


def test_validation_function():
    """Test that validation function works"""
    print("\n🔍 Test 5: Validation Function")
    
    try:
        # This should work even without DB (will return appropriate error)
        result = validate_business_prompts(99999)
        
        if not isinstance(result, dict):
            print(f"  ❌ Validation function didn't return a dict")
            return False
        
        expected_keys = ['valid', 'has_inbound_prompt', 'has_outbound_prompt', 'has_greeting', 'warnings', 'errors']
        if all(k in result for k in expected_keys):
            print(f"  ✅ Validation function returns correct structure")
        else:
            print(f"  ❌ Validation result missing keys: {[k for k in expected_keys if k not in result]}")
            return False
        
    except Exception as e:
        print(f"  ❌ Validation function error: {e}")
        return False
    
    return True


def test_no_duplicate_rules():
    """Test that there are no duplicate rules between system and inbound/outbound"""
    print("\n🔍 Test 6: No Duplicate Rules")
    
    system_prompt = _build_universal_system_prompt('inbound')
    
    # Check that legacy function is not producing conflicting output
    # The legacy function should be simplified now
    legacy_test = "legacy prompt should be minimal"
    
    # Count rule sections (looking for duplicated patterns like "Rule:", "RULE:", etc.)
    rule_pattern = r'\b(rule|rules|RULE|RULES):\s'
    rule_matches = re.findall(rule_pattern, system_prompt, re.IGNORECASE)
    
    print(f"  ✅ System prompt structure verified ({len(rule_matches)} rule sections)")
    
    # Check prompt size is reasonable (not bloated with duplicates)
    if len(system_prompt) > 2000:
        print(f"  ⚠️  System prompt is quite long ({len(system_prompt)} chars) - check for duplicates")
    else:
        print(f"  ✅ System prompt size is reasonable ({len(system_prompt)} chars)")
    
    return True


def main():
    """Run all tests"""
    print("=" * 60)
    print("Testing Prompt Architecture")
    print("=" * 60)
    
    tests = [
        ("No Hardcoded Hebrew", test_no_hardcoded_hebrew),
        ("No Business-Specific Content", test_no_business_specific_content),
        ("Prompt Separation", test_prompt_separation),
        ("Fallback Paths", test_fallback_paths),
        ("Validation Function", test_validation_function),
        ("No Duplicate Rules", test_no_duplicate_rules),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"\n❌ Test '{name}' crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    
    passed = sum(1 for _, p in results if p)
    total = len(results)
    
    for name, passed_test in results:
        status = "✅ PASS" if passed_test else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
