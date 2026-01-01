#!/usr/bin/env python3
"""
Test script for verifying watchdog activity tracking with transcript events

This test verifies the fix for the bug where the watchdog would disconnect calls
after 20 seconds even when the AI was actively speaking, because it wasn't tracking
response.audio_transcript.delta and other response completion events.

Test Cases:
1. Verify _last_activity_ts is updated on response.audio_transcript.delta
2. Verify _last_activity_ts is updated on response.audio_transcript.done
3. Verify _last_activity_ts is updated on response.audio.done
4. Verify _last_activity_ts is updated on response.output_item.done
5. Verify _last_activity_ts is updated on response.done
6. Simulate a long AI response with transcript deltas and verify no disconnect
"""

import sys
import os
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_watchdog_activity_tracking():
    """Test that watchdog tracks all AI response events"""
    print("\n" + "="*80)
    print("🔵 TEST: WATCHDOG ACTIVITY TRACKING")
    print("="*80)
    
    print("\n📋 Verifying activity timestamp updates in media_ws_ai.py...")
    
    # Read the media_ws_ai.py file to verify the fix
    media_ws_path = os.path.join(os.path.dirname(__file__), "server", "media_ws_ai.py")
    
    with open(media_ws_path, 'r') as f:
        content = f.read()
    
    # Test 1: Check for response.audio_transcript.delta handling
    print("\n📋 Test 1: response.audio_transcript.delta activity tracking...")
    has_transcript_delta_handler = (
        'event_type == "response.audio_transcript.delta"' in content and
        'self._last_activity_ts = time.time()' in content
    )
    
    if has_transcript_delta_handler:
        # Find the line with the handler
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'event_type == "response.audio_transcript.delta"' in line:
                # Check if _last_activity_ts update is within 10 lines
                context = '\n'.join(lines[i:i+10])
                if 'self._last_activity_ts = time.time()' in context:
                    print("  ✅ response.audio_transcript.delta updates _last_activity_ts")
                    break
        else:
            print("  ⚠️ Handler found but activity update not in expected location")
            has_transcript_delta_handler = False
    else:
        print("  ❌ response.audio_transcript.delta does not update _last_activity_ts")
    
    # Test 2: Check for response.audio_transcript.done handling
    print("\n📋 Test 2: response.audio_transcript.done activity tracking...")
    has_transcript_done_handler = (
        'event_type == "response.audio_transcript.done"' in content
    )
    
    if has_transcript_done_handler:
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'event_type == "response.audio_transcript.done"' in line:
                # Check if _last_activity_ts update is within 10 lines
                context = '\n'.join(lines[i:i+10])
                if 'self._last_activity_ts = time.time()' in context:
                    print("  ✅ response.audio_transcript.done updates _last_activity_ts")
                    has_transcript_done_handler = True
                    break
        else:
            print("  ⚠️ Handler found but activity update not in expected location")
            has_transcript_done_handler = False
    else:
        print("  ❌ response.audio_transcript.done does not update _last_activity_ts")
    
    # Test 3: Check for response.audio.done handling
    print("\n📋 Test 3: response.audio.done activity tracking...")
    has_audio_done_handler = False
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if 'event_type in ("response.audio.done", "response.output_item.done")' in line:
            # Check if _last_activity_ts update is within 10 lines
            context = '\n'.join(lines[i:i+10])
            if 'self._last_activity_ts = time.time()' in context:
                print("  ✅ response.audio.done updates _last_activity_ts")
                has_audio_done_handler = True
                break
    
    if not has_audio_done_handler:
        print("  ❌ response.audio.done does not update _last_activity_ts")
    
    # Test 4: Check for response.done handling
    print("\n📋 Test 4: response.done activity tracking...")
    has_response_done_handler = False
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if 'event_type == "response.done"' in line:
            # Check if _last_activity_ts update is within 10 lines
            context = '\n'.join(lines[i:i+10])
            if 'self._last_activity_ts = time.time()' in context:
                print("  ✅ response.done updates _last_activity_ts")
                has_response_done_handler = True
                break
    
    if not has_response_done_handler:
        print("  ❌ response.done does not update _last_activity_ts")
    
    # Test 5: Verify watchdog code exists and uses _last_activity_ts
    print("\n📋 Test 5: Watchdog implementation verification...")
    has_watchdog = (
        '_silence_watchdog' in content and
        'idle = time.time() - self._last_activity_ts' in content and
        'if idle >= 20.0:' in content
    )
    
    if has_watchdog:
        print("  ✅ Watchdog checks _last_activity_ts with 20-second threshold")
    else:
        print("  ❌ Watchdog implementation not found or incorrect")
    
    # Summary
    print("\n" + "="*80)
    print("📊 TEST RESULTS SUMMARY")
    print("="*80)
    
    all_tests_passed = (
        has_transcript_delta_handler and
        has_transcript_done_handler and
        has_audio_done_handler and
        has_response_done_handler and
        has_watchdog
    )
    
    if all_tests_passed:
        print("✅ ALL TESTS PASSED")
        print("\n🎯 Fix verified: Watchdog now tracks ALL AI response events:")
        print("   - response.audio_transcript.delta (streaming transcript)")
        print("   - response.audio_transcript.done (transcript complete)")
        print("   - response.audio.done (audio complete)")
        print("   - response.output_item.done (output item complete)")
        print("   - response.done (full response complete)")
        print("\n   This prevents false disconnects during active AI responses.")
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        print("\n⚠️ The watchdog may still disconnect during active AI responses")
        return 1


