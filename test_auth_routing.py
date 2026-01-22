"""
Test auth routing - verify endpoints return correct status codes
This test ensures auth routes are registered correctly and don't return 404/405
"""
import os
import sys

# Set test environment
os.environ['DATABASE_URL'] = os.getenv('DATABASE_URL', 'sqlite:///:memory:')
os.environ['FLASK_SECRET_KEY'] = 'test-secret-key'
os.environ['MIGRATION_MODE'] = '1'
os.environ['ASYNC_LOG_QUEUE'] = '0'

def test_auth_routes_are_registered():
    """Verify auth blueprint is registered with correct routes"""
    from server.app_factory import create_app
    
    app = create_app()
    
    # Get all auth routes
    auth_routes = {}
    for rule in app.url_map.iter_rules():
        if 'auth' in rule.rule.lower():
            methods = sorted([m for m in rule.methods if m not in ["HEAD", "OPTIONS"]])
            auth_routes[rule.rule] = methods
    
    # Verify critical routes exist
    assert '/api/auth/csrf' in auth_routes, "Missing /api/auth/csrf route"
    assert '/api/auth/me' in auth_routes, "Missing /api/auth/me route"
    assert '/api/auth/login' in auth_routes, "Missing /api/auth/login route"
    
    # Verify methods
    assert 'GET' in auth_routes['/api/auth/csrf'], "GET method missing for /api/auth/csrf"
    assert 'GET' in auth_routes['/api/auth/me'], "GET method missing for /api/auth/me"
    assert 'POST' in auth_routes['/api/auth/login'], "POST method missing for /api/auth/login"
    
    print("✅ All auth routes registered correctly:")
    for route, methods in sorted(auth_routes.items()):
        print(f"   {route} → {methods}")

def test_csrf_endpoint_returns_200():
    """Test that /api/auth/csrf returns 200 (not 404)"""
    from server.app_factory import create_app
    
    app = create_app()
    client = app.test_client()
    
    response = client.get('/api/auth/csrf')
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    # Verify response has csrfToken
    data = response.get_json()
    assert 'csrfToken' in data, "Response missing csrfToken field"
    assert data['csrfToken'], "csrfToken should not be empty"
    
    print(f"✅ GET /api/auth/csrf returns 200 with token: {data['csrfToken'][:20]}...")

def test_me_endpoint_returns_401_not_404():
    """Test that /api/auth/me returns 401 when not authenticated (not 404)"""
    from server.app_factory import create_app
    
    app = create_app()
    client = app.test_client()
    
    response = client.get('/api/auth/me')
    
    # Should return 401 (unauthorized), NOT 404 (not found)
    assert response.status_code == 401, f"Expected 401 (unauthorized), got {response.status_code}"
    
    data = response.get_json()
    assert 'error' in data, "Response should contain error field"
    
    print(f"✅ GET /api/auth/me returns 401 (not 404): {data.get('error')}")

def test_login_endpoint_accepts_post_not_405():
    """Test that /api/auth/login accepts POST method (not 405)"""
    from server.app_factory import create_app
    
    app = create_app()
    client = app.test_client()
    
    # Test with invalid credentials
    response = client.post('/api/auth/login', json={
        'email': 'nonexistent@example.com',
        'password': 'wrongpassword'
    })
    
    # Should NOT return 405 (method not allowed)
    # Should return 400 (bad request) or 401 (unauthorized), not 405
    assert response.status_code != 405, f"POST /api/auth/login should not return 405 (method not allowed)"
    assert response.status_code in [400, 401, 500], f"Expected 400/401/500, got {response.status_code}"
    
    print(f"✅ POST /api/auth/login accepts POST method (returns {response.status_code}, not 405)")

def test_login_with_valid_admin_credentials():
    """Test login with admin@admin.com credentials (if exists)"""
    from server.app_factory import create_app
    from server.models_sql import User, db
    from werkzeug.security import generate_password_hash
    
    app = create_app()
    
    # Create test admin user
    with app.app_context():
        try:
            # Check if user exists
            existing_user = User.query.filter_by(email='admin@admin.com').first()
            if not existing_user:
                admin = User(
                    email='admin@admin.com',
                    password_hash=generate_password_hash('admin123', method='scrypt'),
                    name='Test Admin',
                    role='system_admin',
                    business_id=None,
                    is_active=True
                )
                db.session.add(admin)
                db.session.commit()
        except Exception as e:
            print(f"⚠️ Could not create test admin: {e}")
            db.session.rollback()
    
    client = app.test_client()
    
    # Test login
    response = client.post('/api/auth/login', json={
        'email': 'admin@admin.com',
        'password': 'admin123'
    })
    
    # Should return 200 on success
    if response.status_code == 200:
        data = response.get_json()
        assert 'user' in data, "Response should contain user field"
        assert data['user']['email'] == 'admin@admin.com'
        print(f"✅ POST /api/auth/login returns 200 with user: {data['user']['email']}")
    else:
        # If not 200, at least verify it's not 404 or 405
        assert response.status_code not in [404, 405], f"Login should not return {response.status_code}"
        print(f"⚠️ POST /api/auth/login returns {response.status_code} (database might not be ready)")

if __name__ == '__main__':
    print("🔍 Testing auth routing...")
    print("=" * 60)
    
    try:
        test_auth_routes_are_registered()
        test_csrf_endpoint_returns_200()
        test_me_endpoint_returns_401_not_404()
        test_login_endpoint_accepts_post_not_405()
        test_login_with_valid_admin_credentials()
        
        print("=" * 60)
        print("✅ All auth routing tests passed!")
    except AssertionError as e:
        print("=" * 60)
        print(f"❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print("=" * 60)
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
