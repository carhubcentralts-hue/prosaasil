"""
Migration: Gmail Receipts System Enhancements
- Add purpose field to attachments table for file separation
- Add email content fields to receipts table for HTML→PNG rendering
- Add preview_attachment_id to receipts for thumbnails
- Create receipt_sync_runs table for sync job tracking
- Update gmail_connections with last_synced_at (already exists)

Purpose values:
- general_upload: Default for user uploads
- contract_original: Original contract documents
- contract_signed: Signed contract documents
- email_attachment: Email attachments
- whatsapp_media: WhatsApp media files
- receipt_source: Original receipt attachments (PDF/images from Gmail)
- receipt_preview: Generated thumbnails/previews for receipts

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
    """Add Gmail receipts enhancements to database"""
    app = get_process_app()
    
    with app.app_context():
        print("🔧 Running Gmail receipts enhancements migration...")
        
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
            
            # 2. Add email content fields to receipts
            print("2️⃣ Adding email content fields to receipts...")
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
            
            # 3. Add preview_attachment_id to receipts
            print("3️⃣ Adding preview_attachment_id to receipts...")
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
            
            # 4. Create receipt_sync_runs table for tracking long-running syncs
            print("4️⃣ Creating receipt_sync_runs table...")
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
            
            # 5. Update existing attachments with purpose based on context
            print("5️⃣ Updating existing attachments with purpose...")
            db.session.execute(text("""
                -- Mark receipt attachments
                UPDATE attachments a
                SET purpose = 'receipt_source'
                WHERE EXISTS (
                    SELECT 1 FROM receipts r 
                    WHERE r.attachment_id = a.id
                ) AND a.purpose = 'general_upload';
                
                -- Note: Other purposes (contracts, emails, whatsapp) will be set
                -- as those features are updated to use the new purpose field
            """))
            
            db.session.commit()
            
            print("✅ Migration completed successfully!")
            print("")
            print("Summary of changes:")
            print("  • Added 'purpose' field to attachments for file separation")
            print("  • Added email content fields to receipts (subject, from, date, html_snippet)")
            print("  • Added preview_attachment_id to receipts for thumbnails")
            print("  • Created receipt_sync_runs table for sync job tracking")
            print("  • Updated existing receipt attachments with 'receipt_source' purpose")
            print("")
            print("Next steps:")
            print("  1. Update gmail_sync_service.py to implement pagination")
            print("  2. Create receipt_preview_service.py for thumbnail generation")
            print("  3. Update AttachmentPicker.tsx to filter by purpose")
            
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            db.session.rollback()
            raise


if __name__ == "__main__":
    run_migration()
