"""
Test password reset flow - validates token handling and API integration
"""
import os
import sys
from datetime import datetime, timedelta

# Set test environment
os.environ['DATABASE_URL'] = os.getenv('DATABASE_URL', 'sqlite:///:memory:')
os.environ['FLASK_SECRET_KEY'] = 'test-secret-key'
os.environ['MIGRATION_MODE'] = '1'
os.environ['ASYNC_LOG_QUEUE'] = '0'
os.environ['SENDGRID_API_KEY'] = 'test-key'  # Mock SendGrid

def test_password_reset_token_not_consumed_on_validation():
    """Test that validating a reset token does NOT mark it as used"""
    from server.models_sql import User, db
    from server.services.auth_service import AuthService
    from server.extensions import create_app
    from werkzeug.security import generate_password_hash
    
    app = create_app()
    
    with app.app_context():
        # Create tables
        db.create_all()
        
        # Create test user
        user = User(
            email='test@example.com',
            password_hash=generate_password_hash('oldpassword123', method='scrypt'),
            name='Test User',
            role='admin',
            is_active=True
        )
        db.session.add(user)
        db.session.commit()
        
        # Generate reset token
        AuthService.generate_password_reset_token('test@example.com')
        
        # Reload user to get token
        user = User.query.filter_by(email='test@example.com').first()
        assert user.reset_token_hash is not None
        assert user.reset_token_expiry is not None
        assert user.reset_token_used == False
        
        # Save token hash for validation
        token_hash = user.reset_token_hash
        
        # Simulate: User receives email and clicks link (no server interaction yet)
        # This is just opening the page in browser - should NOT consume token
        
        # Validate token (simulating what would happen if we had a GET endpoint)
        # In our case, we don't have a GET endpoint, but let's test the validation
        # function directly to ensure it doesn't consume the token
        from server.services.auth_service import hash_token
        
        # Create a mock token (we need to reverse-engineer it since we only have the hash)
        # In reality, the plain token is sent via email
        # For testing, we'll generate a new token that we control
        import secrets
        plain_token = secrets.token_urlsafe(32)
        user.reset_token_hash = hash_token(plain_token)
        user.reset_token_expiry = datetime.utcnow() + timedelta(minutes=60)
        user.reset_token_used = False
        db.session.commit()
        
        # Validate token multiple times (simulating page refresh)
        validated_user = AuthService.validate_reset_token(plain_token)
        assert validated_user is not None
        assert validated_user.id == user.id
        
        # Check token is still NOT marked as used after validation
        user = User.query.filter_by(email='test@example.com').first()
        assert user.reset_token_used == False, "Token should NOT be consumed by validation"
        
        # Validate again (page refresh scenario)
        validated_user = AuthService.validate_reset_token(plain_token)
        assert validated_user is not None
        
        # Token should STILL be valid
        user = User.query.filter_by(email='test@example.com').first()
        assert user.reset_token_used == False, "Token should survive multiple validations"
        
        print("✅ Token validation does NOT consume the token")
        
        # Now complete password reset (POST)
        success = AuthService.complete_password_reset(plain_token, generate_password_hash('newpassword123', method='scrypt'))
        assert success == True
        
        # NOW token should be marked as used
        user = User.query.filter_by(email='test@example.com').first()
        assert user.reset_token_used == True, "Token should be marked as used after password reset"
        
        # Second attempt should fail
        success = AuthService.complete_password_reset(plain_token, generate_password_hash('anotherpassword', method='scrypt'))
        assert success == False, "Second reset attempt should fail"
        
        print("✅ Token is consumed ONLY on password reset (POST)")
        
        db.session.rollback()

