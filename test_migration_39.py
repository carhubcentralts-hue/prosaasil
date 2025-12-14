#!/usr/bin/env python3
"""
Test Migration 39 - Verify missing columns are added to call_log table

This test verifies that:
1. Migration 39 adds the missing columns (audio_bytes_len, audio_duration_sec, transcript_source)
2. The migration is idempotent (can be run multiple times safely)
3. All columns exist in the database after migration
"""

import os
import sys

# Set migration mode
os.environ['MIGRATION_MODE'] = '1'
os.environ['ASYNC_LOG_QUEUE'] = '0'

def test_migration_39():
    """Test that migration 39 adds missing columns to call_log"""
    print("=" * 80)
    print("TEST: Migration 39 - Missing call_log columns")
    print("=" * 80)
    
    try:
        # Import after setting environment
        from server.app_factory import create_minimal_app
        from server.db_migrate import apply_migrations, check_column_exists, check_table_exists
        from sqlalchemy import text
        from server.db import db
        
        app = create_minimal_app()
        
        with app.app_context():
            print("\n1. Checking if call_log table exists...")
            if not check_table_exists('call_log'):
                print("⚠️  call_log table does not exist - skipping test")
                print("   (This is expected for new/empty databases)")
                return True
            
            print("✅ call_log table exists")
            
            print("\n2. Running migrations...")
            migrations = apply_migrations()
            print(f"✅ Applied {len(migrations)} migrations")
            
            print("\n3. Verifying migration 39 columns exist...")
            required_columns = {
                'audio_bytes_len': 'BIGINT',
                'audio_duration_sec': 'DOUBLE PRECISION',
                'transcript_source': 'VARCHAR(32)',
                'recording_sid': 'VARCHAR(64)'  # From migration 38, but verify
            }
            
            all_exist = True
            for column_name, expected_type in required_columns.items():
                exists = check_column_exists('call_log', column_name)
                if exists:
                    print(f"   ✅ {column_name} exists")
                else:
                    print(f"   ❌ {column_name} MISSING!")
                    all_exist = False
            
            if not all_exist:
                print("\n❌ TEST FAILED: Some columns are missing")
                return False
            
            print("\n4. Querying column details from information_schema...")
            result = db.session.execute(text("""
                SELECT column_name, data_type, character_maximum_length
                FROM information_schema.columns
                WHERE table_name='call_log'
                AND column_name IN ('recording_sid','audio_bytes_len','audio_duration_sec','transcript_source')
                ORDER BY column_name
            """))
            
            rows = result.fetchall()
            print("\n   Column details:")
            for row in rows:
                col_name = row[0]
                data_type = row[1]
                max_length = row[2] if len(row) > 2 else None
                if max_length:
                    print(f"   - {col_name}: {data_type}({max_length})")
                else:
                    print(f"   - {col_name}: {data_type}")
            
            print("\n5. Testing idempotency - running migrations again...")
            migrations2 = apply_migrations()
            print(f"✅ Second run applied {len(migrations2)} migrations (should be 0 or minimal)")
            
            print("\n6. Verifying columns still exist after second run...")
            for column_name, _ in required_columns.items():
                exists = check_column_exists('call_log', column_name)
                if not exists:
                    print(f"   ❌ {column_name} disappeared after second migration!")
                    return False
            print("   ✅ All columns still exist")
            
            print("\n" + "=" * 80)
            print("✅ TEST PASSED: Migration 39 successful")
            print("=" * 80)
            return True
            
    except Exception as e:
        print("\n" + "=" * 80)
        print(f"❌ TEST FAILED: {e}")
        print("=" * 80)
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_migration_39()
    sys.exit(0 if success else 1)
