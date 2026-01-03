"""
Test password reset with inactive users
Validates the fix for the is_active filtering bug
"""
import os
import sys

# Set test environment BEFORE importing anything else
os.environ['DATABASE_URL'] = os.getenv('DATABASE_URL', 'sqlite:///:memory:')
os.environ['FLASK_SECRET_KEY'] = 'test-secret-key'
os.environ['MIGRATION_MODE'] = '1'
os.environ['ASYNC_LOG_QUEUE'] = '0'

from server.app_factory import create_app
from server.models_sql import User, db
from server.services.auth_service import AuthService, hash_token
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import secrets

def test_reset_token_inactive_user():
    """
    Test that reset token lookup finds user even if inactive,
    but validation fails with appropriate message
    """
    app = create_app()
    
    with app.app_context():
        # Clean up test user if exists
        test_email = "test_inactive@example.com"
        existing_user = User.query.filter_by(email=test_email).first()
        if existing_user:
            db.session.delete(existing_user)
            db.session.commit()
        
        # Create test user (active initially)
        test_user = User(
            email=test_email,
            password_hash=generate_password_hash("password123", method='scrypt'),
            name="Test Inactive User",
            role="agent",
            business_id=1,  # Assuming business 1 exists
            is_active=True
        )
        db.session.add(test_user)
        db.session.commit()
        user_id = test_user.id
        
        print(f"✅ Created test user: {test_email} (id={user_id}, is_active=True)")
        
        # Generate reset token while user is active
        plain_token = secrets.token_urlsafe(32)
        token_hash = hash_token(plain_token)
        
        test_user.reset_token_hash = token_hash
        test_user.reset_token_expiry = datetime.utcnow() + timedelta(hours=1)
        test_user.reset_token_used = False
        db.session.commit()
        
        print(f"✅ Generated reset token: first8={plain_token[:8]} last8={plain_token[-8:]}")
        
        # Now mark user as inactive
        test_user.is_active = False
        db.session.commit()
        
        print(f"✅ Marked user as inactive (is_active=False)")
        
        # Validate token - should find user but reject due to inactive status
        validated_user = AuthService.validate_reset_token(plain_token)
        
        # Check result
        if validated_user is None:
            print("✅ PASS: validate_reset_token correctly returned None for inactive user")
            print("   (This is the expected behavior after the fix)")
        else:
            print("❌ FAIL: validate_reset_token should return None for inactive user")
            print(f"   Got user: {validated_user.email}")
            return False
        
        # Verify user was found (check logs would show found_user_id)
        # Manually check that user exists with the token
        found_user = User.query.filter_by(reset_token_hash=token_hash).first()
        if found_user:
            print(f"✅ PASS: User was found in DB by token (id={found_user.id})")
            print(f"   is_active={found_user.is_active}")
        else:
            print("❌ FAIL: User should exist in DB with the token")
            return False
        
        # Clean up
        db.session.delete(test_user)
        db.session.commit()
        print("✅ Cleaned up test user")
        
        return True

def test_reset_token_active_user():
    """
    Test that reset token works normally for active users
    """
    app = create_app()
    
    with app.app_context():
        # Clean up test user if exists
        test_email = "test_active@example.com"
        existing_user = User.query.filter_by(email=test_email).first()
        if existing_user:
            db.session.delete(existing_user)
            db.session.commit()
        
        # Create test user (active)
        test_user = User(
            email=test_email,
            password_hash=generate_password_hash("password123", method='scrypt'),
            name="Test Active User",
            role="agent",
            business_id=1,
            is_active=True
        )
        db.session.add(test_user)
        db.session.commit()
        user_id = test_user.id
        
        print(f"✅ Created test user: {test_email} (id={user_id}, is_active=True)")
        
        # Generate reset token
        plain_token = secrets.token_urlsafe(32)
        token_hash = hash_token(plain_token)
        
        test_user.reset_token_hash = token_hash
        test_user.reset_token_expiry = datetime.utcnow() + timedelta(hours=1)
        test_user.reset_token_used = False
        db.session.commit()
        
        print(f"✅ Generated reset token: first8={plain_token[:8]} last8={plain_token[-8:]}")
        
        # Validate token - should succeed
        validated_user = AuthService.validate_reset_token(plain_token)
        
        # Check result
        if validated_user and validated_user.id == user_id:
            print("✅ PASS: validate_reset_token correctly returned user for active user")
        else:
            print("❌ FAIL: validate_reset_token should return user for active user")
            return False
        
        # Clean up
        db.session.delete(test_user)
        db.session.commit()
        print("✅ Cleaned up test user")
        
        return True

if __name__ == "__main__":
    print("\n" + "="*60)
    print("TEST 1: Reset Token with Inactive User")
    print("="*60)
    result1 = test_reset_token_inactive_user()
    
    print("\n" + "="*60)
    print("TEST 2: Reset Token with Active User")
    print("="*60)
    result2 = test_reset_token_active_user()
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    if result1 and result2:
        print("✅ ALL TESTS PASSED")
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED")
        sys.exit(1)
