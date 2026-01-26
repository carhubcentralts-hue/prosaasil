"""
Migration: Add started_at and ended_at fields to call_log table

This migration adds precise timing fields to fix the "0 seconds duration" issue.
These fields allow us to calculate accurate duration even when Twilio's CallDuration is missing or 0.

Fields added:
- started_at: When call actually started (for accurate duration calculation)
- ended_at: When call actually ended

Run with: python3 migration_add_call_timing_fields.py
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server.app_factory import create_app
from server.db import db
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

def run_migration():
    """Add started_at and ended_at fields to call_log table"""
    app = create_app()
    
    with app.app_context():
        try:
            # Check if columns already exist
            result = db.session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='call_log' AND column_name IN ('started_at', 'ended_at')
            """))
            existing_columns = {row[0] for row in result}
            
            if 'started_at' in existing_columns and 'ended_at' in existing_columns:
                log.info("✅ Columns started_at and ended_at already exist in call_log table")
                return
            
            # Add started_at column if it doesn't exist
            if 'started_at' not in existing_columns:
                log.info("Adding started_at column to call_log table...")
                db.session.execute(text("""
                    ALTER TABLE call_log 
                    ADD COLUMN started_at TIMESTAMP WITHOUT TIME ZONE
                """))
                log.info("✅ Added started_at column")
            
            # Add ended_at column if it doesn't exist
            if 'ended_at' not in existing_columns:
                log.info("Adding ended_at column to call_log table...")
                db.session.execute(text("""
                    ALTER TABLE call_log 
                    ADD COLUMN ended_at TIMESTAMP WITHOUT TIME ZONE
                """))
                log.info("✅ Added ended_at column")
            
            db.session.commit()
            
            # Backfill started_at from created_at for existing calls where started_at is null
            log.info("Backfilling started_at from created_at for existing calls...")
            result = db.session.execute(text("""
                UPDATE call_log 
                SET started_at = created_at 
                WHERE started_at IS NULL AND created_at IS NOT NULL
            """))
            backfilled_count = result.rowcount
            db.session.commit()
            log.info(f"✅ Backfilled {backfilled_count} calls with started_at = created_at")
            
            # For completed calls with duration > 0, estimate ended_at
            log.info("Estimating ended_at for completed calls with duration...")
            result = db.session.execute(text("""
                UPDATE call_log 
                SET ended_at = started_at + (duration || ' seconds')::interval
                WHERE ended_at IS NULL 
                  AND started_at IS NOT NULL 
                  AND duration > 0
                  AND status IN ('completed', 'busy', 'failed', 'no-answer', 'canceled')
            """))
            estimated_count = result.rowcount
            db.session.commit()
            log.info(f"✅ Estimated ended_at for {estimated_count} completed calls")
            
            log.info("✅ Migration completed successfully!")
            
        except Exception as e:
            log.error(f"❌ Migration failed: {e}")
            db.session.rollback()
            raise

if __name__ == "__main__":
    run_migration()
