"""
Migration: Add 'incomplete' status to Receipt table
- Add 'incomplete' to the status check constraint
- This status is used when validation fails (missing snapshot, missing attachments)
- Ensures emails with attachments are ALWAYS saved to CRM (Rule 6/7/10)

Run with: python migration_add_incomplete_status.py
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server.app_factory import get_process_app
from server.db import db
from sqlalchemy import text

def run_migration():
    """Add 'incomplete' status to receipts table check constraint"""
    app = get_process_app()
    
    with app.app_context():
        print("🔧 Running incomplete status migration...")
        
        try:
            # Drop old constraint and create new one with 'incomplete'
            db.session.execute(text("""
                DO $$ 
                BEGIN
                    -- Drop existing constraint if it exists
                    ALTER TABLE receipts DROP CONSTRAINT IF EXISTS chk_receipt_status;
                    
                    -- Create new constraint with 'incomplete' status
                    ALTER TABLE receipts 
                    ADD CONSTRAINT chk_receipt_status 
                    CHECK (status IN ('pending_review', 'approved', 'rejected', 'not_receipt', 'incomplete'));
                    
                    RAISE NOTICE 'Added incomplete status to receipts check constraint';
                END $$;
            """))
            db.session.commit()
            
            print("✅ Migration completed successfully")
            print("")
            print("ℹ️  Receipt status values now include:")
            print("   - pending_review: Low/medium confidence, needs review")
            print("   - approved: High confidence, auto-approved")
            print("   - rejected: User marked as not a receipt")
            print("   - not_receipt: System determined not a receipt")
            print("   - incomplete: Validation failed (missing snapshot/attachments)")
            print("")
            print("📊 Check existing incomplete records:")
            print("   SELECT COUNT(*) FROM receipts WHERE status = 'incomplete';")
            print("")
            
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
