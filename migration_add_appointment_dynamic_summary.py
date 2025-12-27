"""
Migration: Add dynamic_summary and lead_id to appointments
- Add dynamic_summary column to store conversation analysis (intent, sentiment, next_action)
- Add lead_id column to link appointments to leads for navigation
- This enhances the meeting summary display with comprehensive information

Run with: python migration_add_appointment_dynamic_summary.py
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server.app_factory import get_process_app
from server.db import db

def run_migration():
    """Add dynamic_summary and lead_id fields to appointments table"""
    app = get_process_app()
    
    with app.app_context():
        print("🔧 Running appointment dynamic summary migration...")
        
        try:
            # Add dynamic_summary column if it doesn't exist
            db.engine.execute("""
                DO $$ 
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='appointments' 
                        AND column_name='dynamic_summary'
                    ) THEN
                        ALTER TABLE appointments 
                        ADD COLUMN dynamic_summary TEXT;
                        
                        RAISE NOTICE 'Added dynamic_summary column';
                    ELSE
                        RAISE NOTICE 'dynamic_summary column already exists';
                    END IF;
                END $$;
            """)
            
            # Add lead_id column with foreign key if it doesn't exist
            db.engine.execute("""
                DO $$ 
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='appointments' 
                        AND column_name='lead_id'
                    ) THEN
                        ALTER TABLE appointments 
                        ADD COLUMN lead_id INTEGER REFERENCES leads(id);
                        
                        CREATE INDEX IF NOT EXISTS idx_appointments_lead_id ON appointments(lead_id);
                        
                        RAISE NOTICE 'Added lead_id column with foreign key and index';
                    ELSE
                        RAISE NOTICE 'lead_id column already exists';
                    END IF;
                END $$;
            """)
            
            print("✅ Migration completed successfully")
            print("📝 Appointments now support:")
            print("   - dynamic_summary: Full conversation analysis with intent, sentiment, actions")
            print("   - lead_id: Link to leads for easy navigation from calendar")
            
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        return True

if __name__ == '__main__':
    success = run_migration()
    sys.exit(0 if success else 1)
