#!/usr/bin/env python3
"""
Test script to verify migration lock timeout fix.

This test verifies:
1. RUN_MIGRATIONS env var is checked
2. Migration lock uses pg_try_advisory_lock with retry
3. statement_timeout is set to 120s
4. Graceful skip when lock can't be acquired
5. Enhanced worker logging with WORKER_* prefixes
"""
import sys
import os
import re

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_db_migrate_lock_fix():
    """Verify that db_migrate.apply_migrations() has lock timeout fix"""
    print("\n=== Checking db_migrate.py Lock Timeout Fix ===")
    
    filepath = 'server/db_migrate.py'
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        all_ok = True
        
        # Extract apply_migrations function
        apply_migrations_match = re.search(
            r'def apply_migrations\(\):.*?(?=\ndef [a-z_]|\nif __name__|\Z)', 
            content, 
            re.DOTALL
        )
        
        if not apply_migrations_match:
            print(f"  ❌ apply_migrations function not found")
            return False
        
        func_content = apply_migrations_match.group(0)
        
        # Check for RUN_MIGRATIONS env var check
        if "RUN_MIGRATIONS" in func_content:
            print(f"  ✅ apply_migrations checks RUN_MIGRATIONS env var")
        else:
            print(f"  ❌ apply_migrations does NOT check RUN_MIGRATIONS env var")
            all_ok = False
        
        # Check for statement_timeout setting
        if "statement_timeout" in func_content and "120s" in func_content:
            print(f"  ✅ apply_migrations sets statement_timeout to 120s")
        else:
            print(f"  ❌ apply_migrations doesn't set statement_timeout properly")
            all_ok = False
        
        # Check for pg_try_advisory_lock usage
        if "pg_try_advisory_lock" in func_content:
            print(f"  ✅ apply_migrations uses pg_try_advisory_lock")
        else:
            print(f"  ❌ apply_migrations doesn't use pg_try_advisory_lock")
            all_ok = False
        
        # Check for retry loop with time
        if "while time.time()" in func_content or "LOCK_WAIT_SECONDS" in func_content:
            print(f"  ✅ apply_migrations has retry loop with timeout")
        else:
            print(f"  ❌ apply_migrations missing retry loop")
            all_ok = False
        
        # Check for graceful skip return
        if "return 'skip'" in func_content:
            print(f"  ✅ apply_migrations returns 'skip' when lock can't be acquired")
        else:
            print(f"  ❌ apply_migrations doesn't return 'skip' gracefully")
            all_ok = False
        
        # Check for LOCK_ID constant
        if "LOCK_ID = " in func_content:
            print(f"  ✅ apply_migrations defines LOCK_ID constant")
        else:
            print(f"  ⚠️  apply_migrations should use LOCK_ID constant")
        
        # Check for parameterized unlock
        if "pg_advisory_unlock(:id)" in func_content or 'pg_advisory_unlock(:id)' in func_content:
            print(f"  ✅ apply_migrations uses parameterized unlock")
        else:
            print(f"  ⚠️  apply_migrations should use parameterized unlock")
        
        return all_ok
        
    except Exception as e:
        print(f"  ❌ Error checking {filepath}: {e}")
        return False


def check_app_factory_skip_handling():
    """Verify that app_factory handles 'skip' return value"""
    print("\n=== Checking app_factory.py Skip Handling ===")
    
    filepath = 'server/app_factory.py'
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        all_ok = True
        
        # Check for migrations_result variable
        if "migrations_result = apply_migrations()" in content:
            print(f"  ✅ app_factory captures migration result")
        else:
            print(f"  ❌ app_factory doesn't capture migration result")
            all_ok = False
        
        # Check for skip handling
        if "migrations_result == 'skip'" in content or 'migrations_result == "skip"' in content:
            print(f"  ✅ app_factory checks for 'skip' return value")
        else:
            print(f"  ❌ app_factory doesn't handle 'skip' return value")
            all_ok = False
        
        # Check that it doesn't crash on skip
        if "MIGRATIONS SKIPPED" in content:
            print(f"  ✅ app_factory logs skip gracefully")
        else:
            print(f"  ⚠️  app_factory should log when migrations are skipped")
        
        return all_ok
        
    except Exception as e:
        print(f"  ❌ Error checking {filepath}: {e}")
        return False


def check_docker_compose_run_migrations():
    """Verify that docker-compose files use RUN_MIGRATIONS env var"""
    print("\n=== Checking docker-compose.yml RUN_MIGRATIONS ===")
    
    all_ok = True
    
    for filepath in ['docker-compose.yml', 'docker-compose.prod.yml']:
        try:
            with open(filepath, 'r') as f:
                content = f.read()
            
            # Check for RUN_MIGRATIONS in prosaas-api
            if 'RUN_MIGRATIONS: "1"' in content:
                print(f"  ✅ {filepath} has RUN_MIGRATIONS=1 for API service")
            else:
                print(f"  ❌ {filepath} missing RUN_MIGRATIONS=1 for API")
                all_ok = False
            
            # Check for RUN_MIGRATIONS=0 in worker
            if 'RUN_MIGRATIONS: "0"' in content:
                print(f"  ✅ {filepath} has RUN_MIGRATIONS=0 for other services")
            else:
                print(f"  ⚠️  {filepath} should set RUN_MIGRATIONS=0 for worker/calls")
            
        except Exception as e:
            print(f"  ❌ Error checking {filepath}: {e}")
            all_ok = False
    
    return all_ok


def check_worker_logging():
    """Verify enhanced worker logging with WORKER_* prefixes"""
    print("\n=== Checking tasks_recording.py Worker Logging ===")
    
    filepath = 'server/tasks_recording.py'
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        all_ok = True
        required_logs = [
            'WORKER_PICKED',
            'WORKER_SLOT_ACQUIRED',
            'WORKER_DOWNLOAD_DONE',
            'WORKER_RELEASE_SLOT',
            'WORKER_JOB_FAILED'
        ]
        
        for log_prefix in required_logs:
            if log_prefix in content:
                print(f"  ✅ Found {log_prefix} log")
            else:
                print(f"  ❌ Missing {log_prefix} log")
                all_ok = False
        
        return all_ok
        
    except Exception as e:
        print(f"  ❌ Error checking {filepath}: {e}")
        return False


def main():
    """Run all checks"""
    print("=" * 80)
    print("MIGRATION LOCK TIMEOUT FIX VERIFICATION")
    print("=" * 80)
    
    results = []
    
    # Run all checks
    results.append(("db_migrate lock fix", check_db_migrate_lock_fix()))
    results.append(("app_factory skip handling", check_app_factory_skip_handling()))
    results.append(("docker-compose RUN_MIGRATIONS", check_docker_compose_run_migrations()))
    results.append(("worker logging", check_worker_logging()))
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
        if not passed:
            all_passed = False
    
    print("=" * 80)
    
    if all_passed:
        print("\n🎉 All checks passed! Migration lock timeout fix is complete.")
        return 0
    else:
        print("\n❌ Some checks failed. Please review the issues above.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
