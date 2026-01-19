#!/usr/bin/env python3
"""
Diagnostic script for attachments table issue
Run: python diagnose_attachments.py
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    print("=" * 60)
    print("🔍 Attachments Table Diagnostic")
    print("=" * 60)
    print()
    
    # Step 1: Check if models can be imported
    print("1️⃣  Checking if models can be imported...")
    try:
        from server.models_sql import Attachment, Contract, ContractFile
        print("✅ Models imported successfully")
        print(f"   - Attachment table name: {Attachment.__tablename__}")
        print(f"   - Contract table name: {Contract.__tablename__}")
        print(f"   - ContractFile table name: {ContractFile.__tablename__}")
    except Exception as e:
        print(f"❌ Failed to import models: {e}")
        return
    print()
    
    # Step 2: Check database connection
    print("2️⃣  Checking database connection...")
    try:
        from server.app_factory import create_minimal_app
        from server.db import db
        from sqlalchemy import text
        
        app = create_minimal_app()
        
        with app.app_context():
            # Test connection
            result = db.session.execute(text("SELECT 1")).scalar()
            print(f"✅ Database connection OK (test query returned: {result})")
            
            # Get database name
            db_name = db.session.execute(text("SELECT current_database()")).scalar()
            print(f"   - Database: {db_name}")
            
            # Get schema search path
            search_path = db.session.execute(text("SHOW search_path")).scalar()
            print(f"   - Search path: {search_path}")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        import traceback
        traceback.print_exc()
        return
    print()
    
    # Step 3: Check if attachments table exists
    print("3️⃣  Checking if attachments table exists...")
    with app.app_context():
        try:
            # Method 1: Using information_schema
            result = db.session.execute(text("""
                SELECT table_name, table_schema 
                FROM information_schema.tables 
                WHERE table_name = 'attachments'
            """)).fetchall()
            
            if result:
                print(f"✅ attachments table found in information_schema:")
                for row in result:
                    print(f"   - Schema: {row[1]}, Table: {row[0]}")
            else:
                print("❌ attachments table NOT found in information_schema")
                
                # List all tables to see what's there
                print("\n   📋 Available tables:")
                tables = db.session.execute(text("""
                    SELECT table_schema, table_name 
                    FROM information_schema.tables 
                    WHERE table_schema IN ('public', current_schema())
                    ORDER BY table_name
                    LIMIT 20
                """)).fetchall()
                for schema, table in tables:
                    print(f"      - {schema}.{table}")
                    
        except Exception as e:
            print(f"❌ Error checking table existence: {e}")
    print()
    
    # Step 4: Try to query the attachments table
    print("4️⃣  Trying to query attachments table...")
    with app.app_context():
        try:
            # Direct SQL query
            count = db.session.execute(text("SELECT COUNT(*) FROM attachments")).scalar()
            print(f"✅ Successfully queried attachments table")
            print(f"   - Row count: {count}")
        except Exception as e:
            print(f"❌ Failed to query attachments table")
            print(f"   - Error: {e}")
            
            # Check the exact error
            error_str = str(e).lower()
            if 'does not exist' in error_str:
                print("   - ⚠️  TABLE DOES NOT EXIST")
            elif 'permission denied' in error_str:
                print("   - ⚠️  PERMISSION DENIED")
            elif 'schema' in error_str:
                print("   - ⚠️  SCHEMA ISSUE")
    print()
    
    # Step 5: Check if contract_files table exists
    print("5️⃣  Checking if contract_files table exists...")
    with app.app_context():
        try:
            count = db.session.execute(text("SELECT COUNT(*) FROM contract_files")).scalar()
            print(f"✅ Successfully queried contract_files table")
            print(f"   - Row count: {count}")
        except Exception as e:
            print(f"❌ Failed to query contract_files table: {e}")
    print()
    
    # Step 6: Check SQLAlchemy metadata
    print("6️⃣  Checking SQLAlchemy metadata...")
    with app.app_context():
        try:
            inspector = db.inspect(db.engine)
            actual_tables = inspector.get_table_names(schema='public')
            
            print(f"✅ Inspector found {len(actual_tables)} tables in 'public' schema")
            
            if 'attachments' in actual_tables:
                print("   - ✅ attachments table IS in actual_tables list")
                
                # Get column info
                columns = inspector.get_columns('attachments', schema='public')
                print(f"   - Columns ({len(columns)}):")
                for col in columns[:5]:  # Show first 5
                    print(f"      • {col['name']}: {col['type']}")
            else:
                print("   - ❌ attachments table is NOT in actual_tables list")
                
                # Check what tables do exist
                if 'contract' in actual_tables:
                    print("   - ℹ️  'contract' table exists")
                if 'contract_files' in actual_tables:
                    print("   - ℹ️  'contract_files' table exists")
                else:
                    print("   - ⚠️  'contract_files' table also missing")
                    
        except Exception as e:
            print(f"❌ Inspector failed: {e}")
    print()
    
    # Step 7: Check migration status
    print("7️⃣  Checking migration indicators...")
    with app.app_context():
        try:
            # Check if lead_notes exists (Migration 75 prerequisite)
            result = db.session.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'lead_notes'
                )
            """)).scalar()
            
            if result:
                print("✅ lead_notes table exists (Migration 75 area)")
            else:
                print("❌ lead_notes table does not exist")
                
            # Check if whatsapp_broadcasts exists
            result = db.session.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'whatsapp_broadcasts'
                )
            """)).scalar()
            
            if result:
                print("✅ whatsapp_broadcasts table exists")
            else:
                print("❌ whatsapp_broadcasts table does not exist")
                
        except Exception as e:
            print(f"❌ Migration check failed: {e}")
    print()
    
    # Final diagnosis
    print("=" * 60)
    print("📊 DIAGNOSIS")
    print("=" * 60)
    print()
    print("Based on the checks above:")
    print()
    print("If attachments table does NOT exist:")
    print("  → Migration 76 was skipped or failed")
    print("  → Solution: Run migrations manually:")
    print("     docker exec prosaas-backend python -m server.db_migrate")
    print()
    print("If attachments table EXISTS but queries fail:")
    print("  → Schema/search_path issue")
    print("  → Solution: Check PostgreSQL schema settings")
    print()
    print("If contract_files exists but attachments doesn't:")
    print("  → Migration 77 ran but Migration 76 didn't")
    print("  → This should NOT happen (76 is prerequisite for 77)")
    print()

if __name__ == '__main__':
    main()
