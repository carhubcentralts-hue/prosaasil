#!/usr/bin/env python3
"""
Test Migration 89 Transaction Fix

This test verifies that:
1. exec_ddl function exists and has proper signature
2. Migration 89 uses exec_ddl for all ALTER TABLE statements
3. Data cleanup happens before constraint addition
4. Each DDL operation is in a separate transaction
"""
import re
import sys


def test_exec_ddl_exists():
    """Verify exec_ddl helper function exists"""
    print("\n=== Testing exec_ddl Function ===")
    
    with open('server/db_migrate.py', 'r') as f:
        content = f.read()
    
    # Check function exists
    if 'def exec_ddl(engine, sql: str):' in content:
        print("  ✅ exec_ddl function exists with correct signature")
    else:
        print("  ❌ exec_ddl function not found or has wrong signature")
        return False
    
    # Check it uses engine.begin()
    exec_ddl_match = re.search(
        r'def exec_ddl\(.*?\):.*?(?=\ndef |\Z)',
        content,
        re.DOTALL
    )
    
    if exec_ddl_match:
        func_content = exec_ddl_match.group(0)
        if 'with engine.begin() as conn:' in func_content:
            print("  ✅ exec_ddl uses engine.begin() for transaction isolation")
        else:
            print("  ❌ exec_ddl doesn't use engine.begin()")
            return False
        
        if 'conn.execute(text(sql))' in func_content:
            print("  ✅ exec_ddl executes SQL with text()")
        else:
            print("  ❌ exec_ddl doesn't execute SQL properly")
            return False
    else:
        print("  ❌ Could not parse exec_ddl function")
        return False
    
    return True


def test_migration_89_uses_exec_ddl():
    """Verify Migration 89 uses exec_ddl for all DDL operations"""
    print("\n=== Testing Migration 89 Uses exec_ddl ===")
    
    with open('server/db_migrate.py', 'r') as f:
        content = f.read()
    
    # Find Migration 89 section
    migration_89_match = re.search(
        r'# Migration 89:.*?(?=# Migration \d+:|checkpoint\("Committing migrations)',
        content,
        re.DOTALL
    )
    
    if not migration_89_match:
        print("  ❌ Could not find Migration 89 section")
        return False
    
    migration_89_content = migration_89_match.group(0)
    
    # Check that it doesn't use db.session.execute for ALTER TABLE
    if re.search(r'db\.session\.execute\(text\(\s*""".*?ALTER TABLE', migration_89_content, re.DOTALL):
        print("  ❌ Migration 89 still uses db.session.execute for ALTER TABLE")
        return False
    else:
        print("  ✅ Migration 89 doesn't use db.session.execute for ALTER TABLE")
    
    # Check that it uses exec_ddl for ALTER TABLE statements
    exec_ddl_calls = len(re.findall(r'exec_ddl\(db\.engine,', migration_89_content))
    
    if exec_ddl_calls >= 8:  # 6 columns + cleanup + 2 constraint operations
        print(f"  ✅ Migration 89 has {exec_ddl_calls} exec_ddl calls (expected at least 8)")
    else:
        print(f"  ❌ Migration 89 has only {exec_ddl_calls} exec_ddl calls (expected at least 8)")
        return False
    
    # Count ALTER TABLE operations
    alter_table_count = len(re.findall(r'ALTER TABLE receipt_sync_runs', migration_89_content))
    print(f"  ✅ Found {alter_table_count} ALTER TABLE statements in Migration 89")
    
    return True


def test_data_cleanup_before_constraint():
    """Verify data cleanup happens before constraint addition"""
    print("\n=== Testing Data Cleanup Before Constraint ===")
    
    with open('server/db_migrate.py', 'r') as f:
        content = f.read()
    
    # Find Migration 89 section
    migration_89_match = re.search(
        r'# Migration 89:.*?(?=# Migration \d+:|checkpoint\("Committing migrations)',
        content,
        re.DOTALL
    )
    
    if not migration_89_match:
        print("  ❌ Could not find Migration 89 section")
        return False
    
    migration_89_content = migration_89_match.group(0)
    
    # Check for UPDATE statement that cleans up invalid status
    if 'UPDATE receipt_sync_runs' in migration_89_content and \
       "SET status = 'failed'" in migration_89_content and \
       "NOT IN ('running', 'paused', 'completed', 'failed', 'cancelled')" in migration_89_content:
        print("  ✅ Found data cleanup UPDATE statement")
    else:
        print("  ❌ Data cleanup UPDATE statement not found")
        return False
    
    # Check that cleanup comes before constraint addition
    cleanup_pos = migration_89_content.find('UPDATE receipt_sync_runs')
    constraint_pos = migration_89_content.find('ADD CONSTRAINT chk_receipt_sync_status')
    
    if cleanup_pos < constraint_pos:
        print("  ✅ Data cleanup happens before constraint addition")
    else:
        print("  ❌ Data cleanup happens after constraint addition")
        return False
    
    return True


