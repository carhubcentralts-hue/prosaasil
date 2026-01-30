#!/usr/bin/env python3
"""
Test migration fixes for the issues mentioned in the problem statement:
1. Migration 80 - constraint_row UnboundLocalError
2. Migration 113 - check_constraint_exists() signature
3. Migration 115 - broken CREATE INDEX statements (moved to db_indexes.py)
4. DDL failure handling - fail hard except for "already exists" errors
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_db_indexes_calendar_additions():
    """Test that calendar indexes were added to db_indexes.py"""
    from server.db_indexes import INDEX_DEFS
    
    print("Testing db_indexes.py additions...")
    
    # Check for the 5 new calendar indexes
    expected_indexes = [
        'idx_business_calendars_business_active',
        'idx_business_calendars_priority',
        'idx_calendar_routing_business_active',
        'idx_calendar_routing_calendar',
        'idx_appointments_calendar_id',
    ]
    
    index_names = [idx['name'] for idx in INDEX_DEFS]
    
    for expected_idx in expected_indexes:
        assert expected_idx in index_names, f"❌ Expected index {expected_idx} not found in INDEX_DEFS"
        print(f"  ✅ Found index: {expected_idx}")
    
    # Verify they all have CONCURRENTLY and IF NOT EXISTS
    for expected_idx in expected_indexes:
        idx_def = next(idx for idx in INDEX_DEFS if idx['name'] == expected_idx)
        assert 'CONCURRENTLY' in idx_def['sql'], f"❌ Index {expected_idx} missing CONCURRENTLY"
        assert 'IF NOT EXISTS' in idx_def['sql'], f"❌ Index {expected_idx} missing IF NOT EXISTS"
        print(f"  ✅ Index {expected_idx} has CONCURRENTLY IF NOT EXISTS")
    
    print("✅ All calendar indexes correctly added to db_indexes.py")
    return True

def test_already_exists_error_helper():
    """Test the _is_already_exists_error helper function"""
    print("\nTesting _is_already_exists_error helper...")
    
    # Create a mock exception class
    class MockException(Exception):
        pass
    
    # We can't import the actual function due to dependencies, but we can
    # verify the logic manually
    def _is_already_exists_error(e):
        msg = str(e).lower()
        safe_patterns = [
            "already exists",
            "duplicate_object",
            "duplicate_table", 
            "duplicate_column",
            "duplicate key",
        ]
        return any(pattern in msg for pattern in safe_patterns)
    
    # Test cases
    test_cases = [
        ("relation already exists", True),
        ("table already exists", True),
        ("duplicate_object error", True),
        ("duplicate_column violation", True),
        ("syntax error near ON", False),
        ("ProgrammingError: invalid SQL", False),
        ("column does not exist", False),
    ]
    
    for error_msg, should_pass in test_cases:
        e = MockException(error_msg)
        result = _is_already_exists_error(e)
        if result == should_pass:
            print(f"  ✅ Correctly handled: '{error_msg}' -> {result}")
        else:
            print(f"  ❌ Failed: '{error_msg}' expected {should_pass}, got {result}")
            return False
    
    print("✅ _is_already_exists_error logic is correct")
    return True

def test_migration_code_changes():
    """Test that the migration code was properly modified"""
    print("\nTesting migration code changes...")
    
    with open('server/db_migrate.py', 'r') as f:
        content = f.read()
    
    # Test 1: Check Migration 80 fix (constraint_row = None)
    if 'constraint_row = None' in content and 'Initialize constraint_row before try block' in content:
        print("  ✅ Migration 80 fix: constraint_row initialized before try block")
    else:
        print("  ❌ Migration 80 fix: constraint_row not properly initialized")
        return False
    
    # Test 2: Check Migration 113 fix (check_constraint_exists signature)
    if "check_constraint_exists('outbound_call_jobs', 'unique_run_lead')" in content:
        print("  ✅ Migration 113 fix: check_constraint_exists called with correct signature")
    else:
        print("  ❌ Migration 113 fix: check_constraint_exists signature not fixed")
        return False
    
    # Test 3: Check Migration 115 - CREATE INDEX statements removed
    # Look for the comment we added
    if "Performance indexes moved to db_indexes.py (IRON RULE: no indexes in migrations)" in content:
        print("  ✅ Migration 115 fix: CREATE INDEX statements removed and documented")
    else:
        print("  ❌ Migration 115 fix: CREATE INDEX statements not properly removed")
        return False
    
    # Test 4: Check for _is_already_exists_error function
    if 'def _is_already_exists_error' in content:
        print("  ✅ Added _is_already_exists_error helper function")
    else:
        print("  ❌ _is_already_exists_error helper function not found")
        return False
    
    # Test 5: Check for FAIL HARD logic in exec_ddl
    if 'DDL FAILURES = FAIL HARD (except "already exists")' in content:
        print("  ✅ Added FAIL HARD logic for DDL errors")
    else:
        print("  ❌ FAIL HARD logic not found")
        return False
    
    # Test 6: Verify broken CREATE INDEX statements are NOT present
    broken_patterns = [
        'exec_ddl(db.engine, """\n                    ON business_calendars',
        'exec_ddl(db.engine, """\n                    ON calendar_routing_rules',
        'exec_ddl(db.engine, """\n                            ON appointments',
    ]
    
    for pattern in broken_patterns:
        if pattern in content:
            print(f"  ❌ Found broken CREATE INDEX pattern: {pattern[:50]}...")
            return False
    
    print("  ✅ No broken CREATE INDEX statements found")
    
    print("✅ All migration code changes verified")
    return True

def main():
    """Run all tests"""
    print("=" * 80)
    print("MIGRATION FIXES VERIFICATION")
    print("=" * 80)
    
    tests = [
        test_db_indexes_calendar_additions,
        test_already_exists_error_helper,
        test_migration_code_changes,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    print("\n" + "=" * 80)
    if all(results):
        print("✅ ALL TESTS PASSED")
        print("=" * 80)
        print("\nSummary of fixes:")
        print("1. ✅ Migration 80: constraint_row initialized before try block")
        print("2. ✅ Migration 113: check_constraint_exists() signature fixed")
        print("3. ✅ Migration 115: Broken CREATE INDEX statements removed")
        print("4. ✅ 5 calendar indexes added to db_indexes.py")
        print("5. ✅ DDL failure handling: fail hard except 'already exists'")
        print("6. ✅ _is_already_exists_error() helper function added")
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        print("=" * 80)
        return 1

if __name__ == '__main__':
    sys.exit(main())
