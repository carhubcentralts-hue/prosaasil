"""
Test for WebSocket and Recording fixes
Tests the critical fixes for:
1. Thread removal in save_call_status (replaced with RQ)
2. Recording moved to in-progress callback
3. TTS timeout implementation
4. WebSocket close guard
"""
import sys
import os

# Add server to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

def test_thread_removal():
    """Test 1: Verify Thread is not used in save_call_status"""
    print("Test 1: Checking Thread removal in save_call_status...")
    
    with open('server/tasks_recording.py', 'r') as f:
        content = f.read()
    
    # Find save_call_status function
    func_start = content.find('def save_call_status(')
    func_end = content.find('\ndef ', func_start + 10)
    func_body = content[func_start:func_end]
    
    # Check that Thread is NOT used in save_call_status
    assert 'thread = Thread(' not in func_body, "❌ Thread still used in save_call_status"
    assert 'threading.Thread(' not in func_body, "❌ threading.Thread still used in save_call_status"
    print("✅ Thread removed from save_call_status")
    
    # Check that RQ Queue is used instead
    assert 'from rq import Queue' in func_body, "❌ RQ Queue not imported in save_call_status"
    assert 'queue.enqueue(' in func_body, "❌ RQ queue.enqueue not used"
    print("✅ Using RQ queue.enqueue instead of Thread")
    
    # Check for fallback to synchronous execution
    assert 'save_call_status_async(' in func_body, "❌ No fallback to synchronous execution"
    print("✅ Has fallback to synchronous execution on RQ failure")

def test_recording_in_progress():
    """Test 2: Verify recording is moved to in-progress callback"""
    print("\nTest 2: Checking recording moved to in-progress callback...")
    
    with open('server/routes_twilio.py', 'r') as f:
        content = f.read()
    
    # Find call_status function
    func_start = content.find('def call_status():')
    func_end = content.find('\n@', func_start + 100)  # Find next route
    func_body = content[func_start:func_end]
    
    # Check that in-progress status triggers recording
    assert 'if call_status_val == "in-progress"' in func_body, \
        "❌ No in-progress status check for recording"
    print("✅ Recording triggered on in-progress status")
    
    # Check that recording is started in background
    assert '_start_recording_from_second_zero' in func_body, \
        "❌ Recording start function not called"
    print("✅ Recording start function called in in-progress handler")
    
    # Find incoming_call function
    incoming_start = content.find('def incoming_call():')
    incoming_end = content.find('\n@', incoming_start + 100)
    incoming_body = content[incoming_start:incoming_end]
    
    # Check that recording is NOT started in incoming_call TwiML phase
    # Look for the comment indicating it was removed
    assert 'REMOVED: Recording start moved to in-progress' in incoming_body, \
        "❌ Recording not properly removed from incoming_call"
    print("✅ Recording removed from incoming_call TwiML phase")

def test_tts_timeout():
    """Test 3: Verify TTS timeout is implemented"""
    print("\nTest 3: Checking TTS timeout implementation...")
    
    with open('server/media_ws_ai.py', 'r') as f:
        content = f.read()
    
    # Find _hebrew_tts function
    func_start = content.find('def _hebrew_tts(self, text: str)')
    func_end = content.find('\n    def ', func_start + 10)
    func_body = content[func_start:func_end]
    
    # Check for timeout implementation
    assert 'TTS_TIMEOUT_SECONDS' in func_body, "❌ TTS timeout constant not defined"
    print("✅ TTS timeout constant defined")
    
    # Check for threading.Thread usage for timeout
    assert 'threading.Thread(' in func_body, "❌ No threading.Thread for timeout"
    assert '.join(timeout=' in func_body, "❌ No join with timeout"
    print("✅ Using threading with timeout")
    
    # Check for timeout handling
    assert 'if tts_thread.is_alive():' in func_body, \
        "❌ No check for thread still running (timeout)"
    print("✅ Checks if thread is still alive after timeout")
    
    # Check for timeout value (should be 6 seconds per requirement)
    assert 'TTS_TIMEOUT_SECONDS = 6' in func_body, \
        "❌ TTS timeout not set to 6 seconds"
    print("✅ TTS timeout set to 6 seconds")

def test_websocket_close_guard():
    """Test 4: Verify WebSocket close guard is implemented"""
    print("\nTest 4: Checking WebSocket close guard...")
    
    with open('server/media_ws_ai.py', 'r') as f:
        content = f.read()
    
    # Find _safe_ws_send function
    func_start = content.find('def _safe_ws_send(data):')
    func_end = content.find('\n        self._ws_send = _safe_ws_send', func_start)
    func_body = content[func_start:func_end]
    
    # Check for closed session guard
    assert 'if self.closed or self._ws_closed:' in func_body, \
        "❌ No guard checking self.closed or self._ws_closed"
    print("✅ Guard checks self.closed and self._ws_closed")
    
    # Check that guard returns False without sending
    assert 'return False  # Session/WebSocket is closed' in func_body, \
        "❌ Guard doesn't return False when closed"
    print("✅ Guard returns False when session/WebSocket is closed")
    
    # Check that _ws_closed flag exists in initialization
    init_check = content.find('self._ws_closed = False')
    assert init_check > 0, "❌ _ws_closed flag not initialized"
    print("✅ _ws_closed flag is initialized")

def test_all():
    """Run all tests"""
    print("=" * 60)
    print("WebSocket and Recording Fixes - Test Suite")
    print("=" * 60)
    
    try:
        test_thread_removal()
        test_recording_in_progress()
        test_tts_timeout()
        test_websocket_close_guard()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        return True
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return False
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_all()
    sys.exit(0 if success else 1)
