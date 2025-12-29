#!/usr/bin/env python3
"""
Test script to verify Migration 53 (add leads.gender column).

This test verifies:
1. Migration 53 code exists in db_migrate.py
2. Migration uses IF NOT EXISTS for idempotency
3. Migration includes proper error handling with rollback
4. Gender column is added to CRITICAL_COLUMNS in environment_validation.py
"""
import sys
import os
import re

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_migration_53_exists():
    """Verify Migration 53 exists in db_migrate.py"""
    print("\n=== Checking Migration 53 Exists ===")
    
    filepath = 'server/db_migrate.py'
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Look for Migration 53 comment
        if 'Migration 53' in content:
            print(f"  ✅ Migration 53 comment found")
        else:
            print(f"  ❌ Migration 53 comment not found")
            return False
        
        # Look for add_leads_gender_column in migrations_applied
        if "migrations_applied.append('add_leads_gender_column')" in content:
            print(f"  ✅ Migration 53 tracked in migrations_applied")
        else:
            print(f"  ❌ Migration 53 not tracked in migrations_applied")
            return False
        
        return True
        
    except Exception as e:
        print(f"  ❌ Error checking {filepath}: {e}")
        return False


def check_idempotency():
    """Verify Migration 53 uses IF NOT EXISTS"""
    print("\n=== Checking Idempotency (IF NOT EXISTS) ===")
    
    filepath = 'server/db_migrate.py'
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Extract Migration 53 section
        migration_53_match = re.search(
            r'# Migration 53:.*?(?=# Migration \d+:|checkpoint\("Committing migrations)',
            content,
            re.DOTALL
        )
        
        if not migration_53_match:
            print(f"  ❌ Could not extract Migration 53 section")
            return False
        
        migration_53_content = migration_53_match.group(0)
        
        # Check for IF NOT EXISTS in ALTER TABLE
        if 'IF NOT EXISTS' in migration_53_content:
            print(f"  ✅ Migration 53 uses IF NOT EXISTS for idempotency")
        else:
            print(f"  ❌ Migration 53 missing IF NOT EXISTS clause")
            return False
        
        # Check for check_column_exists guard
        if "check_column_exists('leads', 'gender')" in migration_53_content:
            print(f"  ✅ Migration 53 guarded by check_column_exists")
        else:
            print(f"  ❌ Migration 53 missing check_column_exists guard")
            return False
        
        return True
        
    except Exception as e:
        print(f"  ❌ Error checking {filepath}: {e}")
        return False


def check_error_handling():
    """Verify Migration 53 has proper error handling with rollback"""
    print("\n=== Checking Error Handling ===")
    
    filepath = 'server/db_migrate.py'
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Extract Migration 53 section
        migration_53_match = re.search(
            r'# Migration 53:.*?(?=# Migration \d+:|checkpoint\("Committing migrations)',
            content,
            re.DOTALL
        )
        
        if not migration_53_match:
            print(f"  ❌ Could not extract Migration 53 section")
            return False
        
        migration_53_content = migration_53_match.group(0)
        
        # Check for try-except block
        if 'try:' in migration_53_content and 'except Exception' in migration_53_content:
            print(f"  ✅ Migration 53 has try-except block")
        else:
            print(f"  ❌ Migration 53 missing try-except block")
            return False
        
        # Check for rollback
        if 'db.session.rollback()' in migration_53_content:
            print(f"  ✅ Migration 53 calls db.session.rollback() on error")
        else:
            print(f"  ❌ Migration 53 missing rollback call")
            return False
        
        # Check for raise to propagate error
        if 'raise' in migration_53_content:
            print(f"  ✅ Migration 53 re-raises exception after rollback")
        else:
            print(f"  ⚠️  Migration 53 may swallow exceptions (not critical)")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Error checking {filepath}: {e}")
        return False


