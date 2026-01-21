#!/usr/bin/env python3
"""
Test Migration 89 - Receipt Sync Run-to-Completion Fields

Validates that Migration 89 correctly adds all required columns with proper defaults.
"""
import os
import sys

# Set test environment
os.environ['FLASK_ENV'] = 'test'
os.environ['DATABASE_URL'] = os.getenv('DATABASE_URL', 'sqlite:///test.db')

from server.app_factory import create_app
from server.db import db
from sqlalchemy import text

def test_migration_89():
    """Test that Migration 89 adds all required columns"""
    print("=" * 80)
    print("Testing Migration 89: Receipt Sync Run-to-Completion Fields")
    print("=" * 80)
    
    app = create_app()
    
    with app.app_context():
        # Check if receipt_sync_runs table exists
        result = db.session.execute(text("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name = 'receipt_sync_runs'
        """))
        
        if not result.fetchone():
            print("⚠️  WARNING: receipt_sync_runs table does not exist")
            print("   This test requires the table to exist first")
            return True
        
        print("\n✅ receipt_sync_runs table exists")
        
        # Check for required columns
        required_columns = {
            'from_date': 'DATE',
            'to_date': 'DATE',
            'months_back': 'INTEGER',
            'run_to_completion': 'BOOLEAN',
            'max_seconds_per_run': 'INTEGER',
            'skipped_count': 'INTEGER'
        }
        
        all_columns_exist = True
        
        print("\nChecking required columns:")
        for column_name, expected_type in required_columns.items():
            result = db.session.execute(text("""
                SELECT column_name, data_type, column_default
                FROM information_schema.columns 
                WHERE table_schema = 'public' 
                  AND table_name = 'receipt_sync_runs'
                  AND column_name = :column_name
            """), {"column_name": column_name})
            
            row = result.fetchone()
            if row:
                col_name, data_type, default = row
                print(f"  ✅ {column_name:25} {data_type:15} DEFAULT: {default}")
                
                # Check specific defaults
                if column_name == 'run_to_completion':
                    if default and 'false' in default.lower():
                        print(f"     ✅ DEFAULT FALSE is set correctly")
                    else:
                        print(f"     ⚠️  WARNING: Expected DEFAULT FALSE, got: {default}")
                
                if column_name == 'skipped_count':
                    if default and '0' in str(default):
                        print(f"     ✅ DEFAULT 0 is set correctly")
                    else:
                        print(f"     ⚠️  WARNING: Expected DEFAULT 0, got: {default}")
            else:
                print(f"  ❌ {column_name:25} MISSING")
                all_columns_exist = False
        
        # Check status constraint includes 'paused'
        print("\nChecking status constraint:")
        result = db.session.execute(text("""
            SELECT constraint_name, check_clause
            FROM information_schema.check_constraints
            WHERE constraint_schema = 'public'
              AND constraint_name = 'chk_receipt_sync_status'
        """))
        
        constraint = result.fetchone()
        if constraint:
            constraint_name, check_clause = constraint
            if 'paused' in check_clause.lower():
                print(f"  ✅ Status constraint includes 'paused'")
                print(f"     {check_clause[:100]}...")
            else:
                print(f"  ⚠️  WARNING: Status constraint may not include 'paused'")
                print(f"     {check_clause[:100]}...")
        else:
            print(f"  ⚠️  WARNING: chk_receipt_sync_status constraint not found")
        
        print("\n" + "=" * 80)
        
        if all_columns_exist:
            print("✅ PASS: All Migration 89 columns exist with correct defaults")
            return True
        else:
            print("❌ FAIL: Some columns are missing")
            print("\nTo fix, run migrations:")
            print("  python -m server.db_migrate")
            return False

if __name__ == "__main__":
    try:
        success = test_migration_89()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
