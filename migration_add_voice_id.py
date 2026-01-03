"""
Migration: Add voice_id to Business table
- Add voice_id column for per-business voice selection
- Default to 'ash' voice

Run with: python migration_add_voice_id.py
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server.app_factory import get_process_app
from server.db import db
from server.config.voices import DEFAULT_VOICE
from sqlalchemy import text

def run_migration():
    """Add voice_id column to business table"""
    app = get_process_app()
    
    with app.app_context():
        print("🔧 Running voice_id migration...")
        
        try:
            # Add voice_id column if it doesn't exist
            db.session.execute(text(f"""
                DO $$ 
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='business' 
                        AND column_name='voice_id'
                    ) THEN
                        ALTER TABLE business 
                        ADD COLUMN voice_id VARCHAR(32) NOT NULL DEFAULT '{DEFAULT_VOICE}';
                        
                        RAISE NOTICE 'Added voice_id column with default value {DEFAULT_VOICE}';
                    ELSE
                        RAISE NOTICE 'voice_id column already exists';
                    END IF;
                END $$;
            """))
            db.session.commit()
            
            print("✅ Migration completed successfully")
            print("")
            print(f"ℹ️  All businesses now have default voice: '{DEFAULT_VOICE}'")
            print("   Available voices: alloy, ash, ballad, cedar, coral, echo,")
            print("                     fable, marin, nova, onyx, sage, shimmer, verse")
            print("")
            print("   To change voice for a business:")
            print("   UPDATE business SET voice_id='onyx' WHERE id=<business_id>;")
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
