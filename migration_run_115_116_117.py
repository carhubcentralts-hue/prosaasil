#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Standalone Migration Runner for Migrations 115-117
===================================================

This script ensures critical migrations are executed:
- Migration 115: Business calendars and routing rules system
- Migration 116: Scheduled WhatsApp messages system  
- Migration 117: Enable scheduled_messages page for businesses

Run this if migrations haven't executed via normal startup flow.

Usage:
    python migration_run_115_116_117.py

Requirements:
    - DATABASE_URL environment variable must be set
    - Database must be accessible
    - Run from project root directory
"""

import os
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

def checkpoint(msg):
    """Log checkpoint message"""
    logger.info(f"🔧 {msg}")
    print(msg, file=sys.stderr, flush=True)

def main():
    """Run migrations 115, 116, 117"""
    
    checkpoint("=" * 80)
    checkpoint("STANDALONE MIGRATION RUNNER: Migrations 115-117")
    checkpoint("=" * 80)
    
    # Check DATABASE_URL
    if not os.getenv('DATABASE_URL'):
        checkpoint("❌ ERROR: DATABASE_URL environment variable not set!")
        checkpoint("Set DATABASE_URL and try again.")
        return 1
    
    checkpoint(f"Database: {os.getenv('DATABASE_URL').split('@')[0] if '@' in os.getenv('DATABASE_URL', '') else '***'}@***")
    
    try:
        # Import after environment check
        checkpoint("Importing Flask app...")
        from server.app_factory import create_minimal_app
        from server.db import db
        from sqlalchemy import text, inspect
        
        checkpoint("Creating Flask app context...")
        app = create_minimal_app()
        
        with app.app_context():
            checkpoint("Connected to database")
            
            # Check current state
            inspector = inspect(db.engine)
            existing_tables = inspector.get_table_names()
            checkpoint(f"Found {len(existing_tables)} existing tables")
            
            # Check if migrations are needed
            needs_115 = 'business_calendars' not in existing_tables
            needs_116 = 'scheduled_message_rules' not in existing_tables
            needs_117 = True  # Always check this one
            
            if not needs_115 and not needs_116:
                checkpoint("✅ Tables already exist - checking column status...")
            
            # Check appointments.calendar_id specifically
            if 'appointments' in existing_tables:
                columns = [col['name'] for col in inspector.get_columns('appointments')]
                has_calendar_id = 'calendar_id' in columns
                checkpoint(f"appointments table: {'✅ has calendar_id' if has_calendar_id else '❌ MISSING calendar_id'}")
                if not has_calendar_id:
                    needs_115 = True
            
            if not needs_115 and not needs_116 and not needs_117:
                checkpoint("✅ All migrations already applied!")
                checkpoint("=" * 80)
                return 0
            
            # Force migrations to run by calling apply_migrations
            checkpoint("Running apply_migrations()...")
            checkpoint("Note: This will run ALL pending migrations, including 115-117")
            
            # Temporarily set environment to ensure migrations run
            original_service_role = os.getenv('SERVICE_ROLE')
            original_run_migrations = os.getenv('RUN_MIGRATIONS')
            
            os.environ['SERVICE_ROLE'] = 'api'  # Not a worker
            os.environ['RUN_MIGRATIONS'] = '1'  # Enable migrations
            
            try:
                from server.db_migrate import apply_migrations
                result = apply_migrations()
                
                if result == 'skip':
                    checkpoint("⚠️  Migrations were skipped!")
                    checkpoint("This could be due to:")
                    checkpoint("  - Another process holds the migration lock")
                    checkpoint("  - Database connection issue")
                    checkpoint("  - Migration timeout")
                    checkpoint("")
                    checkpoint("Try again in a few seconds, or check logs for errors.")
                    return 1
                else:
                    checkpoint(f"✅ Migrations completed successfully")
                    if isinstance(result, list):
                        checkpoint(f"   Applied {len(result)} migration steps")
                    
            finally:
                # Restore environment
                if original_service_role:
                    os.environ['SERVICE_ROLE'] = original_service_role
                elif 'SERVICE_ROLE' in os.environ:
                    del os.environ['SERVICE_ROLE']
                    
                if original_run_migrations:
                    os.environ['RUN_MIGRATIONS'] = original_run_migrations
                elif 'RUN_MIGRATIONS' in os.environ:
                    del os.environ['RUN_MIGRATIONS']
            
            # Verify results
            checkpoint("")
            checkpoint("=" * 80)
            checkpoint("VERIFICATION")
            checkpoint("=" * 80)
            
            inspector = inspect(db.engine)
            existing_tables = inspector.get_table_names()
            
            # Check Migration 115
            checkpoint("Migration 115: Business Calendars System")
            if 'business_calendars' in existing_tables:
                checkpoint("  ✅ business_calendars table exists")
            else:
                checkpoint("  ❌ business_calendars table MISSING")
                
            if 'calendar_routing_rules' in existing_tables:
                checkpoint("  ✅ calendar_routing_rules table exists")
            else:
                checkpoint("  ❌ calendar_routing_rules table MISSING")
            
            if 'appointments' in existing_tables:
                columns = [col['name'] for col in inspector.get_columns('appointments')]
                if 'calendar_id' in columns:
                    checkpoint("  ✅ appointments.calendar_id column exists")
                else:
                    checkpoint("  ❌ appointments.calendar_id column MISSING")
            
            # Check Migration 116
            checkpoint("")
            checkpoint("Migration 116: Scheduled Messages System")
            tables_116 = ['scheduled_message_rules', 'scheduled_rule_statuses', 'scheduled_messages_queue']
            for table in tables_116:
                if table in existing_tables:
                    checkpoint(f"  ✅ {table} table exists")
                else:
                    checkpoint(f"  ❌ {table} table MISSING")
            
            # Check Migration 117
            checkpoint("")
            checkpoint("Migration 117: Scheduled Messages Page Enabled")
            if 'business' in existing_tables:
                columns = [col['name'] for col in inspector.get_columns('business')]
                if 'enabled_pages' in columns:
                    # Check if any business has scheduled_messages enabled
                    result = db.session.execute(text("""
                        SELECT COUNT(*) FROM business 
                        WHERE enabled_pages::text LIKE '%scheduled_messages%'
                    """))
                    count = result.scalar()
                    checkpoint(f"  ✅ {count} business(es) have scheduled_messages page enabled")
                else:
                    checkpoint("  ⚠️  enabled_pages column not found in business table")
            
            checkpoint("")
            checkpoint("=" * 80)
            checkpoint("✅ MIGRATION CHECK COMPLETE")
            checkpoint("=" * 80)
            
            return 0
            
    except Exception as e:
        checkpoint("")
        checkpoint("=" * 80)
        checkpoint(f"❌ MIGRATION FAILED: {e}")
        checkpoint("=" * 80)
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
