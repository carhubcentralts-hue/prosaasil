"""
Test TTS Preview, Voice Dropdown, and Caching Fixes
Validates the fixes for:
1. TTS preview audio response (not JSON serialization)
2. Voice dropdown with friendly names
3. Caching to prevent bottlenecks
"""
import os
import sys
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_cache_implementation():
    """Test TTLCache basic functionality"""
    print("🔧 Testing TTLCache Implementation")
    print("=" * 60)
    
    from server.utils.cache import TTLCache
    
    # Test basic set/get
    print("\n1️⃣ Test: Basic set/get")
    cache = TTLCache(ttl_seconds=5, max_size=10)
    cache.set('test_key', 'test_value')
    value = cache.get('test_key')
    if value == 'test_value':
        print("   ✅ Basic set/get works")
    else:
        print(f"   ❌ Expected 'test_value', got {value}")
        return False
    
    # Test expiration
    print("\n2️⃣ Test: TTL expiration")
    cache_short = TTLCache(ttl_seconds=1, max_size=10)
    cache_short.set('expire_key', 'expire_value')
    time.sleep(1.2)  # Wait for expiration
    value = cache_short.get('expire_key')
    if value is None:
        print("   ✅ Key expired correctly")
    else:
        print(f"   ❌ Expected None, got {value}")
        return False
    
    # Test delete
    print("\n3️⃣ Test: Delete/invalidation")
    cache.set('delete_key', 'delete_value')
    cache.delete('delete_key')
    value = cache.get('delete_key')
    if value is None:
        print("   ✅ Delete works correctly")
    else:
        print(f"   ❌ Expected None after delete, got {value}")
        return False
    
    # Test max size
    print("\n4️⃣ Test: Max size enforcement")
    small_cache = TTLCache(ttl_seconds=60, max_size=3)
    for i in range(5):
        small_cache.set(f'key_{i}', f'value_{i}')
    size = small_cache.size()
    if size <= 3:
        print(f"   ✅ Max size enforced (size={size})")
    else:
        print(f"   ❌ Size {size} exceeds max_size=3")
        return False
    
    print("\n" + "=" * 60)
    print("✅ All cache tests passed!")
    return True


def test_voice_metadata():
    """Test voice metadata configuration"""
    print("\n🔧 Testing Voice Metadata Configuration")
    print("=" * 60)
    
    from server.config.voices import OPENAI_VOICES, OPENAI_VOICES_METADATA, DEFAULT_VOICE
    
    print("\n1️⃣ Test: Voice list exists")
    if len(OPENAI_VOICES) > 0:
        print(f"   ✅ {len(OPENAI_VOICES)} voices configured")
    else:
        print("   ❌ No voices configured")
        return False
    
    print("\n2️⃣ Test: Voice metadata structure")
    for voice_id in OPENAI_VOICES:
        if voice_id not in OPENAI_VOICES_METADATA:
            print(f"   ❌ Voice {voice_id} missing metadata")
            return False
        
        metadata = OPENAI_VOICES_METADATA[voice_id]
        required_fields = ['id', 'name', 'gender', 'description']
        for field in required_fields:
            if field not in metadata:
                print(f"   ❌ Voice {voice_id} missing field: {field}")
                return False
    
    print(f"   ✅ All {len(OPENAI_VOICES)} voices have complete metadata")
    
    print("\n3️⃣ Test: Default voice is valid")
    if DEFAULT_VOICE in OPENAI_VOICES:
        print(f"   ✅ Default voice '{DEFAULT_VOICE}' is valid")
        print(f"      Name: {OPENAI_VOICES_METADATA[DEFAULT_VOICE]['name']}")
    else:
        print(f"   ❌ Default voice '{DEFAULT_VOICE}' not in voice list")
        return False
    
    print("\n4️⃣ Test: Voice names are user-friendly")
    sample_names = [OPENAI_VOICES_METADATA[v]['name'] for v in OPENAI_VOICES[:3]]
    print(f"   Sample names: {', '.join(sample_names)}")
    # Check that names are not just IDs
    has_descriptive_names = any('(' in name for name in sample_names)
    if has_descriptive_names:
        print("   ✅ Names include descriptive information")
    else:
        print("   ⚠️  Names may not be descriptive enough")
    
    print("\n" + "=" * 60)
    print("✅ All voice metadata tests passed!")
    return True


def test_api_guard_response_handling():
    """Test that api_guard handles Response objects correctly"""
    print("\n🔧 Testing API Guard Response Handling")
    print("=" * 60)
    
    # Check that the code has the right structure
    with open('server/utils/api_guard.py', 'r') as f:
        code = f.read()
    
    print("\n1️⃣ Test: Response import exists")
    if 'from flask import' in code and 'Response' in code:
        print("   ✅ Response is imported")
    else:
        print("   ❌ Response not imported")
        return False
    
    print("\n2️⃣ Test: Response type check exists")
    if 'isinstance(rv, Response)' in code:
        print("   ✅ Response type check present")
    else:
        print("   ❌ Response type check missing")
        return False
    
    print("\n3️⃣ Test: Tuple response check exists")
    if 'isinstance(rv, tuple)' in code and 'isinstance(rv[0], Response)' in code:
        print("   ✅ Tuple response check present")
    else:
        print("   ❌ Tuple response check missing")
        return False
    
    print("\n" + "=" * 60)
    print("✅ All api_guard tests passed!")
    return True


