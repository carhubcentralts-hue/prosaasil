"""
Test for Gemini Live crash fixes:
1. AsyncGeneratorContextManager handling in connect()
2. UnboundLocalError prevention in exception handlers
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock, patch
import sys
import os

# Add server to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))


class TestGeminiLiveConnectFix:
    """Test that Gemini Live connect() properly handles AsyncGeneratorContextManager"""
    
    @pytest.mark.asyncio
    async def test_connect_uses_context_manager_correctly(self):
        """Test that connect() manually enters context manager"""
        from server.services.gemini_realtime_client import GeminiRealtimeClient
        
        # Mock the genai client
        with patch('server.services.gemini_realtime_client.genai') as mock_genai:
            # Create mock context manager
            mock_cm = AsyncMock()
            mock_session = Mock()
            mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
            mock_cm.__aexit__ = AsyncMock(return_value=None)
            
            # Mock the connect method to return context manager
            mock_client = Mock()
            mock_client.aio.live.connect = Mock(return_value=mock_cm)
            mock_genai.Client.return_value = mock_client
            
            # Create client
            client = GeminiRealtimeClient(api_key="test-key")
            
            # Test connect
            result = await client.connect()
            
            # Verify __aenter__ was called
            mock_cm.__aenter__.assert_called_once()
            
            # Verify session is stored
            assert client.session == mock_session
            assert client._session_cm == mock_cm
            assert client._connected is True
            assert result == mock_session
    
    @pytest.mark.asyncio
    async def test_connect_cleanup_on_failure(self):
        """Test that context manager is cleaned up if connection fails after creation"""
        from server.services.gemini_realtime_client import GeminiRealtimeClient
        
        with patch('server.services.gemini_realtime_client.genai') as mock_genai:
            # Create mock context manager that fails on __aenter__
            mock_cm = AsyncMock()
            mock_cm.__aenter__ = AsyncMock(side_effect=ConnectionError("Connection failed"))
            mock_cm.__aexit__ = AsyncMock(return_value=None)
            
            mock_client = Mock()
            mock_client.aio.live.connect = Mock(return_value=mock_cm)
            mock_genai.Client.return_value = mock_client
            
            client = GeminiRealtimeClient(api_key="test-key")
            
            # Test connect fails
            with pytest.raises(ConnectionError):
                await client.connect(max_retries=1, backoff_base=0.1)
            
            # Verify cleanup was attempted
            assert mock_cm.__aexit__.call_count > 0
    
    @pytest.mark.asyncio
    async def test_disconnect_uses_context_manager(self):
        """Test that disconnect() properly exits context manager"""
        from server.services.gemini_realtime_client import GeminiRealtimeClient
        
        with patch('server.services.gemini_realtime_client.genai') as mock_genai:
            mock_cm = AsyncMock()
            mock_session = Mock()
            mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
            mock_cm.__aexit__ = AsyncMock(return_value=None)
            
            mock_client = Mock()
            mock_client.aio.live.connect = Mock(return_value=mock_cm)
            mock_genai.Client.return_value = mock_client
            
            client = GeminiRealtimeClient(api_key="test-key")
            await client.connect()
            
            # Test disconnect
            await client.disconnect()
            
            # Verify __aexit__ was called with proper args
            mock_cm.__aexit__.assert_called_once_with(None, None, None)
            
            # Verify cleanup
            assert client.session is None
            assert client._session_cm is None
            assert client._connected is False


class TestMediaWSUnboundLocalErrorFix:
    """Test that UnboundLocalError is prevented in media_ws_ai.py"""
    
    @pytest.mark.asyncio
    async def test_variables_initialized_before_use(self):
        """Test that business_id_safe, call_direction, full_prompt are initialized"""
        from server.media_ws_ai import MediaStreamHandler
        
        # Create a minimal handler instance
        handler = MediaStreamHandler(Mock())
        handler.call_sid = "test-call-sid"
        handler.business_id = None  # Simulate missing business_id
        
        # Mock the necessary attributes
        handler.business_info_ready_event = Mock()
        handler.business_info_ready_event.wait = Mock(return_value=False)
        handler.t0_connected = 0
        handler.realtime_failed = False
        handler._realtime_failure_reason = None
        handler._metrics_openai_connect_ms = 0
        
        # Patch the clients to raise an error immediately
        with patch('server.media_ws_ai.OpenAIRealtimeClient') as mock_openai:
            with patch('server.media_ws_ai.GeminiRealtimeClient') as mock_gemini:
                mock_client = AsyncMock()
                mock_client.connect = AsyncMock(side_effect=ConnectionError("Test error"))
                mock_openai.return_value = mock_client
                
                # Run the async function and expect it to handle the error gracefully
                try:
                    await handler._run_realtime_mode_async()
                except Exception as e:
                    # Should not get UnboundLocalError
                    assert "UnboundLocalError" not in str(type(e))
                    # Variables should have been initialized with defaults
                    # so no NameError should occur
    
    def test_default_values_set_correctly(self):
        """Test that default values are set in the right place"""
        from server.media_ws_ai import MediaStreamHandler
        
        # Read the source to verify the fix is in place
        import inspect
        source = inspect.getsource(MediaStreamHandler._run_realtime_mode_async)
        
        # Check that default values are set early
        assert "business_id_safe = getattr(self, 'business_id', None) or \"unknown\"" in source
        assert "call_direction = getattr(self, 'call_direction', 'unknown')" in source
        assert "full_prompt = None" in source
        
        # Verify they're set before the try block
        lines = source.split('\n')
        try_line = None
        business_id_line = None
        
        for i, line in enumerate(lines):
            if 'business_id_safe = getattr' in line:
                business_id_line = i
            if line.strip() == 'try:' and business_id_line is not None:
                try_line = i
                break
        
        assert business_id_line is not None, "business_id_safe initialization not found"
        assert try_line is not None, "try block not found"
        assert business_id_line < try_line, "business_id_safe must be set before try block"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
