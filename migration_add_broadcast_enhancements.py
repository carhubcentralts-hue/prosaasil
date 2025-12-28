"""
Migration: Add WhatsApp broadcast enhancements
- Add idempotency_key to whatsapp_broadcasts table
- Update status values to support accepted/queued/sent/delivered/failed

Run with: python migration_add_broadcast_enhancements.py
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server.app_factory import get_process_app
from server.db import db
from sqlalchemy import text

def run_migration():
    """Add enhancements to WhatsApp broadcast tables"""
    app = get_process_app()
    
    with app.app_context():
        print("🔧 Running WhatsApp broadcast enhancements migration...")
        
        try:
            # Add idempotency_key column if it doesn't exist
            db.session.execute(text("""
                DO $$ 
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='whatsapp_broadcasts' 
                        AND column_name='idempotency_key'
                    ) THEN
                        ALTER TABLE whatsapp_broadcasts 
                        ADD COLUMN idempotency_key VARCHAR(64);
                        
                        CREATE INDEX IF NOT EXISTS idx_wa_broadcast_idempotency 
                        ON whatsapp_broadcasts(idempotency_key);
                        
                        RAISE NOTICE 'Added idempotency_key column';
                    ELSE
                        RAISE NOTICE 'idempotency_key column already exists';
                    END IF;
                END $$;
            """))
            
            db.session.commit()
            
            print("✅ Migration completed successfully")
            
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        return True

if __name__ == '__main__':
    success = run_migration()
    sys.exit(0 if success else 1)
