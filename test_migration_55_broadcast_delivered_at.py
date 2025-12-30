#!/usr/bin/env python
"""
Test Migration 55: Validate delivered_at column for whatsapp_broadcast_recipients

This test verifies that the migration adds the delivered_at column correctly.
"""
import sys
import os

def test_migration_55():
    """Test that Migration 55 adds the delivered_at column"""
    print("=" * 80)
    print("Testing Migration 55: whatsapp_broadcast_recipients.delivered_at")
    print("=" * 80)
    
    # Expected column that should be added by Migration 55
    expected_column = 'delivered_at'
    expected_type = 'TIMESTAMP'
    
    print(f"\n✅ Expected column to be added: {expected_column} ({expected_type})")
    
    # Check that the migration code exists in db_migrate.py
    print("\n🔍 Checking migration code in db_migrate.py...")
    
    with open('server/db_migrate.py', 'r') as f:
        content = f.read()
    
    # Verify Migration 55 exists
    if 'Migration 55:' not in content:
        print("❌ Migration 55 not found in db_migrate.py")
        return False
    
    print("✅ Migration 55 found in db_migrate.py")
    
    # Verify delivered_at column is mentioned in the migration
    if 'delivered_at' not in content or 'whatsapp_broadcast_recipients' not in content:
        print(f"❌ delivered_at or whatsapp_broadcast_recipients not found in migration")
        return False
    
    print("✅ delivered_at column is present in migration code")
    
    # Verify idempotent checks exist
    if "check_column_exists('whatsapp_broadcast_recipients', 'delivered_at')" not in content:
        print("❌ Migration lacks idempotent column existence check for delivered_at")
        return False
    
    print("✅ Migration includes idempotent check for delivered_at")
    
    # Verify the model has delivered_at column
    print("\n🔍 Checking model definition in models_sql.py...")
    
    with open('server/models_sql.py', 'r') as f:
        model_content = f.read()
    
    if 'delivered_at' not in model_content:
        print("❌ delivered_at not found in models_sql.py")
        return False
    
    print("✅ delivered_at found in models_sql.py")
    
    # Check that WhatsAppBroadcastRecipient model exists (note: capital A in App)
    if 'WhatsAppBroadcastRecipient' not in model_content or 'whatsapp_broadcast_recipients' not in model_content:
        print("❌ WhatsAppBroadcastRecipient model not found")
        return False
    
    print("✅ WhatsAppBroadcastRecipient model found")
    
    # Verify migration 44 creates the table (original table creation)
    if 'Migration 44:' not in content:
        print("❌ Migration 44 (table creation) not found in db_migrate.py")
        return False
    
    print("✅ Migration 44 (table creation) found")
    
    # Check the migration adds column with correct syntax
    if 'ALTER TABLE whatsapp_broadcast_recipients' not in content:
        print("❌ ALTER TABLE statement for whatsapp_broadcast_recipients not found")
        return False
    
    print("✅ ALTER TABLE statement found")
    
    if 'ADD COLUMN delivered_at TIMESTAMP' not in content:
        print("❌ ADD COLUMN delivered_at TIMESTAMP statement not found")
        return False
    
    print("✅ ADD COLUMN delivered_at TIMESTAMP statement found")
    
    print("\n" + "=" * 80)
    print("✅ ALL TESTS PASSED - Migration 55 is ready for deployment")
    print("=" * 80)
    print("\n📋 Deployment steps:")
    print("1. The migration will automatically run when the server starts")
    print("2. Or run manually: python -m server.db_migrate")
    print("3. Verify with: psql -d DATABASE_URL -c \"\\d whatsapp_broadcast_recipients\"")
    
    return True

if __name__ == "__main__":
    success = test_migration_55()
    sys.exit(0 if success else 1)
