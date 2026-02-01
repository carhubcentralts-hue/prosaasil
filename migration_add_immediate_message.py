"""
Migration: Add immediate_message to ScheduledMessageRule table
- Add immediate_message column for separate immediate send message
- Nullable to allow backward compatibility

Run with: python migration_add_immediate_message.py
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server.app_factory import get_process_app
from server.db import db
from sqlalchemy import text

def run_migration():
    """Add immediate_message column to scheduled_message_rules table"""
    app = get_process_app()
    
    with app.app_context():
        print("🔧 Running immediate_message migration...")
        
        try:
            # Add immediate_message column if it doesn't exist
            db.session.execute(text("""
                DO $$ 
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='scheduled_message_rules' 
                        AND column_name='immediate_message'
                    ) THEN
                        ALTER TABLE scheduled_message_rules 
                        ADD COLUMN immediate_message TEXT NULL;
                        
                        RAISE NOTICE 'Added immediate_message column';
                    ELSE
                        RAISE NOTICE 'immediate_message column already exists';
                    END IF;
                END $$;
            """))
            db.session.commit()
            
            print("✅ Migration completed successfully")
            print("")
            print("ℹ️  immediate_message column added to scheduled_message_rules table")
            print("   This allows separate messages for immediate send vs delayed steps")
            print("   If not set, message_text will be used for backward compatibility")
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
