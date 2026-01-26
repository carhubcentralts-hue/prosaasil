"""
Migration: Add lead_tabs_config to Business table
- Add lead_tabs_config JSON column for flexible tab configuration per business
- Allows businesses to customize which tabs appear in the lead detail page
- Supports up to 6 configurable tabs

Run with: python migration_add_lead_tabs_config.py
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server.app_factory import get_process_app
from server.db import db
from sqlalchemy import text

def run_migration():
    """Add lead_tabs_config column to business table"""
    app = get_process_app()
    
    with app.app_context():
        print("🔧 Running lead_tabs_config migration...")
        
        try:
            # Add lead_tabs_config column if it doesn't exist
            db.session.execute(text("""
                DO $$ 
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='business' 
                        AND column_name='lead_tabs_config'
                    ) THEN
                        ALTER TABLE business 
                        ADD COLUMN lead_tabs_config JSON DEFAULT NULL;
                        
                        COMMENT ON COLUMN business.lead_tabs_config IS 
                        'Flexible tab configuration for lead detail page. JSON array of tab keys. Max 6 tabs. Available tabs: activity, reminders, documents, overview, whatsapp, calls, email, contracts, appointments, ai_notes, notes';
                        
                        RAISE NOTICE 'Added lead_tabs_config column';
                    ELSE
                        RAISE NOTICE 'lead_tabs_config column already exists';
                    END IF;
                END $$;
            """))
            db.session.commit()
            
            print("✅ Migration completed successfully")
            print("")
            print("ℹ️  Lead Tabs Configuration:")
            print("   - Default tabs (if lead_tabs_config is NULL):")
            print("     PRIMARY: activity, reminders, documents")
            print("     SECONDARY (More menu): overview, whatsapp, calls, email, contracts, appointments, ai_notes, notes")
            print("")
            print("   - To customize tabs for a business:")
            print("     UPDATE business")
            print("     SET lead_tabs_config = '{\"primary\": [\"activity\", \"reminders\", \"documents\"], \"secondary\": [\"overview\", \"whatsapp\", \"calls\", \"email\"]}'")
            print("     WHERE id = <business_id>;")
            print("")
            print("   - Available tab keys:")
            print("     * activity: Timeline with all activities")
            print("     * reminders: Tasks and reminders")
            print("     * documents: Contracts + Notes with files")
            print("     * overview: Lead details overview")
            print("     * whatsapp: WhatsApp template + conversation")
            print("     * calls: Phone calls history")
            print("     * email: Email messages")
            print("     * contracts: Contract management")
            print("     * appointments: Scheduled appointments")
            print("     * ai_notes: AI Customer Service notes")
            print("     * notes: Free-form notes")
            print("")
            print("   - Max 3 primary tabs (shown directly)")
            print("   - Up to 6 total tabs (3 primary + 3 in 'More' menu)")
            
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        return True

if __name__ == '__main__':
    success = run_migration()
    sys.exit(0 if success else 1)
