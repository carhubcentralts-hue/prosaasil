"""
Migration: Add webhook_secret to Business table
- Add webhook_secret column for n8n integration
- Create unique index for webhook lookups

Run with: python migration_add_webhook_secret.py
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server.app_factory import get_process_app
from server.db import db
from sqlalchemy import text

def run_migration():
    """Add webhook_secret column to business table"""
    app = get_process_app()
    
    with app.app_context():
        print("🔧 Running webhook_secret migration...")
        
        try:
            # Add webhook_secret column if it doesn't exist
            db.session.execute(text("""
                DO $$ 
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='business' 
                        AND column_name='webhook_secret'
                    ) THEN
                        ALTER TABLE business 
                        ADD COLUMN webhook_secret VARCHAR(255);
                        
                        CREATE UNIQUE INDEX IF NOT EXISTS idx_business_webhook_secret 
                        ON business(webhook_secret) WHERE webhook_secret IS NOT NULL;
                        
                        RAISE NOTICE 'Added webhook_secret column with unique index';
                    ELSE
                        RAISE NOTICE 'webhook_secret column already exists';
                    END IF;
                END $$;
            """))
            db.session.commit()
            
            print("✅ Migration completed successfully")
            print("ℹ️  To set webhook secret for a business, run:")
            print("   UPDATE business SET webhook_secret='wh_n8n_your_random_string' WHERE id=<business_id>;")
            
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        return True

if __name__ == '__main__':
    success = run_migration()
    sys.exit(0 if success else 1)
