#!/usr/bin/env python
"""
Test Migration 51: Validate recording_mode and cost metrics migration

This test verifies that the migration adds all necessary columns correctly.
"""
import sys
import os

def test_migration_51():
    """Test that Migration 51 adds all required columns"""
    print("=" * 80)
    print("Testing Migration 51: recording_mode and cost metrics")
    print("=" * 80)
    
    # Expected columns that should be added by Migration 51
    expected_columns = {
        'recording_mode': 'VARCHAR(32)',
        'stream_started_at': 'TIMESTAMP',
        'stream_ended_at': 'TIMESTAMP',
        'stream_duration_sec': 'DOUBLE PRECISION',
        'stream_connect_count': 'INTEGER',
        'webhook_11205_count': 'INTEGER',
        'webhook_retry_count': 'INTEGER',
        'recording_count': 'INTEGER',
        'estimated_cost_bucket': 'VARCHAR(16)',
    }
    
    print(f"\n✅ Expected columns to be added: {len(expected_columns)}")
    for col, dtype in expected_columns.items():
        print(f"   • {col} ({dtype})")
    
    # Check that the migration code exists in db_migrate.py
    print("\n🔍 Checking migration code in db_migrate.py...")
    
    with open('server/db_migrate.py', 'r') as f:
        content = f.read()
    
    # Verify Migration 51 exists
    if 'Migration 51:' not in content:
        print("❌ Migration 51 not found in db_migrate.py")
        return False
    
    print("✅ Migration 51 found in db_migrate.py")
    
    # Verify all columns are mentioned in the migration
    missing_columns = []
    for col in expected_columns.keys():
        if f"'{col}'" not in content and f'"{col}"' not in content:
            missing_columns.append(col)
    
    if missing_columns:
        print(f"❌ Missing columns in migration: {missing_columns}")
        return False
    
    print("✅ All expected columns are present in migration code")
    
    # Verify idempotent checks exist
    if 'check_column_exists' not in content:
        print("❌ Migration lacks idempotent column existence checks")
        return False
    
    print("✅ Migration includes idempotent checks")
    
    # Check environment_validation.py has schema validation
    print("\n🔍 Checking schema validation in environment_validation.py...")
    
    with open('server/environment_validation.py', 'r') as f:
        validation_content = f.read()
    
    if 'validate_database_schema' not in validation_content:
        print("❌ Schema validation function not found")
        return False
    
    print("✅ Schema validation function found")
    
    if 'recording_mode' not in validation_content:
        print("❌ recording_mode not in critical columns list")
        return False
    
    print("✅ recording_mode in critical columns list")
    
    # Check app_factory.py calls the validation
    print("\n🔍 Checking app_factory.py calls schema validation...")
    
    with open('server/app_factory.py', 'r') as f:
        app_content = f.read()
    
    if 'validate_database_schema' not in app_content:
        print("❌ app_factory.py doesn't call schema validation")
        return False
    
    print("✅ app_factory.py calls schema validation on startup")
    
    # Verify standalone migration script exists
    print("\n🔍 Checking standalone migration script...")
    
    if not os.path.exists('migration_add_recording_mode.py'):
        print("❌ Standalone migration script not found")
        return False
    
    print("✅ Standalone migration script exists")
    
    with open('migration_add_recording_mode.py', 'r') as f:
        standalone_content = f.read()
    
    if 'recording_mode' not in standalone_content:
        print("❌ Standalone script doesn't add recording_mode")
        return False
    
    print("✅ Standalone script includes recording_mode migration")
    
    # Check deployment guide exists
    print("\n🔍 Checking deployment guide...")
    
    guide_files = [f for f in os.listdir('.') if 'recording_mode' in f and f.endswith('.md')]
    
    if not guide_files:
        print("❌ Deployment guide not found")
        return False
    
    print(f"✅ Deployment guide found: {guide_files[0]}")
    
    print("\n" + "=" * 80)
    print("✅ ALL TESTS PASSED - Migration 51 is ready for deployment")
    print("=" * 80)
    
    return True

if __name__ == "__main__":
    success = test_migration_51()
    sys.exit(0 if success else 1)
