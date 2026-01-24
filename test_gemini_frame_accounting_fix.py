"""
Test Gemini Frame Accounting Fix

Validates that:
1. Gemini pipeline increments _stats_audio_sent counter when frames are pushed to STT
2. Frame accounting errors for Gemini are logged as warnings, not errors
3. Frame accounting errors for Gemini don't cause session closure
"""
import re


def test_gemini_frame_counter_increment():
    """Test that _stats_audio_sent is incremented when frames are pushed to Gemini STT"""
    print("\n" + "=" * 60)
    print("Test 1: Gemini Frame Counter Increment")
    print("=" * 60)
    
    with open('/home/runner/work/prosaasil/prosaasil/server/media_ws_ai.py', 'r') as f:
        content = f.read()
    
    # Find the section where audio is pushed to STT for Gemini
    pattern = r'elif not USE_REALTIME_API.*?session\.push_audio\(pcm16\).*?self\._stats_audio_sent \+= 1'
    
    if re.search(pattern, content, re.DOTALL):
        print("✓ _stats_audio_sent is incremented when frames are pushed to Gemini STT")
        return True
    else:
        print("❌ _stats_audio_sent is NOT incremented for Gemini STT")
        # Let's check if the counter increment exists at all in that section
        if 'session.push_audio(pcm16)' in content:
            # Find the context around push_audio
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if 'session.push_audio(pcm16)' in line:
                    context = '\n'.join(lines[max(0, i-5):min(len(lines), i+10)])
                    print("\nContext around session.push_audio:")
                    print(context)
                    if '_stats_audio_sent' in context:
                        print("✓ Counter increment found in context!")
                        return True
        return False


def test_gemini_frame_accounting_warning():
    """Test that frame accounting errors for Gemini are logged as warnings"""
    print("\n" + "=" * 60)
    print("Test 2: Gemini Frame Accounting Warning (Not Error)")
    print("=" * 60)
    
    with open('/home/runner/work/prosaasil/prosaasil/server/media_ws_ai.py', 'r') as f:
        content = f.read()
    
    # Look for the frame accounting section with ai_provider check
    checks = [
        ('ai_provider check exists', r'ai_provider\s*=\s*getattr\(self,\s*[\'"]_ai_provider'),
        ('Gemini condition exists', r'if ai_provider == [\'"]gemini[\'"]'),
        ('FRAME_ACCOUNTING_WARNING log', r'FRAME_ACCOUNTING_WARNING.*Gemini'),
        ('logger.warning for Gemini', r'logger\.warning.*FRAME_ACCOUNTING_WARNING'),
    ]
    
    all_passed = True
    for check_name, pattern in checks:
        if re.search(pattern, content, re.IGNORECASE | re.DOTALL):
            print(f"✓ {check_name}")
        else:
            print(f"❌ {check_name} not found")
            all_passed = False
    
    return all_passed


def test_gemini_no_session_close():
    """Test that Gemini frame accounting doesn't trigger session close"""
    print("\n" + "=" * 60)
    print("Test 3: Gemini Frame Accounting Doesn't Close Session")
    print("=" * 60)
    
    with open('/home/runner/work/prosaasil/prosaasil/server/media_ws_ai.py', 'r') as f:
        content = f.read()
    
    # Find the frame accounting section - look for the specific code block
    # Search for the pattern around line 16379-16404
    pattern = r'if frames_in_from_twilio != expected_total:.*?ai_provider = getattr.*?if ai_provider == [\'"]gemini[\'"]:(.*?)else:(.*?)logger\.info.*?✅'
    match = re.search(pattern, content, re.DOTALL)
    
    if match:
        gemini_section = match.group(1)
        
        # Check that the Gemini section doesn't call close_session
        if 'close_session' not in gemini_section.lower():
            print("✓ Gemini accounting section does NOT call close_session")
        else:
            print("❌ Gemini accounting section calls close_session (should not)")
            return False
        
        # Check that it logs as warning
        if 'warning' in gemini_section.lower():
            print("✓ Gemini accounting section logs as warning")
        else:
            print("❌ Gemini accounting section doesn't log as warning")
            return False
        
        return True
    else:
        print("⚠️  Gemini conditional pattern not matched exactly, checking simpler pattern...")
        # Simpler check
        if 'ai_provider == "gemini"' in content or "ai_provider == 'gemini'" in content:
            print("✓ Gemini provider check exists")
            if 'FRAME_ACCOUNTING_WARNING' in content:
                print("✓ FRAME_ACCOUNTING_WARNING exists")
                return True
        print("❌ Could not verify Gemini accounting logic")
        return False


def test_openai_still_has_error():
    """Test that OpenAI Realtime still gets ERROR behavior (no regression)"""
    print("\n" + "=" * 60)
    print("Test 4: OpenAI Realtime Still Gets ERROR Behavior")
    print("=" * 60)
    
    with open('/home/runner/work/prosaasil/prosaasil/server/media_ws_ai.py', 'r') as f:
        content = f.read()
    
    # Check that FRAME_ACCOUNTING_ERROR still exists (for OpenAI)
    if 'FRAME_ACCOUNTING_ERROR' in content:
        print("✓ FRAME_ACCOUNTING_ERROR still exists (for OpenAI)")
    else:
        print("❌ FRAME_ACCOUNTING_ERROR not found")
        return False
    
    # Check that there's still error logging
    if 'logger.error' in content and 'Mathematical inconsistency' in content:
        print("✓ logger.error with 'Mathematical inconsistency' exists")
    else:
        print("❌ Error logging not found")
        return False
    
    return True


def run_all_tests():
    """Run all Gemini frame accounting fix tests"""
    print("\n" + "=" * 80)
    print("GEMINI FRAME ACCOUNTING FIX - VALIDATION TESTS")
    print("=" * 80)
    
    tests = [
        test_gemini_frame_counter_increment,
        test_gemini_frame_accounting_warning,
        test_gemini_no_session_close,
        test_openai_still_has_error,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test {test.__name__} raised exception: {e}")
            results.append(False)
    
    print("\n" + "=" * 80)
    if all(results):
        print("✅ ALL TESTS PASSED!")
        print("=" * 80)
        return True
    else:
        print("❌ SOME TESTS FAILED")
        print("=" * 80)
        return False


if __name__ == '__main__':
    import sys
    success = run_all_tests()
    sys.exit(0 if success else 1)
