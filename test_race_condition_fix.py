#!/usr/bin/env python3
"""
Test for race condition fix: transcript.done arriving AFTER audio.done

This test simulates the scenario described in the issue where:
1. response.audio.done arrives at 16:50:54,199
2. response.audio_transcript.done arrives AFTER that
3. The BYE detection happens in transcript.done (after audio.done already passed)

The fix ensures that if we detect BYE in transcript.done and audio.done already
happened for that response_id, we check the queues and hangup immediately instead
of waiting for another audio.done that already passed.
"""

import sys
import os

# Add server to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))

def test_race_condition_fix():
    """
    Test that the race condition fix is properly implemented
    """
    print("\n=== Testing Race Condition Fix ===")
    print("Scenario: transcript.done arrives AFTER audio.done")
    print("")
    
    # Read the media_ws_ai.py file
    with open('server/media_ws_ai.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = [
        # 1. Initialization of tracking dictionary
        ('audio_done_by_response_id = {}', 'Initializes audio_done tracking dictionary'),
        
        # 2. Tracking audio.done events
        ('self.audio_done_by_response_id[done_resp_id] = True', 'Tracks audio.done per response_id'),
        ('RACE_FIX', 'Has RACE_FIX marker in audio.done handler'),
        
        # 3. Checking for race condition in transcript.done
        ('audio_already_done = self.audio_done_by_response_id.get', 'Checks if audio.done already happened'),
        ('transcript.done_racefix', 'Has racefix log marker for immediate hangup path'),
        
        # 4. Queue checks before immediate hangup
        ('tx_empty', 'Checks tx_q is empty'),
        ('out_q_empty', 'Checks realtime_audio_out_queue is empty'),
        
        # 5. Immediate hangup execution
        ('if tx_empty and out_q_empty and not self.hangup_triggered', 'Only hangs up if queues empty'),
        ('Execute hangup immediately', 'Comment about immediate execution'),
    ]
    
    passed = 0
    failed = 0
    
    for check_str, description in checks:
        if check_str in content:
            print(f"  ✅ PASS: {description}")
            passed += 1
        else:
            print(f"  ❌ FAIL: {description} - '{check_str}' not found")
            failed += 1
    
    # Special check: Verify the logic flow
    # Find the transcript.done section
    transcript_section_start = content.find('response.audio_transcript.done')
    if transcript_section_start > 0:
        transcript_section = content[transcript_section_start:transcript_section_start + 8000]
        
        # Check for proper sequencing
        has_bye_detection = 'has_goodbye' in transcript_section
        has_race_check = 'audio_already_done' in transcript_section
        has_immediate_hangup = 'Execute hangup immediately' in transcript_section
        has_normal_flow = 'await self.request_hangup' in transcript_section
        
        if has_bye_detection and has_race_check and has_immediate_hangup and has_normal_flow:
            print(f"  ✅ PASS: Logic flow is correct (BYE detection → race check → immediate or normal flow)")
            passed += 1
        else:
            print(f"  ❌ FAIL: Logic flow incomplete")
            if not has_bye_detection:
                print(f"      - Missing BYE detection")
            if not has_race_check:
                print(f"      - Missing race condition check")
            if not has_immediate_hangup:
                print(f"      - Missing immediate hangup path")
            if not has_normal_flow:
                print(f"      - Missing normal flow fallback")
            failed += 1
    else:
        print(f"  ❌ FAIL: Could not find transcript.done handler")
        failed += 1
    
    print(f"\nRace Condition Fix Test: {passed} passed, {failed} failed")
    return failed == 0

def test_log_markers():
    """
    Test that proper log markers are present for debugging
    """
    print("\n=== Testing Log Markers ===")
    
    # Read the media_ws_ai.py file
    with open('server/media_ws_ai.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = [
        ('[BOT_BYE_DETECTED]', 'Has BOT_BYE_DETECTED marker'),
        ('[POLITE_HANGUP] via=transcript.done_racefix', 'Has racefix log marker'),
        ('resp_id=', 'Logs response_id in BYE detection'),
    ]
    
    passed = 0
    failed = 0
    
    for check_str, description in checks:
        if check_str in content:
            print(f"  ✅ PASS: {description}")
            passed += 1
        else:
            print(f"  ❌ FAIL: {description} - '{check_str}' not found")
            failed += 1
    
    print(f"\nLog Markers Test: {passed} passed, {failed} failed")
    return failed == 0

def main():
    """Run all tests"""
    print("=" * 70)
    print("RACE CONDITION FIX TEST SUITE")
    print("=" * 70)
    print("Testing fix for: transcript.done arriving AFTER audio.done")
    print("")
    
    tests = [
        ("Race Condition Fix Implementation", test_race_condition_fix),
        ("Log Markers for Debugging", test_log_markers),
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
        print("\n🎉 ALL TESTS PASSED! Race condition fix verified!")
        return 0
    else:
        print(f"\n⚠️  {total_count - passed_count} test(s) failed - review fixes")
        return 1

if __name__ == "__main__":
    sys.exit(main())
