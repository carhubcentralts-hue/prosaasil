"""
Test for Push Service DATABASE_URL validation
"""
import os
import sys
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

def test_push_service_startup_validation():
    """Test that push services validate DATABASE_URL at startup"""
    log.info("Testing push service DATABASE_URL validation...")
    
    # Temporarily unset DATABASE_URL to test validation
    original_url = os.getenv('DATABASE_URL')
    
    try:
        # Test 1: Missing DATABASE_URL should raise RuntimeError
        log.info("Test 1: Checking startup validation with missing DATABASE_URL...")
        os.environ.pop('DATABASE_URL', None)
        
        from server.app_factory import create_minimal_app
        
        try:
            app = create_minimal_app()
            with app.app_context():
                # Try to start reminder scheduler
                from server.services.notifications.reminder_scheduler import start_reminder_scheduler
                
                try:
                    start_reminder_scheduler(app)
                    log.error("❌ TEST FAILED: scheduler started without DATABASE_URL!")
                    return False
                except RuntimeError as e:
                    if "DATABASE_URL" in str(e):
                        log.info(f"✅ Scheduler correctly rejected missing DATABASE_URL: {str(e)[:100]}...")
                    else:
                        log.error(f"❌ Wrong error: {e}")
                        return False
        except RuntimeError as e:
            if "DATABASE_URL" in str(e):
                log.info(f"✅ App correctly rejected missing DATABASE_URL: {str(e)[:100]}...")
            else:
                log.error(f"❌ Wrong error: {e}")
                return False
        
        # Test 2: With DATABASE_URL should work
        if original_url:
            log.info("Test 2: Checking startup with valid DATABASE_URL...")
            os.environ['DATABASE_URL'] = original_url
            os.environ['MIGRATION_MODE'] = '1'  # Minimal app for testing
            
            try:
                app = create_minimal_app()
                log.info("✅ App created successfully with DATABASE_URL")
            except Exception as e:
                log.error(f"❌ Failed to create app with valid DATABASE_URL: {e}")
                return False
        
        log.info("✅ TEST PASSED: Push service DATABASE_URL validation works")
        return True
        
    finally:
        # Restore original DATABASE_URL
        if original_url:
            os.environ['DATABASE_URL'] = original_url

if __name__ == '__main__':
    log.info("=" * 80)
    log.info("Testing Push Service DATABASE_URL Validation")
    log.info("=" * 80)
    
    try:
        if test_push_service_startup_validation():
            log.info("=" * 80)
            log.info("✅ ALL TESTS PASSED")
            log.info("=" * 80)
            sys.exit(0)
        else:
            log.error("=" * 80)
            log.error("❌ TEST FAILED")
            log.error("=" * 80)
            sys.exit(1)
    except Exception as e:
        log.error(f"❌ Test failed with exception: {e}")
        log.exception(e)
        sys.exit(1)
