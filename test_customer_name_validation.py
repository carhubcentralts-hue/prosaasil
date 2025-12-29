#!/usr/bin/env python3
"""
Test Customer Name Validation
===============================

Verifies that customer name validation properly filters out invalid/placeholder names.
"""

def test_is_valid_customer_name():
    """Test the customer name validation logic."""
    
    def _is_valid_customer_name(name: str) -> bool:
        """Validate that customer name is real data, not a placeholder.
        
        Rejects:
        - None/empty strings
        - Common placeholder values: 'unknown', 'test', '-'
        """
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
    
    print("=" * 80)
    print("🧪 CUSTOMER NAME VALIDATION TEST")
    print("=" * 80)
    print()
    
    # Test valid names
    valid_names = [
        "דני",
        "אבי",
        "יוסי",
        "David",
        "Sarah Cohen",
        "משה כהן",
    ]
    
    print("📋 Testing VALID names:")
    all_valid_passed = True
    for name in valid_names:
        result = _is_valid_customer_name(name)
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status}: '{name}' -> {result}")
        if not result:
            all_valid_passed = False
    print()
    
    # Test invalid names
    invalid_names = [
        None,
        "",
        "   ",
        "unknown",
        "Unknown",
        "UNKNOWN",
        "test",
        "Test",
        "TEST",
        "-",
        "null",
        "Null",
        "NULL",
        "none",
        "None",
        "NONE",
        "n/a",
        "N/A",
        "na",
        "NA",
    ]
    
    print("📋 Testing INVALID names (should be rejected):")
    all_invalid_passed = True
    for name in invalid_names:
        result = _is_valid_customer_name(name)
        status = "✅ PASS" if not result else "❌ FAIL"
        display_name = repr(name) if name is not None else "None"
        print(f"   {status}: {display_name} -> {result} (should be False)")
        if result:
            all_invalid_passed = False
    print()
    
    # Final summary
    print("=" * 80)
    print("📊 TEST SUMMARY")
    print("=" * 80)
    
    if all_valid_passed and all_invalid_passed:
        print("🎉 ALL TESTS PASSED!")
        print()
        print("✅ Valid names are correctly accepted")
        print("✅ Invalid/placeholder names are correctly rejected")
        return 0
    else:
        print("❌ SOME TESTS FAILED!")
        if not all_valid_passed:
            print("   ❌ Some valid names were incorrectly rejected")
        if not all_invalid_passed:
            print("   ❌ Some invalid names were incorrectly accepted")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(test_is_valid_customer_name())
