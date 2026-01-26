"""
Test: Gemini Initialization Fix
Verifies that Gemini clients are initialized at startup, not during conversations
"""
import os
import sys
from unittest.mock import patch, MagicMock, Mock

def test_ai_service_initializes_gemini_eagerly():
    """Test that AIService initializes Gemini client at creation, not lazily"""
    print("🧪 Testing AIService eager Gemini initialization...")
    
    # Import first
    from server.services.ai_service import AIService
    
    # Mock the Gemini client getter
    mock_gemini_client = MagicMock()
    
    with patch('server.services.providers.google_clients.get_gemini_llm_client', return_value=mock_gemini_client) as mock_getter:
        # Create AIService instance
        service = AIService(business_id=123)
        
        # Verify get_gemini_llm_client was called during __init__ (eager initialization)
        assert mock_getter.called, "get_gemini_llm_client should be called during AIService.__init__"
        print(f"  ✅ get_gemini_llm_client called {mock_getter.call_count} time(s) during __init__")
        
        # Verify client is stored
        assert service._gemini_client is mock_gemini_client
        print("  ✅ Gemini client stored in AIService instance")
        
        # When _get_gemini_client() is called later, it should just return the cached client
        result = service._get_gemini_client()
        assert result is mock_gemini_client
        print("  ✅ _get_gemini_client() returns cached client")
        
        # Verify no additional calls were made
        assert mock_getter.call_count == 1, "get_gemini_llm_client should only be called once (during init)"
        print("  ✅ No lazy loading - client reused from cache")


def test_ai_service_handles_missing_gemini():
    """Test that AIService handles missing Gemini gracefully"""
    print("\n🧪 Testing AIService handles missing Gemini...")
    
    # Import first
    from server.services.ai_service import AIService
    
    # Mock the Gemini client getter to raise RuntimeError
    with patch('server.services.providers.google_clients.get_gemini_llm_client', side_effect=RuntimeError("API key not set")) as mock_getter:
        # Create AIService instance - should NOT fail even if Gemini unavailable
        service = AIService(business_id=123)
        print("  ✅ AIService created successfully even without Gemini")
        
        # Verify client is None
        assert service._gemini_client is None
        print("  ✅ _gemini_client is None when unavailable")
        
        # When _get_gemini_client() is called, it should raise RuntimeError
        try:
            service._get_gemini_client()
            assert False, "_get_gemini_client() should raise RuntimeError when client unavailable"
        except RuntimeError as e:
            assert "not available" in str(e).lower()
            print(f"  ✅ _get_gemini_client() raises RuntimeError with clear message: {e}")


def test_warmup_returns_status():
    """Test that warmup_google_clients returns status dict"""
    print("\n🧪 Testing warmup_google_clients returns status...")
    
    # Reset clients
    from server.services.providers.google_clients import reset_clients
    reset_clients()
    
    # Mock get_gemini_api_key and genai module
    mock_client = MagicMock()
    
    with patch('server.services.providers.google_clients.get_gemini_api_key', return_value='test-key'):
        with patch('server.services.providers.google_clients.genai') as mock_genai:
            mock_genai.Client.return_value = mock_client
            
            from server.services.providers.google_clients import warmup_google_clients
            
            status = warmup_google_clients()
            
            # Verify status is a dict
            assert isinstance(status, dict), "warmup should return dict"
            print(f"  ✅ warmup returns dict: {status}")
            
            # Verify it has the expected keys
            assert 'stt' in status
            assert 'gemini_llm' in status
            assert 'gemini_tts' in status
            print("  ✅ Status dict has all expected keys")
            
            # When Gemini is available, both should be True
            assert status['gemini_llm'] == True, "gemini_llm should be True when API key available"
            assert status['gemini_tts'] == True, "gemini_tts should be True when API key available"
            print("  ✅ Both Gemini clients marked as initialized")


def test_no_lazy_loading_logs():
    """Test that 'singleton ready' log doesn't appear during conversation"""
    print("\n🧪 Testing no lazy loading logs...")
    
    # Create a log capture
    import logging
    from io import StringIO
    from server.services.ai_service import AIService
    
    log_capture = StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setLevel(logging.INFO)
    
    # Get the ai_service logger
    logger = logging.getLogger('server.services.ai_service')
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    
    # Mock the Gemini client
    mock_gemini_client = MagicMock()
    
    with patch('server.services.providers.google_clients.get_gemini_llm_client', return_value=mock_gemini_client):
        service = AIService(business_id=123)
        
        # Get log output from initialization
        init_logs = log_capture.getvalue()
        
        # Clear the log for conversation simulation
        log_capture.truncate(0)
        log_capture.seek(0)
        
        # Simulate conversation - call _get_gemini_client
        result = service._get_gemini_client()
        
        # Get log output from conversation
        conversation_logs = log_capture.getvalue()
        
        # Verify no "singleton ready" message in conversation logs
        assert "singleton ready" not in conversation_logs.lower(), "Should not log 'singleton ready' during conversation"
        print("  ✅ No 'singleton ready' log during conversation")
        
        # The DEBUG log should appear in init logs
        assert "gemini" in init_logs.lower() or len(init_logs) == 0, "Init should have Gemini-related logs or be silent"
        print("  ✅ Initialization logs are at DEBUG level or silent")
    
    logger.removeHandler(handler)


if __name__ == '__main__':
    print("🔥 Testing Gemini Initialization Fix\n")
    print("=" * 60)
    
    test_ai_service_initializes_gemini_eagerly()
    test_ai_service_handles_missing_gemini()
    test_warmup_returns_status()
    test_no_lazy_loading_logs()
    
    print("\n" + "=" * 60)
    print("✅ All tests passed! Gemini initialization moved to startup.")
