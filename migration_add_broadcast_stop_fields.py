"""
Migration: Add WhatsApp broadcast stop functionality
- Add stopped_by to whatsapp_broadcasts table
- Add stopped_at to whatsapp_broadcasts table
- Add started_at to whatsapp_broadcasts table (for better tracking)

Run with: python migration_add_broadcast_stop_fields.py
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server.app_factory import get_process_app
from server.db import db
from sqlalchemy import text

def run_migration():
    """Add stop functionality fields to WhatsApp broadcast tables"""
    app = get_process_app()
    
    with app.app_context():
        print("🔧 Running WhatsApp broadcast stop fields migration...")
        
        try:
            # Check if table exists
            result = db.session.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'whatsapp_broadcasts'
                );
            """))
            table_exists = result.scalar()
            
            if not table_exists:
                print("⚠️  whatsapp_broadcasts table doesn't exist yet - skipping migration")
                return True
            
            # Add stopped_by column if it doesn't exist
            db.session.execute(text("""
                DO $$ 
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='whatsapp_broadcasts' 
                        AND column_name='stopped_by'
                    ) THEN
                        ALTER TABLE whatsapp_broadcasts 
                        ADD COLUMN stopped_by INTEGER;
                        
                        ALTER TABLE whatsapp_broadcasts
                        ADD CONSTRAINT fk_broadcast_stopped_by
                        FOREIGN KEY (stopped_by) REFERENCES users(id);
                        
                        RAISE NOTICE 'Added stopped_by column';
                    ELSE
                        RAISE NOTICE 'stopped_by column already exists';
                    END IF;
                END $$;
            """))
            
            # Add stopped_at column if it doesn't exist
            db.session.execute(text("""
                DO $$ 
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='whatsapp_broadcasts' 
                        AND column_name='stopped_at'
                    ) THEN
                        ALTER TABLE whatsapp_broadcasts 
                        ADD COLUMN stopped_at TIMESTAMP;
                        
                        RAISE NOTICE 'Added stopped_at column';
                    ELSE
                        RAISE NOTICE 'stopped_at column already exists';
                    END IF;
                END $$;
            """))
            
            # Add started_at column if it doesn't exist
            db.session.execute(text("""
                DO $$ 
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='whatsapp_broadcasts' 
                        AND column_name='started_at'
                    ) THEN
                        ALTER TABLE whatsapp_broadcasts 
                        ADD COLUMN started_at TIMESTAMP;
                        
                        RAISE NOTICE 'Added started_at column';
                    ELSE
                        RAISE NOTICE 'started_at column already exists';
                    END IF;
                END $$;
            """))
            
            db.session.commit()
            
            print("✅ Migration completed successfully")
            print("   - stopped_by field added")
            print("   - stopped_at field added")
            print("   - started_at field added")
            
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