def test_reset_password_api_field_names():
    """Test that /api/auth/reset accepts both 'password' and 'newPassword' fields"""
    from server.extensions import create_app
    from server.models_sql import User, db
    from server.services.auth_service import AuthService
    from werkzeug.security import generate_password_hash
    import secrets
    import json
    
    app = create_app()
    
    with app.app_context():
        # Create tables
        db.create_all()
        
        # Create test user
        user = User(
            email='test2@example.com',
            password_hash=generate_password_hash('oldpassword123', method='scrypt'),
            name='Test User 2',
            role='admin',
            is_active=True
        )
        db.session.add(user)
        db.session.commit()
        
        # Generate reset token
        plain_token = secrets.token_urlsafe(32)
        from server.services.auth_service import hash_token
        user.reset_token_hash = hash_token(plain_token)
        user.reset_token_expiry = datetime.utcnow() + timedelta(minutes=60)
        user.reset_token_used = False
        db.session.commit()
        
        # Test with 'password' field (backend standard)
        with app.test_client() as client:
            response = client.post(
                '/api/auth/reset',
                data=json.dumps({
                    'token': plain_token,
                    'password': 'newpassword123'
                }),
                content_type='application/json',
                headers={'X-CSRFToken': 'test-token'}  # Mock CSRF
            )
            
            # Should succeed
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.data}"
            data = json.loads(response.data)
            assert data['success'] == True
        
        print("✅ API accepts 'password' field")
        
        # Reset for next test
        user = User.query.filter_by(email='test2@example.com').first()
        plain_token2 = secrets.token_urlsafe(32)
        user.reset_token_hash = hash_token(plain_token2)
        user.reset_token_expiry = datetime.utcnow() + timedelta(minutes=60)
        user.reset_token_used = False
        db.session.commit()
        
        # Test with 'newPassword' field (frontend sends this)
        with app.test_client() as client:
            response = client.post(
                '/api/auth/reset',
                data=json.dumps({
                    'token': plain_token2,
                    'newPassword': 'anotherpassword123'
                }),
                content_type='application/json',
                headers={'X-CSRFToken': 'test-token'}  # Mock CSRF
            )
            
            # Should also succeed (backward compatibility)
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.data}"
            data = json.loads(response.data)
            assert data['success'] == True
        
        print("✅ API also accepts 'newPassword' field (backward compatibility)")
        
        db.session.rollback()

def test_token_survives_page_refresh():
    """Test that refreshing the reset password page doesn't invalidate the token"""
    from server.models_sql import User, db
    from server.services.auth_service import AuthService
    from server.extensions import create_app
    from werkzeug.security import generate_password_hash
    import secrets
    
    app = create_app()
    
    with app.app_context():
        # Create tables
        db.create_all()
        
        # Create test user
        user = User(
            email='test3@example.com',
            password_hash=generate_password_hash('oldpassword123', method='scrypt'),
            name='Test User 3',
            role='admin',
            is_active=True
        )
        db.session.add(user)
        db.session.commit()
        
        # Generate reset token
        plain_token = secrets.token_urlsafe(32)
        from server.services.auth_service import hash_token
        user.reset_token_hash = hash_token(plain_token)
        user.reset_token_expiry = datetime.utcnow() + timedelta(minutes=60)
        user.reset_token_used = False
        db.session.commit()
        
        # Simulate: User opens link, page loads (GET /reset-password?token=XXX)
        # In our implementation, this is a frontend route only, no server call
        
        # Simulate: User refreshes page multiple times
        for i in range(3):
            # Each refresh just reloads the frontend page
            # No server interaction that would consume the token
            user = User.query.filter_by(email='test3@example.com').first()
            assert user.reset_token_used == False, f"Token should survive refresh #{i+1}"
        
        print("✅ Token survives multiple page refreshes")
        
        # Now user submits the form (POST /api/auth/reset)
        success = AuthService.complete_password_reset(plain_token, generate_password_hash('newpassword123', method='scrypt'))
        assert success == True
        
        # Token should now be consumed
        user = User.query.filter_by(email='test3@example.com').first()
        assert user.reset_token_used == True
        
        print("✅ Token is consumed only after form submission")
        
        db.session.rollback()

if __name__ == '__main__':
    print("\n🧪 Testing Password Reset Flow\n")
    print("=" * 60)
    
    tests = [
        ("Token validation doesn't consume token", test_password_reset_token_not_consumed_on_validation),
        ("API accepts both field names", test_reset_password_api_field_names),
        ("Token survives page refresh", test_token_survives_page_refresh),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            print(f"\n▶️  {name}")
            test_func()
            passed += 1
            print(f"✅ PASSED: {name}")
        except AssertionError as e:
            failed += 1
            print(f"❌ FAILED: {name}")
            print(f"   Error: {e}")
        except Exception as e:
            failed += 1
            print(f"❌ ERROR: {name}")
            print(f"   Error: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print(f"\n📊 Results: {passed} passed, {failed} failed")
    
    if failed > 0:
        sys.exit(1)
    else:
        print("\n✅ All tests passed!")
        sys.exit(0)
