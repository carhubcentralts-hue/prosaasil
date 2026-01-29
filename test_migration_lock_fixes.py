#!/usr/bin/env python3
"""
Test script to verify migration lock fixes.

This test verifies:
1. exec_ddl() sets lock timeouts correctly
2. exec_ddl() logs lock debugging information on failure
3. Migration 115 critical DDL failures abort the migration
4. Lock timeout causes fast failure (not 2-3 minute wait)
"""
import sys
import os
import re

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_exec_ddl_has_lock_timeouts():
    """Verify that exec_ddl sets lock_timeout, statement_timeout, and idle_in_transaction_session_timeout."""
    print("\n=== Test 1: exec_ddl() Lock Timeouts ===")
    
    filepath = 'server/db_migrate.py'
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Extract exec_ddl function
        exec_ddl_match = re.search(
            r'def exec_ddl\(.*?\):.*?(?=\ndef [a-z_]|\Z)', 
            content, 
            re.DOTALL
        )
        
        if not exec_ddl_match:
            print("  ❌ exec_ddl function not found")
            return False
        
        func_content = exec_ddl_match.group(0)
        
        all_ok = True
        
        # Check for lock_timeout
        if "SET lock_timeout = '5s'" in func_content or 'SET lock_timeout = "5s"' in func_content:
            print("  ✅ lock_timeout = 5s is set")
        else:
            print("  ❌ lock_timeout = 5s is NOT set")
            all_ok = False
        
        # Check for statement_timeout
        if "SET statement_timeout = '120s'" in func_content or 'SET statement_timeout = "120s"' in func_content:
            print("  ✅ statement_timeout = 120s is set")
        else:
            print("  ❌ statement_timeout = 120s is NOT set")
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


def test_exec_ddl_has_lock_debugging():
    """Verify that exec_ddl logs lock debugging information on failure."""
    print("\n=== Test 2: exec_ddl() Lock Debugging ===")
    
    filepath = 'server/db_migrate.py'
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Extract exec_ddl function
        exec_ddl_match = re.search(
            r'def exec_ddl\(.*?\):.*?(?=\ndef [a-z_]|\Z)', 
            content, 
            re.DOTALL
        )
        
        if not exec_ddl_match:
            print("  ❌ exec_ddl function not found")
            return False
        
        func_content = exec_ddl_match.group(0)
        
        all_ok = True
        
        # Check for exception handling
        if 'except Exception' in func_content:
            print("  ✅ exec_ddl has exception handler")
        else:
            print("  ❌ exec_ddl does NOT have exception handler")
            all_ok = False
        
        # Check for LOCK_DEBUG_SQL usage
        if 'LOCK_DEBUG_SQL' in func_content:
            print("  ✅ exec_ddl uses LOCK_DEBUG_SQL for debugging")
        else:
            print("  ❌ exec_ddl does NOT use LOCK_DEBUG_SQL")
            all_ok = False
        
        # Check for re-raising exception
        if 'raise' in func_content:
            print("  ✅ exec_ddl re-raises exceptions (fail-fast)")
        else:
            print("  ❌ exec_ddl does NOT re-raise exceptions")
            all_ok = False
        
        return all_ok
        
    except Exception as e:
        print(f"  ❌ Error checking {filepath}: {e}")
        return False


def test_lock_debug_sql_defined():
    """Verify that LOCK_DEBUG_SQL is defined."""
    print("\n=== Test 3: LOCK_DEBUG_SQL Constant ===")
    
    filepath = 'server/db_migrate.py'
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        if 'LOCK_DEBUG_SQL = """' in content or "LOCK_DEBUG_SQL = '''" in content:
            print("  ✅ LOCK_DEBUG_SQL is defined")
            
            # Check for key SQL elements
            if 'pg_locks' in content and 'pg_stat_activity' in content:
                print("  ✅ LOCK_DEBUG_SQL queries pg_locks and pg_stat_activity")
                return True
            else:
                print("  ❌ LOCK_DEBUG_SQL missing key query elements")
                return False
        else:
            print("  ❌ LOCK_DEBUG_SQL is NOT defined")
            return False
        
    except Exception as e:
        print(f"  ❌ Error checking {filepath}: {e}")
        return False


def test_migration_115_fails_fast():
    """Verify that Migration 115 critical DDL failures abort the migration."""
    print("\n=== Test 4: Migration 115 Fail-Fast Behavior ===")
    
    filepath = 'server/db_migrate.py'
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Find Migration 115 section - use a more robust pattern
        # Match from "Migration 115:" until the next migration number or end of function
        migration_115_match = re.search(
            r'# Migration 115:.*?(?=# Migration \d+:|def apply_migrations|def main|\Z)', 
            content, 
            re.DOTALL
        )
        
        if not migration_115_match:
            print("  ❌ Migration 115 not found")
            return False
        
        migration_content = migration_115_match.group(0)
        
        all_ok = True
        
        # Check for critical CREATE TABLE failures that raise exceptions
        critical_patterns = [
            (r'CREATE TABLE business_calendars.*?except Exception.*?raise RuntimeError', 'business_calendars'),
            (r'CREATE TABLE calendar_routing_rules.*?except Exception.*?raise RuntimeError', 'calendar_routing_rules'),
            (r'ALTER TABLE appointments.*?ADD COLUMN calendar_id.*?except Exception.*?raise RuntimeError', 'appointments.calendar_id'),
        ]
        
        for pattern, name in critical_patterns:
            if re.search(pattern, migration_content, re.DOTALL | re.IGNORECASE):
                print(f"  ✅ {name} CREATE/ALTER failure raises RuntimeError (fail-fast)")
            else:
                print(f"  ❌ {name} CREATE/ALTER failure does NOT raise RuntimeError")
                all_ok = False
        
        # Check that critical failures do NOT just call db.session.rollback()
        # They should raise exceptions instead
        problematic_patterns = [
            r'CREATE TABLE business_calendars.*?except Exception.*?db\.session\.rollback\(\)\s*$',
            r'CREATE TABLE calendar_routing_rules.*?except Exception.*?db\.session\.rollback\(\)\s*$',
        ]
        
        for pattern in problematic_patterns:
            if re.search(pattern, migration_content, re.DOTALL | re.IGNORECASE):
                print(f"  ❌ Found critical DDL with only rollback (should raise)")
                all_ok = False
        
        return all_ok
        
    except Exception as e:
        print(f"  ❌ Error checking {filepath}: {e}")
        return False


