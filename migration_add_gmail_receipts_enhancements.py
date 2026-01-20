"""
Migration: Gmail Receipts System Enhancements + Complete File Separation
- Add purpose field to attachments table for file separation
- Add origin_module field to track where files came from
- Add email content fields to receipts table for HTML→PNG rendering
- Add preview_attachment_id to receipts for thumbnails
- Create receipt_sync_runs table for sync job tracking
- Update gmail_connections with last_synced_at (already exists)

Purpose values (STRICT):
- general_upload: Default for user uploads
- email_attachment: Email attachments only
- whatsapp_media: WhatsApp media files only
- broadcast_media: Broadcast media files
- contract_original: Original contract documents
- contract_signed: Signed contract documents
- receipt_source: Original receipt attachments (PDF/images from Gmail)
- receipt_preview: Generated thumbnails/previews for receipts

Origin Module values:
- uploads: General user uploads
- email: Email system
- whatsapp: WhatsApp messages
- broadcast: Broadcast messages
- contracts: Contract management
- receipts: Receipt management

Security:
- API must filter by purpose/context - NO DEFAULT "show all"
- Multi-tenant isolation enforced at all levels
- UI must specify context to prevent mixing

Run with: python migration_add_gmail_receipts_enhancements.py
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server.app_factory import get_process_app
from server.db import db
from sqlalchemy import text

def run_migration():
    """Add Gmail receipts enhancements to database with complete file separation"""
    app = get_process_app()
    
    with app.app_context():
        print("🔧 Running Gmail receipts enhancements migration...")
        print("   This adds purpose-based file separation for security")
        
        try:
            # 1. Add purpose to attachments table
            print("1️⃣ Adding purpose field to attachments...")
            db.session.execute(text("""
                DO $$ 
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='attachments' 
                        AND column_name='purpose'
                    ) THEN
                        -- Add purpose column with default
                        ALTER TABLE attachments 
                        ADD COLUMN purpose VARCHAR(50) NOT NULL DEFAULT 'general_upload';
                        
                        -- Add index for efficient filtering
                        CREATE INDEX idx_attachments_purpose 
                        ON attachments(business_id, purpose, created_at);
                        
                        RAISE NOTICE 'Added purpose column to attachments';
                    ELSE
                        RAISE NOTICE 'purpose column already exists in attachments';
                    END IF;
                END $$;
            """))
            
            # 2. Add origin_module to attachments table
            print("2️⃣ Adding origin_module field to attachments...")
            db.session.execute(text("""
                DO $$ 
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='attachments' 
                        AND column_name='origin_module'
                    ) THEN
                        ALTER TABLE attachments 
                        ADD COLUMN origin_module VARCHAR(50);
                        
                        CREATE INDEX idx_attachments_origin 
                        ON attachments(business_id, origin_module);
                        
                        RAISE NOTICE 'Added origin_module column to attachments';
                    ELSE
                        RAISE NOTICE 'origin_module column already exists';
                    END IF;
                END $$;
            """))
            
            # 3. Add email content fields to receipts
            print("3️⃣ Adding email content fields to receipts...")
            db.session.execute(text("""
                DO $$ 
                BEGIN
                    -- Add email_subject
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='receipts' 
                        AND column_name='email_subject'
                    ) THEN
                        ALTER TABLE receipts 
                        ADD COLUMN email_subject VARCHAR(500);
                        
                        -- Copy from existing subject field if available
                        UPDATE receipts 
                        SET email_subject = subject 
                        WHERE subject IS NOT NULL;
                        
                        RAISE NOTICE 'Added email_subject column';
                    END IF;
                    
                    -- Add email_from
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='receipts' 
                        AND column_name='email_from'
                    ) THEN
                        ALTER TABLE receipts 
                        ADD COLUMN email_from VARCHAR(255);
                        
                        -- Copy from existing from_email field
                        UPDATE receipts 
                        SET email_from = from_email 
                        WHERE from_email IS NOT NULL;
                        
                        RAISE NOTICE 'Added email_from column';
                    END IF;
                    
                    -- Add email_date
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='receipts' 
                        AND column_name='email_date'
                    ) THEN
                        ALTER TABLE receipts 
                        ADD COLUMN email_date TIMESTAMP;
                        
                        -- Copy from existing received_at field
                        UPDATE receipts 
                        SET email_date = received_at 
                        WHERE received_at IS NOT NULL;
                        
                        RAISE NOTICE 'Added email_date column';
                    END IF;
                    
                    -- Add email_html_snippet (limited size for DB efficiency)
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='receipts' 
                        AND column_name='email_html_snippet'
                    ) THEN
                        ALTER TABLE receipts 
                        ADD COLUMN email_html_snippet TEXT;
                        
                        RAISE NOTICE 'Added email_html_snippet column';
                    END IF;
                END $$;
            """))
            
            # 4. Add preview_attachment_id to receipts
            print("4️⃣ Adding preview_attachment_id to receipts...")
            db.session.execute(text("""
                DO $$ 
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='receipts' 
                        AND column_name='preview_attachment_id'
                    ) THEN
                        ALTER TABLE receipts 
                        ADD COLUMN preview_attachment_id INTEGER 
                        REFERENCES attachments(id) ON DELETE SET NULL;
                        
                        CREATE INDEX idx_receipts_preview_attachment 
                        ON receipts(preview_attachment_id);
                        
                        RAISE NOTICE 'Added preview_attachment_id column';
                    ELSE
                        RAISE NOTICE 'preview_attachment_id column already exists';
                    END IF;
                END $$;
            """))
            
            # 5. Create receipt_sync_runs table for tracking long-running syncs
            print("5️⃣ Creating receipt_sync_runs table...")
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS receipt_sync_runs (
                    id SERIAL PRIMARY KEY,
                    business_id INTEGER NOT NULL REFERENCES business(id) ON DELETE CASCADE,
                    
                    -- Sync configuration
                    mode VARCHAR(20) NOT NULL DEFAULT 'incremental', -- full|incremental
                    
                    -- Progress tracking
                    status VARCHAR(20) NOT NULL DEFAULT 'running', -- running|completed|failed
                    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    finished_at TIMESTAMP,
                    
                    -- Counters
                    pages_scanned INTEGER DEFAULT 0,
                    messages_scanned INTEGER DEFAULT 0,
                    candidate_receipts INTEGER DEFAULT 0,
                    saved_receipts INTEGER DEFAULT 0,
                    preview_generated_count INTEGER DEFAULT 0,
                    errors_count INTEGER DEFAULT 0,
                    
                    -- State for resumable syncs
                    last_page_token VARCHAR(255),
                    last_internal_date VARCHAR(50),
                    
                    -- Error tracking
                    error_message TEXT,
                    
                    -- Audit
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
                
                CREATE INDEX IF NOT EXISTS idx_receipt_sync_runs_business 
                ON receipt_sync_runs(business_id, started_at DESC);
                
                CREATE INDEX IF NOT EXISTS idx_receipt_sync_runs_status 
                ON receipt_sync_runs(status, started_at DESC);
            """))
            print("   ✓ Created receipt_sync_runs table")
            
            # 6. Backfill existing attachments with purpose based on usage
            print("6️⃣ Backfilling existing attachments with purpose and origin...")
            
            # Mark receipt attachments
            result = db.session.execute(text("""
                UPDATE attachments a
                SET 
                    purpose = 'receipt_source',
                    origin_module = 'receipts'
                WHERE EXISTS (
                    SELECT 1 FROM receipts r 
                    WHERE r.attachment_id = a.id
                ) AND a.purpose = 'general_upload'
                RETURNING a.id;
            """))
            receipt_count = len(result.fetchall())
            print(f"   ✓ Updated {receipt_count} receipt attachments")
            
            # Mark contract attachments (if contract_files table exists)
            result = db.session.execute(text("""
                DO $$ 
                BEGIN
                    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='contract_files') THEN
                        UPDATE attachments a
                        SET 
                            purpose = CASE 
                                WHEN cf.file_type = 'signed' THEN 'contract_signed'
                                ELSE 'contract_original'
                            END,
                            origin_module = 'contracts'
                        FROM contract_files cf
                        WHERE cf.attachment_id = a.id
                        AND a.purpose = 'general_upload';
                    END IF;
                END $$;
            """))
            print("   ✓ Updated contract attachments (if any)")
            
            # Set origin_module for remaining general uploads
            db.session.execute(text("""
                UPDATE attachments
                SET origin_module = 'uploads'
                WHERE purpose = 'general_upload' AND origin_module IS NULL;
            """))
            print("   ✓ Set origin_module for general uploads")
            
            db.session.commit()
            
            print("✅ Migration completed successfully!")
            print("")
            print("Summary of changes:")
            print("  • Added 'purpose' field to attachments for file separation")
            print("  • Added 'origin_module' field to track source system")
            print("  • Added email content fields to receipts (subject, from, date, html_snippet)")
            print("  • Added preview_attachment_id to receipts for thumbnails")
            print("  • Created receipt_sync_runs table for sync job tracking")
            print("  • Backfilled existing attachments with appropriate purpose/origin")
            print("")
            print("🔒 SECURITY NOTES:")
            print("  • API now requires context parameter to filter attachments")
            print("  • Default behavior is secure: only general_upload without context")
            print("  • Contract/receipt files are isolated and won't appear in email/whatsapp")
            print("")
            print("Next steps:")
            print("  1. API already updated to enforce purpose filtering")
            print("  2. AttachmentPicker already updated to use purposesAllowed")
            print("  3. Test the sync: POST /api/receipts/sync {\"mode\": \"full\"}")
            print("  4. Verify file separation in AttachmentPicker")
            
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            db.session.rollback()
            raise


if __name__ == "__main__":
    run_migration()
