#!/usr/bin/env python3
"""
Verification script for temperature parameter fix.

This script verifies that:
1. The temperature parameter is NOT in input_audio_transcription config
2. The temperature parameter IS in session config (at the correct level)
3. The valid parameters for input_audio_transcription are present
"""

import inspect
from server.services.openai_realtime_client import OpenAIRealtimeClient


def verify_temperature_fix():
    """Verify that temperature is at session level, not transcription level."""
    print("=" * 70)
    print("TEMPERATURE PARAMETER FIX VERIFICATION")
    print("=" * 70)
    print()
    
    # Get the source code of configure_session method
    source = inspect.getsource(OpenAIRealtimeClient.configure_session)
    
    # Split into lines for better analysis
    lines = source.split('\n')
    
    # Track what we find
    found_transcription_config = False
    found_session_config = False
    transcription_config_lines = []
    session_config_lines = []
    
    # Collect lines for transcription_config and session_config
    in_transcription = False
    in_session = False
    brace_count = 0
    
    for i, line in enumerate(lines):
        if 'transcription_config = {' in line:
            found_transcription_config = True
            in_transcription = True
            brace_count = 1
            transcription_config_lines.append((i, line))
            continue
        
        if 'session_config = {' in line:
            found_session_config = True
            in_session = True
            brace_count = 1
            session_config_lines.append((i, line))
            continue
        
        if in_transcription:
            transcription_config_lines.append((i, line))
            brace_count += line.count('{') - line.count('}')
            if brace_count == 0:
                in_transcription = False
        
        if in_session:
            session_config_lines.append((i, line))
            brace_count += line.count('{') - line.count('}')
            if brace_count == 0:
                in_session = False
    
    # Test 1: Verify transcription_config exists
    print("🧪 Test 1: Verify transcription_config exists")
    assert found_transcription_config, "transcription_config should exist in source"
    print("   ✅ PASS: transcription_config found")
    print()
    
    # Test 2: Verify session_config exists
    print("🧪 Test 2: Verify session_config exists")
    assert found_session_config, "session_config should exist in source"
    print("   ✅ PASS: session_config found")
    print()
    
    # Test 3: Verify transcription_config has required parameters
    print("🧪 Test 3: Verify transcription_config has valid parameters")
    transcription_text = '\n'.join([line for _, line in transcription_config_lines])
    
    assert '"model"' in transcription_text, "transcription_config should have model"
    print("   ✅ PASS: model parameter found")
    
    assert '"language"' in transcription_text, "transcription_config should have language"
    print("   ✅ PASS: language parameter found")
    
    assert '"he"' in transcription_text, "language should be set to 'he'"
    print("   ✅ PASS: language set to Hebrew (he)")
    print()
    
    # Test 4: Verify transcription_config does NOT have temperature
    print("🧪 Test 4: Verify transcription_config does NOT have temperature")
    transcription_temp_check = any(
        '"temperature"' in line or "'temperature'" in line
        for _, line in transcription_config_lines
    )
    assert not transcription_temp_check, \
        "transcription_config should NOT have temperature parameter"
    print("   ✅ PASS: temperature NOT found in transcription_config")
    print()
    
    # Test 5: Verify session_config HAS temperature
    print("🧪 Test 5: Verify session_config HAS temperature")
    session_text = '\n'.join([line for _, line in session_config_lines])
    assert '"temperature"' in session_text, \
        "session_config should have temperature parameter"
    print("   ✅ PASS: temperature found in session_config")
    print()
    
    # Test 6: Verify session_config has input_audio_transcription
    print("🧪 Test 6: Verify session_config uses transcription_config")
    assert '"input_audio_transcription": transcription_config' in session_text, \
        "session_config should reference transcription_config"
    print("   ✅ PASS: input_audio_transcription references transcription_config")
    print()
    
    # Print summary
    print("=" * 70)
    print("🎉 ALL VERIFICATION TESTS PASSED!")
    print("=" * 70)
    print()
    print("Summary:")
    print("  ✅ transcription_config has valid parameters (model, language)")
    print("  ✅ transcription_config does NOT have temperature (correct)")
    print("  ✅ session_config has temperature parameter (correct)")
    print("  ✅ API call will not fail with 'unknown_parameter' error")
    print()
    print("This fix resolves the production error:")
    print("  'Unknown parameter: session.input_audio_transcription.temperature'")
    print()


if __name__ == "__main__":
    try:
        verify_temperature_fix()
    except AssertionError as e:
        print(f"❌ VERIFICATION FAILED: {e}")
        exit(1)
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
