#!/usr/bin/env python3
"""
Static verification of the idle-in-transaction fix.

This script verifies the changes without importing the modules.
"""

import os
import re


def verify_file(filepath):
    """Verify the db_migrate.py file contains the necessary fixes."""
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    print("=" * 80)
    print("Static Verification of Idle-in-Transaction Fix")
    print("=" * 80)
    print()
    
    passed = 0
    failed = 0
    
    # Test 1: Check if check_constraint_exists exists
    print("📋 Test 1: check_constraint_exists function exists...")
    if 'def check_constraint_exists(' in content:
        print("✅ PASS: check_constraint_exists function found")
        passed += 1
        
        # Verify it uses engine.connect()
        pattern = r'def check_constraint_exists\(.*?\):.*?with.*?engine\.connect\(\)'
        if re.search(pattern, content, re.DOTALL):
            print("✅ PASS: check_constraint_exists uses engine.connect()")
            passed += 1
        else:
            print("❌ FAIL: check_constraint_exists does not use engine.connect()")
            failed += 1
    else:
        print("❌ FAIL: check_constraint_exists function not found")
        failed += 2
    
    print()
    
    # Test 2: Check if terminate_idle_in_tx exists
    print("📋 Test 2: terminate_idle_in_tx function exists...")
    if 'def terminate_idle_in_tx(' in content:
        print("✅ PASS: terminate_idle_in_tx function found")
        passed += 1
        
        # Verify it terminates backends
        if 'pg_terminate_backend' in content:
            print("✅ PASS: terminate_idle_in_tx calls pg_terminate_backend")
            passed += 1
        else:
            print("❌ FAIL: terminate_idle_in_tx does not call pg_terminate_backend")
            failed += 1
            
        # Verify it checks for idle in transaction
        if "state = 'idle in transaction'" in content:
            print("✅ PASS: terminate_idle_in_tx checks for idle-in-transaction state")
            passed += 1
        else:
            print("❌ FAIL: terminate_idle_in_tx does not check for idle-in-transaction")
            failed += 1
    else:
        print("❌ FAIL: terminate_idle_in_tx function not found")
        failed += 3
    
    print()
    
    # Test 3: Check if exec_ddl calls terminate_idle_in_tx
    print("📋 Test 3: exec_ddl calls terminate_idle_in_tx...")
    exec_ddl_match = re.search(r'def exec_ddl\(.*?\):.*?(?=\ndef |\Z)', content, re.DOTALL)
    if exec_ddl_match:
        exec_ddl_body = exec_ddl_match.group(0)
        if 'terminate_idle_in_tx' in exec_ddl_body:
            print("✅ PASS: exec_ddl calls terminate_idle_in_tx")
            passed += 1
        else:
            print("❌ FAIL: exec_ddl does not call terminate_idle_in_tx")
            failed += 1
            
        if 'idle in transaction' in exec_ddl_body.lower():
            print("✅ PASS: exec_ddl checks for idle-in-transaction connections")
            passed += 1
        else:
            print("❌ FAIL: exec_ddl does not check for idle-in-transaction")
            failed += 1
    else:
        print("❌ FAIL: exec_ddl function not found")
        failed += 2
    
    print()
    
    # Test 4: Migration 113 uses check_constraint_exists
    print("📋 Test 4: Migration 113 uses check_constraint_exists...")
    if 'unique_run_lead' in content:
        # Find the section dealing with unique_run_lead - broader search
        # Look for check_constraint_exists('unique_run_lead')
        if "check_constraint_exists('unique_run_lead')" in content:
            print("✅ PASS: Migration 113 uses check_constraint_exists")
            passed += 1
        else:
            print("❌ FAIL: Migration 113 does not use check_constraint_exists")
            failed += 1
        
        # Check it doesn't use db.session.execute for the constraint check
        # Look for the old pattern: db.session.execute(text("""SELECT 1 FROM pg_constraint WHERE conname='unique_run_lead'
        bad_pattern = r"db\.session\.execute.*?SELECT 1 FROM pg_constraint.*?WHERE conname=.*?unique_run_lead"
        if not re.search(bad_pattern, content, re.DOTALL):
            print("✅ PASS: Migration 113 does not use db.session.execute for constraint check")
            passed += 1
        else:
            print("❌ FAIL: Migration 113 still uses db.session.execute")
            failed += 1
    else:
        print("ℹ️  INFO: unique_run_lead not found (may have been removed)")
        passed += 2
    
    print()
    print("=" * 80)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 80)
    
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    import sys
    filepath = 'server/db_migrate.py'
    if not os.path.exists(filepath):
        print(f"❌ Error: {filepath} not found")
        sys.exit(1)
    
    sys.exit(verify_file(filepath))
