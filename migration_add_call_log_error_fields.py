#!/usr/bin/env python
"""
Migration: Add error tracking fields to call_log table

This migration adds error_message and error_code columns to the call_log table
to enable proper error tracking for failed outbound calls.

ISSUE: PostgreSQL error "column 'error_message' of relation 'call_log' does not exist"
FIX: Add error_message (TEXT) and error_code (VARCHAR) columns

Run with: python migration_add_call_log_error_fields.py
"""
import os
import sys
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
log = logging.getLogger(__name__)

def run_migration():
    """Run the error fields migration"""
    log.info("=" * 80)
    log.info("Migration: Add error tracking fields to call_log")
    log.info("=" * 80)
    
    # Validate DATABASE_URL
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        log.error("❌ DATABASE_URL environment variable is not set!")
        return False
    
    try:
        # Import Flask and create minimal app
        log.info("Creating Flask app context...")
        from server.app_factory import create_minimal_app
        app = create_minimal_app()
        
        with app.app_context():
            from server.db import db
            from sqlalchemy import text
            
            # Check if call_log table exists
            log.info("Checking if call_log table exists...")
            result = db.session.execute(text("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name = 'call_log'
            """))
            
            if not result.fetchone():
                log.error("❌ call_log table does not exist!")
                return False
            
            log.info("✅ call_log table exists")
            
            # List of columns to add
            columns_to_add = [
                ('error_message', 'TEXT', None, 'Error message for failed calls'),
                ('error_code', 'VARCHAR(64)', None, 'Error code for failed calls'),
            ]
            
            columns_added = []
            columns_existed = []
            
            for col_name, col_type, default_val, description in columns_to_add:
                # Check if column already exists
                result = db.session.execute(text("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                      AND table_name = 'call_log' 
                      AND column_name = :col_name
                """), {"col_name": col_name})
                
                if result.fetchone():
                    log.info(f"⏭️  Column '{col_name}' already exists - skipping")
                    columns_existed.append(col_name)
                    continue
                
                # Add the column
                log.info(f"Adding column '{col_name}' ({description})...")
                
                if default_val:
                    sql = f"ALTER TABLE call_log ADD COLUMN {col_name} {col_type} DEFAULT {default_val}"
                else:
                    sql = f"ALTER TABLE call_log ADD COLUMN {col_name} {col_type}"
                
                db.session.execute(text(sql))
                columns_added.append(col_name)
                log.info(f"✅ Added column '{col_name}'")
            
            # Commit all changes
            if columns_added:
                db.session.commit()
                log.info(f"✅ Successfully added {len(columns_added)} column(s) to call_log table")
                log.info(f"   New columns: {', '.join(columns_added)}")
            else:
                log.info("✅ All columns already exist - no changes needed")
            
            if columns_existed:
                log.info(f"   Existing columns: {', '.join(columns_existed)}")
            
            log.info("=" * 80)
            log.info("✅ Migration completed successfully!")
            log.info("=" * 80)
            
            return True
            
    except Exception as e:
        log.error(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
