"""
Test Migration 109 Backward Compatibility
Verify system works WITHOUT started_at/ended_at/duration_sec columns
Uses Migration 51 columns: stream_started_at, stream_ended_at, stream_duration_sec
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
    """Test that migration 109 is a NO-OP and doesn't create columns"""
    logger.info("Testing Migration 109 is NO-OP...")
    
    # Import and run migrations
    from server.db_migrate import run_migrations
    
    # Create tables first
    db.create_all()
    
    # Run migrations - should NOT fail on migration 109
    try:
        migrations_applied = run_migrations()
        logger.info(f"✅ Migrations ran successfully: {len(migrations_applied)} applied")
        
        # Check columns
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        call_log_columns = [col['name'] for col in inspector.get_columns('call_log')]
        
        # Migration 51 columns MUST exist
        assert 'stream_started_at' in call_log_columns, "❌ stream_started_at missing (Migration 51)"
        assert 'stream_ended_at' in call_log_columns, "❌ stream_ended_at missing (Migration 51)"
        assert 'stream_duration_sec' in call_log_columns, "❌ stream_duration_sec missing (Migration 51)"
        logger.info("✅ Migration 51 columns exist: stream_started_at, stream_ended_at, stream_duration_sec")
        
        # Migration 109 columns should NOT exist (NO-OP)
        assert 'started_at' not in call_log_columns, "❌ started_at should NOT exist (Migration 109 is NO-OP)"
        assert 'ended_at' not in call_log_columns, "❌ ended_at should NOT exist (Migration 109 is NO-OP)"
        assert 'duration_sec' not in call_log_columns, "❌ duration_sec should NOT exist (Migration 109 is NO-OP)"
        logger.info("✅ Migration 109 columns DON'T exist (correct - NO-OP)")
        
        logger.info("✅ Migration 109 NO-OP test passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration 109 test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_call_log_with_stream_columns():
    """Test that CallLog works with stream_* columns (Migration 51)"""
    logger.info("Testing CallLog operations with stream_* columns...")
    
    try:
        # Create a business
        business = Business(
            name="Test Business",
            business_type="general",
            is_active=True
        )
        db.session.add(business)
        db.session.commit()
        
        # Create a call log - uses stream_* columns
        call_log = CallLog(
            business_id=business.id,
            call_sid="test-call-sid-" + str(datetime.utcnow().timestamp()),
            from_number="+1234567890",
            to_number="+0987654321",
            direction="inbound",
            status="completed",
            duration=60
        )
        
        # Set stream_* columns (Migration 51 - these MUST work)
        call_log.stream_started_at = datetime.utcnow()
        call_log.stream_ended_at = datetime.utcnow()
        call_log.stream_duration_sec = 60.0
        logger.info("✅ Set stream_started_at, stream_ended_at, stream_duration_sec")
        
        # Save to database
        db.session.add(call_log)
        db.session.commit()
        
        # Read it back
        saved_call = CallLog.query.filter_by(call_sid=call_log.call_sid).first()
        assert saved_call is not None
        assert saved_call.duration == 60
        assert saved_call.stream_started_at is not None
        assert saved_call.stream_ended_at is not None
        assert saved_call.stream_duration_sec == 60.0
        
        logger.info("✅ CallLog operations test passed with stream_* columns")
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
            test2_passed = test_call_log_with_stream_columns()
            
            if test1_passed and test2_passed:
                logger.info("✅ ALL TESTS PASSED - System works with Migration 51 columns only")
                sys.exit(0)
            else:
                logger.error("❌ SOME TESTS FAILED")
                sys.exit(1)
    finally:
        cleanup()
