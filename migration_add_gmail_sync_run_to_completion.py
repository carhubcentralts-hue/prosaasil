"""
Migration: Gmail Sync Run-to-Completion Enhancements
- Add from_date, to_date, months_back fields to track sync parameters
- Add run_to_completion flag for syncs that should ignore time limits
- Add max_seconds_per_run to track per-run time limits
- Add skipped_count for better progress tracking

This enables:
1. Syncs to run until completion when RUN_TO_COMPLETION=true
2. Progress to persist across page refreshes with full context
3. Auto-resume functionality with complete checkpoint state

Run with: python migration_add_gmail_sync_run_to_completion.py
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server.app_factory import get_process_app
from server.db import db
from sqlalchemy import text

def run_migration():
    """Add run-to-completion fields to receipt_sync_runs table"""
    app = get_process_app()
    
    with app.app_context():
        print("🔧 Running Gmail sync run-to-completion migration...")
        print("   This adds fields for persistent progress and auto-resume")
        
        try:
            # Add new fields to receipt_sync_runs table
            print("1️⃣ Adding sync parameter tracking fields...")
            db.session.execute(text("""
                DO $$ 
                BEGIN
                    -- Add from_date for tracking date range start
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='receipt_sync_runs' 
                        AND column_name='from_date'
                    ) THEN
                        ALTER TABLE receipt_sync_runs 
                        ADD COLUMN from_date DATE;
                        RAISE NOTICE 'Added from_date column';
                    END IF;
                    
                    -- Add to_date for tracking date range end
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='receipt_sync_runs' 
                        AND column_name='to_date'
                    ) THEN
                        ALTER TABLE receipt_sync_runs 
                        ADD COLUMN to_date DATE;
                        RAISE NOTICE 'Added to_date column';
                    END IF;
                    
                    -- Add months_back for tracking backfill scope
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='receipt_sync_runs' 
                        AND column_name='months_back'
                    ) THEN
                        ALTER TABLE receipt_sync_runs 
                        ADD COLUMN months_back INTEGER;
                        RAISE NOTICE 'Added months_back column';
                    END IF;
                    
                    -- Add run_to_completion flag
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='receipt_sync_runs' 
                        AND column_name='run_to_completion'
                    ) THEN
                        ALTER TABLE receipt_sync_runs 
                        ADD COLUMN run_to_completion BOOLEAN DEFAULT FALSE;
                        RAISE NOTICE 'Added run_to_completion column';
                    END IF;
                    
                    -- Add max_seconds_per_run to track per-run limits
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='receipt_sync_runs' 
                        AND column_name='max_seconds_per_run'
                    ) THEN
                        ALTER TABLE receipt_sync_runs 
                        ADD COLUMN max_seconds_per_run INTEGER;
                        RAISE NOTICE 'Added max_seconds_per_run column';
                    END IF;
                    
                    -- Add skipped_count for better progress tracking
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='receipt_sync_runs' 
                        AND column_name='skipped_count'
                    ) THEN
                        ALTER TABLE receipt_sync_runs 
                        ADD COLUMN skipped_count INTEGER DEFAULT 0;
                        RAISE NOTICE 'Added skipped_count column';
                    END IF;
                    
                    -- Update status constraint to include 'paused' status
                    -- First, drop the old constraint if it exists
                    IF EXISTS (
                        SELECT 1 FROM information_schema.constraint_column_usage 
                        WHERE table_name='receipt_sync_runs' 
                        AND constraint_name='chk_receipt_sync_status'
                    ) THEN
                        ALTER TABLE receipt_sync_runs DROP CONSTRAINT chk_receipt_sync_status;
                        RAISE NOTICE 'Dropped old status constraint';
                    END IF;
                    
                    -- Add updated constraint with 'paused' status
                    ALTER TABLE receipt_sync_runs 
                    ADD CONSTRAINT chk_receipt_sync_status 
                    CHECK (status IN ('running', 'completed', 'failed', 'cancelled', 'paused'));
                    RAISE NOTICE 'Added updated status constraint with paused';
                    
                END $$;
            """))
            
            db.session.commit()
            print("✅ Migration completed successfully!")
            print("   New fields added:")
            print("   - from_date: Track sync date range start")
            print("   - to_date: Track sync date range end")
            print("   - months_back: Track backfill scope")
            print("   - run_to_completion: Flag for time-unlimited syncs")
            print("   - max_seconds_per_run: Per-run time limit")
            print("   - skipped_count: Count of skipped messages")
            print("   - status constraint updated to include 'paused'")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Migration failed: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == '__main__':
    run_migration()
