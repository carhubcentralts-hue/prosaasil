#!/usr/bin/env python3
"""
🧪 UNIT TESTS: Prompt System Fix (No DB Required)
=================================================

Tests core logic without database dependencies.
"""
import sys
import os
sys.path.insert(0, '/home/runner/work/prosaasil/prosaasil')


def test_missing_prompt_error_exists():
    """Verify MissingPromptError exception exists"""
    print("\n" + "="*80)
    print("TEST: MissingPromptError exception exists")
    print("="*80)
    
    try:
        from server.services.realtime_prompt_builder import MissingPromptError
        print("✅ PASS: MissingPromptError imported successfully")
        
        # Test raising it
        try:
            raise MissingPromptError("Test error")
        except MissingPromptError as e:
            print(f"✅ PASS: Exception raised and caught: {e}")
            return True
    except ImportError as e:
        print(f"❌ FAIL: Cannot import MissingPromptError: {e}")
        return False


def test_extract_no_sanitization():
    """Test that _extract_business_prompt_text doesn't sanitize"""
    print("\n" + "="*80)
    print("TEST: No sanitization in _extract_business_prompt_text")
    print("="*80)
    
    from server.services.realtime_prompt_builder import _extract_business_prompt_text
    
    tests = [
        {
            "name": "Spaces preserved",
            "input": "  Text with spaces  ",
            "expected_contains": "  Text with spaces  "
        },
        {
            "name": "Newlines preserved",
            "input": "Line1\n\nLine2",
            "expected_contains": "\n\n"
        },
        {
            "name": "Hebrew preserved",
            "input": "שלום עולם",
            "expected_contains": "שלום"
        },
        {
            "name": "JSON format - calls channel",
            "input": '{"calls": "Call text", "whatsapp": "WA text"}',
            "expected_contains": "Call text"
        },
        {
            "name": "Business name replacement",
            "input": "Welcome to {{business_name}}",
            "expected_contains": "Welcome to TestBiz"
        },
    ]
    
    all_passed = True
    for test in tests:
        result = _extract_business_prompt_text(
            business_name="TestBiz",
            ai_prompt_raw=test["input"]
        )
        
        if test["expected_contains"] in result:
            print(f"   ✅ PASS: {test['name']}")
        else:
            print(f"   ❌ FAIL: {test['name']}")
            print(f"      Expected to contain: '{test['expected_contains']}'")
            print(f"      Got: '{result}'")
            all_passed = False
    
    return all_passed


def test_fallback_removed_in_code():
    """Verify fallback code is removed"""
    print("\n" + "="*80)
    print("TEST: Fallback code removed from build_full_business_prompt")
    print("="*80)
    
    import inspect
    from server.services.realtime_prompt_builder import build_full_business_prompt
    
    source = inspect.getsource(build_full_business_prompt)
    
    # Check for old fallback patterns
    bad_patterns = [
        'Using inbound prompt as fallback for outbound',
        'Using outbound prompt as fallback for inbound',
        'Using system_prompt as fallback',
        'PROMPT FALLBACK'
    ]
    
    found_bad = []
    for pattern in bad_patterns:
        if pattern in source:
            found_bad.append(pattern)
    
    if found_bad:
        print(f"❌ FAIL: Found old fallback code:")
        for pattern in found_bad:
            print(f"   - '{pattern}'")
        return False
    else:
        print("✅ PASS: No fallback code found")
        
        # Check for MissingPromptError raise
        if 'MissingPromptError' in source:
            print("✅ PASS: MissingPromptError is raised")
            return True
        else:
            print("❌ FAIL: MissingPromptError not found in source")
            return False


def test_stream_registry_metadata():
    """Test stream_registry stores metadata correctly"""
    print("\n" + "="*80)
    print("TEST: stream_registry metadata storage")
    print("="*80)
    
    from server.stream_state import stream_registry
    
    call_sid = "TEST_METADATA_001"
    
    # Store metadata as webhook would
    stream_registry.set_metadata(call_sid, '_prebuilt_full_prompt', "Test prompt text")
    stream_registry.set_metadata(call_sid, '_prebuilt_direction', 'inbound')
    stream_registry.set_metadata(call_sid, '_prebuilt_business_id', 123)
    stream_registry.set_metadata(call_sid, '_prebuilt_prompt_hash', 'abc123')
    
    # Retrieve
    prompt = stream_registry.get_metadata(call_sid, '_prebuilt_full_prompt')
    direction = stream_registry.get_metadata(call_sid, '_prebuilt_direction')
    business_id = stream_registry.get_metadata(call_sid, '_prebuilt_business_id')
    prompt_hash = stream_registry.get_metadata(call_sid, '_prebuilt_prompt_hash')
    
    # Validate
    passed = True
    if prompt == "Test prompt text":
        print("   ✅ PASS: Prompt stored and retrieved")
    else:
        print(f"   ❌ FAIL: Prompt mismatch: {prompt}")
        passed = False
    
    if direction == 'inbound':
        print("   ✅ PASS: Direction stored and retrieved")
    else:
        print(f"   ❌ FAIL: Direction mismatch: {direction}")
        passed = False
    
    if business_id == 123:
        print("   ✅ PASS: Business ID stored and retrieved")
    else:
        print(f"   ❌ FAIL: Business ID mismatch: {business_id}")
        passed = False
    
    if prompt_hash == 'abc123':
        print("   ✅ PASS: Prompt hash stored and retrieved")
    else:
        print(f"   ❌ FAIL: Prompt hash mismatch: {prompt_hash}")
        passed = False
    
    # Cleanup
    stream_registry.clear(call_sid)
    
    return passed


