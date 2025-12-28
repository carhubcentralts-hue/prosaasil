#!/usr/bin/env python3
"""
Test script to verify Migration 50 is correctly implemented
- Migration 50: lead_id and dynamic_summary columns in appointments

This test checks:
1. Migration is present in db_migrate.py
2. Migration uses proper idempotent patterns (check_column_exists)
3. Migration has proper error handling with rollback
4. Index creation for lead_id uses IF NOT EXISTS
5. Foreign key constraint is properly defined
"""
import sys
import os
import re

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_migration_50():
    """Check Migration 50: lead_id and dynamic_summary columns"""
    print("\n=== Checking Migration 50: lead_id and dynamic_summary ===")
    
    with open('server/db_migrate.py', 'r') as f:
        content = f.read()
    
    all_ok = True
    
    # Find Migration 50 section - look for it specifically until the "Committing migrations" checkpoint
    # This is more robust than looking for the next migration number
    migration_50_pattern = r'# Migration 50:.*?checkpoint\("Committing migrations'
    migration_50_match = re.search(migration_50_pattern, content, re.DOTALL)
    
    if not migration_50_match:
        print("  ❌ Migration 50 not found in db_migrate.py")
        return False
    
    migration_50_text = migration_50_match.group(0)
    print("  ✅ Migration 50 found in db_migrate.py")
    
    # Check for checkpoint
    if 'checkpoint("Migration 50:' in migration_50_text:
        print("  ✅ Migration 50 has checkpoint logging")
    else:
        print("  ❌ Migration 50 missing checkpoint logging")
        all_ok = False
    
    # Check for check_table_exists
    if 'check_table_exists' in migration_50_text and "'appointments'" in migration_50_text:
        print("  ✅ Migration 50 checks if appointments table exists")
    else:
        print("  ❌ Migration 50 doesn't check table existence")
        all_ok = False
    
    # Check for lead_id column
    if 'check_column_exists' in migration_50_text and "'lead_id'" in migration_50_text:
        print("  ✅ Migration 50 checks for lead_id column existence")
    else:
        print("  ❌ Migration 50 doesn't check lead_id column existence")
        all_ok = False
    
    # Check for ALTER TABLE with lead_id
    if 'ALTER TABLE appointments' in migration_50_text and 'ADD COLUMN lead_id INTEGER REFERENCES leads(id)' in migration_50_text:
        print("  ✅ Migration 50 adds lead_id column with foreign key correctly")
    else:
        print("  ❌ Migration 50 doesn't add lead_id column properly")
        all_ok = False
    
    # Check for lead_id index
    if 'CREATE INDEX IF NOT EXISTS' in migration_50_text and 'idx_appointments_lead_id' in migration_50_text:
        print("  ✅ Migration 50 creates index on lead_id with IF NOT EXISTS")
    else:
        print("  ❌ Migration 50 doesn't create lead_id index properly")
        all_ok = False
    
    # Check for dynamic_summary column
    if 'check_column_exists' in migration_50_text and "'dynamic_summary'" in migration_50_text:
        print("  ✅ Migration 50 checks for dynamic_summary column existence")
    else:
        print("  ❌ Migration 50 doesn't check dynamic_summary column existence")
        all_ok = False
    
    # Check for ALTER TABLE with dynamic_summary
    if 'ALTER TABLE appointments' in migration_50_text and 'ADD COLUMN dynamic_summary TEXT' in migration_50_text:
        print("  ✅ Migration 50 adds dynamic_summary column correctly")
    else:
        print("  ❌ Migration 50 doesn't add dynamic_summary column properly")
        all_ok = False
    
    # Check for error handling
    if 'try:' in migration_50_text and 'except Exception' in migration_50_text and 'db.session.rollback()' in migration_50_text:
        print("  ✅ Migration 50 has proper error handling with rollback")
    else:
        print("  ❌ Migration 50 missing proper error handling")
        all_ok = False
    
    # Check for migrations_applied append
    if 'migrations_applied.append' in migration_50_text and 'add_appointments_lead_id' in migration_50_text:
        print("  ✅ Migration 50 appends lead_id to migrations_applied")
    else:
        print("  ❌ Migration 50 doesn't append lead_id to migrations_applied")
        all_ok = False
    
    if 'migrations_applied.append' in migration_50_text and 'add_appointments_dynamic_summary' in migration_50_text:
        print("  ✅ Migration 50 appends dynamic_summary to migrations_applied")
    else:
        print("  ❌ Migration 50 doesn't append dynamic_summary to migrations_applied")
        all_ok = False
    
    # Check for completion checkpoint
    if 'checkpoint("✅ Migration 50 completed' in migration_50_text:
        print("  ✅ Migration 50 has completion checkpoint")
    else:
        print("  ❌ Migration 50 missing completion checkpoint")
        all_ok = False
    
    return all_ok

def check_models_have_columns():
    """Verify that the Appointment model defines these columns"""
    print("\n=== Checking Appointment Model Definitions ===")
    
    with open('server/models_sql.py', 'r') as f:
        content = f.read()
    
    all_ok = True
    
    # Check for lead_id in Appointment model (flexible matching)
    if 'lead_id = db.Column' in content and 'db.ForeignKey("leads.id")' in content:
        print("  ✅ Appointment model defines lead_id column with foreign key")
    else:
        print("  ❌ Appointment model missing lead_id column")
        all_ok = False
    
    # Check for dynamic_summary in Appointment model (flexible matching)
    if 'dynamic_summary = db.Column' in content and 'db.Text' in content:
        print("  ✅ Appointment model defines dynamic_summary column")
    else:
        print("  ❌ Appointment model missing dynamic_summary column")
        all_ok = False
    
    return all_ok

def check_deprecated_file_removed():
    """Check that the deprecated migration file was removed"""
    print("\n=== Checking Deprecated Files ===")
    
    deprecated_file = 'migration_add_appointment_dynamic_summary.py'
    
    if os.path.exists(deprecated_file):
        print(f"  ❌ Deprecated file still exists: {deprecated_file}")
        return False
    else:
        print(f"  ✅ Deprecated file removed: {deprecated_file}")
        return True

def main():
    """Run all checks"""
    print("=" * 60)
    print("Testing Migration 50: appointments.lead_id and dynamic_summary")
    print("=" * 60)
    
    results = []
    
    # Check models
    results.append(("Appointment Model Definitions", check_models_have_columns()))
    
    # Check migration
    results.append(("Migration 50 Implementation", check_migration_50()))
    
    # Check deprecated file removed
    results.append(("Deprecated File Removed", check_deprecated_file_removed()))
    
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
        print("\n✅ All checks passed! Migration 50 is correctly implemented.")
        print("\n📋 Migration 50 will:")
        print("  1. Add lead_id column to appointments table (INTEGER with FK to leads)")
        print("  2. Create index idx_appointments_lead_id for performance")
        print("  3. Add dynamic_summary column to appointments table (TEXT)")
        print("  4. Run idempotently (safe to run multiple times)")
        print("  5. Rollback automatically on any error")
        return 0
    else:
        print("\n❌ Some checks failed. Please review the migration implementation.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
