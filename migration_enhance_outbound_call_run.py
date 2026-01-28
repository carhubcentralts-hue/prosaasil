"""
Migration: Enhance OutboundCallRun with additional tracking fields
- Add created_by_user_id for audit trail
- Add started_at and ended_at for precise timing
- Add cursor_position for progress tracking
- Add locked_by_worker for worker coordination
- Add lock_ts for lock timeout detection
- Add unique constraint on (run_id, lead_id) in OutboundCallJob to prevent duplicates

Run with: python migration_enhance_outbound_call_run.py
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server.app_factory import get_process_app
from server.db import db
from sqlalchemy import text

def run_migration():
    """Add tracking fields to OutboundCallRun and constraints to OutboundCallJob"""
    app = get_process_app()
    
    with app.app_context():
        print("🔧 Running OutboundCallRun enhancement migration...")
        
        try:
            # Add new fields to outbound_call_runs table
            db.session.execute(text("""
                DO $$ 
                BEGIN
                    -- Add created_by_user_id if it doesn't exist
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='outbound_call_runs' 
                        AND column_name='created_by_user_id'
                    ) THEN
                        ALTER TABLE outbound_call_runs 
                        ADD COLUMN created_by_user_id INTEGER REFERENCES users(id);
                        
                        RAISE NOTICE 'Added created_by_user_id column';
                    ELSE
                        RAISE NOTICE 'created_by_user_id column already exists';
                    END IF;
                    
                    -- Add started_at if it doesn't exist
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='outbound_call_runs' 
                        AND column_name='started_at'
                    ) THEN
                        ALTER TABLE outbound_call_runs 
                        ADD COLUMN started_at TIMESTAMP;
                        
                        RAISE NOTICE 'Added started_at column';
                    ELSE
                        RAISE NOTICE 'started_at column already exists';
                    END IF;
                    
                    -- Add ended_at if it doesn't exist
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='outbound_call_runs' 
                        AND column_name='ended_at'
                    ) THEN
                        ALTER TABLE outbound_call_runs 
                        ADD COLUMN ended_at TIMESTAMP;
                        
                        RAISE NOTICE 'Added ended_at column';
                    ELSE
                        RAISE NOTICE 'ended_at column already exists';
                    END IF;
                    
                    -- Add cursor_position if it doesn't exist
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='outbound_call_runs' 
                        AND column_name='cursor_position'
                    ) THEN
                        ALTER TABLE outbound_call_runs 
                        ADD COLUMN cursor_position INTEGER DEFAULT 0;
                        
                        RAISE NOTICE 'Added cursor_position column';
                    ELSE
                        RAISE NOTICE 'cursor_position column already exists';
                    END IF;
                    
                    -- Add locked_by_worker if it doesn't exist
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='outbound_call_runs' 
                        AND column_name='locked_by_worker'
                    ) THEN
                        ALTER TABLE outbound_call_runs 
                        ADD COLUMN locked_by_worker VARCHAR(128);
                        
                        RAISE NOTICE 'Added locked_by_worker column';
                    ELSE
                        RAISE NOTICE 'locked_by_worker column already exists';
                    END IF;
                    
                    -- Add lock_ts if it doesn't exist
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='outbound_call_runs' 
                        AND column_name='lock_ts'
                    ) THEN
                        ALTER TABLE outbound_call_runs 
                        ADD COLUMN lock_ts TIMESTAMP;
                        
                        RAISE NOTICE 'Added lock_ts column';
                    ELSE
                        RAISE NOTICE 'lock_ts column already exists';
                    END IF;
                    
                    -- Add unique constraint on (run_id, lead_id) in outbound_call_jobs
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint 
                        WHERE conname='unique_run_lead'
                    ) THEN
                        -- First, remove any existing duplicates (keep oldest)
                        DELETE FROM outbound_call_jobs a
                        USING outbound_call_jobs b
                        WHERE a.id > b.id
                          AND a.run_id = b.run_id
                          AND a.lead_id = b.lead_id;
                        
                        -- Now add the unique constraint
                        ALTER TABLE outbound_call_jobs 
                        ADD CONSTRAINT unique_run_lead UNIQUE (run_id, lead_id);
                        
                        RAISE NOTICE 'Added unique constraint on (run_id, lead_id)';
                    ELSE
                        RAISE NOTICE 'unique_run_lead constraint already exists';
                    END IF;
                    
                    -- Add business_id to outbound_call_jobs if missing (for extra isolation)
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='outbound_call_jobs' 
                        AND column_name='business_id'
                    ) THEN
                        -- Add business_id with a temporary nullable constraint
                        ALTER TABLE outbound_call_jobs 
                        ADD COLUMN business_id INTEGER;
                        
                        -- Populate from parent run
                        UPDATE outbound_call_jobs 
                        SET business_id = (
                            SELECT business_id FROM outbound_call_runs 
                            WHERE outbound_call_runs.id = outbound_call_jobs.run_id
                        );
                        
                        -- Make it NOT NULL and add FK
                        ALTER TABLE outbound_call_jobs 
                        ALTER COLUMN business_id SET NOT NULL;
                        
                        ALTER TABLE outbound_call_jobs 
                        ADD CONSTRAINT fk_outbound_call_jobs_business 
                        FOREIGN KEY (business_id) REFERENCES business(id);
                        
                        -- Add index for performance
                        CREATE INDEX idx_outbound_call_jobs_business_id 
                        ON outbound_call_jobs(business_id);
                        
                        RAISE NOTICE 'Added business_id column with FK and index';
                    ELSE
                        RAISE NOTICE 'business_id column already exists in outbound_call_jobs';
                    END IF;
                END $$;
            """))
            db.session.commit()
            
            print("✅ Migration completed successfully")
            print("")
            print("ℹ️  Added fields to outbound_call_runs:")
            print("   - created_by_user_id: User who started the run")
            print("   - started_at: When run actually started processing")
            print("   - ended_at: When run finished (completed/cancelled/failed)")
            print("   - cursor_position: Current position in queue for resume")
            print("   - locked_by_worker: Worker ID holding the lock")
            print("   - lock_ts: Lock timestamp for timeout detection")
            print("")
            print("ℹ️  Added constraints:")
            print("   - unique_run_lead: Prevents duplicate jobs for same lead in run")
            print("   - business_id in outbound_call_jobs: Extra isolation layer")
            print("")
            
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        return True

if __name__ == '__main__':
    success = run_migration()
    sys.exit(0 if success else 1)
