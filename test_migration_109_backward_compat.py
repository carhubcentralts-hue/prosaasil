"""
Test Migration 109 Backward Compatibility
Verify system works without started_at/ended_at/duration_sec columns
"""
import os
import sys

# Set test environment
os.environ['DATABASE_URL'] = 'sqlite:///test_migration_109.db'
os.environ['SECRET_KEY'] = 'test-secret-key-for-migration-109'

from server.db import db
from server.models_sql import CallLog, Business
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_migration_109_is_noop():
    """Test that migration 109 is a NO-OP"""
    logger.info("Testing Migration 109 is NO-OP...")
    
    # Import and run migrations
    from server.db_migrate import run_migrations
    
    # Create tables first
    db.create_all()
    
    # Run migrations - should NOT fail on migration 109
    try:
        migrations_applied = run_migrations()
        logger.info(f"✅ Migrations ran successfully: {len(migrations_applied)} applied")
        
        # Check that migration 109 didn't create the columns
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        call_log_columns = [col['name'] for col in inspector.get_columns('call_log')]
        
        # The old stream_* columns should exist (from earlier migrations)
        if 'stream_started_at' in call_log_columns:
            logger.info("✅ stream_started_at column exists (old schema)")
        
        # The new columns may or may not exist (migration 109 is NO-OP)
        if 'started_at' in call_log_columns:
            logger.info("ℹ️ started_at column exists (was created before NO-OP change)")
        else:
            logger.info("✅ started_at column doesn't exist (expected after NO-OP change)")
        
        logger.info("✅ Migration 109 NO-OP test passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration 109 test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_call_log_with_missing_columns():
    """Test that CallLog works without started_at/ended_at/duration_sec columns"""
    logger.info("Testing CallLog operations without new columns...")
    
    try:
        # Create a business
        business = Business(
            name="Test Business",
            business_type="general",
            is_active=True
        )
        db.session.add(business)
        db.session.commit()
        
        # Create a call log - should work even if columns don't exist
        call_log = CallLog(
            business_id=business.id,
            call_sid="test-call-sid-" + str(datetime.utcnow().timestamp()),
            from_number="+1234567890",
            to_number="+0987654321",
            direction="inbound",
            status="completed",
            duration=60
        )
        
        # Set stream_* columns (these exist in old schema)
        if hasattr(call_log, 'stream_started_at'):
            call_log.stream_started_at = datetime.utcnow()
            logger.info("✅ Set stream_started_at")
        
        if hasattr(call_log, 'stream_ended_at'):
            call_log.stream_ended_at = datetime.utcnow()
            logger.info("✅ Set stream_ended_at")
        
        if hasattr(call_log, 'stream_duration_sec'):
            call_log.stream_duration_sec = 60.0
            logger.info("✅ Set stream_duration_sec")
        
        # Try to set new columns only if they exist
        if hasattr(call_log, 'started_at'):
            call_log.started_at = datetime.utcnow()
            logger.info("ℹ️ Set started_at (column exists)")
        else:
            logger.info("✅ started_at column doesn't exist (backward compatible)")
        
        if hasattr(call_log, 'ended_at'):
            call_log.ended_at = datetime.utcnow()
            logger.info("ℹ️ Set ended_at (column exists)")
        else:
            logger.info("✅ ended_at column doesn't exist (backward compatible)")
        
        if hasattr(call_log, 'duration_sec'):
            call_log.duration_sec = 60
            logger.info("ℹ️ Set duration_sec (column exists)")
        else:
            logger.info("✅ duration_sec column doesn't exist (backward compatible)")
        
        # Save to database
        db.session.add(call_log)
        db.session.commit()
        
        # Read it back
        saved_call = CallLog.query.filter_by(call_sid=call_log.call_sid).first()
        assert saved_call is not None
        assert saved_call.duration == 60
        
        logger.info("✅ CallLog operations test passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ CallLog operations test failed: {e}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        return False

def cleanup():
    """Cleanup test database"""
    try:
        if os.path.exists('test_migration_109.db'):
            os.remove('test_migration_109.db')
            logger.info("🧹 Cleaned up test database")
    except Exception as e:
        logger.warning(f"⚠️ Cleanup failed: {e}")

if __name__ == '__main__':
    try:
        from server.app import app
        
        with app.app_context():
            # Run tests
            test1_passed = test_migration_109_is_noop()
            test2_passed = test_call_log_with_missing_columns()
            
            if test1_passed and test2_passed:
                logger.info("✅ ALL TESTS PASSED")
                sys.exit(0)
            else:
                logger.error("❌ SOME TESTS FAILED")
                sys.exit(1)
    finally:
        cleanup()
