"""
Migration: Add transcript field to appointments
- Add call_transcript column to store full conversation transcript
- This complements call_summary which stores AI-generated summary

Run with: python migration_add_appointment_transcript.py
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server.app_factory import get_process_app
from server.db import db

def run_migration():
    """Add transcript field to appointments table"""
    app = get_process_app()
    
    with app.app_context():
        print("🔧 Running appointment transcript migration...")
        
        try:
            # Add call_transcript column if it doesn't exist
            db.engine.execute("""
                DO $$ 
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='appointments' 
                        AND column_name='call_transcript'
                    ) THEN
                        ALTER TABLE appointments 
                        ADD COLUMN call_transcript TEXT;
                        
                        RAISE NOTICE 'Added call_transcript column';
                    ELSE
                        RAISE NOTICE 'call_transcript column already exists';
                    END IF;
                END $$;
            """)
            
            print("✅ Migration completed successfully")
            print("📝 Appointments now support both call_summary (AI summary) and call_transcript (full transcript)")
            
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        return True

if __name__ == '__main__':
    success = run_migration()
    sys.exit(0 if success else 1)