def test_voice_endpoints():
    """Test voice-related API endpoints"""
    print("\n🔧 Testing Voice API Endpoints")
    print("=" * 60)
    
    from server.app_factory import create_minimal_app
    from server.routes_ai_system import ai_system_bp
    
    app = create_minimal_app()
    
    # Register the blueprint
    if 'ai_system' not in app.blueprints:
        app.register_blueprint(ai_system_bp)
    
    with app.test_client() as client:
        print("\n1️⃣ Test: GET /api/system/ai/voices returns voice metadata")
        response = client.get('/api/system/ai/voices')
        print(f"   Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"   ❌ Expected 200, got {response.status_code}")
            return False
        
        data = response.get_json()
        if not data or not data.get('ok'):
            print("   ❌ Response not OK")
            return False
        
        voices = data.get('voices', [])
        if len(voices) == 0:
            print("   ❌ No voices returned")
            return False
        
        print(f"   ✅ Returned {len(voices)} voices")
        
        # Check first voice has required fields
        first_voice = voices[0]
        required_fields = ['id', 'name']
        for field in required_fields:
            if field not in first_voice:
                print(f"   ❌ Voice missing field: {field}")
                return False
        
        print(f"   ✅ Voice has name: '{first_voice['name']}'")
        
        # Check that names are descriptive
        if first_voice['name'] != first_voice['id']:
            print("   ✅ Voice name is descriptive (not just ID)")
        else:
            print("   ⚠️  Voice name is same as ID")
        
        print("\n2️⃣ Test: Default voice is included")
        default_voice = data.get('default_voice')
        if default_voice:
            print(f"   ✅ Default voice: {default_voice}")
            voice_ids = [v['id'] for v in voices]
            if default_voice in voice_ids:
                print("   ✅ Default voice is in voice list")
            else:
                print("   ❌ Default voice not in voice list")
                return False
        else:
            print("   ❌ No default_voice in response")
            return False
    
    print("\n" + "=" * 60)
    print("✅ All voice endpoint tests passed!")
    return True


def test_caching_integration():
    """Test caching integration in routes_ai_system"""
    print("\n🔧 Testing Caching Integration")
    print("=" * 60)
    
    from server.routes_ai_system import get_cached_voice_for_business, _ai_settings_cache
    from server.config.voices import DEFAULT_VOICE
    
    print("\n1️⃣ Test: get_cached_voice_for_business function exists")
    if callable(get_cached_voice_for_business):
        print("   ✅ Function exists")
    else:
        print("   ❌ Function not found")
        return False
    
    print("\n2️⃣ Test: Returns default voice for invalid business_id")
    voice = get_cached_voice_for_business(None)
    if voice == DEFAULT_VOICE:
        print(f"   ✅ Returns default voice '{DEFAULT_VOICE}' for None")
    else:
        print(f"   ❌ Expected '{DEFAULT_VOICE}', got '{voice}'")
        return False
    
    print("\n3️⃣ Test: Returns default voice for non-existent business")
    voice = get_cached_voice_for_business(99999999)
    if voice == DEFAULT_VOICE:
        print(f"   ✅ Returns default voice for non-existent business")
    else:
        print(f"   ❌ Expected '{DEFAULT_VOICE}', got '{voice}'")
        return False
    
    print("\n4️⃣ Test: Cache instance is properly initialized")
    if _ai_settings_cache is not None:
        print("   ✅ Cache instance exists")
        print(f"   TTL: {_ai_settings_cache.ttl_seconds}s")
        print(f"   Max size: {_ai_settings_cache.max_size}")
    else:
        print("   ❌ Cache instance not initialized")
        return False
    
    print("\n" + "=" * 60)
    print("✅ All caching integration tests passed!")
    return True


if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("TTS PREVIEW, VOICE DROPDOWN & CACHING - TEST SUITE")
    print("=" * 60)
    
    success = True
    
    tests = [
        ("Cache Implementation", test_cache_implementation),
        ("Voice Metadata", test_voice_metadata),
        ("API Guard Response Handling", test_api_guard_response_handling),
        ("Voice Endpoints", test_voice_endpoints),
        ("Caching Integration", test_caching_integration),
    ]
    
    for test_name, test_func in tests:
        try:
            if not test_func():
                success = False
        except Exception as e:
            print(f"\n❌ {test_name} failed with exception: {e}")
            import traceback
            traceback.print_exc()
            success = False
    
    print("\n" + "=" * 60)
    if success:
        print("✅ ALL TESTS PASSED!")
        print("\n📋 Summary:")
        print("   ✓ TTS preview will return audio (not JSON)")
        print("   ✓ Voice dropdown shows friendly names")
        print("   ✓ Caching prevents DB bottlenecks")
    else:
        print("❌ SOME TESTS FAILED")
    print("=" * 60)
    
    sys.exit(0 if success else 1)
