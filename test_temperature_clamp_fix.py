"""
Test for Critical Temperature Clamp Fix in OpenAI Realtime API

Problem: OpenAI Realtime API requires temperature >= 0.6, but code was sending 0.0
Solution: Added _clamp_temperature() function to ensure minimum of 0.6
"""
import sys
import os

def test_temperature_constants():
    """Test that temperature constants are defined correctly"""
    print("\n🔍 Test 1: Verify temperature constants")
    
    # Import the module
    from server.services.openai_realtime_client import (
        REALTIME_TEMPERATURE_MIN,
        REALTIME_TEMPERATURE_DEFAULT
    )
    
    # Verify constants
    assert REALTIME_TEMPERATURE_MIN == 0.6, f"Expected MIN=0.6, got {REALTIME_TEMPERATURE_MIN}"
    assert REALTIME_TEMPERATURE_DEFAULT == 0.6, f"Expected DEFAULT=0.6, got {REALTIME_TEMPERATURE_DEFAULT}"
    
    print(f"  ✅ REALTIME_TEMPERATURE_MIN = {REALTIME_TEMPERATURE_MIN}")
    print(f"  ✅ REALTIME_TEMPERATURE_DEFAULT = {REALTIME_TEMPERATURE_DEFAULT}")


def test_clamp_function():
    """Test that _clamp_temperature() works correctly"""
    print("\n🔍 Test 2: Verify temperature clamping function")
    
    from server.services.openai_realtime_client import _clamp_temperature
    
    # Test cases
    test_cases = [
        (None, 0.6, "None should default to 0.6"),
        (0.0, 0.6, "0.0 should be clamped to 0.6"),
        (0.3, 0.6, "0.3 should be clamped to 0.6"),
        (0.5, 0.6, "0.5 should be clamped to 0.6"),
        (0.6, 0.6, "0.6 should stay 0.6"),
        (0.7, 0.7, "0.7 should stay 0.7"),
        (1.0, 1.0, "1.0 should stay 1.0"),
        (1.5, 1.5, "1.5 should stay 1.5"),
    ]
    
    for input_val, expected, description in test_cases:
        result = _clamp_temperature(input_val)
        assert result == expected, f"Failed: {description}. Expected {expected}, got {result}"
        print(f"  ✅ {description}: {input_val} → {result}")


def test_configure_session_signature():
    """Test that configure_session has correct default temperature"""
    print("\n🔍 Test 3: Verify configure_session signature")
    
    import inspect
    from server.services.openai_realtime_client import OpenAIRealtimeClient
    
    # Get the method signature
    sig = inspect.signature(OpenAIRealtimeClient.configure_session)
    
    # Check temperature parameter
    temp_param = sig.parameters.get('temperature')
    assert temp_param is not None, "temperature parameter not found"
    
    # The default should be None (which gets clamped to 0.6 in the function)
    assert temp_param.default is None, f"Expected default=None, got {temp_param.default}"
    
    print(f"  ✅ temperature parameter default: {temp_param.default}")
    print(f"  ✅ (None will be clamped to 0.6 by _clamp_temperature)")


def test_no_temperature_zero_in_realtime_code():
    """Test that temperature=0.0 has been removed from Realtime code"""
    print("\n🔍 Test 4: Verify no temperature=0.0 in Realtime code")
    
    import re
    from pathlib import Path
    
    # Get the project root directory (where this test file is located)
    project_root = Path(__file__).parent
    
    # Check openai_realtime_client.py
    realtime_client_path = project_root / 'server' / 'services' / 'openai_realtime_client.py'
    with open(realtime_client_path, 'r') as f:
        content = f.read()
    
    # Look for problematic patterns (excluding comments and the clamping logic itself)
    lines = content.split('\n')
    problems = []
    
    for i, line in enumerate(lines, 1):
        # Skip comments
        if line.strip().startswith('#'):
            continue
        # Skip the clamp function definition itself
        if '_clamp_temperature' in line:
            continue
        # Skip the constant definitions
        if 'REALTIME_TEMPERATURE_MIN' in line or 'REALTIME_TEMPERATURE_DEFAULT' in line:
            continue
        
        # Check for temperature=0 or temperature: 0
        if re.search(r'["\']?temperature["\']?\s*[:=]\s*0\.0', line):
            problems.append((i, line.strip()))
    
    if problems:
        print("  ❌ Found temperature=0.0 in realtime client:")
        for line_num, line in problems:
            print(f"     Line {line_num}: {line[:80]}")
        assert False, "temperature=0.0 should be removed from Realtime code"
    else:
        print("  ✅ No problematic temperature=0.0 found in openai_realtime_client.py")
    
    # Check media_ws_ai.py for configure_session calls
    media_ws_path = project_root / 'server' / 'media_ws_ai.py'
    with open(media_ws_path, 'r') as f:
        content = f.read()
    
    # Find configure_session calls with temperature parameter
    pattern = r'configure_session\([^)]*temperature\s*=\s*0\.0'
    matches = re.findall(pattern, content, re.DOTALL)
    
    if matches:
        print(f"  ❌ Found configure_session with temperature=0.0 in media_ws_ai.py")
        for match in matches:
            print(f"     {match[:100]}")
        assert False, "configure_session should not be called with temperature=0.0"
    else:
        print("  ✅ No configure_session calls with temperature=0.0 in media_ws_ai.py")


def test_integration():
    """Test that the complete flow works"""
    print("\n🔍 Test 5: Integration test")
    
    from server.services.openai_realtime_client import _clamp_temperature
    
    # Simulate what happens when configure_session is called
    # Case 1: No temperature specified (typical usage now)
    temp1 = _clamp_temperature(None)
    assert temp1 == 0.6, f"Default case failed: got {temp1}"
    print(f"  ✅ Case 1 (no temp specified): None → {temp1}")
    
    # Case 2: Someone tries to pass 0.0 explicitly
    temp2 = _clamp_temperature(0.0)
    assert temp2 == 0.6, f"Clamp case failed: got {temp2}"
    print(f"  ✅ Case 2 (explicit 0.0): 0.0 → {temp2}")
    
    # Case 3: Valid temperature
    temp3 = _clamp_temperature(0.8)
    assert temp3 == 0.8, f"Valid temp case failed: got {temp3}"
    print(f"  ✅ Case 3 (valid temp): 0.8 → {temp3}")


if __name__ == "__main__":
    print("=" * 70)
    print("Testing Critical Temperature Clamp Fix for OpenAI Realtime API")
    print("=" * 70)
    print("\n📋 Problem: OpenAI returns error: decimal_below_min_value")
    print("   Expected >= 0.6, got 0.0")
    print("\n✨ Solution: Added _clamp_temperature() to ensure minimum of 0.6")
    print("=" * 70)
    
    try:
        test_temperature_constants()
        test_clamp_function()
        test_configure_session_signature()
        test_no_temperature_zero_in_realtime_code()
        test_integration()
        
        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED!")
        print("=" * 70)
        print("\n📊 Summary:")
        print("  ✅ Temperature constants defined correctly (0.6)")
        print("  ✅ Clamp function works for all cases")
        print("  ✅ configure_session signature updated")
        print("  ✅ No temperature=0.0 in Realtime code")
        print("  ✅ Integration flow verified")
        print("\n🎉 The fix prevents the decimal_below_min_value error!")
        print("   OpenAI Realtime API will now accept the temperature value.")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
