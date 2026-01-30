#!/usr/bin/env python3
"""
Test script to verify Migration 95 constraint fix with exec_ddl_heavy.

This test verifies:
1. exec_ddl_heavy() function exists and has correct timeouts
2. exec_ddl_heavy() has retry logic with exponential backoff
3. exec_ddl_heavy() has lock debugging on failures
4. Migration 95 uses exec_ddl_heavy() instead of DO $$ block
5. Migration 95 is split into two separate ALTER statements
"""
import sys
import os
import re

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_exec_ddl_heavy_exists():
    """Verify that exec_ddl_heavy function exists."""
    print("\n=== Test 1: exec_ddl_heavy() Function Exists ===")
    
    filepath = 'server/db_migrate.py'
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Check if function exists
        if 'def exec_ddl_heavy(' in content:
            print("  ✅ exec_ddl_heavy function exists")
            return True
        else:
            print("  ❌ exec_ddl_heavy function NOT found")
            return False
            
    except Exception as e:
        print(f"  ❌ Error checking {filepath}: {e}")
        return False


def test_exec_ddl_heavy_timeouts():
    """Verify that exec_ddl_heavy sets correct lock timeouts."""
    print("\n=== Test 2: exec_ddl_heavy() Lock Timeouts ===")
    
    filepath = 'server/db_migrate.py'
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Extract exec_ddl_heavy function
        exec_ddl_heavy_match = re.search(
            r'def exec_ddl_heavy\(.*?\):.*?(?=\ndef [a-z_]|\Z)', 
            content, 
            re.DOTALL
        )
        
        if not exec_ddl_heavy_match:
            print("  ❌ exec_ddl_heavy function not found")
            return False
        
        func_content = exec_ddl_heavy_match.group(0)
        
        all_ok = True
        
        # Check for lock_timeout = 120s (longer than regular DDL)
        if "SET lock_timeout = '120s'" in func_content or 'SET lock_timeout = "120s"' in func_content:
            print("  ✅ lock_timeout = 120s is set (correct for heavy DDL)")
        else:
            print("  ❌ lock_timeout = 120s is NOT set")
            all_ok = False
        
        # Check for statement_timeout = 0 (unlimited)
        if "SET statement_timeout = 0" in func_content:
            print("  ✅ statement_timeout = 0 is set (unlimited for waiting)")
        else:
            print("  ❌ statement_timeout = 0 is NOT set")
            all_ok = False
        
        # Check for idle_in_transaction_session_timeout
        if "SET idle_in_transaction_session_timeout = '60s'" in func_content or 'SET idle_in_transaction_session_timeout = "60s"' in func_content:
            print("  ✅ idle_in_transaction_session_timeout = 60s is set")
        else:
            print("  ❌ idle_in_transaction_session_timeout = 60s is NOT set")
            all_ok = False
        
        return all_ok
        
    except Exception as e:
        print(f"  ❌ Error checking {filepath}: {e}")
        return False


def test_exec_ddl_heavy_retry_logic():
    """Verify that exec_ddl_heavy has retry logic with exponential backoff."""
    print("\n=== Test 3: exec_ddl_heavy() Retry Logic ===")
    
    filepath = 'server/db_migrate.py'
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Extract exec_ddl_heavy function
        exec_ddl_heavy_match = re.search(
            r'def exec_ddl_heavy\(.*?\):.*?(?=\ndef [a-z_]|\Z)', 
            content, 
            re.DOTALL
        )
        
        if not exec_ddl_heavy_match:
            print("  ❌ exec_ddl_heavy function not found")
            return False
        
        func_content = exec_ddl_heavy_match.group(0)
        
        all_ok = True
        
        # Check for retries parameter with default
        if 'retries=10' in func_content:
            print("  ✅ Default retries=10 configured")
        else:
            print("  ❌ Default retries=10 NOT configured")
            all_ok = False
        
        # Check for retry loop
        if 'for i in range(retries)' in func_content:
            print("  ✅ Retry loop implemented")
        else:
            print("  ❌ Retry loop NOT found")
            all_ok = False
        
        # Check for exponential backoff
        if 'delay * 1.5' in func_content or 'delay * 2' in func_content:
            print("  ✅ Exponential backoff implemented")
        else:
            print("  ❌ Exponential backoff NOT found")
            all_ok = False
        
        # Check for sleep/time.sleep
        if 'time.sleep' in func_content:
            print("  ✅ Sleep between retries implemented")
        else:
            print("  ❌ Sleep between retries NOT found")
            all_ok = False
        
        # Check for lock error detection
        if 'locknotavailable' in func_content.lower() or 'lock timeout' in func_content.lower():
            print("  ✅ Lock error detection implemented")
        else:
            print("  ❌ Lock error detection NOT found")
            all_ok = False
        
        return all_ok
        
    except Exception as e:
        print(f"  ❌ Error checking {filepath}: {e}")
        return False


