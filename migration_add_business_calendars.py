"""
Migration: Add Business Calendars System
- Add business_calendars table for multi-calendar management
- Add calendar_routing_rules table for intelligent calendar selection
- Add calendar_id to appointments table for calendar association
- Migrate existing businesses to have a default calendar

Run with: python migration_add_business_calendars.py
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server.app_factory import get_process_app
from server.db import db
from sqlalchemy import text

def run_migration():
    """Add business calendars system tables and migrate existing data"""
    app = get_process_app()
    
    with app.app_context():
        print("🔧 Running business calendars migration...")
        
        try:
            # Step 1: Create business_calendars table
            print("📋 Creating business_calendars table...")
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS business_calendars (
                    id SERIAL PRIMARY KEY,
                    business_id INTEGER NOT NULL REFERENCES business(id) ON DELETE CASCADE,
                    name VARCHAR(255) NOT NULL,
                    type_key VARCHAR(64),
                    provider VARCHAR(32) DEFAULT 'internal' NOT NULL,
                    calendar_external_id VARCHAR(255),
                    is_active BOOLEAN DEFAULT TRUE NOT NULL,
                    priority INTEGER DEFAULT 0 NOT NULL,
                    default_duration_minutes INTEGER DEFAULT 60,
                    buffer_before_minutes INTEGER DEFAULT 0,
                    buffer_after_minutes INTEGER DEFAULT 0,
                    allowed_tags JSONB DEFAULT '[]'::jsonb NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_business_calendars_business_active 
                    ON business_calendars(business_id, is_active);
                CREATE INDEX IF NOT EXISTS idx_business_calendars_priority 
                    ON business_calendars(business_id, priority);
            """))
            
            # Step 2: Create calendar_routing_rules table
            print("📋 Creating calendar_routing_rules table...")
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS calendar_routing_rules (
                    id SERIAL PRIMARY KEY,
                    business_id INTEGER NOT NULL REFERENCES business(id) ON DELETE CASCADE,
                    calendar_id INTEGER NOT NULL REFERENCES business_calendars(id) ON DELETE CASCADE,
                    match_labels JSONB DEFAULT '[]'::jsonb NOT NULL,
                    match_keywords JSONB DEFAULT '[]'::jsonb NOT NULL,
                    channel_scope VARCHAR(32) DEFAULT 'all' NOT NULL,
                    when_ambiguous_ask BOOLEAN DEFAULT FALSE,
                    question_text VARCHAR(500),
                    priority INTEGER DEFAULT 0 NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_calendar_routing_business_active 
                    ON calendar_routing_rules(business_id, is_active);
                CREATE INDEX IF NOT EXISTS idx_calendar_routing_calendar 
                    ON calendar_routing_rules(calendar_id);
            """))
            
            # Step 3: Add calendar_id to appointments table
            print("📋 Adding calendar_id to appointments table...")
            db.session.execute(text("""
                DO $$ 
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='appointments' 
                        AND column_name='calendar_id'
                    ) THEN
                        ALTER TABLE appointments 
                        ADD COLUMN calendar_id INTEGER REFERENCES business_calendars(id) ON DELETE SET NULL;
                        
                        CREATE INDEX IF NOT EXISTS idx_appointments_calendar_id 
                            ON appointments(calendar_id);
                        
                        RAISE NOTICE 'Added calendar_id column to appointments';
                    ELSE
                        RAISE NOTICE 'calendar_id column already exists in appointments';
                    END IF;
                END $$;
            """))
            
            db.session.commit()
            
            # Step 4: Migrate existing businesses to have default calendar
            print("🔄 Creating default calendars for existing businesses...")
            result = db.session.execute(text("""
                INSERT INTO business_calendars (
                    business_id, 
                    name, 
                    type_key, 
                    provider, 
                    is_active, 
                    priority,
                    default_duration_minutes,
                    allowed_tags
                )
                SELECT 
                    b.id,
                    'לוח ברירת מחדל' as name,
                    'default' as type_key,
                    'internal' as provider,
                    TRUE as is_active,
                    1 as priority,
                    COALESCE(bs.slot_size_min, 60) as default_duration_minutes,
                    '[]'::jsonb as allowed_tags
                FROM business b
                LEFT JOIN business_settings bs ON bs.business_id = b.id
                WHERE NOT EXISTS (
                    SELECT 1 FROM business_calendars bc 
                    WHERE bc.business_id = b.id
                )
                RETURNING business_id
            """))
            
            migrated_count = result.rowcount
            db.session.commit()
            
            print(f"✅ Created default calendars for {migrated_count} existing business(es)")
            
            # Step 5: Link existing appointments to default calendar
            print("🔗 Linking existing appointments to default calendars...")
            result = db.session.execute(text("""
                UPDATE appointments a
                SET calendar_id = bc.id
                FROM business_calendars bc
                WHERE a.business_id = bc.business_id
                  AND bc.type_key = 'default'
                  AND a.calendar_id IS NULL
                RETURNING a.id
            """))
            
            linked_count = result.rowcount
            db.session.commit()
            
            print(f"✅ Linked {linked_count} existing appointment(s) to default calendars")
            
            print("✅ Migration completed successfully")
            print("")
            print("📚 Next Steps:")
            print("   1. Businesses can now add multiple calendars via the CRM UI")
            print("   2. Configure routing rules for intelligent calendar selection")
            print("   3. AI will automatically use calendar_list() and calendar_resolve_target()")
            print("")
            print("ℹ️  Backward Compatibility:")
            print("   - Existing appointments work as before with default calendar")
            print("   - Single-calendar businesses continue working without changes")
            print("   - Multi-calendar is opt-in via UI configuration")
            
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
