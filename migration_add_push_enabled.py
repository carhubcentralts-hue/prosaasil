"""
Migration: Add push_enabled to User table
- Add push_enabled column for user's push notification preference
- Default to True (opt-out model)
- Separate from subscription existence (which indicates device capability)

Run with: python migration_add_push_enabled.py
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server.app_factory import get_process_app
from server.db import db
from sqlalchemy import text

def run_migration():
    """Add push_enabled column to users table"""
    app = get_process_app()
    
    with app.app_context():
        print("🔧 Running push_enabled migration...")
        
        try:
            # Add push_enabled column if it doesn't exist
            db.session.execute(text("""
                DO $$ 
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='users' 
                        AND column_name='push_enabled'
                    ) THEN
                        ALTER TABLE users 
                        ADD COLUMN push_enabled BOOLEAN NOT NULL DEFAULT TRUE;
                        
                        RAISE NOTICE 'Added push_enabled column with default value TRUE';
                    ELSE
                        RAISE NOTICE 'push_enabled column already exists';
                    END IF;
                END $$;
            """))
            db.session.commit()
            
            print("✅ Migration completed successfully")
            print("")
            print("ℹ️  All users now have push_enabled=TRUE by default")
            print("   This represents the user's preference for push notifications")
            print("   Separate from subscription existence (device capability)")
            print("")
            print("   The effective 'enabled' state is:")
            print("   enabled = push_enabled AND has_active_subscription")
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
