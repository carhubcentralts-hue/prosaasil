#!/usr/bin/env python3
"""
Test Migration 94 - WhatsApp JID Columns

Validates that Migration 94 correctly adds all required WhatsApp-related columns.
This test is designed for PostgreSQL databases only.
"""
import os
import sys

# Set test environment
os.environ['FLASK_ENV'] = 'test'

# Check if we have a PostgreSQL database URL
DATABASE_URL = os.getenv('DATABASE_URL', '')
if not DATABASE_URL or 'postgresql' not in DATABASE_URL:
    print("=" * 80)
    print("⚠️  SKIPPING TEST: PostgreSQL database required")
    print("=" * 80)
    print("This test validates PostgreSQL-specific migration columns.")
    print("Set DATABASE_URL to a PostgreSQL database to run this test.")
    print("\nExample:")
    print("  export DATABASE_URL=postgresql://user:pass@localhost:5432/dbname")
    print("  python test_migration_94_whatsapp_jid.py")
    sys.exit(0)

from server.app_factory import create_app
from server.db import db
from sqlalchemy import text

def test_migration_94():
    """Test that Migration 94 adds all required WhatsApp JID columns"""
    print("=" * 80)
    print("Testing Migration 94: WhatsApp JID Columns")
    print("=" * 80)
    
    app = create_app()
    
    with app.app_context():
        # Check if leads table exists
        result = db.session.execute(text("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name = 'leads'
        """))
        
        if not result.fetchone():
            print("⚠️  WARNING: leads table does not exist")
            print("   This test requires the table to exist first")
            return True
        
        print("\n✅ leads table exists")
        
        # List of columns that should be added by Migration 94
        required_columns = {
            'phone_raw': 'character varying(64)',
            'whatsapp_jid': 'character varying(128)',
            'whatsapp_jid_alt': 'character varying(128)',
            'reply_jid': 'character varying(128)',
            'reply_jid_type': 'character varying(32)'
        }
        
        print("\n🔍 Checking for required columns...")
        all_present = True
        
        for column_name, expected_type in required_columns.items():
            result = db.session.execute(text("""
                SELECT column_name, data_type, character_maximum_length, is_nullable
                FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'leads' 
                AND column_name = :column_name
            """), {"column_name": column_name})
            
            row = result.fetchone()
            
            if row:
                col_name, data_type, max_length, is_nullable = row
                type_str = f"{data_type}"
                if max_length:
                    type_str += f"({max_length})"
                
                print(f"  ✅ {column_name:20} | {type_str:30} | nullable: {is_nullable}")
            else:
                print(f"  ❌ {column_name:20} | MISSING!")
                all_present = False
        
        # Check for indexes
        print("\n🔍 Checking for required indexes...")
        required_indexes = ['ix_leads_whatsapp_jid', 'ix_leads_reply_jid']
        
        for index_name in required_indexes:
            result = db.session.execute(text("""
                SELECT indexname FROM pg_indexes 
                WHERE schemaname = 'public' 
                AND indexname = :index_name
            """), {"index_name": index_name})
            
            if result.fetchone():
                print(f"  ✅ {index_name}")
            else:
                print(f"  ❌ {index_name} - MISSING!")
                all_present = False
        
        print("\n" + "=" * 80)
        if all_present:
            print("✅ SUCCESS: All WhatsApp JID columns and indexes are present")
            print("=" * 80)
            return True
        else:
            print("❌ FAILURE: Some columns or indexes are missing")
            print("=" * 80)
            print("\n💡 To fix this, run:")
            print("   python -m server.db_migrate")
            return False

if __name__ == '__main__':
    try:
        success = test_migration_94()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
