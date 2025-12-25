#!/usr/bin/env python3
"""
Test that verifies the CLOSING state logic is properly implemented.

This test checks:
1. Audio input blocking when call_state = CLOSING
2. response.create blocking when call_state = CLOSING
3. Full text logging (no truncation) in BOT_BYE_DETECTED
"""

import re

def test_closing_state_audio_blocking():
    """Test that audio input is blocked when in CLOSING state"""
    print("\n=== Testing CLOSING state audio blocking ===")
    
    with open('server/media_ws_ai.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the audio sender loop section
    audio_section_start = content.find('def _realtime_audio_sender')
    if audio_section_start == -1:
        print("  ❌ FAIL: _realtime_audio_sender function not found")
        return False
    
    audio_section = content[audio_section_start:audio_section_start + 20000]
    
    # Check for CLOSING state check
    checks = [
        ('if self.call_state == CallState.CLOSING:', 'Has CLOSING state check'),
        ('ignoring all user audio input', 'Logs that audio is being ignored'),
        ('_closing_block_logged', 'Has closing block logged flag'),
        ('_stats_audio_blocked', 'Increments blocked stats'),
        ('continue', 'Skips sending audio when CLOSING'),
    ]
    
    passed = 0
    failed = 0
    
    for check_str, description in checks:
        if check_str in audio_section:
            print(f"  ✅ PASS: {description}")
            passed += 1
        else:
            print(f"  ❌ FAIL: {description} - '{check_str}' not found")
            failed += 1
    
    print(f"\nAudio blocking test: {passed} passed, {failed} failed")
    return failed == 0

def test_closing_state_response_blocking():
    """Test that response.create is blocked when in CLOSING state"""
    print("\n=== Testing CLOSING state response.create blocking ===")
    
    with open('server/media_ws_ai.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the trigger_response function
    trigger_section_start = content.find('async def trigger_response')
    if trigger_section_start == -1:
        print("  ❌ FAIL: trigger_response function not found")
        return False
    
    trigger_section = content[trigger_section_start:trigger_section_start + 5000]
    
    # Check for CLOSING state guard
    checks = [
        ('if self.call_state == CallState.CLOSING:', 'Has CLOSING state guard'),
        ('Call in CLOSING state - blocking new responses', 'Logs blocking message'),
        ('return False', 'Returns False to block response'),
    ]
    
    passed = 0
    failed = 0
    
    for check_str, description in checks:
        if check_str in trigger_section:
            print(f"  ✅ PASS: {description}")
            passed += 1
        else:
            print(f"  ❌ FAIL: {description} - '{check_str}' not found")
            failed += 1
    
    print(f"\nResponse blocking test: {passed} passed, {failed} failed")
    return failed == 0

def test_full_text_logging():
    """Test that BOT_BYE_DETECTED logs full text without truncation"""
    print("\n=== Testing full text logging in BOT_BYE_DETECTED ===")
    
    with open('server/media_ws_ai.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the BOT_BYE_DETECTED section
    bye_section_start = content.find('[BOT_BYE_DETECTED]')
    if bye_section_start == -1:
        print("  ❌ FAIL: [BOT_BYE_DETECTED] not found")
        return False
    
    bye_section = content[bye_section_start-200:bye_section_start + 500]
    
    # Check that we're logging full text, not truncated
    checks = [
        ("text='{_t_raw}'", 'Logs full text without truncation'),
        ('# 🔥 FIX: Log full text without truncation', 'Has fix comment'),
    ]
    
    # Check that old truncated version is NOT present
    if "[:80]" in bye_section or "[:120]" in bye_section:
        print(f"  ❌ FAIL: Still truncating text with [:80] or [:120]")
        return False
    else:
        print(f"  ✅ PASS: Not truncating text")
    
    passed = 1  # Count the truncation check
    failed = 0
    
    for check_str, description in checks:
        if check_str in bye_section:
            print(f"  ✅ PASS: {description}")
            passed += 1
        else:
            print(f"  ❌ FAIL: {description} - '{check_str}' not found")
            failed += 1
    
    print(f"\nFull text logging test: {passed} passed, {failed} failed")
    return failed == 0

def test_closing_block_logged_initialization():
    """Test that _closing_block_logged flag is initialized"""
    print("\n=== Testing _closing_block_logged initialization ===")
    
    with open('server/media_ws_ai.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the __init__ section around greeting_lock_active
    init_section_start = content.find('self.greeting_lock_active = False')
    if init_section_start == -1:
        print("  ❌ FAIL: greeting_lock_active initialization not found")
        return False
    
    init_section = content[init_section_start:init_section_start + 1000]
    
    # Check for _closing_block_logged initialization
    if 'self._closing_block_logged = False' in init_section:
        print(f"  ✅ PASS: _closing_block_logged is initialized to False")
        return True
    else:
        print(f"  ❌ FAIL: _closing_block_logged not initialized")
        return False

def main():
    print("="*70)
    print("CLOSING STATE LOGIC TEST SUITE")
    print("="*70)
    
    results = []
    
    results.append(("Audio blocking in CLOSING state", test_closing_state_audio_blocking()))
    results.append(("Response.create blocking in CLOSING state", test_closing_state_response_blocking()))
    results.append(("Full text logging", test_full_text_logging()))
    results.append(("_closing_block_logged initialization", test_closing_block_logged_initialization()))
    
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed_count = sum(1 for _, result in results if result)
    total_count = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {name}")
    
    print("\n" + "="*70)
    print(f"TOTAL: {passed_count}/{total_count} tests passed")
    print("="*70)
    
    if passed_count == total_count:
        print("\n✅ All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total_count - passed_count} test(s) failed")
        return 1

if __name__ == '__main__':
    exit(main())
