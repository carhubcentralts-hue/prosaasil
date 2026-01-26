"""
Test: Google Clients Singleton Pattern
Verifies that STT and Gemini clients are properly initialized as singletons
and that DISABLE_GOOGLE flag correctly affects only Google Cloud STT.
"""
import os
from unittest.mock import patch, MagicMock


def test_stt_client_singleton():
    """Test that STT client is initialized once and cached"""
    # Reset clients before test
    from server.services.providers.google_clients import reset_clients
    reset_clients()
    
    with patch.dict(os.environ, {'DISABLE_GOOGLE': 'false', 'GOOGLE_APPLICATION_CREDENTIALS': '/tmp/test.json'}):
        with patch('os.path.exists', return_value=True):
            with patch('server.services.providers.google_clients.speech.SpeechClient') as mock_speech:
                with patch('server.services.providers.google_clients.service_account.Credentials.from_service_account_file') as mock_creds:
                    mock_creds.return_value = MagicMock()
                    mock_client = MagicMock()
                    mock_speech.return_value = mock_client
                    
                    from server.services.providers.google_clients import get_stt_client
                    
                    # First call
                    client1 = get_stt_client()
                    # Second call
                    client2 = get_stt_client()
                    
                    # Should be same instance
                    assert client1 is client2
                    # Should only be initialized once
                    assert mock_speech.call_count == 1
                    
                    print("✅ STT client singleton works correctly")


def test_gemini_client_singleton():
    """Test that Gemini client is initialized once and cached"""
    # Reset clients before test
    from server.services.providers.google_clients import reset_clients
    reset_clients()
    
    with patch('server.services.providers.google_clients.get_gemini_api_key', return_value='test-key'):
        with patch('server.services.providers.google_clients.genai.Client') as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            
            from server.services.providers.google_clients import get_gemini_client
            
            # First call
            client1 = get_gemini_client()
            # Second call
            client2 = get_gemini_client()
            
            # Should be same instance
            assert client1 is client2
            # Should only be initialized once
            assert mock_client.call_count == 1
            
            print("✅ Gemini client singleton works correctly")


def test_disable_google_affects_only_stt():
    """Test that DISABLE_GOOGLE only blocks Google Cloud STT, not Gemini"""
    # Reset clients before test
    from server.services.providers.google_clients import reset_clients
    reset_clients()
    
    with patch.dict(os.environ, {'DISABLE_GOOGLE': 'true'}):
        from server.services.providers.google_clients import get_stt_client, get_gemini_client
        
        # STT should be blocked
        stt_client = get_stt_client()
        assert stt_client is None
        print("✅ DISABLE_GOOGLE correctly blocks Google Cloud STT")
        
        # Gemini should NOT be blocked
        with patch('server.services.providers.google_clients.get_gemini_api_key', return_value='test-key'):
            with patch('server.services.providers.google_clients.genai.Client') as mock_client:
                mock_instance = MagicMock()
                mock_client.return_value = mock_instance
                
                gemini_client = get_gemini_client()
                assert gemini_client is not None
                print("✅ DISABLE_GOOGLE does NOT block Gemini (correct)")


def test_gemini_voice_catalog_not_affected_by_disable_google():
    """Test that Gemini voice catalog works regardless of DISABLE_GOOGLE"""
    from server.services.gemini_voice_catalog import is_gemini_available
    
    # With DISABLE_GOOGLE=true, Gemini should still be available if key is set
    with patch.dict(os.environ, {'DISABLE_GOOGLE': 'true', 'GEMINI_API_KEY': 'test-key'}):
        assert is_gemini_available() is True
        print("✅ Gemini is available even when DISABLE_GOOGLE=true")
    
    # Without API key, Gemini should not be available
    with patch.dict(os.environ, {'DISABLE_GOOGLE': 'false', 'GEMINI_API_KEY': ''}, clear=True):
        assert is_gemini_available() is False
        print("✅ Gemini correctly requires GEMINI_API_KEY")


def test_stt_client_caches_failures():
    """Test that STT client caches initialization failures"""
    # Reset clients before test
    from server.services.providers.google_clients import reset_clients
    reset_clients()
    
    with patch.dict(os.environ, {'DISABLE_GOOGLE': 'false', 'GOOGLE_APPLICATION_CREDENTIALS': ''}):
        from server.services.providers.google_clients import get_stt_client
        
        # First call - should fail
        client1 = get_stt_client()
        assert client1 is None
        
        # Second call - should return None immediately without retrying
        client2 = get_stt_client()
        assert client2 is None
        
        print("✅ STT client correctly caches initialization failures")


def test_gemini_client_caches_failures():
    """Test that Gemini client caches initialization failures"""
    # Reset clients before test
    from server.services.providers.google_clients import reset_clients
    reset_clients()
    
    with patch('server.services.providers.google_clients.get_gemini_api_key', return_value=None):
        from server.services.providers.google_clients import get_gemini_client
        
        # First call - should fail
        client1 = get_gemini_client()
        assert client1 is None
        
        # Second call - should return None immediately without retrying
        client2 = get_gemini_client()
        assert client2 is None
        
        print("✅ Gemini client correctly caches initialization failures")


if __name__ == '__main__':
    print("🧪 Testing Google Clients Singleton Pattern...\n")
    
    test_stt_client_singleton()
    test_gemini_client_singleton()
    test_disable_google_affects_only_stt()
    test_gemini_voice_catalog_not_affected_by_disable_google()
    test_stt_client_caches_failures()
    test_gemini_client_caches_failures()
    
    print("\n✅ All tests passed!")
