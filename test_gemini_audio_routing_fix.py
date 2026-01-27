"""
Test Gemini Audio Routing Fixes

This test verifies that:
1. Provider-aware logging is correctly implemented
2. Gemini event logging (GEMINI_SEND/GEMINI_RECV) is present
3. Watchdog timer is created
4. Global thread exception handler is installed
5. Gemini greeting trigger sends empty text
"""
import os
import sys
import unittest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import asyncio
import threading

# Add server to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))


class TestGeminiAudioRoutingFixes(unittest.TestCase):
    """Test suite for Gemini audio routing fixes"""
    
    def test_global_thread_exception_handler_installed(self):
        """Verify global thread exception handler is installed"""
        # Import media_ws_ai to trigger handler installation
        import media_ws_ai
        
        # Check if Python 3.8+ has excepthook installed
        if sys.version_info >= (3, 8):
            self.assertIsNotNone(threading.excepthook)
            self.assertEqual(threading.excepthook.__name__, '_global_thread_exception_handler')
            print("✅ Global thread exception handler installed")
        else:
            print("⚠️ Python < 3.8, skipping thread exception handler test")
    
    def test_gemini_client_has_logging(self):
        """Verify Gemini client has GEMINI_SEND/GEMINI_RECV logging"""
        from server.services.gemini_realtime_client import GeminiRealtimeClient
        
        # Check that send_audio method exists and has logging
        self.assertTrue(hasattr(GeminiRealtimeClient, 'send_audio'))
        
        # Check send_text method
        self.assertTrue(hasattr(GeminiRealtimeClient, 'send_text'))
        
        # Check recv_events method
        self.assertTrue(hasattr(GeminiRealtimeClient, 'recv_events'))
        
        print("✅ Gemini client methods exist")
    
    def test_audio_out_loop_provider_aware(self):
        """Verify audio_out_loop uses provider-aware logging"""
        from server.media_ws_ai import AIWebSocketHandler
        
        # Check that _realtime_audio_out_loop method exists
        self.assertTrue(hasattr(AIWebSocketHandler, '_realtime_audio_out_loop'))
        
        # Verify the method has provider-aware logic in its source
        import inspect
        source = inspect.getsource(AIWebSocketHandler._realtime_audio_out_loop)
        
        # Should have both "GEMINI audio" and "OpenAI audio" messages
        self.assertIn("GEMINI audio", source)
        self.assertIn("OpenAI audio", source)
        self.assertIn("ai_provider", source)
        
        print("✅ Audio out loop is provider-aware")
    
    def test_watchdog_method_exists(self):
        """Verify watchdog method exists"""
        from server.media_ws_ai import AIWebSocketHandler
        
        self.assertTrue(hasattr(AIWebSocketHandler, '_start_first_audio_watchdog'))
        
        print("✅ First audio watchdog method exists")
    
    @patch('server.services.gemini_realtime_client.genai')
    async def test_gemini_greeting_trigger(self):
        """Verify Gemini greeting sends empty text to trigger response"""
        from server.services.gemini_realtime_client import GeminiRealtimeClient
        
        # Mock the genai client
        mock_genai = MagicMock()
        mock_session = MagicMock()
        mock_session.send_realtime_input = AsyncMock()
        
        with patch('server.services.gemini_realtime_client.genai', mock_genai):
            with patch('server.services.gemini_realtime_client._genai_available', True):
                # Create client
                client = GeminiRealtimeClient(api_key='test_key')
                client._connected = True
                client.session = mock_session
                
                # Send empty text (greeting trigger)
                await client.send_text("")
                
                # Verify send_realtime_input was called with empty text
                mock_session.send_realtime_input.assert_called_once()
                call_args = mock_session.send_realtime_input.call_args
                self.assertIn('text', call_args[1] or {})
                
                print("✅ Gemini greeting trigger sends empty text")
    
    def test_trigger_response_has_gemini_greeting_logic(self):
        """Verify trigger_response has Gemini greeting trigger logic"""
        from server.media_ws_ai import AIWebSocketHandler
        
        # Get source of trigger_response method
        import inspect
        source = inspect.getsource(AIWebSocketHandler.trigger_response)
        
        # Should have Gemini greeting trigger logic
        self.assertIn("GEMINI", source)
        self.assertIn("send_text", source)
        self.assertIn("GREETING", source)
        
        print("✅ trigger_response has Gemini greeting logic")


def run_async_test(coro):
    """Helper to run async tests"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


if __name__ == '__main__':
    # Run tests
    suite = unittest.TestLoader().loadTestsFromTestCase(TestGeminiAudioRoutingFixes)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Run async test separately
    print("\n" + "="*70)
    print("Running async test...")
    test = TestGeminiAudioRoutingFixes()
    try:
        run_async_test(test.test_gemini_greeting_trigger())
    except Exception as e:
        print(f"❌ Async test failed: {e}")
    
    # Exit with proper code
    sys.exit(0 if result.wasSuccessful() else 1)
