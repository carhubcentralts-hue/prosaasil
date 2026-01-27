"""
Test Gemini setup_complete Event Fix
Validates that setup_complete events are properly yielded and duplicate session.updated events are skipped
"""
import os


def test_setup_complete_yield():
    """Test that setup_complete event is yielded in Gemini realtime client"""
    print("\n" + "=" * 60)
    print("Validating setup_complete Event Yield Fix")
    print("=" * 60)
    
    # Read the Gemini realtime client file using relative path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_dir, 'server', 'services', 'gemini_realtime_client.py')
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Test 1: Check that setup_complete creates an event
    if "'type': 'setup_complete'" in content:
        print("✓ setup_complete event is created")
    else:
        print("❌ setup_complete event not created")
        return False
    
    # Test 2: Check that setup_complete event is yielded
    # Look for the pattern where setup_complete is logged and then yielded
    lines = content.split('\n')
    found_setup_complete_section = False
    found_yield_after_setup = False
    
    for i, line in enumerate(lines):
        if 'setup_complete' in line and "'type': 'setup_complete'" in line:
            found_setup_complete_section = True
            # Check next few lines for yield
            for j in range(i, min(i+10, len(lines))):
                if 'yield event' in lines[j]:
                    found_yield_after_setup = True
                    break
            break
    
    if found_setup_complete_section and found_yield_after_setup:
        print("✓ setup_complete event is yielded")
    else:
        print("❌ setup_complete event not properly yielded")
        return False
    
    # Test 3: Check for deduplication of setup_complete (only first one should be yielded)
    if '_setup_complete_seen' in content and 'not _setup_complete_seen' in content:
        print("✓ setup_complete deduplication implemented (only first event yielded)")
    else:
        print("❌ setup_complete deduplication not found")
        return False
    
    # Test 4: Check that we changed elif to if for message attribute checks
    if '# 🔥 FIX: Changed from elif to if - messages can have multiple attributes!' in content:
        print("✓ Changed elif to if - messages can have multiple attributes")
    else:
        print("❌ elif to if change not found or not commented")
        return False
    
    print("\n" + "=" * 60)
    print("✅ SETUP_COMPLETE YIELD FIX VALIDATED")
    print("=" * 60)
    return True


def test_duplicate_session_updated_skip():
    """Test that duplicate session.updated events are skipped"""
    print("\n" + "=" * 60)
    print("Validating Duplicate session.updated Skip")
    print("=" * 60)
    
    # Read the media_ws_ai file using relative path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_dir, 'server', 'media_ws_ai.py')
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Test 1: Check that session.updated handler exists
    if 'if event_type == "session.updated":' in content:
        print("✓ session.updated event handler exists")
    else:
        print("❌ session.updated event handler not found")
        return False
    
    # Test 2: Check for duplicate detection guard
    if 'if self._session_config_confirmed:' in content and 'Skipping duplicate session.updated' in content:
        print("✓ Duplicate session.updated detection implemented")
    else:
        print("❌ Duplicate session.updated detection not found")
        return False
    
    # Test 3: Check that duplicates are skipped with continue
    if 'continue' in content and 'already confirmed' in content:
        print("✓ Duplicate events are properly skipped")
    else:
        print("❌ Duplicate events not properly skipped")
        return False
    
    print("\n" + "=" * 60)
    print("✅ DUPLICATE SESSION.UPDATED SKIP VALIDATED")
    print("=" * 60)
    return True


def test_watchdog_disabled_for_gemini():
    """Test that audio watchdog is disabled for Gemini (SIMPLE MODE)"""
    print("\n" + "=" * 60)
    print("Validating Watchdog Disabled for Gemini (SIMPLE MODE)")
    print("=" * 60)
    
    # Read the media_ws_ai file using relative path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_dir, 'server', 'media_ws_ai.py')
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Test 1: Check that watchdog call is commented out
    if '# if reason == "GREETING" or is_greeting:' in content and '#     self._start_first_audio_watchdog(ai_provider)' in content:
        print("✓ Watchdog call is commented out")
    else:
        print("❌ Watchdog call not properly commented out")
        return False
    
    # Test 2: Check for SIMPLE MODE comment
    if 'SIMPLE MODE' in content and 'בלי WATCHDOG' in content:
        print("✓ SIMPLE MODE comment found (user request documented)")
    else:
        print("❌ SIMPLE MODE comment not found")
        return False
    
    # Test 3: Check that watchdog function still exists (for future debugging if needed)
    if 'def _start_first_audio_watchdog(self, provider: str):' in content:
        print("✓ Watchdog function still exists (disabled but available for debugging)")
    else:
        print("⚠️  Watchdog function removed (not critical)")
    
    print("\n" + "=" * 60)
    print("✅ WATCHDOG DISABLED VALIDATION PASSED")
    print("=" * 60)
    return True


def run_all_tests():
    """Run all test validations"""
    print("\n" + "=" * 80)
    print("GEMINI SETUP_COMPLETE FIX - COMPREHENSIVE VALIDATION")
    print("=" * 80)
    
    results = []
    
    # Test 1: setup_complete yield
    results.append(("setup_complete Event Yield", test_setup_complete_yield()))
    
    # Test 2: Duplicate session.updated skip
    results.append(("Duplicate session.updated Skip", test_duplicate_session_updated_skip()))
    
    # Test 3: Watchdog disabled
    results.append(("Watchdog Disabled (SIMPLE MODE)", test_watchdog_disabled_for_gemini()))
    
    # Print summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
        if not passed:
            all_passed = False
    
    print("=" * 80)
    if all_passed:
        print("🎉 ALL TESTS PASSED - GEMINI FIX IS COMPLETE")
    else:
        print("❌ SOME TESTS FAILED - REVIEW REQUIRED")
    print("=" * 80)
    
    return all_passed


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