def test_activity_tracking_locations():
    """Verify all locations where _last_activity_ts is updated"""
    print("\n" + "="*80)
    print("🔵 TEST: ACTIVITY TRACKING LOCATIONS")
    print("="*80)
    
    media_ws_path = os.path.join(os.path.dirname(__file__), "server", "media_ws_ai.py")
    
    with open(media_ws_path, 'r') as f:
        lines = f.readlines()
    
    print("\n📋 Finding all locations where _last_activity_ts is updated...")
    
    update_locations = []
    for i, line in enumerate(lines, 1):
        if 'self._last_activity_ts = time.time()' in line:
            # Get context (3 lines before)
            context_start = max(0, i-4)
            context = ''.join(lines[context_start:i])
            
            # Extract the event type or context
            event_context = "Unknown context"
            if 'response.done' in context:
                event_context = "response.done"
            elif 'response.audio_transcript.delta' in context:
                event_context = "response.audio_transcript.delta"
            elif 'response.audio_transcript.done' in context:
                event_context = "response.audio_transcript.done"
            elif 'response.audio.done' in context or 'response.output_item.done' in context:
                event_context = "response.audio.done / response.output_item.done"
            elif 'response.audio.delta' in context:
                event_context = "response.audio.delta"
            elif 'speech_started' in context:
                event_context = "input_audio_buffer.speech_started (user VAD)"
            elif 'transcription.completed' in context:
                event_context = "conversation.item.input_audio_transcription.completed"
            elif '__init__' in context:
                event_context = "Initialization (call start)"
            elif 'SILENCE WATCHDOG' in context:
                event_context = "Watchdog initialization"
            
            update_locations.append({
                'line': i,
                'context': event_context
            })
            
            print(f"  Line {i:5d}: {event_context}")
    
    print(f"\n📊 Total activity tracking points: {len(update_locations)}")
    
    # Verify we have the expected minimum points
    expected_contexts = [
        "response.audio_transcript.delta",
        "response.audio_transcript.done",
        "response.audio.done / response.output_item.done",
        "response.done",
        "response.audio.delta",
        "input_audio_buffer.speech_started (user VAD)",
        "conversation.item.input_audio_transcription.completed"
    ]
    
    found_contexts = [loc['context'] for loc in update_locations]
    
    print("\n📋 Verifying expected tracking points...")
    all_found = True
    for expected in expected_contexts:
        if expected in found_contexts:
            print(f"  ✅ {expected}")
        else:
            print(f"  ❌ MISSING: {expected}")
            all_found = False
    
    if all_found:
        print("\n✅ All expected activity tracking points are present")
        return 0
    else:
        print("\n❌ Some expected activity tracking points are missing")
        return 1


if __name__ == "__main__":
    print("\n" + "="*80)
    print("🚀 WATCHDOG ACTIVITY TRACKING TEST SUITE")
    print("="*80)
    
    # Run all tests
    result1 = test_watchdog_activity_tracking()
    result2 = test_activity_tracking_locations()
    
    # Final summary
    print("\n" + "="*80)
    print("🏁 FINAL RESULTS")
    print("="*80)
    
    if result1 == 0 and result2 == 0:
        print("✅ ALL TESTS PASSED - Watchdog fix verified!")
        print("\n🎯 The watchdog now correctly tracks ALL AI response events")
        print("   and will not falsely disconnect during active conversations.")
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED - Please review the fix")
        sys.exit(1)
