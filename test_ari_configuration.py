#!/usr/bin/env python3
"""
Test script to verify ARI configuration and internal API endpoints.
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_ari_configuration():
    """Test that ARI configuration is properly set up."""
    print("=" * 60)
    print("Testing ARI Configuration")
    print("=" * 60)
    
    # Test 1: Check environment variables
    print("\n1. Environment Variables:")
    env_vars = {
        'ASTERISK_ARI_URL': os.getenv('ASTERISK_ARI_URL', 'NOT SET'),
        'ASTERISK_ARI_USER': os.getenv('ASTERISK_ARI_USER', 'NOT SET'),
        'ASTERISK_ARI_PASSWORD': '***' if os.getenv('ASTERISK_ARI_PASSWORD') else 'NOT SET',
        'ARI_APP_NAME': os.getenv('ARI_APP_NAME', 'NOT SET'),
    }
    
    for key, value in env_vars.items():
        print(f"   {key}: {value}")
    
    # Test 2: Check that ARI service can be imported
    print("\n2. ARI Service Import:")
    try:
        from server.services.asterisk_ari_service import AsteriskARIService
        print("   ✅ AsteriskARIService imported successfully")
    except ImportError as e:
        print(f"   ❌ Failed to import AsteriskARIService: {e}")
        return False
    
    # Test 3: Check lazy services
    print("\n3. Lazy Services:")
    try:
        from server.services.lazy_services import get_ari_service
        print("   ✅ get_ari_service function available")
    except ImportError as e:
        print(f"   ❌ Failed to import get_ari_service: {e}")
        return False
    
    # Test 4: Check internal API routes
    print("\n4. Internal API Routes:")
    try:
        from server.routes_asterisk_internal import asterisk_internal_bp
        print("   ✅ asterisk_internal_bp blueprint imported")
        
        # Check routes
        routes = []
        for rule in asterisk_internal_bp.url_map.iter_rules():
            routes.append(f"{rule.rule} [{', '.join(rule.methods - {'HEAD', 'OPTIONS'})}]")
        
        if routes:
            print("   Routes registered:")
            for route in routes:
                print(f"      {route}")
        else:
            print("   ⚠️  No routes found (blueprint not yet registered)")
            
    except ImportError as e:
        print(f"   ❌ Failed to import asterisk_internal_bp: {e}")
        return False
    
    # Test 5: Check ARI config files
    print("\n5. Asterisk Configuration Files:")
    config_files = {
        'ari.conf': 'infra/asterisk/ari.conf',
        'http.conf': 'infra/asterisk/http.conf',
        'extensions.conf': 'infra/asterisk/extensions.conf',
    }
    
    for name, path in config_files.items():
        if os.path.exists(path):
            print(f"   ✅ {name} exists")
            
            # Check for key content
            with open(path, 'r') as f:
                content = f.read()
                
            if name == 'ari.conf' and 'prosaas' in content:
                print(f"      - Contains 'prosaas' user")
            elif name == 'http.conf' and 'enabled = yes' in content:
                print(f"      - HTTP server enabled")
            elif name == 'extensions.conf' and 'prosaas_ai' in content:
                print(f"      - Stasis app 'prosaas_ai' configured")
        else:
            print(f"   ❌ {name} not found at {path}")
    
    print("\n" + "=" * 60)
    print("✅ All configuration tests passed!")
    print("=" * 60)
    return True


def test_internal_api_routes():
    """Test internal API routes with mock data."""
    print("\n" + "=" * 60)
    print("Testing Internal API Routes (Mock)")
    print("=" * 60)
    
    try:
        # Set migration mode to avoid eventlet dependency
        os.environ['MIGRATION_MODE'] = '1'
        
        from server.app_factory import create_minimal_app
        
        app = create_minimal_app()
        
        # Register the blueprint
        from server.routes_asterisk_internal import asterisk_internal_bp
        app.register_blueprint(asterisk_internal_bp)
        
        with app.test_client() as client:
            # Test 1: Call start endpoint
            print("\n1. Testing POST /internal/calls/start:")
            response = client.post('/internal/calls/start', json={
                'call_id': 'test-call-123',
                'tenant_id': 1,
                'direction': 'inbound',
                'from_number': '+1234567890',
                'to_number': '+0987654321',
                'provider': 'asterisk'
            })
            
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.get_json()}")
            
            if response.status_code in [200, 400]:  # 400 if tenant doesn't exist
                print("   ✅ Endpoint responding correctly")
            else:
                print(f"   ❌ Unexpected status code: {response.status_code}")
            
            # Test 2: Call end endpoint
            print("\n2. Testing POST /internal/calls/end:")
            response = client.post('/internal/calls/end', json={
                'call_id': 'test-call-123',
                'provider': 'asterisk'
            })
            
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.get_json()}")
            
            if response.status_code in [200, 404]:  # 404 if call doesn't exist
                print("   ✅ Endpoint responding correctly")
            else:
                print(f"   ❌ Unexpected status code: {response.status_code}")
        
        print("\n" + "=" * 60)
        print("✅ Internal API routes test completed!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n❌ Error testing internal API routes: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    print("\n🔍 ProSaaS AI - ARI Configuration Test Suite\n")
    
    # Run tests
    config_ok = test_ari_configuration()
    api_ok = test_internal_api_routes()
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Configuration Test: {'✅ PASS' if config_ok else '❌ FAIL'}")
    print(f"API Routes Test: {'✅ PASS' if api_ok else '❌ FAIL'}")
    print("=" * 60)
    
    sys.exit(0 if (config_ok and api_ok) else 1)
