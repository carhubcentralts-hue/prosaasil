#!/usr/bin/env python3
"""
Test standalone migration files to ensure they use correct SQLAlchemy syntax
This validates the migration files without requiring a database connection
"""
import sys
import os
import re

def check_migration_file(filename, expected_column, expected_table):
    """Check a standalone migration file for correct syntax"""
    print(f"\n=== Checking {filename} ===")
    
    try:
        with open(filename, 'r') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"  ❌ File not found: {filename}")
        return False
    
    all_ok = True
    
    # Check imports
    if 'from sqlalchemy import text' in content:
        print("  ✅ Imports sqlalchemy.text")
    else:
        print("  ❌ Missing 'from sqlalchemy import text' import")
        all_ok = False
    
    # Check for deprecated db.engine.execute
    if 'db.engine.execute' in content:
        print("  ❌ Uses deprecated db.engine.execute()")
        all_ok = False
    else:
        print("  ✅ Does not use deprecated db.engine.execute()")
    
    # Check for modern db.session.execute(text(...))
    if 'db.session.execute(text(' in content:
        print("  ✅ Uses modern db.session.execute(text(...))")
    else:
        print("  ❌ Does not use db.session.execute(text(...))")
        all_ok = False
    
    # Check for db.session.commit()
    if 'db.session.commit()' in content:
        print("  ✅ Calls db.session.commit()")
    else:
        print("  ⚠️  Missing db.session.commit() - changes may not persist")
        # Not a critical error for DO $$ blocks, but worth noting
    
    # Check for idempotency (DO $$ BEGIN ... IF NOT EXISTS ...)
    if 'DO $$' in content and 'IF NOT EXISTS' in content:
        print("  ✅ Uses idempotent pattern (DO $$ ... IF NOT EXISTS)")
    else:
        print("  ⚠️  May not be fully idempotent")
    
    # Check for expected table and column
    if expected_table in content and expected_column in content:
        print(f"  ✅ Modifies expected table/column: {expected_table}.{expected_column}")
    else:
        print(f"  ❌ Does not modify expected table/column: {expected_table}.{expected_column}")
        all_ok = False
    
    # Check for error handling
    if 'try:' in content and 'except Exception' in content:
        print("  ✅ Has error handling")
    else:
        print("  ⚠️  Missing error handling")
    
    return all_ok

def main():
    """Run all checks"""
    print("=" * 80)
    print("Testing Standalone Migration Files")
    print("=" * 80)
    
    migrations_to_check = [
        ('migration_add_appointment_transcript.py', 'call_transcript', 'appointments'),
        ('migration_add_broadcast_enhancements.py', 'idempotency_key', 'whatsapp_broadcasts'),
    ]
    
    all_passed = True
    for filename, column, table in migrations_to_check:
        result = check_migration_file(filename, column, table)
        if not result:
            all_passed = False
    
    print("\n" + "=" * 80)
    if all_passed:
        print("✅ ALL CHECKS PASSED")
        return 0
    else:
        print("❌ SOME CHECKS FAILED")
        return 1

if __name__ == '__main__':
    sys.exit(main())
