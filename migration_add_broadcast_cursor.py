"""
Migration: Add cursor-based pagination for WhatsApp broadcasts
- Add last_processed_recipient_id to whatsapp_broadcasts table for resumable broadcasts

🎯 FIX #5: This column was being added at runtime in broadcast_job.py
which is incorrect. It MUST be added via proper migration.

Run with: python migration_add_broadcast_cursor.py
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server.app_factory import get_process_app
from server.db import db
from sqlalchemy import text

def run_migration():
    """Add cursor column for broadcast pagination"""
    app = get_process_app()
    
    with app.app_context():
        print("🔧 Running WhatsApp broadcast cursor migration...")
        
        try:
            # Add last_processed_recipient_id column if it doesn't exist
            db.session.execute(text("""
                DO $$ 
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='whatsapp_broadcasts' 
                        AND column_name='last_processed_recipient_id'
                    ) THEN
                        ALTER TABLE whatsapp_broadcasts 
                        ADD COLUMN last_processed_recipient_id INTEGER DEFAULT 0;
                        
                        RAISE NOTICE 'Added last_processed_recipient_id column';
                    ELSE
                        RAISE NOTICE 'last_processed_recipient_id column already exists';
                    END IF;
                END $$;
            """))
            
            db.session.commit()
            
            print("✅ Migration completed successfully")
            
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            return False
        
        return True

if __name__ == '__main__':
    success = run_migration()
    sys.exit(0 if success else 1)
