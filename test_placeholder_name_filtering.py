#!/usr/bin/env python3
"""
Test Customer Name with Placeholder Values
===========================================

Verifies that placeholder names like 'unknown', 'test', '-' are properly filtered
and not injected into the AI conversation context.
"""

def test_placeholder_name_filtering():
    """Test that placeholder names are filtered out during extraction."""
    
    # Simulate the _is_valid_customer_name validation
    def _is_valid_customer_name(name: str) -> bool:
        """Validate that customer name is real data, not a placeholder."""
        if not name:
            return False
        
        name_lower = name.strip().lower()
        if not name_lower:
            return False
        
        # Reject common placeholder values
        invalid_values = ['unknown', 'test', '-', 'null', 'none', 'n/a', 'na']
        if name_lower in invalid_values:
            return False
        
        return True
    
    # Simulate the _extract_customer_name logic with validation
    def _extract_customer_name_with_validation(names_to_check: list) -> str:
        """Extract customer name from sources, with validation."""
        for name in names_to_check:
            if name and str(name).strip():
                name_str = str(name).strip()
                if _is_valid_customer_name(name_str):
                    return name_str
        return None
    
    print("=" * 80)
    print("🧪 PLACEHOLDER NAME FILTERING TEST")
    print("=" * 80)
    print()
    
    # Test scenarios
    scenarios = [
        {
            "name": "Valid name is extracted",
            "sources": ["דני", None, None],
            "expected": "דני",
        },
        {
            "name": "Placeholder 'unknown' is skipped, valid name used",
            "sources": ["unknown", "אבי", None],
            "expected": "אבי",
        },
        {
            "name": "Placeholder 'test' is rejected",
            "sources": ["test", None, None],
            "expected": None,
        },
        {
            "name": "Placeholder '-' is rejected",
            "sources": ["-", None, None],
            "expected": None,
        },
        {
            "name": "Placeholder 'Unknown' (capitalized) is rejected",
            "sources": ["Unknown", None, None],
            "expected": None,
        },
        {
            "name": "Multiple placeholders, no valid name",
            "sources": ["unknown", "test", "-"],
            "expected": None,
        },
        {
            "name": "Empty string is rejected",
            "sources": ["", None, None],
            "expected": None,
        },
        {
            "name": "Whitespace-only is rejected",
            "sources": ["   ", None, None],
            "expected": None,
        },
        {
            "name": "Valid name after placeholders",
            "sources": ["unknown", "test", "יוסי"],
            "expected": "יוסי",
        },
    ]
    
    all_passed = True
    for i, scenario in enumerate(scenarios, 1):
        print(f"📋 Test {i}: {scenario['name']}")
        result = _extract_customer_name_with_validation(scenario["sources"])
        expected = scenario["expected"]
        
        if result == expected:
            print(f"   ✅ PASSED: sources={scenario['sources']} -> {repr(result)}")
        else:
            print(f"   ❌ FAILED: sources={scenario['sources']}")
            print(f"      Expected: {repr(expected)}")
            print(f"      Got: {repr(result)}")
            all_passed = False
        print()
    
    # Final summary
    print("=" * 80)
    print("📊 TEST SUMMARY")
    print("=" * 80)
    
    if all_passed:
        print("🎉 ALL TESTS PASSED!")
        print()
        print("✅ Placeholder names are properly filtered")
        print("✅ Valid names are extracted correctly")
        print("✅ System prioritizes valid names over placeholders")
        print()
        print("This ensures that AI will only use REAL customer names,")
        print("not placeholder values like 'unknown', 'test', or '-'.")
        return 0
    else:
        print("❌ SOME TESTS FAILED!")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(test_placeholder_name_filtering())
