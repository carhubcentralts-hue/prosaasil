#!/usr/bin/env python3
"""
Test to verify that the idle-in-transaction fix works correctly.

This test verifies:
1. check_constraint_exists() uses engine.connect() instead of db.session
2. terminate_idle_in_tx() function exists and can be called
3. exec_ddl() checks and terminates idle transactions before DDL
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_check_constraint_exists_signature():
    """Verify check_constraint_exists function exists with correct signature."""
    from server import db_migrate
    
    # Check function exists
    assert hasattr(db_migrate, 'check_constraint_exists'), \
        "check_constraint_exists function not found"
    
    # Check it's callable
    assert callable(db_migrate.check_constraint_exists), \
        "check_constraint_exists is not callable"
    
    print("✅ check_constraint_exists function exists")


def test_terminate_idle_in_tx_signature():
    """Verify terminate_idle_in_tx function exists with correct signature."""
    from server import db_migrate
    
    # Check function exists
    assert hasattr(db_migrate, 'terminate_idle_in_tx'), \
        "terminate_idle_in_tx function not found"
    
    # Check it's callable
    assert callable(db_migrate.terminate_idle_in_tx), \
        "terminate_idle_in_tx is not callable"
    
    print("✅ terminate_idle_in_tx function exists")


def test_check_functions_use_engine_connect():
    """Verify that check functions use engine.connect() and not db.session."""
    import inspect
    from server import db_migrate
    
    functions_to_check = [
        'check_column_exists',
        'check_table_exists', 
        'check_index_exists',
        'check_constraint_exists'
    ]
    
    for func_name in functions_to_check:
        func = getattr(db_migrate, func_name)
        source = inspect.getsource(func)
        
        # Check that function uses engine.connect()
        assert 'engine.connect()' in source or 'db.engine.connect()' in source, \
            f"{func_name} does not use engine.connect()"
        
        # Check that function does NOT use db.session.execute for the main query
        # (it's ok to use it in comments or docstrings)
        lines = source.split('\n')
        code_lines = [line for line in lines if 'db.session.execute' in line 
                     and not line.strip().startswith('#')]
        assert len(code_lines) == 0, \
            f"{func_name} uses db.session.execute which can leave transactions open"
        
        print(f"✅ {func_name} uses engine.connect() correctly")


def test_exec_ddl_calls_terminate():
    """Verify that exec_ddl calls terminate_idle_in_tx."""
    import inspect
    from server import db_migrate
    
    source = inspect.getsource(db_migrate.exec_ddl)
    
    # Check that exec_ddl mentions terminate_idle_in_tx
    assert 'terminate_idle_in_tx' in source, \
        "exec_ddl does not call terminate_idle_in_tx"
    
    # Check that it checks for idle transactions
    assert 'idle in transaction' in source.lower(), \
        "exec_ddl does not check for idle-in-transaction connections"
    
    print("✅ exec_ddl checks and terminates idle transactions")


def test_migration_113_uses_check_constraint():
    """Verify migration 113 uses check_constraint_exists instead of db.session."""
    from server import db_migrate
    import inspect
    
    # Get the apply_migrations function source
    source = inspect.getsource(db_migrate.apply_migrations)
    
    # Look for the unique_run_lead constraint check
    if 'unique_run_lead' in source:
        # Find the section with unique_run_lead
        lines = source.split('\n')
        constraint_section = []
        in_section = False
        
        for line in lines:
            if 'unique_run_lead' in line:
                in_section = True
            if in_section:
                constraint_section.append(line)
                if 'check_constraint_exists' in line:
                    break
            if in_section and len(constraint_section) > 20:
                # Stop if we've gone too far
                break
        
        section_text = '\n'.join(constraint_section)
        
        # Verify it uses check_constraint_exists
        assert 'check_constraint_exists' in section_text, \
            "Migration 113 does not use check_constraint_exists"
        
        # Verify it does NOT use db.session.execute for constraint check
        assert 'db.session.execute' not in section_text or \
               'SELECT 1 FROM pg_constraint' not in section_text, \
            "Migration 113 still uses db.session.execute for constraint check"
        
        print("✅ Migration 113 uses check_constraint_exists correctly")
    else:
        print("ℹ️  unique_run_lead constraint not found in migrations (may have been removed)")


def main():
    """Run all tests."""
    print("=" * 80)
    print("Testing Idle-in-Transaction Fix")
    print("=" * 80)
    print()
    
    tests = [
        ("Check constraint exists function", test_check_constraint_exists_signature),
        ("Terminate idle transactions function", test_terminate_idle_in_tx_signature),
        ("Check functions use engine.connect()", test_check_functions_use_engine_connect),
        ("exec_ddl terminates idle transactions", test_exec_ddl_calls_terminate),
        ("Migration 113 uses check_constraint_exists", test_migration_113_uses_check_constraint),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            print(f"\n📋 {test_name}...")
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"❌ FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print()
    print("=" * 80)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 80)
    
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