def test_exec_ddl_heavy_lock_debugging():
    """Verify that exec_ddl_heavy logs lock debugging information on failure."""
    print("\n=== Test 4: exec_ddl_heavy() Lock Debugging ===")
    
    filepath = 'server/db_migrate.py'
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Extract exec_ddl_heavy function
        exec_ddl_heavy_match = re.search(
            r'def exec_ddl_heavy\(.*?\):.*?(?=\ndef [a-z_]|\Z)', 
            content, 
            re.DOTALL
        )
        
        if not exec_ddl_heavy_match:
            print("  ❌ exec_ddl_heavy function not found")
            return False
        
        func_content = exec_ddl_heavy_match.group(0)
        
        all_ok = True
        
        # Check for LOCK_DEBUG_SQL usage
        if 'LOCK_DEBUG_SQL' in func_content:
            print("  ✅ LOCK_DEBUG_SQL query is used")
        else:
            print("  ❌ LOCK_DEBUG_SQL query is NOT used")
            all_ok = False
        
        # Check for lock debug logging
        if 'LOCK DEBUG' in func_content:
            print("  ✅ Lock debug logging implemented")
        else:
            print("  ❌ Lock debug logging NOT found")
            all_ok = False
        
        # Check for blocking process info
        if 'Blocking PID' in func_content or 'blocking_pid' in func_content.lower():
            print("  ✅ Blocking process information logged")
        else:
            print("  ❌ Blocking process information NOT logged")
            all_ok = False
        
        return all_ok
        
    except Exception as e:
        print(f"  ❌ Error checking {filepath}: {e}")
        return False


def test_migration_95_uses_exec_ddl_heavy():
    """Verify that Migration 95 uses exec_ddl_heavy instead of DO $$ block."""
    print("\n=== Test 5: Migration 95 Uses exec_ddl_heavy ===")
    
    filepath = 'server/db_migrate.py'
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Find Migration 95 section
        migration_95_match = re.search(
            r'# Migration 95:.*?(?=# Migration 96:|# Migration \d+:|\Z)',
            content,
            re.DOTALL
        )
        
        if not migration_95_match:
            print("  ❌ Migration 95 not found")
            return False
        
        migration_95_content = migration_95_match.group(0)
        
        all_ok = True
        
        # Check that DO $$ block is NOT used in actual code (comments are OK)
        # Look for actual DO $$ usage, not just in comments
        lines = migration_95_content.split('\n')
        has_do_block = False
        for line in lines:
            # Skip comments
            if line.strip().startswith('#'):
                continue
            if 'DO $$' in line:
                has_do_block = True
                break
        
        if has_do_block:
            print("  ❌ Migration 95 still uses DO $$ block (should be removed)")
            all_ok = False
        else:
            print("  ✅ Migration 95 does NOT use DO $$ block in code")
        
        # Check that exec_ddl_heavy is used
        if 'exec_ddl_heavy(' in migration_95_content:
            print("  ✅ Migration 95 uses exec_ddl_heavy")
        else:
            print("  ❌ Migration 95 does NOT use exec_ddl_heavy")
            all_ok = False
        
        # Count how many times exec_ddl_heavy is called (should be 2: DROP + ADD)
        # Count actual function calls, not mentions in comments
        heavy_ddl_count = 0
        for line in lines:
            # Skip comments
            if line.strip().startswith('#'):
                continue
            heavy_ddl_count += line.count('exec_ddl_heavy(')
        
        if heavy_ddl_count == 2:
            print(f"  ✅ Migration 95 calls exec_ddl_heavy exactly 2 times (DROP + ADD)")
        elif heavy_ddl_count > 2:
            print(f"  ⚠️  Migration 95 calls exec_ddl_heavy {heavy_ddl_count} times (expected 2, but may be OK)")
        else:
            print(f"  ❌ Migration 95 calls exec_ddl_heavy {heavy_ddl_count} times (expected 2)")
            all_ok = False
        
        return all_ok
        
    except Exception as e:
        print(f"  ❌ Error checking {filepath}: {e}")
        return False


