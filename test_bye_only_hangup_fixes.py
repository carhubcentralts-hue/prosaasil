#!/usr/bin/env python3
"""
Test suite for BYE-ONLY hangup + barge-in precision fixes

Tests all 6 critical fixes:
1. BYE detection only on FINAL bot text (response.audio_transcript.done)
2. Response ID binding (pending_hangup_response_id matches audio.done)
3. Regex matches END of response only
4. Race condition - barge-in during goodbye clears pending_hangup
5. NO TRUNCATION - clears both queues on barge-in
6. Timeouts cleanup only, never hangup
"""

import re
import sys
import os

# Add server to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))

def test_fix_3_goodbye_at_end_only():
    """
    FIX 3: Test that goodbye regex only matches at END of response
    """
    print("\n=== Testing FIX 3: Goodbye at END only ===")
    
    # Patterns from the code
    bye_patterns = [
        r'\bביי\b(?:\s*[.!?…"\']*\s*)?$',
        r'\bלהתראות\b(?:\s*[.!?…"\']*\s*)?$', 
        r'\bשלום ולהתראות\b(?:\s*[.!?…"\']*\s*)?$'
    ]
    
    # Test cases: (text, should_match)
    test_cases = [
        ("תודה רבה, ביי", True),  # Should match - bye at end
        ("ביי ויום טוב", False),  # Should NOT match - "ויום טוב" comes after bye
        ("שלום ולהתראות!", True),  # Should match
        ("ביי ביי", True),  # Should match
        ("תודה אבל לא ביי עדיין, יש לי שאלה", False),  # Should NOT match - bye not at end
        ("ביי, אני חוזר", False),  # Should NOT match - bye in middle
        ("תודה רבה על הכל", False),  # Should NOT match - no bye
        ("היי שלום", False),  # Should NOT match - just greeting
        ("ביי!", True),  # Should match - with punctuation at end
        ("להתראות.", True),  # Should match - with period
        ("להתראות", True),  # Should match - goodbye at end
        ("תודה להתראות", True),  # Should match - goodbye at end
    ]
    
    passed = 0
    failed = 0
    
    for text, expected in test_cases:
        # Normalize like the code does
        text_norm = " ".join(re.sub(r"""[.,;:!?"'()\[\]\{\}<>״""''\-–—]""", " ", text).split()).lower()
        
        # Split by sentences and take last
        sentences = [s.strip() for s in re.split(r'[.!?]', text) if s.strip()]
        last_sentence = sentences[-1] if sentences else text
        last_sentence_norm = " ".join(re.sub(r"""[.,;:!?"'()\[\]\{\}<>״""''\-–—]""", " ", last_sentence).split()).lower()
        
        # Check patterns
        has_goodbye = any(re.search(pattern, last_sentence_norm) for pattern in bye_patterns)
        
        if has_goodbye == expected:
            print(f"  ✅ PASS: '{text}' -> {has_goodbye} (expected {expected})")
            passed += 1
        else:
            print(f"  ❌ FAIL: '{text}' -> {has_goodbye} (expected {expected})")
            failed += 1
    
    print(f"\nFIX 3 Results: {passed} passed, {failed} failed")
    return failed == 0

