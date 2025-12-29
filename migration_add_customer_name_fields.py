"""
Migration: Add customer_name to call_log and lead_name to outbound_call_jobs
Purpose: Fix NAME_ANCHOR system to retrieve customer name from database
"""
import sys
from sqlalchemy import text

def run_migration(db):
    """Add customer_name and lead_name fields for NAME_ANCHOR SSOT"""
    
    try:
        # 1. Add customer_name to call_log
        print("📊 Adding customer_name to call_log...")
        db.session.execute(text("""
            ALTER TABLE call_log 
            ADD COLUMN IF NOT EXISTS customer_name VARCHAR(255)
        """))
        print("✅ call_log.customer_name added")
        
        # 2. Add lead_name to outbound_call_jobs
        print("📊 Adding lead_name to outbound_call_jobs...")
        db.session.execute(text("""
            ALTER TABLE outbound_call_jobs 
            ADD COLUMN IF NOT EXISTS lead_name VARCHAR(255)
        """))
        print("✅ outbound_call_jobs.lead_name added")
        
        db.session.commit()
        print("✅ Migration completed successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        db.session.rollback()
        return False


if __name__ == "__main__":
    from server.app_factory import create_app
    from server.db import db
    
    app = create_app()
    with app.app_context():
        success = run_migration(db)
        sys.exit(0 if success else 1)
