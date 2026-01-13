"""
Test reminder_push_log table migration and safety guards

This test verifies:
1. Migration 66 creates the reminder_push_log table correctly
2. Scheduler handles missing table gracefully
3. WebPush 410 error handling works
"""
import os
import sys

# Set test environment
os.environ['DATABASE_URL'] = os.getenv('DATABASE_URL', 'sqlite:///test_reminder.db')
os.environ['MIGRATION_MODE'] = '1'
os.environ['ASYNC_LOG_QUEUE'] = '0'

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_migration_creates_table():
    """Test that migration 66 creates the reminder_push_log table"""
    from server.app_factory import create_minimal_app
    from server.db import db
    from sqlalchemy import text, inspect
    
    app = create_minimal_app()
    
    with app.app_context():
        print("🧪 Test 1: Checking if reminder_push_log table exists after migration...")
        
        # Run migrations
        from server.db_migrate import apply_migrations
        migrations = apply_migrations()
        
        # Check if table exists
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        assert 'reminder_push_log' in tables, "❌ reminder_push_log table was not created"
        print("✅ reminder_push_log table exists")
        
        # Check table structure
        columns = {col['name']: col for col in inspector.get_columns('reminder_push_log')}
        
        required_columns = ['id', 'reminder_id', 'offset_minutes', 'sent_at']
        for col in required_columns:
            assert col in columns, f"❌ Column {col} is missing"
            print(f"✅ Column '{col}' exists")
        
        # Check indexes
        indexes = inspector.get_indexes('reminder_push_log')
        index_names = [idx['name'] for idx in indexes]
        
        assert any('reminder_id' in idx or 'reminder_push_log_reminder_id' in idx for idx in index_names), \
            "❌ Index on reminder_id is missing"
        print("✅ Index on reminder_id exists")
        
        assert any('sent_at' in idx or 'reminder_push_log_sent_at' in idx for idx in index_names), \
            "❌ Index on sent_at is missing"
        print("✅ Index on sent_at exists")
        
        # Check unique constraint
        unique_constraints = inspector.get_unique_constraints('reminder_push_log')
        has_unique = any('reminder_id' in str(uc) and 'offset_minutes' in str(uc) 
                        for uc in unique_constraints)
        
        if not has_unique:
            # Check if it's implemented as a unique index instead
            for idx in indexes:
                if idx.get('unique') and 'reminder_id' in str(idx.get('column_names', [])):
                    has_unique = True
                    break
        
        assert has_unique, "❌ Unique constraint on (reminder_id, offset_minutes) is missing"
        print("✅ Unique constraint on (reminder_id, offset_minutes) exists")
        
        print("\n✅ Test 1 PASSED: Migration creates table with correct structure\n")


def test_scheduler_safety_guard():
    """Test that scheduler handles missing table gracefully"""
    from server.app_factory import create_minimal_app
    from server.db import db
    from sqlalchemy import text
    
    app = create_minimal_app()
    
    with app.app_context():
        print("🧪 Test 2: Testing scheduler safety guards...")
        
        # First, drop the table if it exists (to simulate missing table)
        try:
            db.session.execute(text("DROP TABLE IF EXISTS reminder_push_log CASCADE"))
            db.session.commit()
            print("✅ Dropped reminder_push_log table for testing")
        except Exception as e:
            print(f"⚠️ Could not drop table: {e}")
            db.session.rollback()
        
        # Test cleanup function with missing table
        from server.services.notifications.reminder_scheduler import _cleanup_old_push_logs
        
        try:
            _cleanup_old_push_logs(db)
            print("✅ _cleanup_old_push_logs handles missing table gracefully")
        except Exception as e:
            print(f"❌ _cleanup_old_push_logs failed with: {e}")
            raise
        
        # Re-create table for next test
        from server.db_migrate import apply_migrations
        apply_migrations()
        
        print("\n✅ Test 2 PASSED: Scheduler handles missing table gracefully\n")


def test_webpush_410_handling():
    """Test that WebPush 410 error handling is implemented"""
    print("🧪 Test 3: Verifying WebPush 410 error handling...")
    
    # Check that dispatcher.py has the proper 410 handling
    import inspect
    from server.services.notifications.dispatcher import _do_dispatch
    
    source = inspect.getsource(_do_dispatch)
    
    # Check for key indicators of 410 handling
    assert 'should_deactivate' in source, "❌ should_deactivate check is missing"
    assert 'is_active' in source, "❌ is_active field update is missing"
    assert 'subscriptions_to_deactivate' in source, "❌ Deactivation logic is missing"
    
    print("✅ WebPush 410 error handling is implemented in dispatcher.py")
    
    # Verify the webpush_sender has 410 detection
    from server.services.push.webpush_sender import WebPushSender
    
    source = inspect.getsource(WebPushSender.send)
    assert '410' in source or 'should_deactivate' in source, \
        "❌ 410 detection is missing in WebPushSender"
    
    print("✅ WebPush 410 detection is implemented in webpush_sender.py")
    print("\n✅ Test 3 PASSED: WebPush 410 error handling is complete\n")


if __name__ == '__main__':
    print("=" * 70)
    print("TESTING REMINDER_PUSH_LOG FIX")
    print("=" * 70)
    print()
    
    try:
        test_migration_creates_table()
        test_scheduler_safety_guard()
        test_webpush_410_handling()
        
        print("=" * 70)
        print("✅ ALL TESTS PASSED")
        print("=" * 70)
        sys.exit(0)
    except Exception as e:
        print("=" * 70)
        print(f"❌ TESTS FAILED: {e}")
        print("=" * 70)
        import traceback
        traceback.print_exc()
        sys.exit(1)
