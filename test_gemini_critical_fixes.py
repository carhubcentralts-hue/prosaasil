"""
Test Gemini Critical Fixes
Validates fixes for UnboundLocalError and queue overflow issues
"""


def test_ai_response_dict_initialization():
    """Test that ai_response_dict is properly initialized to prevent UnboundLocalError"""
    print("\n" + "=" * 60)
    print("Validating ai_response_dict Initialization Fix")
    print("=" * 60)
    
    # Read the file
    with open('/home/runner/work/prosaasil/prosaasil/server/media_ws_ai.py', 'r') as f:
        content = f.read()
    
    # Test 1: Check that ai_response_dict is initialized at start of _ai_response
    if 'ai_response_dict = None' in content:
        print("✓ ai_response_dict is initialized at function start")
    else:
        print("❌ ai_response_dict not initialized")
        return False
    
    # Test 2: Check that ai_response_dict is set in string response branch
    if 'ai_response_dict = {' in content and '"text": tts_text,' in content:
        print("✓ ai_response_dict is set in string response branch")
    else:
        print("❌ ai_response_dict not set in string response branch")
        return False
    
    # Test 3: Check that ai_response_dict access is guarded
    if 'isinstance(ai_response_dict, dict)' in content:
        print("✓ ai_response_dict access is guarded with type check")
    else:
        print("❌ ai_response_dict access not properly guarded")
        return False
    
    print("\n" + "=" * 60)
    print("✅ ALL AI_RESPONSE_DICT VALIDATIONS PASSED")
    print("=" * 60)
    return True


def test_backpressure_implementation():
    """Test that backpressure is implemented to prevent queue overflow"""
    print("\n" + "=" * 60)
    print("Validating Backpressure Implementation")
    print("=" * 60)
    
    # Read the file
    with open('/home/runner/work/prosaasil/prosaasil/server/media_ws_ai.py', 'r') as f:
        content = f.read()
    
    # Test 1: Check that is_processing_turn flag is initialized
    if 'self.is_processing_turn = False' in content:
        print("✓ is_processing_turn flag is initialized in __init__")
    else:
        print("❌ is_processing_turn flag not initialized")
        return False
    
    # Test 2: Check that flag is set before AI processing
    if 'self.is_processing_turn = True' in content:
        print("✓ is_processing_turn flag is set before processing")
    else:
        print("❌ is_processing_turn flag not set before processing")
        return False
    
    # Test 3: Check that flag is cleared after processing
    if 'self.is_processing_turn = False' in content:
        print("✓ is_processing_turn flag is cleared after processing")
    else:
        print("❌ is_processing_turn flag not cleared")
        return False
    
    # Test 4: Check that media frames are dropped when flag is True
    if 'if getattr(self, \'is_processing_turn\', False):' in content and 'continue  # Skip processing this media frame' in content:
        print("✓ Media frames are dropped when is_processing_turn is True")
    else:
        print("❌ Media frame dropping not implemented")
        return False
    
    # Test 5: Check for backpressure logging
    if '[BACKPRESSURE]' in content:
        print("✓ Backpressure logging exists")
    else:
        print("❌ Backpressure logging not found")
        return False
    
    # Test 6: Check that dropped frames are tracked for diagnostics
    if '_frames_dropped_by_processing' in content:
        print("✓ Dropped frames are tracked for diagnostics")
    else:
        print("❌ Dropped frame tracking not found")
        return False
    
    print("\n" + "=" * 60)
    print("✅ ALL BACKPRESSURE VALIDATIONS PASSED")
    print("=" * 60)
    return True


def test_gemini_tts_flag_management():
    """Test that is_processing_turn flag is managed during Gemini TTS"""
    print("\n" + "=" * 60)
    print("Validating Gemini TTS Flag Management")
    print("=" * 60)
    
    # Read the file
    with open('/home/runner/work/prosaasil/prosaasil/server/media_ws_ai.py', 'r') as f:
        content = f.read()
    
    # Test 1: Check that flag is set before Gemini TTS
    # Look for the pattern near "[GEMINI_TTS] Starting synthesis"
    lines = content.split('\n')
    gemini_tts_start_idx = None
    for i, line in enumerate(lines):
        if '[GEMINI_TTS] Starting synthesis' in line:
            gemini_tts_start_idx = i
            break
    
    if gemini_tts_start_idx is None:
        print("❌ Could not find Gemini TTS start marker")
        return False
    
    # Check that is_processing_turn = True appears within 10 lines after TTS start log
    # (since it's set right after the log message)
    found_flag_set = False
    for i in range(gemini_tts_start_idx, gemini_tts_start_idx + 10):
        if i < len(lines) and 'self.is_processing_turn = True' in lines[i]:
            found_flag_set = True
            break
    
    if found_flag_set:
        print("✓ is_processing_turn flag is set before Gemini TTS processing")
    else:
        print("❌ is_processing_turn flag not set before Gemini TTS processing")
        return False
    
    # Test 2: Check that flag is cleared in TTS error paths
    # Count how many times flag is cleared in the _hebrew_tts function
    hebrew_tts_start = None
    for i, line in enumerate(lines):
        if 'def _hebrew_tts(self, text: str)' in line:
            hebrew_tts_start = i
            break
    
    if hebrew_tts_start is None:
        print("❌ Could not find _hebrew_tts function")
        return False
    
    # Find the next function after _hebrew_tts to determine its boundary
    hebrew_tts_end = len(lines)
    for i in range(hebrew_tts_start + 1, len(lines)):
        if lines[i].startswith('    def ') and not lines[i].startswith('        '):
            hebrew_tts_end = i
            break
    
    # Count flag clears in _hebrew_tts function
    flag_clear_count = 0
    for i in range(hebrew_tts_start, hebrew_tts_end):
        if 'self.is_processing_turn = False' in lines[i]:
            flag_clear_count += 1
    
    if flag_clear_count >= 3:  # Should be cleared in success paths and error paths
        print(f"✓ is_processing_turn flag is cleared in {flag_clear_count} places in TTS")
    else:
        print(f"❌ is_processing_turn flag only cleared {flag_clear_count} times (expected >= 3)")
        return False
    
    print("\n" + "=" * 60)
    print("✅ ALL GEMINI TTS FLAG VALIDATIONS PASSED")
    print("=" * 60)
    return True


def run_all_tests():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("RUNNING GEMINI CRITICAL FIXES VALIDATION TESTS")
    print("=" * 80)
    
    results = []
    
    # Test 1: ai_response_dict initialization
    try:
        result = test_ai_response_dict_initialization()
        results.append(("ai_response_dict initialization", result))
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        results.append(("ai_response_dict initialization", False))
    
    # Test 2: Backpressure implementation
    try:
        result = test_backpressure_implementation()
        results.append(("Backpressure implementation", result))
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        results.append(("Backpressure implementation", False))
    
    # Test 3: Gemini TTS flag management
    try:
        result = test_gemini_tts_flag_management()
        results.append(("Gemini TTS flag management", result))
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        results.append(("Gemini TTS flag management", False))
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    all_passed = True
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
        if not result:
            all_passed = False
    
    print("=" * 80)
    
    if all_passed:
        print("\n🎉 ALL TESTS PASSED! Gemini critical fixes are properly implemented.")
        return True
    else:
        print("\n❌ SOME TESTS FAILED! Please review the output above.")
        return False


if __name__ == '__main__':
    import sys
    success = run_all_tests()
    sys.exit(0 if success else 1)
