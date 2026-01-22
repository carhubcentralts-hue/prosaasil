"""
Migration: Add phone_raw, whatsapp_jid, and reply_jid fields to Lead table
- Add phone_raw column for storing original phone input (debugging)
- Add whatsapp_jid column for storing WhatsApp identifiers (@lid, etc.)
- Add whatsapp_jid_alt column for storing alternative JID (sender_pn)
- Add reply_jid column for storing the EXACT JID to reply to (critical for Android/LID)

This supports:
- Phone number normalization with audit trail
- WhatsApp LID support (Android/Business accounts)
- Proper identity mapping across channels
- Reliable reply routing (always reply to last seen JID)

Run with: python migration_add_lead_phone_whatsapp_fields.py
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server.app_factory import get_process_app
from server.db import db
from sqlalchemy import text

def run_migration():
    """Add phone_raw, WhatsApp JID fields, and reply_jid to leads table"""
    app = get_process_app()
    
    with app.app_context():
        print("🔧 Running lead phone/WhatsApp/reply fields migration...")
        
        try:
            # Add columns if they don't exist
            db.session.execute(text("""
                DO $$ 
                BEGIN
                    -- Add phone_raw column for storing original phone input
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='leads' 
                        AND column_name='phone_raw'
                    ) THEN
                        ALTER TABLE leads 
                        ADD COLUMN phone_raw VARCHAR(64) NULL;
                        
                        RAISE NOTICE 'Added phone_raw column';
                    ELSE
                        RAISE NOTICE 'phone_raw column already exists';
                    END IF;
                    
                    -- Add whatsapp_jid column for storing WhatsApp identifiers
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='leads' 
                        AND column_name='whatsapp_jid'
                    ) THEN
                        ALTER TABLE leads 
                        ADD COLUMN whatsapp_jid VARCHAR(128) NULL;
                        
                        RAISE NOTICE 'Added whatsapp_jid column';
                    ELSE
                        RAISE NOTICE 'whatsapp_jid column already exists';
                    END IF;
                    
                    -- Add whatsapp_jid_alt column for storing alternative JID (sender_pn)
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='leads' 
                        AND column_name='whatsapp_jid_alt'
                    ) THEN
                        ALTER TABLE leads 
                        ADD COLUMN whatsapp_jid_alt VARCHAR(128) NULL;
                        
                        RAISE NOTICE 'Added whatsapp_jid_alt column';
                    ELSE
                        RAISE NOTICE 'whatsapp_jid_alt column already exists';
                    END IF;
                    
                    -- Add reply_jid column for storing EXACT JID to reply to
                    -- 🔥 CRITICAL for Android/LID: Always reply to last seen JID, don't reconstruct
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='leads' 
                        AND column_name='reply_jid'
                    ) THEN
                        ALTER TABLE leads 
                        ADD COLUMN reply_jid VARCHAR(128) NULL;
                        
                        RAISE NOTICE 'Added reply_jid column';
                    ELSE
                        RAISE NOTICE 'reply_jid column already exists';
                    END IF;
                    
                    -- Add index on whatsapp_jid for fast lookups
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_indexes 
                        WHERE indexname = 'ix_leads_whatsapp_jid'
                    ) THEN
                        CREATE INDEX ix_leads_whatsapp_jid ON leads(whatsapp_jid);
                        RAISE NOTICE 'Created index on whatsapp_jid';
                    ELSE
                        RAISE NOTICE 'Index on whatsapp_jid already exists';
                    END IF;
                    
                    -- Add index on reply_jid for fast lookups
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_indexes 
                        WHERE indexname = 'ix_leads_reply_jid'
                    ) THEN
                        CREATE INDEX ix_leads_reply_jid ON leads(reply_jid);
                        RAISE NOTICE 'Created index on reply_jid';
                    ELSE
                        RAISE NOTICE 'Index on reply_jid already exists';
                    END IF;
                END $$;
            """))
            db.session.commit()
            
            print("✅ Migration completed successfully")
            print("")
            print("ℹ️  New fields added to leads table:")
            print("   - phone_raw: Original phone input (before normalization)")
            print("   - whatsapp_jid: Primary WhatsApp identifier (remoteJid)")
            print("   - whatsapp_jid_alt: Alternative WhatsApp identifier (sender_pn)")
            print("   - reply_jid: EXACT JID to reply to (last seen, for Android/LID)")
            print("")
            print("💡 These fields enable:")
            print("   - Audit trail for phone normalization")
            print("   - WhatsApp LID support (@lid identifiers)")
            print("   - Proper identity mapping across phone and WhatsApp channels")
            print("   - Reliable reply routing (always use last seen reply_jid)")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Migration failed: {str(e)}")
            raise

if __name__ == '__main__':
    run_migration()
