#!/usr/bin/env python
"""
Migration 51: Add recording_mode and cost metrics columns to call_log table

This migration adds the missing recording_mode column and all related
Twilio cost tracking fields to the call_log table.

ISSUE: PostgreSQL error "column call_log.recording_mode does not exist"
FIX: Add recording_mode and other cost metric columns

Run with: python migration_add_recording_mode.py
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
    """Run the recording_mode migration"""
    log.info("=" * 80)
    log.info("Migration 51: Add recording_mode and cost metrics to call_log")
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
                ('recording_mode', 'VARCHAR(32)', None, 'Recording mode tracking'),
                ('stream_started_at', 'TIMESTAMP', None, 'WebSocket stream start time'),
                ('stream_ended_at', 'TIMESTAMP', None, 'WebSocket stream end time'),
                ('stream_duration_sec', 'DOUBLE PRECISION', None, 'Stream duration in seconds'),
                ('stream_connect_count', 'INTEGER', '0', 'WebSocket reconnection count'),
                ('webhook_11205_count', 'INTEGER', '0', 'Twilio 11205 error count'),
                ('webhook_retry_count', 'INTEGER', '0', 'Webhook retry count'),
                ('recording_count', 'INTEGER', '0', 'Number of recordings created'),
                ('estimated_cost_bucket', 'VARCHAR(16)', None, 'Cost classification (LOW/MED/HIGH)'),
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
            log.info("✅ Migration 51 completed successfully!")
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
