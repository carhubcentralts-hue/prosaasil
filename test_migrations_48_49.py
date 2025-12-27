#!/usr/bin/env python3
"""
Test script to verify migrations 48 and 49 are correctly implemented
- Migration 48: call_transcript column in appointments
- Migration 49: idempotency_key column in whatsapp_broadcasts

This test checks:
1. Migrations are present in db_migrate.py
2. Migrations use proper idempotent patterns (check_column_exists)
3. Migrations have proper error handling with rollback
4. Index creation for idempotency_key uses IF NOT EXISTS
"""
import sys
import os
import re

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_migration_48():
    """Check Migration 48: call_transcript column"""
    print("\n=== Checking Migration 48: call_transcript ===")
    
    with open('server/db_migrate.py', 'r') as f:
        content = f.read()
    
    all_ok = True
    
    # Find Migration 48 section
    migration_48_pattern = r'# Migration 48:.*?(?=# Migration 49:|checkpoint\("Committing)'
    migration_48_match = re.search(migration_48_pattern, content, re.DOTALL)
    
    if not migration_48_match:
        print("  ❌ Migration 48 not found in db_migrate.py")
        return False
    
    migration_48_text = migration_48_match.group(0)
    
    # Check for checkpoint
    if 'checkpoint("Migration 48:' in migration_48_text:
        print("  ✅ Migration 48 has checkpoint logging")
    else:
        print("  ❌ Migration 48 missing checkpoint logging")
        all_ok = False
    
    # Check for check_column_exists
    if 'check_column_exists' in migration_48_text and "'appointments'" in migration_48_text and "'call_transcript'" in migration_48_text:
        print("  ✅ Migration 48 uses check_column_exists for idempotency")
    else:
        print("  ❌ Migration 48 doesn't properly check column existence")
        all_ok = False
    
    # Check for ALTER TABLE
    if 'ALTER TABLE appointments' in migration_48_text and 'ADD COLUMN call_transcript TEXT' in migration_48_text:
        print("  ✅ Migration 48 adds call_transcript column correctly")
    else:
        print("  ❌ Migration 48 doesn't add call_transcript column properly")
        all_ok = False
    
    # Check for error handling
    if 'try:' in migration_48_text and 'except Exception' in migration_48_text and 'db.session.rollback()' in migration_48_text:
        print("  ✅ Migration 48 has proper error handling with rollback")
    else:
        print("  ❌ Migration 48 missing proper error handling")
        all_ok = False
    
    # Check for migrations_applied append
    if 'migrations_applied.append' in migration_48_text and 'add_appointments_call_transcript' in migration_48_text:
        print("  ✅ Migration 48 appends to migrations_applied")
    else:
        print("  ❌ Migration 48 doesn't append to migrations_applied")
        all_ok = False
    
    return all_ok

def check_migration_49():
    """Check Migration 49: idempotency_key column"""
    print("\n=== Checking Migration 49: idempotency_key ===")
    
    with open('server/db_migrate.py', 'r') as f:
        content = f.read()
    
    all_ok = True
    
    # Find Migration 49 section
    migration_49_pattern = r'# Migration 49:.*?(?=checkpoint\("Committing)'
    migration_49_match = re.search(migration_49_pattern, content, re.DOTALL)
    
    if not migration_49_match:
        print("  ❌ Migration 49 not found in db_migrate.py")
        return False
    
    migration_49_text = migration_49_match.group(0)
    
    # Check for checkpoint
    if 'checkpoint("Migration 49:' in migration_49_text:
        print("  ✅ Migration 49 has checkpoint logging")
    else:
        print("  ❌ Migration 49 missing checkpoint logging")
        all_ok = False
    
    # Check for check_column_exists
    if 'check_column_exists' in migration_49_text and "'whatsapp_broadcasts'" in migration_49_text and "'idempotency_key'" in migration_49_text:
        print("  ✅ Migration 49 uses check_column_exists for idempotency")
    else:
        print("  ❌ Migration 49 doesn't properly check column existence")
        all_ok = False
    
    # Check for ALTER TABLE
    if 'ALTER TABLE whatsapp_broadcasts' in migration_49_text and 'ADD COLUMN idempotency_key VARCHAR(64)' in migration_49_text:
        print("  ✅ Migration 49 adds idempotency_key column correctly")
    else:
        print("  ❌ Migration 49 doesn't add idempotency_key column properly")
        all_ok = False
    
    # Check for index creation with IF NOT EXISTS
    if 'CREATE INDEX IF NOT EXISTS' in migration_49_text and 'idx_wa_broadcast_idempotency' in migration_49_text:
        print("  ✅ Migration 49 creates index with IF NOT EXISTS")
    else:
        print("  ❌ Migration 49 doesn't create index properly")
        all_ok = False
    
    # Check for error handling
    if 'try:' in migration_49_text and 'except Exception' in migration_49_text and 'db.session.rollback()' in migration_49_text:
        print("  ✅ Migration 49 has proper error handling with rollback")
    else:
        print("  ❌ Migration 49 missing proper error handling")
        all_ok = False
    
    # Check for migrations_applied append
    if 'migrations_applied.append' in migration_49_text and 'add_whatsapp_broadcasts_idempotency_key' in migration_49_text:
        print("  ✅ Migration 49 appends to migrations_applied")
    else:
        print("  ❌ Migration 49 doesn't append to migrations_applied")
        all_ok = False
    
    return all_ok

def check_models_have_columns():
    """Verify that the models define these columns"""
    print("\n=== Checking Model Definitions ===")
    
    with open('server/models_sql.py', 'r') as f:
        content = f.read()
    
    all_ok = True
    
    # Check for call_transcript in Appointment model
    if 'call_transcript = db.Column(db.Text)' in content:
        print("  ✅ Appointment model defines call_transcript column")
    else:
        print("  ❌ Appointment model missing call_transcript column")
        all_ok = False
    
    # Check for idempotency_key in WhatsAppBroadcast model
    if 'idempotency_key = db.Column(db.String(64)' in content:
        print("  ✅ WhatsAppBroadcast model defines idempotency_key column")
    else:
        print("  ❌ WhatsAppBroadcast model missing idempotency_key column")
        all_ok = False
    
    return all_ok

def main():
    """Run all checks"""
    print("=" * 60)
    print("Testing Migrations 48 and 49")
    print("=" * 60)
    
    results = []
    
    # Check models
    results.append(("Model Definitions", check_models_have_columns()))
    
    # Check migrations
    results.append(("Migration 48", check_migration_48()))
    results.append(("Migration 49", check_migration_49()))
    
    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {name}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("\n✅ All checks passed! Migrations 48 and 49 are correctly implemented.")
        return 0
    else:
        print("\n❌ Some checks failed. Please review the migration implementation.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