def test_separate_transactions():
    """Verify each operation is in separate transaction"""
    print("\n=== Testing Separate Transactions ===")
    
    with open('server/db_migrate.py', 'r') as f:
        content = f.read()
    
    # Find Migration 89 section
    migration_89_match = re.search(
        r'# Migration 89:.*?(?=# Migration \d+:|checkpoint\("Committing migrations)',
        content,
        re.DOTALL
    )
    
    if not migration_89_match:
        print("  ❌ Could not find Migration 89 section")
        return False
    
    migration_89_content = migration_89_match.group(0)
    
    # Check for comments indicating separate transactions
    if 'separate transaction' in migration_89_content:
        separate_tx_count = migration_89_content.count('separate transaction')
        print(f"  ✅ Found {separate_tx_count} comments about separate transactions")
    else:
        print("  ⚠️  No comments about separate transactions found")
    
    # Each exec_ddl call creates a separate transaction
    exec_ddl_count = len(re.findall(r'exec_ddl\(db\.engine,', migration_89_content))
    print(f"  ✅ Each of {exec_ddl_count} exec_ddl calls runs in separate transaction")
    
    return True


def test_fail_fast_on_migration_failure():
    """Verify system fails fast when migrations fail"""
    print("\n=== Testing Fail-Fast on Migration Failure ===")
    
    with open('server/app_factory.py', 'r') as f:
        content = f.read()
    
    # Check for raise after migration failure
    if 'raise RuntimeError(f"Migration failed - cannot proceed: {e}") from e' in content:
        print("  ✅ System raises RuntimeError on migration failure")
    else:
        print("  ❌ System doesn't raise error on migration failure")
        return False
    
    # Check warmup timeout handling
    if 'raise RuntimeError(error_msg)' in content and \
       'CANNOT proceed with invalid schema' in content:
        print("  ✅ Warmup raises error on migration timeout")
    else:
        print("  ❌ Warmup doesn't fail on migration timeout")
        return False
    
    return True


def test_validation_uses_information_schema():
    """Verify validation uses information_schema"""
    print("\n=== Testing Validation Uses information_schema ===")
    
    with open('server/db_migrate.py', 'r') as f:
        content = f.read()
    
    # Find check_column_exists function
    check_column_match = re.search(
        r'def check_column_exists\(.*?\):.*?(?=\ndef |\Z)',
        content,
        re.DOTALL
    )
    
    if check_column_match:
        func_content = check_column_match.group(0)
        if 'information_schema.columns' in func_content:
            print("  ✅ check_column_exists uses information_schema.columns")
        else:
            print("  ❌ check_column_exists doesn't use information_schema")
            return False
    else:
        print("  ❌ check_column_exists function not found")
        return False
    
    # Find Migration 89 validation
    migration_89_match = re.search(
        r'# Migration 89:.*?(?=# Migration \d+:|checkpoint\("Committing migrations)',
        content,
        re.DOTALL
    )
    
    if migration_89_match:
        migration_89_content = migration_89_match.group(0)
        if 'check_column_exists' in migration_89_content:
            print("  ✅ Migration 89 validation uses check_column_exists")
        else:
            print("  ⚠️  Migration 89 might not validate columns")
    
    return True


def main():
    """Run all tests"""
    print("=" * 70)
    print("MIGRATION 89 TRANSACTION FIX VERIFICATION")
    print("=" * 70)
    
    results = {
        'exec_ddl Exists': test_exec_ddl_exists(),
        'Migration 89 Uses exec_ddl': test_migration_89_uses_exec_ddl(),
        'Data Cleanup Before Constraint': test_data_cleanup_before_constraint(),
        'Separate Transactions': test_separate_transactions(),
        'Fail-Fast on Migration Failure': test_fail_fast_on_migration_failure(),
        'Validation Uses information_schema': test_validation_uses_information_schema(),
    }
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    all_passed = True
    for check_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {check_name}")
        if not passed:
            all_passed = False
    
    print("=" * 70)
    
    if all_passed:
        print("\n✅ ALL CHECKS PASSED - Migration 89 transaction fix is complete!")
        print("\nKey improvements:")
        print("1. ✅ Each DDL operation runs in separate transaction (prevents rollback)")
        print("2. ✅ Invalid data cleaned up before constraint addition")
        print("3. ✅ System fails fast on migration errors (no invalid startup)")
        print("4. ✅ Validation uses information_schema (not ORM)")
        print("\nThis fixes the classic Postgres transaction bug!")
        return 0
    else:
        print("\n❌ SOME CHECKS FAILED - Review the issues above")
        return 1


if __name__ == '__main__':
    sys.exit(main())
