"""
Test Live Call AIService Fix
Validates that AIService now accepts business_id parameter
"""
import os
import sys
from unittest.mock import Mock, patch

# Set test environment
os.environ['TESTING'] = 'true'
os.environ['OPENAI_API_KEY'] = 'test-key-for-validation'

# Mock OpenAI before importing ai_service
sys.modules['openai'] = Mock()


def test_aiservice_initialization():
    """Test that AIService can be initialized with business_id"""
    from server.services.ai_service import AIService
    
    print("\n" + "=" * 60)
    print("Testing AIService Initialization")
    print("=" * 60)
    
    # Test 1: Initialize without business_id (backward compatible)
    ai_service = AIService()
    assert ai_service.business_id is None, "business_id should be None when not provided"
    print("✓ Can initialize without business_id (backward compatible)")
    
    # Test 2: Initialize with business_id
    ai_service_with_id = AIService(business_id=123)
    assert ai_service_with_id.business_id == 123, "business_id should be stored"
    print("✓ Can initialize with business_id=123")
    
    # Test 3: Verify other attributes are still initialized
    assert hasattr(ai_service, 'client'), "Should have OpenAI client"
    assert hasattr(ai_service, '_cache'), "Should have cache"
    assert hasattr(ai_service, '_cache_timeout'), "Should have cache timeout"
    print("✓ All other attributes initialized correctly")
    
    print("\n✅ AIService initialization test passed")


def test_get_system_prompt_method():
    """Test the new get_system_prompt convenience method"""
    from server.services.ai_service import AIService
    from unittest.mock import patch, Mock
    
    print("\n" + "=" * 60)
    print("Testing get_system_prompt Method")
    print("=" * 60)
    
    # Test 1: Calling without business_id should raise error
    ai_service = AIService()
    try:
        ai_service.get_system_prompt(channel='calls')
        assert False, "Should raise ValueError when business_id not set"
    except ValueError as e:
        assert "business_id must be provided" in str(e)
        print("✓ Raises ValueError when business_id not set")
    
    # Test 2: Calling with business_id set should work
    ai_service_with_id = AIService(business_id=456)
    
    # Mock get_business_prompt to avoid DB calls
    with patch.object(ai_service_with_id, 'get_business_prompt') as mock_get_prompt:
        mock_get_prompt.return_value = {
            "system_prompt": "Test prompt for business 456",
            "model": "gpt-4o-mini",
            "max_tokens": 350
        }
        
        result = ai_service_with_id.get_system_prompt(channel='calls')
        
        # Verify it called get_business_prompt with correct args
        mock_get_prompt.assert_called_once_with(456, 'calls')
        assert result == "Test prompt for business 456"
        print("✓ get_system_prompt() uses stored business_id correctly")
    
    print("\n✅ get_system_prompt method test passed")


def test_live_call_integration():
    """Test the live call scenario"""
    from server.services.ai_service import AIService
    from unittest.mock import patch
    
    print("\n" + "=" * 60)
    print("Testing Live Call Integration Pattern")
    print("=" * 60)
    
    business_id = 789
    
    # Simulate live call route code
    ai_service = AIService(business_id=business_id)
    
    # Mock get_business_prompt to avoid DB
    with patch.object(ai_service, 'get_business_prompt') as mock_get_prompt:
        mock_get_prompt.return_value = {
            "system_prompt": "אתה העוזר הדיגיטלי של העסק שלנו",
            "model": "gpt-4o-mini",
            "max_tokens": 350,
            "temperature": 0.0
        }
        
        # This is what live call route does
        system_prompt = ai_service.get_system_prompt(channel='calls')
        
        assert system_prompt is not None
        assert isinstance(system_prompt, str)
        assert len(system_prompt) > 0
        
        print(f"✓ System prompt retrieved: '{system_prompt[:50]}...'")
        print(f"✓ Length: {len(system_prompt)} characters")
    
    print("\n✅ Live call integration pattern works correctly")


def main():
    """Run all tests"""
    print("\n" + "=" * 70)
    print("Live Call AIService Fix - Validation Tests")
    print("=" * 70)
    
    try:
        test_aiservice_initialization()
        test_get_system_prompt_method()
        test_live_call_integration()
        
        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED")
        print("=" * 70)
        print("\nFix Summary:")
        print("1. AIService.__init__() now accepts optional business_id parameter")
        print("2. New get_system_prompt() method for convenience (uses stored business_id)")
        print("3. Backward compatible - existing code still works")
        print("4. Live call pattern now works: AIService(business_id=X)")
        print("\nLive call TypeError is FIXED! ✓")
        return 0
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
