"""
Test Barge-In Verification Fixes
Tests the new is_ai_speaking_now and is_verified_user_speech functions
"""
import sys
import os
import time

# Add server to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))

# Mock the necessary components for testing
class MockWebSocketStream:
    """Mock WebSocket stream for testing"""
    def __init__(self):
        self.call_sid = "test_call"
        self.stream_sid = "test_stream"
        self.last_ai_audio_ts = None
        self.user_speaking = False
        self._realtime_speech_active = False
        self._utterance_start_ts = None
        self._last_ai_audio_ts = None
        self.realtime_audio_out_queue = MockQueue()
        self.tx_q = MockQueue()
        self._ai_speech_start = None
        self.ECHO_WINDOW_MS = 350


class MockQueue:
    """Mock queue for testing"""
    def __init__(self):
        self._size = 0
    
    def qsize(self):
        return self._size
    
    def set_size(self, size):
        self._size = size


def test_is_ai_speaking_now_recent_audio():
    """Test that recent audio (<400ms) returns True"""
    # Import the functions by creating an instance
    from server.media_ws_ai import WebSocketStream
    
    # Mock just the necessary parts
    stream = MockWebSocketStream()
    stream.last_ai_audio_ts = time.time() - 0.2  # 200ms ago
    
    # Bind the method
    result = WebSocketStream.is_ai_speaking_now(stream)
    
    assert result == True, "Recent audio (<400ms) should indicate AI is speaking"
    print("✅ is_ai_speaking_now with recent audio test passed")


def test_is_ai_speaking_now_old_audio():
    """Test that old audio (>1200ms) returns False"""
    from server.media_ws_ai import WebSocketStream
    
    stream = MockWebSocketStream()
    stream.last_ai_audio_ts = time.time() - 2.0  # 2000ms ago
    
    result = WebSocketStream.is_ai_speaking_now(stream)
    
    assert result == False, "Old audio (>1200ms) should indicate AI is NOT speaking"
    print("✅ is_ai_speaking_now with old audio test passed")


def test_is_ai_speaking_now_with_queue():
    """Test that queued audio with somewhat recent timestamp returns True"""
    from server.media_ws_ai import WebSocketStream
    
    stream = MockWebSocketStream()
    stream.last_ai_audio_ts = time.time() - 0.8  # 800ms ago
    stream.realtime_audio_out_queue.set_size(5)  # Has queued audio
    
    result = WebSocketStream.is_ai_speaking_now(stream)
    
    assert result == True, "Queued audio with recent-ish timestamp should indicate AI is speaking"
    print("✅ is_ai_speaking_now with queued audio test passed")


def test_is_ai_speaking_now_queue_too_old():
    """Test that queued audio with old timestamp returns False"""
    from server.media_ws_ai import WebSocketStream
    
    stream = MockWebSocketStream()
    stream.last_ai_audio_ts = time.time() - 1.5  # 1500ms ago (>1200ms)
    stream.realtime_audio_out_queue.set_size(5)  # Has queued audio
    
    result = WebSocketStream.is_ai_speaking_now(stream)
    
    assert result == False, "Queued audio with old timestamp (>1200ms) should return False"
    print("✅ is_ai_speaking_now with old queued audio test passed")


def test_is_verified_user_speech_basic():
    """Test basic user speech verification"""
    from server.media_ws_ai import WebSocketStream
    
    stream = MockWebSocketStream()
    stream.user_speaking = True
    stream._realtime_speech_active = True
    stream._utterance_start_ts = time.time() - 0.2  # 200ms ago
    stream._last_ai_audio_ts = time.time() - 2.0  # Not in echo window
    
    result = WebSocketStream.is_verified_user_speech(stream)
    
    assert result == True, "Sustained user speech (200ms) should be verified"
    print("✅ is_verified_user_speech basic test passed")


def test_is_verified_user_speech_too_short():
    """Test that very short speech is not verified"""
    from server.media_ws_ai import WebSocketStream
    
    stream = MockWebSocketStream()
    stream.user_speaking = True
    stream._realtime_speech_active = True
    stream._utterance_start_ts = time.time() - 0.05  # Only 50ms ago
    stream._last_ai_audio_ts = time.time() - 2.0  # Not in echo window
    
    result = WebSocketStream.is_verified_user_speech(stream)
    
    assert result == False, "Very short speech (<160ms) should NOT be verified"
    print("✅ is_verified_user_speech too short test passed")


def test_is_verified_user_speech_in_echo_window():
    """Test that speech in echo window requires longer duration"""
    from server.media_ws_ai import WebSocketStream
    
    # Case 1: 180ms duration in echo window - should NOT verify (needs >= 240ms)
    stream = MockWebSocketStream()
    stream.user_speaking = True
    stream._realtime_speech_active = True
    stream._utterance_start_ts = time.time() - 0.18  # 180ms ago
    stream._last_ai_audio_ts = time.time() - 0.2  # 200ms ago (in echo window <350ms)
    
    result = WebSocketStream.is_verified_user_speech(stream)
    
    assert result == False, "Speech in echo window with 180ms duration should NOT be verified"
    
    # Case 2: 250ms duration in echo window - should verify (>= 240ms)
    stream2 = MockWebSocketStream()
    stream2.user_speaking = True
    stream2._realtime_speech_active = True
    stream2._utterance_start_ts = time.time() - 0.25  # 250ms ago
    stream2._last_ai_audio_ts = time.time() - 0.2  # 200ms ago (in echo window)
    
    result2 = WebSocketStream.is_verified_user_speech(stream2)
    
    assert result2 == True, "Speech in echo window with 250ms duration should be verified"
    print("✅ is_verified_user_speech echo window test passed")


def test_is_verified_user_speech_not_speaking():
    """Test that returns False when user_speaking is False"""
    from server.media_ws_ai import WebSocketStream
    
    stream = MockWebSocketStream()
    stream.user_speaking = False  # Not speaking
    stream._realtime_speech_active = True
    stream._utterance_start_ts = time.time() - 0.2
    
    result = WebSocketStream.is_verified_user_speech(stream)
    
    assert result == False, "Should return False when user_speaking is False"
    print("✅ is_verified_user_speech not speaking test passed")


def test_is_verified_user_speech_no_vad_confirmation():
    """Test that returns False when OpenAI VAD hasn't confirmed"""
    from server.media_ws_ai import WebSocketStream
    
    stream = MockWebSocketStream()
    stream.user_speaking = True
    stream._realtime_speech_active = False  # No VAD confirmation
    stream._utterance_start_ts = time.time() - 0.2
    
    result = WebSocketStream.is_verified_user_speech(stream)
    
    assert result == False, "Should return False when OpenAI VAD hasn't confirmed"
    print("✅ is_verified_user_speech no VAD confirmation test passed")


def run_all_tests():
    """Run all test functions"""
    print("🧪 Running Barge-In Verification Tests\n")
    print("=" * 60)
    
    test_is_ai_speaking_now_recent_audio()
    test_is_ai_speaking_now_old_audio()
    test_is_ai_speaking_now_with_queue()
    test_is_ai_speaking_now_queue_too_old()
    test_is_verified_user_speech_basic()
    test_is_verified_user_speech_too_short()
    test_is_verified_user_speech_in_echo_window()
    test_is_verified_user_speech_not_speaking()
    test_is_verified_user_speech_no_vad_confirmation()
    
    print("=" * 60)
    print("✅ All Barge-In Verification tests passed!")


if __name__ == "__main__":
    run_all_tests()