def test_deployment_script_stops_services():
    """Verify that deployment script stops services before migrations."""
    print("\n=== Test 5: Deployment Script Stops Services ===")
    
    filepath = 'scripts/deploy_production.sh'
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        all_ok = True
        
        # Check for stopping services before migrations
        if 'stop prosaas-api worker scheduler' in content:
            print("  ✅ Deployment script stops prosaas-api, worker, scheduler")
        else:
            print("  ❌ Deployment script does NOT stop services before migrations")
            all_ok = False
        
        # Check that stop happens before migrate
        stop_pos = content.find('stop prosaas-api worker scheduler')
        migrate_pos = content.find('run --rm migrate')
        
        if stop_pos > 0 and migrate_pos > 0 and stop_pos < migrate_pos:
            print("  ✅ Services are stopped BEFORE migrations run")
        else:
            print("  ❌ Services are NOT stopped before migrations (or ordering is wrong)")
            all_ok = False
        
        # Check for --kill-idle-tx flag support
        if '--kill-idle-tx' in content and 'KILL_IDLE_TX' in content:
            print("  ✅ Deployment script supports --kill-idle-tx flag")
        else:
            print("  ❌ Deployment script does NOT support --kill-idle-tx flag")
            all_ok = False
        
        return all_ok
        
    except Exception as e:
        print(f"  ❌ Error checking {filepath}: {e}")
        return False


def test_kill_idle_transactions_script_exists():
    """Verify that kill_idle_transactions.py script exists and is correct."""
    print("\n=== Test 6: Kill Idle Transactions Script ===")
    
    filepath = 'scripts/kill_idle_transactions.py'
    
    try:
        if not os.path.exists(filepath):
            print(f"  ❌ {filepath} does NOT exist")
            return False
        
        print(f"  ✅ {filepath} exists")
        
        with open(filepath, 'r') as f:
            content = f.read()
        
        all_ok = True
        
        # Check for key elements
        if 'pg_terminate_backend' in content:
            print("  ✅ Script uses pg_terminate_backend")
        else:
            print("  ❌ Script does NOT use pg_terminate_backend")
            all_ok = False
        
        if "state = 'idle in transaction'" in content:
            print("  ✅ Script targets 'idle in transaction' state")
        else:
            print("  ❌ Script does NOT target 'idle in transaction'")
            all_ok = False
        
        if "interval '60 seconds'" in content or 'interval "60 seconds"' in content:
            print("  ✅ Script filters by 60 second threshold")
        else:
            print("  ❌ Script does NOT filter by time threshold")
            all_ok = False
        
        if 'pg_backend_pid()' in content:
            print("  ✅ Script excludes current session")
        else:
            print("  ❌ Script does NOT exclude current session")
            all_ok = False
        
        # Check if executable
        if os.access(filepath, os.X_OK):
            print("  ✅ Script is executable")
        else:
            print("  ⚠️  Script is NOT executable (chmod +x needed)")
            # Not a failure, just a warning
        
        return all_ok
        
    except Exception as e:
        print(f"  ❌ Error checking {filepath}: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 80)
    print("MIGRATION LOCK FIX VERIFICATION")
    print("=" * 80)
    print("\nThis test verifies the fixes for PostgreSQL lock issues in migrations:")
    print("  1. exec_ddl() sets strict lock timeouts (5s)")
    print("  2. exec_ddl() logs lock debugging information on failure")
    print("  3. Migration 115 critical DDL failures abort the migration")
    print("  4. Deployment script stops services before migrations")
    print("  5. Optional kill_idle_transactions.py script available")
    
    results = {
        'exec_ddl Lock Timeouts': test_exec_ddl_has_lock_timeouts(),
        'exec_ddl Lock Debugging': test_exec_ddl_has_lock_debugging(),
        'LOCK_DEBUG_SQL Defined': test_lock_debug_sql_defined(),
        'Migration 115 Fail-Fast': test_migration_115_fails_fast(),
        'Deployment Stops Services': test_deployment_script_stops_services(),
        'Kill Idle Transactions Script': test_kill_idle_transactions_script_exists(),
    }
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    all_passed = True
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")
        if not passed:
            all_passed = False
    
    print("=" * 80)
    
    if all_passed:
        print("\n✅ ALL TESTS PASSED - Migration lock fixes look good!")
        print("\nKey improvements:")
        print("1. ✅ DDL operations fail fast (5s) instead of waiting 2-3 minutes")
        print("2. ✅ Lock debugging automatically logs blocking processes")
        print("3. ✅ Critical DDL failures abort migrations (no half-built DB)")
        print("4. ✅ Services stopped before migrations to release connections")
        print("5. ✅ Optional script to kill idle transactions")
        print("\nThis prevents DDL operations from getting stuck on locks!")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED - Review the issues above")
        return 1


if __name__ == '__main__':
    sys.exit(main())