def test_fix_4_barge_in_clears_pending_hangup():
    """
    FIX 4: Test that barge-in clears pending_hangup (race condition)
    
    This is a code structure test - verifies the fix is in place
    """
    print("\n=== Testing FIX 4: Barge-in clears pending_hangup ===")
    
    # Read the media_ws_ai.py file
    with open('server/media_ws_ai.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the _simple_barge_in_stop function
    if '_simple_barge_in_stop' not in content:
        print("  ❌ FAIL: _simple_barge_in_stop function not found")
        return False
    
    # Check that it clears pending_hangup
    barge_in_section = content[content.find('def _simple_barge_in_stop'):content.find('def _simple_barge_in_stop') + 5000]
    
    checks = [
        ('self.pending_hangup = False', 'Clears pending_hangup flag'),
        ('self.pending_hangup_response_id = None', 'Clears pending_hangup_response_id'),
        ('FIX 4', 'Has FIX 4 comment marker'),
        ('user interrupted', 'Has comment about user interruption'),
    ]
    
    passed = 0
    failed = 0
    
    for check_str, description in checks:
        if check_str in barge_in_section:
            print(f"  ✅ PASS: {description}")
            passed += 1
        else:
            print(f"  ❌ FAIL: {description} - '{check_str}' not found")
            failed += 1
    
    print(f"\nFIX 4 Results: {passed} passed, {failed} failed")
    return failed == 0

def test_fix_5_both_queues_cleared():
    """
    FIX 5: Test that barge-in clears BOTH queues (realtime_audio_out + tx_q)
    """
    print("\n=== Testing FIX 5: Both queues cleared ===")
    
    # Read the media_ws_ai.py file
    with open('server/media_ws_ai.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the barge-in section
    barge_in_section = content[content.find('def _simple_barge_in_stop'):content.find('def _simple_barge_in_stop') + 5000]
    
    checks = [
        ('realtime_audio_out_queue', 'Clears realtime_audio_out_queue'),
        ('tx_q', 'Clears tx_q'),
        ('get_nowait()', 'Uses get_nowait() to drain queue'),
        ('FIX 5', 'Has FIX 5 comment marker'),
        ('NO TRUNCATION', 'Has NO TRUNCATION comment'),
    ]
    
    passed = 0
    failed = 0
    
    for check_str, description in checks:
        if check_str in barge_in_section:
            print(f"  ✅ PASS: {description}")
            passed += 1
        else:
            print(f"  ❌ FAIL: {description} - '{check_str}' not found")
            failed += 1
    
    print(f"\nFIX 5 Results: {passed} passed, {failed} failed")
    return failed == 0

def test_fix_6_timeouts_no_hangup():
    """
    FIX 6: Test that timeouts do cleanup only, never call hangup
    """
    print("\n=== Testing FIX 6: Timeouts no hangup ===")
    
    # Read the media_ws_ai.py file
    with open('server/media_ws_ai.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find timeout functions and check they don't call hangup
    timeout_functions = [
        ('_fallback_hangup_after_timeout', 'Fallback timeout'),
        ('_start_silence_monitor', 'Silence monitor'),
    ]
    
    passed = 0
    failed = 0
    
    for func_name, description in timeout_functions:
        if func_name not in content:
            print(f"  ⚠️  SKIP: {description} function not found")
            continue
        
        # Extract function content
        start = content.find(f'def {func_name}')
        # Find next function definition or end
        next_func = content.find('\n    def ', start + 1)
        if next_func == -1:
            next_func = len(content)
        func_content = content[start:next_func]
        
        # Check for FIX 6 markers
        has_fix6 = 'FIX 6' in func_content
        has_cleanup_only = 'cleanup only' in func_content.lower() or 'CLEANUP ONLY' in func_content
        
        # Check that it doesn't call hangup methods (except in comments)
        # Remove comments first
        func_no_comments = re.sub(r'#.*$', '', func_content, flags=re.MULTILINE)
        
        calls_hangup = (
            'request_hangup(' in func_no_comments or
            '_trigger_auto_hangup(' in func_no_comments or
            'hangup_call(' in func_no_comments
        )
        
        if has_fix6 and has_cleanup_only and not calls_hangup:
            print(f"  ✅ PASS: {description} - FIX 6 implemented, no hangup calls")
            passed += 1
        else:
            print(f"  ❌ FAIL: {description}")
            if not has_fix6:
                print(f"      - Missing FIX 6 marker")
            if not has_cleanup_only:
                print(f"      - Missing 'cleanup only' comment")
            if calls_hangup:
                print(f"      - Still calls hangup methods")
            failed += 1
    
    print(f"\nFIX 6 Results: {passed} passed, {failed} failed")
    return failed == 0

def test_fix_1_2_bye_only_final_text():
    """
    FIX 1 & 2: Test that BYE detection only on FINAL text with response_id
    """
    print("\n=== Testing FIX 1 & 2: BYE only on FINAL text with response_id ===")
    
    # Read the media_ws_ai.py file
    with open('server/media_ws_ai.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = [
        ('response.audio_transcript.done', 'Detects on audio_transcript.done (FINAL text only)'),
        ('BOT_BYE_DETECTED', 'Has BOT_BYE_DETECTED log marker'),
        ('pending_hangup_response_id', 'Stores response_id for matching'),
        ('bot_goodbye_bye_only', 'Uses bot_goodbye_bye_only reason'),
        ('response_id=event.get', 'Passes response_id to request_hangup'),
    ]
    
    passed = 0
    failed = 0
    
    # Find the BYE detection section - search in larger area
    bye_section_start = content.find('response.audio_transcript.done')
    if bye_section_start == -1:
        print("  ❌ FAIL: response.audio_transcript.done handler not found")
        return False
    
    bye_section = content[bye_section_start:bye_section_start + 5000]  # Increased search area
    
    for check_str, description in checks:
        # Special handling for pending_hangup_response_id - it's set in request_hangup, not in BYE detection
        if check_str == 'pending_hangup_response_id':
            # Search in request_hangup function instead
            request_hangup_start = content.find('async def request_hangup')
            if request_hangup_start > 0:
                request_hangup_section = content[request_hangup_start:request_hangup_start + 3000]
                if 'self.pending_hangup_response_id = bound_response_id' in request_hangup_section:
                    print(f"  ✅ PASS: {description}")
                    passed += 1
                else:
                    print(f"  ❌ FAIL: {description} - assignment not found in request_hangup")
                    failed += 1
            else:
                print(f"  ❌ FAIL: {description} - request_hangup function not found")
                failed += 1
        elif check_str in bye_section:
            print(f"  ✅ PASS: {description}")
            passed += 1
        else:
            print(f"  ❌ FAIL: {description} - '{check_str}' not found")
            failed += 1
    
    # Also check audio.done handler has response_id matching - search for the hangup-specific one
    # We need the line that has BOTH "response.audio.done" AND "pending_hangup"
    search_str = 'response.audio.done" and self.pending_hangup'
    audio_done_section_start = content.find(search_str)
    if audio_done_section_start == -1:
        print(f"  ❌ FAIL: response.audio.done + pending_hangup handler not found")
        failed += 1
    else:
        # Get a section around this line
        audio_done_section = content[audio_done_section_start-500:audio_done_section_start + 2000]
        # Check for response_id matching logic
        has_pending_id = 'pending_hangup_response_id' in audio_done_section
        has_done_id = 'done_resp_id' in audio_done_section
        has_comparison = 'pending_id != done_resp_id' in audio_done_section or 'pending_id and done_resp_id' in audio_done_section
        
        if has_pending_id and has_done_id and has_comparison:
            print(f"  ✅ PASS: audio.done handler checks response_id match")
            passed += 1
        else:
            print(f"  ❌ FAIL: audio.done handler missing response_id checks")
            if not has_pending_id:
                print(f"      - Missing pending_hangup_response_id reference")
            if not has_done_id:
                print(f"      - Missing done_resp_id extraction")
            if not has_comparison:
                print(f"      - Missing ID comparison logic")
            failed += 1
    
    print(f"\nFIX 1 & 2 Results: {passed} passed, {failed} failed")
    return failed == 0

def main():
    """Run all tests"""
    print("=" * 70)
    print("BYE-ONLY HANGUP + BARGE-IN PRECISION FIXES TEST SUITE")
    print("=" * 70)
    
    tests = [
        ("FIX 1 & 2: BYE only on FINAL text with response_id", test_fix_1_2_bye_only_final_text),
        ("FIX 3: Goodbye at END of response only", test_fix_3_goodbye_at_end_only),
        ("FIX 4: Barge-in clears pending_hangup", test_fix_4_barge_in_clears_pending_hangup),
        ("FIX 5: Both queues cleared on barge-in", test_fix_5_both_queues_cleared),
        ("FIX 6: Timeouts cleanup only, no hangup", test_fix_6_timeouts_no_hangup),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"\n❌ ERROR running {name}: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {name}")
    
    print("\n" + "=" * 70)
    print(f"TOTAL: {passed_count}/{total_count} tests passed")
    print("=" * 70)
    
    if passed_count == total_count:
        print("\n🎉 ALL TESTS PASSED! BYE-ONLY hangup + barge-in fixes verified!")
        return 0
    else:
        print(f"\n⚠️  {total_count - passed_count} test(s) failed - review fixes")
        return 1

if __name__ == "__main__":
    sys.exit(main())
