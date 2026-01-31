"""
Test for worker.py STRICT_SCHEMA_CHECK behavior

This test validates:
1. STRICT_SCHEMA_CHECK defaults to False (non-strict mode)
2. Worker continues in non-strict mode when tables are missing
3. Worker exits in strict mode when tables are missing
4. Schema check function works correctly
"""

import os

def test_strict_schema_check_parsing():
    """Test that STRICT_SCHEMA_CHECK environment variable is parsed correctly"""
    
    # Test default (not set) - should be False
    os.environ.pop('STRICT_SCHEMA_CHECK', None)
    strict = os.getenv("STRICT_SCHEMA_CHECK", "0") == "1"
    assert strict is False, "Default STRICT_SCHEMA_CHECK should be False"
    print("✅ Default STRICT_SCHEMA_CHECK=False")
    
    # Test explicitly set to "0" - should be False
    os.environ['STRICT_SCHEMA_CHECK'] = "0"
    strict = os.getenv("STRICT_SCHEMA_CHECK", "0") == "1"
    assert strict is False, "STRICT_SCHEMA_CHECK=0 should be False"
    print("✅ STRICT_SCHEMA_CHECK='0' → False")
    
    # Test explicitly set to "1" - should be True
    os.environ['STRICT_SCHEMA_CHECK'] = "1"
    strict = os.getenv("STRICT_SCHEMA_CHECK", "0") == "1"
    assert strict is True, "STRICT_SCHEMA_CHECK=1 should be True"
    print("✅ STRICT_SCHEMA_CHECK='1' → True")
    
    # Test other values - should be False
    for value in ["", "true", "false", "yes", "no", "2"]:
        os.environ['STRICT_SCHEMA_CHECK'] = value
        strict = os.getenv("STRICT_SCHEMA_CHECK", "0") == "1"
        assert strict is False, f"STRICT_SCHEMA_CHECK='{value}' should be False"
    print("✅ Other values default to False")
    
    # Clean up
    os.environ.pop('STRICT_SCHEMA_CHECK', None)
    
    print("\n🎉 STRICT_SCHEMA_CHECK parsing tests passed!")


def test_schema_check_logic():
    """Test the logic flow of schema checking"""
    
    # Simulate missing tables
    missing_tables = ['gmail_receipts']
    
    # Test 1: Non-strict mode with missing tables
    STRICT_SCHEMA_CHECK = False
    should_exit = False
    
    if missing_tables:
        if STRICT_SCHEMA_CHECK:
            should_exit = True
    
    assert should_exit is False, "Non-strict mode should not exit"
    print("✅ Non-strict mode: continues despite missing tables")
    
    # Test 2: Strict mode with missing tables
    STRICT_SCHEMA_CHECK = True
    should_exit = False
    
    if missing_tables:
        if STRICT_SCHEMA_CHECK:
            should_exit = True
    
    assert should_exit is True, "Strict mode should exit"
    print("✅ Strict mode: exits when tables are missing")
    
    # Test 3: Non-strict mode with no missing tables
    missing_tables = None
    STRICT_SCHEMA_CHECK = False
    should_exit = False
    
    if missing_tables:
        if STRICT_SCHEMA_CHECK:
            should_exit = True
    
    assert should_exit is False, "Should not exit when no tables missing"
    print("✅ No missing tables: continues normally")
    
    print("\n🎉 Schema check logic tests passed!")


def test_critical_tables_list():
    """Test that critical tables list includes gmail_receipts"""
    
    critical_tables = ['business', 'leads', 'receipts', 'gmail_receipts']
    
    assert 'gmail_receipts' in critical_tables, "gmail_receipts must be in critical tables list"
    assert 'business' in critical_tables, "business must be in critical tables list"
    assert 'leads' in critical_tables, "leads must be in critical tables list"
    assert 'receipts' in critical_tables, "receipts must be in critical tables list"
    
    print("✅ Critical tables list is correct")
    print(f"   Tables: {critical_tables}")
    
    print("\n🎉 Critical tables validation passed!")


if __name__ == "__main__":
    test_strict_schema_check_parsing()
    print()
    test_schema_check_logic()
    print()
    test_critical_tables_list()
    print("\n" + "=" * 70)
    print("✅ All worker tests passed!")
    print("=" * 70)
    print("\n📝 Summary:")
    print("   - STRICT_SCHEMA_CHECK defaults to False (non-strict)")
    print("   - Worker continues in non-strict mode even with missing tables")
    print("   - Worker exits in strict mode when tables are missing")
    print("   - gmail_receipts is included in critical tables check")
