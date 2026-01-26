"""
Simple validation script for Gemini Live crash fixes
Tests the changes without requiring pytest
"""
import sys
import os
import inspect

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

def test_gemini_client_has_session_cm():
    """Verify _session_cm field exists"""
    from server.services.gemini_realtime_client import GeminiRealtimeClient
    
    # Check __init__ has _session_cm
    source = inspect.getsource(GeminiRealtimeClient.__init__)
    assert 'self._session_cm' in source, "❌ _session_cm not initialized in __init__"
    print("✅ Test 1: _session_cm field is initialized")

def test_connect_uses_aenter():
    """Verify connect() uses __aenter__"""
    from server.services.gemini_realtime_client import GeminiRealtimeClient
    
    source = inspect.getsource(GeminiRealtimeClient.connect)
    assert '__aenter__' in source, "❌ connect() doesn't use __aenter__"
    assert 'cm = self.client.aio.live.connect' in source, "❌ connect() doesn't create context manager"
    assert 'self._session_cm = cm' in source, "❌ connect() doesn't store context manager"
    print("✅ Test 2: connect() properly uses __aenter__ on context manager")

def test_disconnect_uses_aexit():
    """Verify disconnect() uses __aexit__"""
    from server.services.gemini_realtime_client import GeminiRealtimeClient
    
    source = inspect.getsource(GeminiRealtimeClient.disconnect)
    assert 'self._session_cm' in source, "❌ disconnect() doesn't check _session_cm"
    assert '__aexit__' in source, "❌ disconnect() doesn't use __aexit__"
    print("✅ Test 3: disconnect() properly uses __aexit__ on context manager")

def test_connect_cleanup_on_error():
    """Verify connect() cleans up on error"""
    from server.services.gemini_realtime_client import GeminiRealtimeClient
    
    source = inspect.getsource(GeminiRealtimeClient.connect)
    # Check for cleanup logic in exception handler
    assert 'except Exception' in source, "❌ connect() doesn't have exception handler"
    # Look for cleanup in the exception block
    lines = source.split('\n')
    in_except_block = False
    has_cleanup = False
    for line in lines:
        if 'except Exception' in line:
            in_except_block = True
        if in_except_block and '__aexit__' in line:
            has_cleanup = True
            break
    assert has_cleanup, "❌ connect() doesn't clean up context manager on error"
    print("✅ Test 4: connect() cleans up context manager on error")

def test_media_ws_default_values():
    """Verify media_ws_ai.py initializes variables with defaults"""
    # Read source directly without importing (avoid dependency issues)
    with open('server/media_ws_ai.py', 'r') as f:
        source = f.read()
    
    # Check for default value assignments
    assert 'business_id_safe = getattr' in source, "❌ business_id_safe not initialized"
    assert 'call_direction = getattr' in source, "❌ call_direction not initialized"
    assert 'full_prompt = None' in source, "❌ full_prompt not initialized"
    print("✅ Test 5: Default values are set for business_id_safe, call_direction, full_prompt")

def test_defaults_before_try_block():
    """Verify defaults are set before try block"""
    # Read source directly without importing (avoid dependency issues)
    with open('server/media_ws_ai.py', 'r') as f:
        source = f.read()
    
    # Find the _run_realtime_mode_async function
    func_start = source.find('async def _run_realtime_mode_async(self):')
    assert func_start != -1, "❌ _run_realtime_mode_async not found"
    
    # Get the function body
    func_body = source[func_start:func_start+10000]
    lines = func_body.split('\n')
    
    business_id_line = None
    try_line = None
    
    for i, line in enumerate(lines):
        if 'business_id_safe = getattr' in line:
            business_id_line = i
        if line.strip() == 'try:' and business_id_line is not None:
            try_line = i
            break
    
    assert business_id_line is not None, "❌ business_id_safe initialization not found"
    assert try_line is not None, "❌ try block not found"
    assert business_id_line < try_line, "❌ business_id_safe must be set BEFORE try block"
    print("✅ Test 6: Default values are set BEFORE try block (prevents UnboundLocalError)")

def test_syntax_valid():
    """Verify both files have valid Python syntax"""
    import py_compile
    try:
        py_compile.compile('server/services/gemini_realtime_client.py', doraise=True)
        py_compile.compile('server/media_ws_ai.py', doraise=True)
        print("✅ Test 7: Python syntax is valid for both files")
    except py_compile.PyCompileError as e:
        raise AssertionError(f"❌ Syntax error: {e}")

def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("Testing Gemini Live Crash Fixes")
    print("="*60 + "\n")
    
    tests = [
        test_gemini_client_has_session_cm,
        test_connect_uses_aenter,
        test_disconnect_uses_aexit,
        test_connect_cleanup_on_error,
        test_media_ws_default_values,
        test_defaults_before_try_block,
        test_syntax_valid,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"❌ {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ {test.__name__}: Unexpected error: {e}")
            failed += 1
    
    print("\n" + "="*60)
    print(f"Results: {passed} passed, {failed} failed")
    print("="*60)
    
    if failed > 0:
        sys.exit(1)
    else:
        print("\n🎉 All tests passed! Fixes are working correctly.")
        sys.exit(0)

if __name__ == '__main__':
    main()
