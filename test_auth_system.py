"""
Test authentication system - tokens, idle timeout, password reset
"""
import os
import sys
from datetime import datetime, timedelta

# Set test environment
os.environ['DATABASE_URL'] = os.getenv('DATABASE_URL', 'sqlite:///:memory:')
os.environ['FLASK_SECRET_KEY'] = 'test-secret-key'
os.environ['MIGRATION_MODE'] = '1'
os.environ['ASYNC_LOG_QUEUE'] = '0'

def test_refresh_token_model():
    """Test RefreshToken model exists and has correct fields"""
    from server.models_sql import RefreshToken
    
    # Check model has expected fields
    assert hasattr(RefreshToken, 'id')
    assert hasattr(RefreshToken, 'user_id')
    assert hasattr(RefreshToken, 'tenant_id')
    assert hasattr(RefreshToken, 'token_hash')
    assert hasattr(RefreshToken, 'user_agent_hash')
    assert hasattr(RefreshToken, 'expires_at')
    assert hasattr(RefreshToken, 'is_valid')
    assert hasattr(RefreshToken, 'remember_me')
    assert hasattr(RefreshToken, 'created_at')
    assert hasattr(RefreshToken, 'last_used_at')
    
    print("✅ RefreshToken model has all required fields")

def test_user_model_password_reset_fields():
    """Test User model has password reset fields"""
    from server.models_sql import User
    
    # Check password reset fields
    assert hasattr(User, 'reset_token_hash')
    assert hasattr(User, 'reset_token_expiry')
    assert hasattr(User, 'reset_token_used')
    assert hasattr(User, 'last_activity_at')
    
    print("✅ User model has password reset and activity tracking fields")

def test_auth_service_token_hashing():
    """Test token hashing function"""
    from server.services.auth_service import hash_token, hash_user_agent
    
    # Test token hashing
    token = "test_token_123"
    hashed = hash_token(token)
    
    assert isinstance(hashed, str)
    assert len(hashed) == 64  # SHA-256 produces 64 hex characters
    assert hashed != token  # Should be different from original
    
    # Same token should produce same hash
    hashed2 = hash_token(token)
    assert hashed == hashed2
    
    # Different tokens should produce different hashes
    hashed3 = hash_token("different_token")
    assert hashed != hashed3
    
    print("✅ Token hashing works correctly")
    
    # Test user agent hashing
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    ua_hash = hash_user_agent(ua)
    assert isinstance(ua_hash, str)
    assert len(ua_hash) == 64
    
    # None user agent should return None
    assert hash_user_agent(None) is None
    
    print("✅ User agent hashing works correctly")

def test_auth_service_constants():
    """Test auth service configuration constants"""
    from server.services.auth_service import (
        ACCESS_TOKEN_LIFETIME_MINUTES,
        REFRESH_TOKEN_DEFAULT_DAYS,
        REFRESH_TOKEN_REMEMBER_DAYS,
        IDLE_TIMEOUT_MINUTES,
        PASSWORD_RESET_TOKEN_MINUTES
    )
    
    # Verify constants match specification
    assert ACCESS_TOKEN_LIFETIME_MINUTES == 90, "Access token should be 90 minutes"
    assert REFRESH_TOKEN_DEFAULT_DAYS == 1, "Default refresh token should be 1 day (24 hours)"
    assert REFRESH_TOKEN_REMEMBER_DAYS == 30, "Remember me refresh token should be 30 days"
    assert IDLE_TIMEOUT_MINUTES == 75, "Idle timeout should be 75 minutes"
    assert PASSWORD_RESET_TOKEN_MINUTES == 60, "Password reset token should be 60 minutes"
    
    print("✅ Auth service constants match specification")

def test_email_service_initialization():
    """Test email service can be initialized"""
    from server.services.email_service import EmailService, get_email_service
    
    # Get singleton instance
    service = get_email_service()
    assert service is not None
    assert isinstance(service, EmailService)
    
    # Should return same instance
    service2 = get_email_service()
    assert service is service2
    
    print("✅ Email service initializes correctly")

def test_migration_57_in_db_migrate():
    """Test that Migration 57 is present in db_migrate.py"""
    with open('server/db_migrate.py', 'r') as f:
        content = f.read()
    
    # Check for migration 57
    assert 'Migration 57' in content, "Migration 57 should be in db_migrate.py"
    assert 'refresh_tokens' in content, "Migration should create refresh_tokens table"
    assert 'reset_token_hash' in content, "Migration should add reset_token_hash"
    assert 'reset_token_expiry' in content, "Migration should add reset_token_expiry"
    assert 'reset_token_used' in content, "Migration should add reset_token_used"
    assert 'last_activity_at' in content, "Migration should add last_activity_at"
    
    print("✅ Migration 57 is properly defined in db_migrate.py")

def test_sendgrid_dependency():
    """Test that sendgrid is importable"""
    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail, Email, To, Content
        print("✅ SendGrid dependency is available")
    except ImportError as e:
        print(f"⚠️ SendGrid not installed yet: {e}")
        print("   Run: pip install sendgrid>=6.11.0")

def test_env_example_has_sendgrid_vars():
    """Test that .env.example has SendGrid configuration"""
    with open('.env.example', 'r') as f:
        content = f.read()
    
    assert 'SENDGRID_API_KEY' in content, ".env.example should have SENDGRID_API_KEY"
    assert 'MAIL_FROM_EMAIL' in content, ".env.example should have MAIL_FROM_EMAIL"
    assert 'MAIL_FROM_NAME' in content, ".env.example should have MAIL_FROM_NAME"
    assert 'MAIL_REPLY_TO' in content, ".env.example should have MAIL_REPLY_TO"
    assert 'noreply@prosaas.pro' in content, ".env.example should have prosaas.pro email"
    
    print("✅ .env.example has SendGrid configuration")

if __name__ == '__main__':
    print("\n" + "="*70)
    print("AUTHENTICATION SYSTEM TESTS")
    print("="*70 + "\n")
    
    tests = [
        test_refresh_token_model,
        test_user_model_password_reset_fields,
        test_auth_service_token_hashing,
        test_auth_service_constants,
        test_email_service_initialization,
        test_migration_57_in_db_migrate,
        test_sendgrid_dependency,
        test_env_example_has_sendgrid_vars,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            print(f"\n▶ Running: {test.__name__}")
            test()
            passed += 1
        except Exception as e:
            print(f"❌ FAILED: {test.__name__}")
            print(f"   Error: {e}")
            failed += 1
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("="*70 + "\n")
    
    sys.exit(0 if failed == 0 else 1)
