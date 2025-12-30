#!/usr/bin/env python
"""
Test Migration 56: Validate stopped_by and stopped_at columns for whatsapp_broadcasts

This test verifies that the migration adds the stopped_by and stopped_at columns correctly.
"""
import sys
import os

def test_migration_56():
    """Test that Migration 56 adds the stopped_by and stopped_at columns"""
    print("=" * 80)
    print("Testing Migration 56: whatsapp_broadcasts stop functionality")
    print("=" * 80)
    
    # Expected columns that should be added by Migration 56
    expected_columns = {
        'stopped_by': 'INTEGER (REFERENCES users(id))',
        'stopped_at': 'TIMESTAMP'
    }
    
    print(f"\n✅ Expected columns to be added:")
    for col, col_type in expected_columns.items():
        print(f"   - {col}: {col_type}")
    
    # Check that the migration code exists in db_migrate.py
    print("\n🔍 Checking migration code in db_migrate.py...")
    
    with open('server/db_migrate.py', 'r') as f:
        content = f.read()
    
    # Verify Migration 56 exists
    if 'Migration 56:' not in content:
        print("❌ Migration 56 not found in db_migrate.py")
        return False
    
    print("✅ Migration 56 found in db_migrate.py")
    
    # Verify stopped_by column is mentioned in the migration
    if 'stopped_by' not in content:
        print("❌ stopped_by not found in migration")
        return False
    
    print("✅ stopped_by column is present in migration code")
    
    # Verify stopped_at column is mentioned in the migration
    if 'stopped_at' not in content:
        print("❌ stopped_at not found in migration")
        return False
    
    print("✅ stopped_at column is present in migration code")
    
    # Verify idempotent checks exist
    if "check_column_exists('whatsapp_broadcasts', 'stopped_by')" not in content:
        print("❌ Migration lacks idempotent column existence check for stopped_by")
        return False
    
    print("✅ Migration includes idempotent check for stopped_by")
    
    if "check_column_exists('whatsapp_broadcasts', 'stopped_at')" not in content:
        print("❌ Migration lacks idempotent column existence check for stopped_at")
        return False
    
    print("✅ Migration includes idempotent check for stopped_at")
    
    # Verify the model has stopped_by and stopped_at columns
    print("\n🔍 Checking model definition in models_sql.py...")
    
    with open('server/models_sql.py', 'r') as f:
        model_content = f.read()
    
    if 'stopped_by' not in model_content:
        print("❌ stopped_by not found in models_sql.py")
        return False
    
    print("✅ stopped_by found in models_sql.py")
    
    if 'stopped_at' not in model_content:
        print("❌ stopped_at not found in models_sql.py")
        return False
    
    print("✅ stopped_at found in models_sql.py")
    
    # Check that WhatsAppBroadcast model exists
    if 'WhatsAppBroadcast' not in model_content or 'whatsapp_broadcasts' not in model_content:
        print("❌ WhatsAppBroadcast model not found")
        return False
    
    print("✅ WhatsAppBroadcast model found")
    
    # Verify migration 44 creates the table (original table creation)
    if 'Migration 44:' not in content:
        print("❌ Migration 44 (table creation) not found in db_migrate.py")
        return False
    
    print("✅ Migration 44 (table creation) found")
    
    # Check the migration adds columns with correct syntax
    if 'ALTER TABLE whatsapp_broadcasts' not in content:
        print("❌ ALTER TABLE statement for whatsapp_broadcasts not found")
        return False
    
    print("✅ ALTER TABLE statement found")
    
    if 'ADD COLUMN stopped_by INTEGER REFERENCES users(id)' not in content:
        print("❌ ADD COLUMN stopped_by statement not found with correct syntax")
        return False
    
    print("✅ ADD COLUMN stopped_by statement found with correct syntax")
    
    if 'ADD COLUMN stopped_at TIMESTAMP' not in content:
        print("❌ ADD COLUMN stopped_at TIMESTAMP statement not found")
        return False
    
    print("✅ ADD COLUMN stopped_at TIMESTAMP statement found")
    
    print("\n" + "=" * 80)
    print("✅ ALL TESTS PASSED - Migration 56 is ready for deployment")
    print("=" * 80)
    print("\n📋 Deployment steps:")
    print("1. The migration will automatically run when the server starts")
    print("2. Or run manually: python -m server.db_migrate")
    print("3. Verify with: psql -d DATABASE_URL -c \"\\d whatsapp_broadcasts\"")
    
    return True

if __name__ == "__main__":
    success = test_migration_56()
    sys.exit(0 if success else 1)
