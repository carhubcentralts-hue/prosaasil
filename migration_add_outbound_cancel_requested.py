"""
Migration: Add cancel_requested to OutboundCallRun table
- Add cancel_requested column for cancellation support
- Default to False
- Required for queue cancellation feature

Run with: python migration_add_outbound_cancel_requested.py
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server.app_factory import get_process_app
from server.db import db
from sqlalchemy import text

def run_migration():
    """Add cancel_requested column to outbound_call_runs table"""
    app = get_process_app()
    
    with app.app_context():
        print("🔧 Running outbound_call_runs cancel_requested migration...")
        
        try:
            # Add cancel_requested column if it doesn't exist
            db.session.execute(text("""
                DO $$ 
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='outbound_call_runs' 
                        AND column_name='cancel_requested'
                    ) THEN
                        ALTER TABLE outbound_call_runs 
                        ADD COLUMN cancel_requested BOOLEAN NOT NULL DEFAULT FALSE;
                        
                        RAISE NOTICE 'Added cancel_requested column with default value FALSE';
                    ELSE
                        RAISE NOTICE 'cancel_requested column already exists';
                    END IF;
                END $$;
            """))
            db.session.commit()
            
            print("✅ Migration completed successfully")
            print("")
            print("ℹ️  All existing runs now have cancel_requested=FALSE")
            print("   This field is used to request cancellation of running queues")
            
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            db.session.rollback()
            raise

if __name__ == "__main__":
    run_migration()