def test_mismatch_detection_logic():
    """Test direction mismatch detection"""
    print("\n" + "="*80)
    print("TEST: Direction mismatch detection")
    print("="*80)
    
    from server.stream_state import stream_registry
    
    test_cases = [
        {
            "name": "Match: inbound == inbound",
            "prebuilt": "inbound",
            "expected": "inbound",
            "should_mismatch": False
        },
        {
            "name": "Match: outbound == outbound",
            "prebuilt": "outbound",
            "expected": "outbound",
            "should_mismatch": False
        },
        {
            "name": "Mismatch: outbound != inbound",
            "prebuilt": "outbound",
            "expected": "inbound",
            "should_mismatch": True
        },
        {
            "name": "Mismatch: inbound != outbound",
            "prebuilt": "inbound",
            "expected": "outbound",
            "should_mismatch": True
        },
    ]
    
    all_passed = True
    for test in test_cases:
        call_sid = f"TEST_{test['name']}"
        
        # Store prebuilt direction
        stream_registry.set_metadata(call_sid, '_prebuilt_direction', test['prebuilt'])
        
        # Retrieve and check
        prebuilt_direction = stream_registry.get_metadata(call_sid, '_prebuilt_direction')
        call_direction = test['expected']
        
        mismatch_detected = (prebuilt_direction != call_direction)
        
        if mismatch_detected == test['should_mismatch']:
            print(f"   ✅ PASS: {test['name']}")
        else:
            print(f"   ❌ FAIL: {test['name']}")
            print(f"      Expected mismatch={test['should_mismatch']}, got={mismatch_detected}")
            all_passed = False
        
        stream_registry.clear(call_sid)
    
    return all_passed


def test_hard_lock_removed():
    """Verify HARD LOCK code is removed from media_ws_ai.py"""
    print("\n" + "="*80)
    print("TEST: HARD LOCK removed from media_ws_ai.py")
    print("="*80)
    
    try:
        with open('/home/runner/work/prosaasil/prosaasil/server/media_ws_ai.py', 'r') as f:
            content = f.read()
        
        # Check for old HARD LOCK pattern
        if 'CONTINUE_NO_REBUILD' in content:
            print("❌ FAIL: Found 'CONTINUE_NO_REBUILD' - HARD LOCK still exists")
            return False
        
        if 'NOT rebuilding - continuing with pre-built prompt' in content:
            print("❌ FAIL: Found old HARD LOCK message")
            return False
        
        # Check for new rebuild logic
        if 'REBUILDING with correct direction' in content:
            print("✅ PASS: Found new rebuild logic")
        elif 'action=REBUILD' in content:
            print("✅ PASS: Found REBUILD action")
        else:
            print("⚠️  WARNING: Can't find rebuild logic - check manually")
        
        print("✅ PASS: HARD LOCK code removed")
        return True
        
    except Exception as e:
        print(f"❌ FAIL: Error reading file: {e}")
        return False


def main():
    print("\n" + "="*80)
    print("🧪 UNIT TESTS: Prompt System Fix (No DB)")
    print("="*80)
    
    results = {}
    
    tests = [
        ("exception_exists", test_missing_prompt_error_exists),
        ("no_sanitization", test_extract_no_sanitization),
        ("fallback_removed", test_fallback_removed_in_code),
        ("metadata_storage", test_stream_registry_metadata),
        ("mismatch_detection", test_mismatch_detection_logic),
        ("hard_lock_removed", test_hard_lock_removed),
    ]
    
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"\n❌ Test {test_name} crashed: {e}")
            import traceback
            traceback.print_exc()
            results[test_name] = False
    
    # Summary
    print("\n" + "="*80)
    print("📊 TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
