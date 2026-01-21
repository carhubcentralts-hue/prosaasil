#!/usr/bin/env python3
"""
Diagnostic script for attachments table issue
Run: python diagnose_attachments.py
"""
import os
import sys
import logging

logger = logging.getLogger(__name__)


# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    logger.info("=" * 60)
    logger.info("🔍 Attachments Table Diagnostic")
    logger.info("=" * 60)
    logger.info()
    
    # Step 1: Check if models can be imported
    logger.info("1️⃣  Checking if models can be imported...")
    try:
        from server.models_sql import Attachment, Contract, ContractFile
        logger.info("✅ Models imported successfully")
        logger.info(f"   - Attachment table name: {Attachment.__tablename__}")
        logger.info(f"   - Contract table name: {Contract.__tablename__}")
        logger.info(f"   - ContractFile table name: {ContractFile.__tablename__}")
    except Exception as e:
        logger.error(f"❌ Failed to import models: {e}")
        return
    logger.info()
    
    # Step 2: Check database connection
    logger.info("2️⃣  Checking database connection...")
    try:
        from server.app_factory import create_minimal_app
        from server.db import db
        from sqlalchemy import text
        
        app = create_minimal_app()
        
        with app.app_context():
            # Test connection
            result = db.session.execute(text("SELECT 1")).scalar()
            logger.info(f"✅ Database connection OK (test query returned: {result})")
            
            # Get database name
            db_name = db.session.execute(text("SELECT current_database()")).scalar()
            logger.info(f"   - Database: {db_name}")
            
            # Get schema search path
            search_path = db.session.execute(text("SHOW search_path")).scalar()
            logger.info(f"   - Search path: {search_path}")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        import traceback
        traceback.print_exc()
        return
    logger.info()
    
    # Step 3: Check if attachments table exists
    logger.info("3️⃣  Checking if attachments table exists...")
    with app.app_context():
        try:
            # Method 1: Using information_schema
            result = db.session.execute(text("""
                SELECT table_name, table_schema 
                FROM information_schema.tables 
                WHERE table_name = 'attachments'
            """)).fetchall()
            
            if result:
                logger.info(f"✅ attachments table found in information_schema:")
                for row in result:
                    logger.info(f"   - Schema: {row[1]}, Table: {row[0]}")
            else:
                logger.error("❌ attachments table NOT found in information_schema")
                
                # List all tables to see what's there
                logger.info("\n   📋 Available tables:")
                tables = db.session.execute(text("""
                    SELECT table_schema, table_name 
                    FROM information_schema.tables 
                    WHERE table_schema IN ('public', current_schema())
                    ORDER BY table_name
                    LIMIT 20
                """)).fetchall()
                for schema, table in tables:
                    logger.info(f"      - {schema}.{table}")
                    
        except Exception as e:
            logger.error(f"❌ Error checking table existence: {e}")
    logger.info()
    
    # Step 4: Try to query the attachments table
    logger.info("4️⃣  Trying to query attachments table...")
    with app.app_context():
        try:
            # Direct SQL query
            count = db.session.execute(text("SELECT COUNT(*) FROM attachments")).scalar()
            logger.info(f"✅ Successfully queried attachments table")
            logger.info(f"   - Row count: {count}")
        except Exception as e:
            logger.error(f"❌ Failed to query attachments table")
            logger.error(f"   - Error: {e}")
            
            # Check the exact error
            error_str = str(e).lower()
            if 'does not exist' in error_str:
                logger.warning("   - ⚠️  TABLE DOES NOT EXIST")
            elif 'permission denied' in error_str:
                logger.warning("   - ⚠️  PERMISSION DENIED")
            elif 'schema' in error_str:
                logger.warning("   - ⚠️  SCHEMA ISSUE")
    logger.info()
    
    # Step 5: Check if contract_files table exists
    logger.info("5️⃣  Checking if contract_files table exists...")
    with app.app_context():
        try:
            count = db.session.execute(text("SELECT COUNT(*) FROM contract_files")).scalar()
            logger.info(f"✅ Successfully queried contract_files table")
            logger.info(f"   - Row count: {count}")
        except Exception as e:
            logger.error(f"❌ Failed to query contract_files table: {e}")
    logger.info()
    
    # Step 6: Check SQLAlchemy metadata
    logger.info("6️⃣  Checking SQLAlchemy metadata...")
    with app.app_context():
        try:
            inspector = db.inspect(db.engine)
            actual_tables = inspector.get_table_names(schema='public')
            
            logger.info(f"✅ Inspector found {len(actual_tables)} tables in 'public' schema")
            
            if 'attachments' in actual_tables:
                logger.info("   - ✅ attachments table IS in actual_tables list")
                
                # Get column info
                columns = inspector.get_columns('attachments', schema='public')
                logger.info(f"   - Columns ({len(columns)}):")
                for col in columns[:5]:  # Show first 5
                    logger.info(f"      • {col['name']}: {col['type']}")
            else:
                logger.error("   - ❌ attachments table is NOT in actual_tables list")
                
                # Check what tables do exist
                if 'contract' in actual_tables:
                    logger.info("   - ℹ️  'contract' table exists")
                if 'contract_files' in actual_tables:
                    logger.info("   - ℹ️  'contract_files' table exists")
                else:
                    logger.warning("   - ⚠️  'contract_files' table also missing")
                    
        except Exception as e:
            logger.error(f"❌ Inspector failed: {e}")
    logger.info()
    
    # Step 7: Check migration status
    logger.info("7️⃣  Checking migration indicators...")
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
                logger.info("✅ lead_notes table exists (Migration 75 area)")
            else:
                logger.error("❌ lead_notes table does not exist")
                
            # Check if whatsapp_broadcasts exists
            result = db.session.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'whatsapp_broadcasts'
                )
            """)).scalar()
            
            if result:
                logger.info("✅ whatsapp_broadcasts table exists")
            else:
                logger.error("❌ whatsapp_broadcasts table does not exist")
                
        except Exception as e:
            logger.error(f"❌ Migration check failed: {e}")
    logger.info()
    
    # Final diagnosis
    logger.info("=" * 60)
    logger.info("📊 DIAGNOSIS")
    logger.info("=" * 60)
    logger.info()
    logger.info("Based on the checks above:")
    logger.info()
    logger.info("If attachments table does NOT exist:")
    logger.error("  → Migration 76 was skipped or failed")
    logger.info("  → Solution: Run migrations manually:")
    logger.info("     docker exec prosaas-backend python -m server.db_migrate")
    logger.info()
    logger.info("If attachments table EXISTS but queries fail:")
    logger.info("  → Schema/search_path issue")
    logger.info("  → Solution: Check PostgreSQL schema settings")
    logger.info()
    logger.info("If contract_files exists but attachments doesn't:")
    logger.info("  → Migration 77 ran but Migration 76 didn't")
    logger.info("  → This should NOT happen (76 is prerequisite for 77)")
    logger.info()

if __name__ == '__main__':
    main()