def test_migration_95_split_statements():
    """Verify that Migration 95 uses separate ALTER statements."""
    print("\n=== Test 6: Migration 95 Split into Separate ALTER Statements ===")
    
    filepath = 'server/db_migrate.py'
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Find Migration 95 section
        migration_95_match = re.search(
            r'# Migration 95:.*?(?=# Migration 96:|# Migration \d+:|\Z)',
            content,
            re.DOTALL
        )
        
        if not migration_95_match:
            print("  ❌ Migration 95 not found")
            return False
        
        migration_95_content = migration_95_match.group(0)
        
        all_ok = True
        
        # Check for DROP CONSTRAINT statement
        if 'DROP CONSTRAINT' in migration_95_content:
            print("  ✅ DROP CONSTRAINT statement found")
        else:
            print("  ❌ DROP CONSTRAINT statement NOT found")
            all_ok = False
        
        # Check for ADD CONSTRAINT statement
        if 'ADD CONSTRAINT' in migration_95_content:
            print("  ✅ ADD CONSTRAINT statement found")
        else:
            print("  ❌ ADD CONSTRAINT statement NOT found")
            all_ok = False
        
        # Check for IF EXISTS (idempotency)
        if 'IF EXISTS' in migration_95_content:
            print("  ✅ IF EXISTS clause found (idempotent)")
        else:
            print("  ❌ IF EXISTS clause NOT found (not idempotent)")
            all_ok = False
        
        # Check for 'incomplete' status in constraint
        if "'incomplete'" in migration_95_content or '"incomplete"' in migration_95_content:
            print("  ✅ 'incomplete' status included in constraint")
        else:
            print("  ❌ 'incomplete' status NOT found in constraint")
            all_ok = False
        
        # Check that constraint name is chk_receipt_status
        if 'chk_receipt_status' in migration_95_content:
            print("  ✅ Constraint name 'chk_receipt_status' is correct")
        else:
            print("  ❌ Constraint name 'chk_receipt_status' NOT found")
            all_ok = False
        
        return all_ok
        
    except Exception as e:
        print(f"  ❌ Error checking {filepath}: {e}")
        return False


def test_migration_95_documentation():
    """Verify that Migration 95 has proper documentation about heavy DDL."""
    print("\n=== Test 7: Migration 95 Documentation ===")
    
    filepath = 'server/db_migrate.py'
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Find Migration 95 section
        migration_95_match = re.search(
            r'# Migration 95:.*?(?=# Migration 96:|# Migration \d+:|\Z)',
            content,
            re.DOTALL
        )
        
        if not migration_95_match:
            print("  ❌ Migration 95 not found")
            return False
        
        migration_95_content = migration_95_match.group(0)
        
        all_ok = True
        
        # Check for "heavy DDL" or "AccessExclusive" in comments
        if 'heavy DDL' in migration_95_content or 'AccessExclusive' in migration_95_content:
            print("  ✅ Documentation mentions heavy DDL or AccessExclusive lock")
        else:
            print("  ⚠️  Documentation doesn't mention heavy DDL (optional)")
        
        # Check for timeout explanation
        if '120s' in migration_95_content or 'lock_timeout' in migration_95_content:
            print("  ✅ Documentation mentions timeout settings")
        else:
            print("  ⚠️  Documentation doesn't mention timeout settings (optional)")
        
        return all_ok
        
    except Exception as e:
        print(f"  ❌ Error checking {filepath}: {e}")
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("MIGRATION 95 CONSTRAINT FIX - TEST SUITE")
    print("=" * 80)
    
    tests = [
        test_exec_ddl_heavy_exists,
        test_exec_ddl_heavy_timeouts,
        test_exec_ddl_heavy_retry_logic,
        test_exec_ddl_heavy_lock_debugging,
        test_migration_95_uses_exec_ddl_heavy,
        test_migration_95_split_statements,
        test_migration_95_documentation,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"  ❌ Test failed with exception: {e}")
            results.append(False)
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    passed = sum(results)
    total = len(results)
    
    print(f"\nPassed: {passed}/{total}")
    
    if all(results):
        print("\n✅ ALL TESTS PASSED")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED")
        return 1


if __name__ == '__main__':
    sys.exit(main())