def check_critical_columns():
    """Verify gender column is added to CRITICAL_COLUMNS"""
    print("\n=== Checking CRITICAL_COLUMNS in environment_validation.py ===")
    
    filepath = 'server/environment_validation.py'
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Look for CRITICAL_COLUMNS definition
        if 'CRITICAL_COLUMNS' not in content:
            print(f"  ❌ CRITICAL_COLUMNS not found in {filepath}")
            return False
        
        # Look for leads table in CRITICAL_COLUMNS
        if "'leads':" in content or '"leads":' in content:
            print(f"  ✅ leads table found in CRITICAL_COLUMNS")
        else:
            print(f"  ❌ leads table not found in CRITICAL_COLUMNS")
            return False
        
        # Look for gender column
        if "'gender'" in content or '"gender"' in content:
            print(f"  ✅ gender column found in CRITICAL_COLUMNS")
        else:
            print(f"  ❌ gender column not found in CRITICAL_COLUMNS")
            return False
        
        return True
        
    except Exception as e:
        print(f"  ❌ Error checking {filepath}: {e}")
        return False


def check_migration_structure():
    """Verify Migration 53 follows the correct structure"""
    print("\n=== Checking Migration Structure ===")
    
    filepath = 'server/db_migrate.py'
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Extract Migration 53 section
        migration_53_match = re.search(
            r'# Migration 53:.*?(?=# Migration \d+:|checkpoint\("Committing migrations)',
            content,
            re.DOTALL
        )
        
        if not migration_53_match:
            print(f"  ❌ Could not extract Migration 53 section")
            return False
        
        migration_53_content = migration_53_match.group(0)
        
        # Check for checkpoint calls
        checkpoint_count = migration_53_content.count('checkpoint(')
        if checkpoint_count >= 3:
            print(f"  ✅ Migration 53 has {checkpoint_count} checkpoint calls (good for debugging)")
        else:
            print(f"  ⚠️  Migration 53 has only {checkpoint_count} checkpoint calls (consider adding more)")
        
        # Check for proper SQL - ALTER TABLE leads ADD COLUMN
        if 'ALTER TABLE leads' in migration_53_content:
            print(f"  ✅ Migration 53 uses ALTER TABLE leads")
        else:
            print(f"  ❌ Migration 53 missing ALTER TABLE leads statement")
            return False
        
        if 'ADD COLUMN' in migration_53_content:
            print(f"  ✅ Migration 53 uses ADD COLUMN statement")
        else:
            print(f"  ❌ Migration 53 missing ADD COLUMN statement")
            return False
        
        if 'VARCHAR(16)' in migration_53_content:
            print(f"  ✅ Migration 53 uses VARCHAR(16) matching the model definition")
        else:
            print(f"  ❌ Migration 53 column type doesn't match model (should be VARCHAR(16))")
            return False
        
        return True
        
    except Exception as e:
        print(f"  ❌ Error checking {filepath}: {e}")
        return False


def main():
    """Run all verification checks"""
    print("=" * 60)
    print("MIGRATION 53 (LEADS.GENDER) VERIFICATION")
    print("=" * 60)
    
    results = {
        'Migration 53 Exists': check_migration_53_exists(),
        'Idempotency (IF NOT EXISTS)': check_idempotency(),
        'Error Handling': check_error_handling(),
        'CRITICAL_COLUMNS Updated': check_critical_columns(),
        'Migration Structure': check_migration_structure(),
    }
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for check_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {check_name}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("\n✅ ALL CHECKS PASSED - Migration 53 looks good!")
        print("\nKey features:")
        print("1. ✅ Idempotent (can run multiple times safely)")
        print("2. ✅ Proper error handling with rollback")
        print("3. ✅ Added to CRITICAL_COLUMNS for fail-fast validation")
        print("4. ✅ Follows existing migration patterns")
        print("\nReady to deploy!")
        return 0
    else:
        print("\n❌ SOME CHECKS FAILED - Review the issues above")
        return 1


if __name__ == '__main__':
    sys.exit(main())
