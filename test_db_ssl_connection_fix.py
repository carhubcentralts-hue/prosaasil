"""
Test DB SSL Connection Fix for /api/receipts/sync/status

This test verifies that:
1. pool_pre_ping is enabled in SQLAlchemy configuration
2. pool_recycle is set to 180 seconds
3. OperationalError handling is in place for the sync/status endpoint
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_production_config_has_pool_settings():
    """Test that production config has correct pool settings"""
    from server.production_config import ProductionConfig
    
    config = ProductionConfig.SQLALCHEMY_ENGINE_OPTIONS
    
    # Verify pool_pre_ping is enabled (prevents stale connections)
    assert config.get('pool_pre_ping') is True, "pool_pre_ping should be True"
    
    # Verify pool_recycle is set to 180 seconds (before Supabase timeout)
    assert config.get('pool_recycle') == 180, "pool_recycle should be 180 seconds"
    
    # Verify pool_timeout is set
    assert config.get('pool_timeout') == 30, "pool_timeout should be 30 seconds"
    
    # Verify pool_size is set
    assert config.get('pool_size') == 5, "pool_size should be 5"
    
    # Verify max_overflow is set
    assert config.get('max_overflow') == 10, "max_overflow should be 10"
    
    print("✅ ProductionConfig has correct pool settings")


def test_app_factory_has_pool_settings():
    """Test that app_factory has correct pool settings"""
    # Just verify the file can be parsed
    with open('server/app_factory.py', 'r') as f:
        content = f.read()
        
    # Check for pool_pre_ping
    assert "'pool_pre_ping': True" in content or '"pool_pre_ping": True' in content, \
        "app_factory should have pool_pre_ping enabled"
    
    # Check for pool_recycle: 180
    assert "'pool_recycle': 180" in content or '"pool_recycle": 180' in content, \
        "app_factory should have pool_recycle set to 180"
    
    print("✅ app_factory.py has correct pool settings")


def test_sync_status_endpoint_has_error_handling():
    """Test that sync/status endpoint has OperationalError handling"""
    with open('server/routes_receipts.py', 'r') as f:
        content = f.read()
    
    # Verify OperationalError is imported at the top
    import_section = content[:5000]  # Check first 5000 chars for imports
    assert 'from sqlalchemy.exc import OperationalError' in import_section, \
        "OperationalError should be imported at the top of file"
    
    # Verify error handling is in place
    assert 'except OperationalError' in content, \
        "Should have OperationalError exception handling"
    
    # Verify db.session.rollback() is called
    assert 'db.session.rollback()' in content, \
        "Should rollback session on OperationalError"
    
    # Verify 503 status code is returned
    assert '503' in content, \
        "Should return 503 status on connection error"
    
    # Verify retry flag is set
    assert '"retry": True' in content or "'retry': True" in content, \
        "Should set retry flag on connection error"
    
    # Verify success: False is included in error response
    error_response_section = content[content.find('except OperationalError'):content.find('except OperationalError') + 500]
    assert '"success": False' in error_response_section or "'success': False" in error_response_section, \
        "Error response should include 'success': False"
    
    print("✅ sync/status endpoint has proper error handling")


def test_database_url_has_ssl_mode():
    """Test that database_url module handles SSL correctly"""
    with open('server/database_url.py', 'r') as f:
        content = f.read()
    
    # Verify sslmode=require is added when SSL is enabled
    assert 'sslmode=require' in content, \
        "database_url should add sslmode=require parameter"
    
    print("✅ database_url.py handles SSL correctly")


if __name__ == '__main__':
    print("Testing DB SSL Connection Fix...\n")
    
    test_production_config_has_pool_settings()
    test_app_factory_has_pool_settings()
    test_sync_status_endpoint_has_error_handling()
    test_database_url_has_ssl_mode()
    
    print("\n✅ All tests passed!")
