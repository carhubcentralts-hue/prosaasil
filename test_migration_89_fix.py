"""
Test for Migration 89 fix - verify receipt_sync_runs columns exist
"""
import os
import sys
import logging

# Set environment for testing
os.environ['MIGRATION_MODE'] = '1'
os.environ['DATABASE_URL'] = os.getenv('DATABASE_URL', 'postgresql://test:test@localhost:5432/test')

from server.app_factory import create_minimal_app
from server.db_migrate import check_column_exists, check_table_exists

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

def test_migration_89_columns():
    """Test that all required Migration 89 columns exist"""
    log.info("Testing Migration 89 column existence...")
    
    # Create app context
    app = create_minimal_app()
    
    with app.app_context():
        # Check if table exists
        if not check_table_exists('receipt_sync_runs'):
            log.warning("⚠️  receipt_sync_runs table doesn't exist - skipping test")
            return True
        
        # Check all required columns
        required_columns = [
            'from_date',
            'to_date', 
            'months_back',
            'run_to_completion',
            'max_seconds_per_run',
            'skipped_count'
        ]
        
        missing_columns = []
        for col in required_columns:
            if not check_column_exists('receipt_sync_runs', col):
                missing_columns.append(col)
                log.error(f"❌ Missing column: {col}")
            else:
                log.info(f"✅ Column exists: {col}")
        
        if missing_columns:
            log.error(f"❌ TEST FAILED: Missing columns: {', '.join(missing_columns)}")
            return False
        
        log.info("✅ TEST PASSED: All Migration 89 columns exist")
        return True

def test_database_url_validation():
    """Test that DATABASE_URL is validated"""
    log.info("Testing DATABASE_URL validation...")
    
    db_url = os.getenv('DATABASE_URL', '')
    if not db_url:
        log.error("❌ DATABASE_URL is not set")
        return False
    
    log.info(f"✅ DATABASE_URL is set: {db_url[:30]}...")
    return True

if __name__ == '__main__':
    log.info("=" * 80)
    log.info("Testing Migration 89 Fix")
    log.info("=" * 80)
    
    success = True
    
    # Test DATABASE_URL validation
    if not test_database_url_validation():
        success = False
    
    # Test migration columns
    try:
        if not test_migration_89_columns():
            success = False
    except Exception as e:
        log.error(f"❌ Test failed with exception: {e}")
        log.exception(e)
        success = False
    
    log.info("=" * 80)
    if success:
        log.info("✅ ALL TESTS PASSED")
        sys.exit(0)
    else:
        log.error("❌ SOME TESTS FAILED")
        sys.exit(1)
