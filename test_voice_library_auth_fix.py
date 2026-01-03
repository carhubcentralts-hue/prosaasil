"""
Test Voice Library Authentication Fix
Verify that business_id is properly resolved from session/JWT context
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_business_id_resolution():
    """Test that get_business_id_from_context() works correctly"""
    from server.app_factory import create_minimal_app
    from flask import g, session
    
    print("🔧 Testing Voice Library Authentication Fix")
    print("=" * 60)
    
    app = create_minimal_app()
    
    with app.app_context():
        with app.test_request_context():
            # Import the function we created
            from server.routes_ai_system import get_business_id_from_context
            
            print("\n1️⃣ Test: No business context (should return None)")
            business_id = get_business_id_from_context()
            if business_id is None:
                print("   ✅ Correctly returns None when no context")
            else:
                print(f"   ❌ Expected None, got {business_id}")
                return False
            
            print("\n2️⃣ Test: business_id from g.tenant")
            g.tenant = 123
            business_id = get_business_id_from_context()
            if business_id == 123:
                print("   ✅ Correctly reads from g.tenant")
            else:
                print(f"   ❌ Expected 123, got {business_id}")
                return False
            
            # Clear g.tenant
            g.tenant = None
            
            print("\n3️⃣ Test: business_id from session.user.business_id")
            session['user'] = {'business_id': 456}
            business_id = get_business_id_from_context()
            if business_id == 456:
                print("   ✅ Correctly reads from session['user']['business_id']")
            else:
                print(f"   ❌ Expected 456, got {business_id}")
                return False
            
            # Clear session
            session.clear()
            
            print("\n4️⃣ Test: business_id from session['business_id'] directly")
            session['business_id'] = 789
            business_id = get_business_id_from_context()
            if business_id == 789:
                print("   ✅ Correctly reads from session['business_id']")
            else:
                print(f"   ❌ Expected 789, got {business_id}")
                return False
            
            print("\n" + "=" * 60)
            print("✅ All business_id resolution tests passed!")
            return True


def test_voice_endpoints_status_codes():
    """Test that endpoints return 401 (not 400) when business_id is missing"""
    from server.app_factory import create_minimal_app
    
    print("\n🔧 Testing Voice Endpoints Status Codes")
    print("=" * 60)
    
    app = create_minimal_app()
    
    # Register the blueprint
    from server.routes_ai_system import ai_system_bp
    if 'ai_system' not in app.blueprints:
        app.register_blueprint(ai_system_bp)
    
    with app.test_client() as client:
        print("\n1️⃣ Test: GET /api/business/settings/ai without auth")
        response = client.get('/api/business/settings/ai')
        print(f"   Status: {response.status_code}")
        if response.status_code == 401:
            print("   ✅ Correctly returns 401 Unauthorized")
        elif response.status_code == 400:
            print("   ❌ Returns 400 (should be 401)")
            return False
        else:
            print(f"   ⚠️  Unexpected status code: {response.status_code}")
        
        print("\n2️⃣ Test: PUT /api/business/settings/ai without auth")
        response = client.put('/api/business/settings/ai', 
                             json={'voice_id': 'ash'},
                             content_type='application/json')
        print(f"   Status: {response.status_code}")
        if response.status_code == 401:
            print("   ✅ Correctly returns 401 Unauthorized")
        elif response.status_code == 400:
            print("   ❌ Returns 400 (should be 401)")
            return False
        else:
            print(f"   ⚠️  Unexpected status code: {response.status_code}")
        
        print("\n3️⃣ Test: POST /api/ai/tts/preview without auth")
        response = client.post('/api/ai/tts/preview',
                              json={'text': 'Hello World', 'voice_id': 'ash'},
                              content_type='application/json')
        print(f"   Status: {response.status_code}")
        if response.status_code == 401:
            print("   ✅ Correctly returns 401 Unauthorized")
        elif response.status_code == 400:
            print("   ❌ Returns 400 (should be 401)")
            return False
        else:
            print(f"   ⚠️  Unexpected status code: {response.status_code}")
        
        print("\n4️⃣ Test: GET /api/system/ai/voices (should not require auth)")
        response = client.get('/api/system/ai/voices')
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ Correctly returns 200 OK (no auth required)")
            data = response.get_json()
            if data and data.get('ok') and 'voices' in data:
                print(f"   ✅ Returns voice list ({len(data['voices'])} voices)")
            else:
                print(f"   ⚠️  Unexpected response format")
        else:
            print(f"   ❌ Expected 200, got {response.status_code}")
            return False
        
        print("\n" + "=" * 60)
        print("✅ All status code tests passed!")
        return True


if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("VOICE LIBRARY AUTHENTICATION FIX - TEST SUITE")
    print("=" * 60)
    
    success = True
    
    try:
        success = test_business_id_resolution() and success
    except Exception as e:
        print(f"\n❌ test_business_id_resolution failed: {e}")
        import traceback
        traceback.print_exc()
        success = False
    
    try:
        success = test_voice_endpoints_status_codes() and success
    except Exception as e:
        print(f"\n❌ test_voice_endpoints_status_codes failed: {e}")
        import traceback
        traceback.print_exc()
        success = False
    
    print("\n" + "=" * 60)
    if success:
        print("✅ ALL TESTS PASSED!")
    else:
        print("❌ SOME TESTS FAILED")
    print("=" * 60)
    
    sys.exit(0 if success else 1)
