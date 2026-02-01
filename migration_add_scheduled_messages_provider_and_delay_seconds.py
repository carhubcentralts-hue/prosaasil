"""
Database Migration: Add Provider and Delay Seconds to Scheduled Messages
Adds provider selection and delay_seconds fields for immediate event-driven triggering
"""
import sys
from sqlalchemy import text
from server.db import db
from server.app_factory import create_app
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_migration():
    """
    Add provider and delay_seconds fields to scheduled messages tables
    
    Changes:
    1. Add delay_seconds to scheduled_message_rules (default 0)
    2. Add provider to scheduled_message_rules (default 'baileys')
    3. Add channel to scheduled_messages_queue (default 'whatsapp')
    4. Add provider to scheduled_messages_queue (default 'baileys')
    5. Add attempts to scheduled_messages_queue (default 0)
    
    Migration is idempotent - safe to run multiple times
    """
    logger.info("=" * 80)
    logger.info("🚀 Starting Migration: Add Provider and Delay Seconds to Scheduled Messages")
    logger.info("=" * 80)
    
    try:
        # Step 1: Add delay_seconds to scheduled_message_rules (if not exists)
        logger.info("Step 1: Adding delay_seconds to scheduled_message_rules...")
        try:
            db.session.execute(text("""
                ALTER TABLE scheduled_message_rules 
                ADD COLUMN IF NOT EXISTS delay_seconds INTEGER NOT NULL DEFAULT 0
            """))
            logger.info("✅ Added delay_seconds column")
        except Exception as e:
            if "already exists" in str(e).lower():
                logger.info("  Column delay_seconds already exists - skipping")
            else:
                raise
        
        # Step 2: Add provider to scheduled_message_rules (if not exists)
        logger.info("Step 2: Adding provider to scheduled_message_rules...")
        try:
            db.session.execute(text("""
                ALTER TABLE scheduled_message_rules 
                ADD COLUMN IF NOT EXISTS provider VARCHAR(32) NOT NULL DEFAULT 'baileys'
            """))
            logger.info("✅ Added provider column")
        except Exception as e:
            if "already exists" in str(e).lower():
                logger.info("  Column provider already exists - skipping")
            else:
                raise
        
        # Step 3: Migrate existing delay_minutes to delay_seconds (if delay_seconds is 0 and delay_minutes > 0)
        logger.info("Step 3: Migrating existing delay_minutes to delay_seconds...")
        result = db.session.execute(text("""
            UPDATE scheduled_message_rules 
            SET delay_seconds = delay_minutes * 60 
            WHERE delay_seconds = 0 AND delay_minutes > 0
        """))
        logger.info(f"✅ Migrated {result.rowcount} rule(s) from delay_minutes to delay_seconds")
        
        # Step 4: Add channel to scheduled_messages_queue (if not exists)
        logger.info("Step 4: Adding channel to scheduled_messages_queue...")
        try:
            db.session.execute(text("""
                ALTER TABLE scheduled_messages_queue 
                ADD COLUMN IF NOT EXISTS channel VARCHAR(32) NOT NULL DEFAULT 'whatsapp'
            """))
            logger.info("✅ Added channel column")
        except Exception as e:
            if "already exists" in str(e).lower():
                logger.info("  Column channel already exists - skipping")
            else:
                raise
        
        # Step 5: Add provider to scheduled_messages_queue (if not exists)
        logger.info("Step 5: Adding provider to scheduled_messages_queue...")
        try:
            db.session.execute(text("""
                ALTER TABLE scheduled_messages_queue 
                ADD COLUMN IF NOT EXISTS provider VARCHAR(32) NOT NULL DEFAULT 'baileys'
            """))
            logger.info("✅ Added provider column")
        except Exception as e:
            if "already exists" in str(e).lower():
                logger.info("  Column provider already exists - skipping")
            else:
                raise
        
        # Step 6: Add attempts to scheduled_messages_queue (if not exists)
        logger.info("Step 6: Adding attempts to scheduled_messages_queue...")
        try:
            db.session.execute(text("""
                ALTER TABLE scheduled_messages_queue 
                ADD COLUMN IF NOT EXISTS attempts INTEGER NOT NULL DEFAULT 0
            """))
            logger.info("✅ Added attempts column")
        except Exception as e:
            if "already exists" in str(e).lower():
                logger.info("  Column attempts already exists - skipping")
            else:
                raise
        
        # Commit all changes
        db.session.commit()
        
        logger.info("=" * 80)
        logger.info("✅ Migration completed successfully!")
        logger.info("=" * 80)
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}", exc_info=True)
        db.session.rollback()
        return False

def main():
    """Run migration in Flask application context"""
    app = create_app()
    
    with app.app_context():
        success = run_migration()
        sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()
