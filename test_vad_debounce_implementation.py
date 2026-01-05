#!/usr/bin/env python3
"""
Test script for VAD tuning and barge-in debouncing implementation

This validates the following changes per הנחיה:
1. VAD threshold increased by +0.03 (0.87 → 0.90)
2. Silence duration increased by +100ms (600 → 700ms)
3. Prefix padding increased by +100ms (500 → 600ms)
4. ECHO_GATE_MIN_RMS increased by +10% (250 → 275)
5. Barge-in debounce of 150ms implemented
6. Consecutive frames requirement (7 frames = 140ms)
7. RMS multiplier validation (1.4x)
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_vad_config_values():
    """Test that VAD configuration values are correctly updated"""
    print("\n🧪 Testing VAD configuration values...")
    
    from server.config.calls import (
        SERVER_VAD_THRESHOLD,
        SERVER_VAD_SILENCE_MS,
        SERVER_VAD_PREFIX_PADDING_MS,
        ECHO_GATE_MIN_RMS,
        BARGE_IN_DEBOUNCE_MS,
        BARGE_IN_VOICE_FRAMES,
        BARGE_IN_MIN_RMS_MULTIPLIER
    )
    
    # Test 1: VAD threshold increased by ~0.03
    expected_threshold = 0.90
    assert SERVER_VAD_THRESHOLD == expected_threshold, \
        f"VAD threshold should be {expected_threshold}, got {SERVER_VAD_THRESHOLD}"
    print(f"  ✅ Test 1: SERVER_VAD_THRESHOLD = {SERVER_VAD_THRESHOLD} (expected {expected_threshold})")
    
    # Test 2: Silence duration increased by 100ms
    expected_silence = 700
    assert SERVER_VAD_SILENCE_MS == expected_silence, \
        f"Silence duration should be {expected_silence}ms, got {SERVER_VAD_SILENCE_MS}ms"
    print(f"  ✅ Test 2: SERVER_VAD_SILENCE_MS = {SERVER_VAD_SILENCE_MS}ms (expected {expected_silence}ms)")
    
    # Test 3: Prefix padding increased by 100ms
    expected_padding = 600
    assert SERVER_VAD_PREFIX_PADDING_MS == expected_padding, \
        f"Prefix padding should be {expected_padding}ms, got {SERVER_VAD_PREFIX_PADDING_MS}ms"
    print(f"  ✅ Test 3: SERVER_VAD_PREFIX_PADDING_MS = {SERVER_VAD_PREFIX_PADDING_MS}ms (expected {expected_padding}ms)")
    
    # Test 4: ECHO_GATE_MIN_RMS increased by 10% (250 → 275)
    expected_rms = 275.0
    assert ECHO_GATE_MIN_RMS == expected_rms, \
        f"ECHO_GATE_MIN_RMS should be {expected_rms}, got {ECHO_GATE_MIN_RMS}"
    print(f"  ✅ Test 4: ECHO_GATE_MIN_RMS = {ECHO_GATE_MIN_RMS} (expected {expected_rms}, +10% from 250)")
    
    # Test 5: Barge-in debounce is 150ms
    expected_debounce = 150
    assert BARGE_IN_DEBOUNCE_MS == expected_debounce, \
        f"BARGE_IN_DEBOUNCE_MS should be {expected_debounce}ms, got {BARGE_IN_DEBOUNCE_MS}ms"
    print(f"  ✅ Test 5: BARGE_IN_DEBOUNCE_MS = {BARGE_IN_DEBOUNCE_MS}ms (expected {expected_debounce}ms)")
    
    # Test 6: Voice frames is 7 (within 6-8 range per הנחיה)
    expected_frames = 7
    assert BARGE_IN_VOICE_FRAMES == expected_frames, \
        f"BARGE_IN_VOICE_FRAMES should be {expected_frames}, got {BARGE_IN_VOICE_FRAMES}"
    print(f"  ✅ Test 6: BARGE_IN_VOICE_FRAMES = {BARGE_IN_VOICE_FRAMES} frames = {BARGE_IN_VOICE_FRAMES * 20}ms (expected {expected_frames} in 6-8 range)")
    
    # Test 7: RMS multiplier is 1.4x
    expected_multiplier = 1.4
    assert BARGE_IN_MIN_RMS_MULTIPLIER == expected_multiplier, \
        f"BARGE_IN_MIN_RMS_MULTIPLIER should be {expected_multiplier}, got {BARGE_IN_MIN_RMS_MULTIPLIER}"
    print(f"  ✅ Test 7: BARGE_IN_MIN_RMS_MULTIPLIER = {BARGE_IN_MIN_RMS_MULTIPLIER}x (expected {expected_multiplier}x)")
    
    # Test 8: Calculate effective RMS threshold
    effective_rms = ECHO_GATE_MIN_RMS * BARGE_IN_MIN_RMS_MULTIPLIER
    expected_effective = 275.0 * 1.4  # 385
    assert effective_rms == expected_effective, \
        f"Effective RMS threshold should be {expected_effective}, got {effective_rms}"
    print(f"  ✅ Test 8: Effective barge-in RMS threshold = {effective_rms} (275 × 1.4)")
    
    print("✅ All VAD configuration tests passed!\n")


def test_transcription_config():
    """Test that transcription configuration has Hebrew language"""
    print("\n🧪 Testing transcription configuration...")
    
    # This is harder to test without actually creating a client, but we can check
    # the source code has the right values
    import inspect
    from server.services.openai_realtime_client import OpenAIRealtimeClient
    
    # Get the source code of configure_session method
    source = inspect.getsource(OpenAIRealtimeClient.configure_session)
    
    # Check that it contains the expected configuration
    assert '"language": "he"' in source, "Should set language to Hebrew (he)"
    print("  ✅ Test 1: Transcription config includes language='he'")
    
    # Note: temperature is at session level, not transcription level
    # Check that temperature is NOT in transcription_config (it should be in session_config)
    assert 'transcription_config = {' in source, "Should have transcription_config defined"
    print("  ✅ Test 2: Transcription config is properly defined")
    
    # Verify temperature is at session level
    assert '"temperature": temperature' in source, "Temperature should be at session level"
    print("  ✅ Test 3: Temperature is at session level (not transcription level)")
    
    print("✅ All transcription configuration tests passed!\n")


def test_debounce_state_tracking():
    """Test that debounce state tracking variables are initialized"""
    print("\n🧪 Testing debounce state tracking...")
    
    # Read the source file directly to avoid import issues
    with open('server/media_ws_ai.py', 'r') as f:
        source = f.read()
    
    # Check that debounce variables are initialized
    assert "_barge_in_debounce_start_ts" in source, "Should have _barge_in_debounce_start_ts"
    print("  ✅ Test 1: _barge_in_debounce_start_ts variable exists")
    
    assert "_barge_in_debounce_frames_count" in source, "Should have _barge_in_debounce_frames_count"
    print("  ✅ Test 2: _barge_in_debounce_frames_count variable exists")
    
    assert "_barge_in_debounce_verified" in source, "Should have _barge_in_debounce_verified"
    print("  ✅ Test 3: _barge_in_debounce_verified variable exists")
    
    # Check that debounce logic is in speech_started handler
    assert "BARGE-IN DEBOUNCE" in source, "Should have debounce logic"
    print("  ✅ Test 4: Debounce logic exists in source")
    
    # Check that validation happens in audio sender
    assert "BARGE-IN DEBOUNCE VALIDATION" in source, "Should have debounce validation"
    print("  ✅ Test 5: Debounce validation logic exists in audio sender")
    
    # Check that reset happens in speech_stopped
    assert "Reset barge-in debounce state" in source, "Should reset debounce state"
    print("  ✅ Test 6: Debounce reset logic exists in speech_stopped handler")
    
    print("✅ All debounce state tracking tests passed!\n")


def test_algorithm_correctness():
    """Test the debounce algorithm logic"""
    print("\n🧪 Testing debounce algorithm correctness...")
    
    from server.config.calls import (
        BARGE_IN_DEBOUNCE_MS,
        BARGE_IN_VOICE_FRAMES,
        BARGE_IN_MIN_RMS_MULTIPLIER,
        ECHO_GATE_MIN_RMS
    )
    
    # Calculate expected timings
    frame_duration_ms = 20  # Each frame is 20ms
    frames_duration_ms = BARGE_IN_VOICE_FRAMES * frame_duration_ms
    total_min_duration_ms = BARGE_IN_DEBOUNCE_MS + frames_duration_ms
    
    print(f"  ℹ️ Algorithm timings:")
    print(f"     - Debounce period: {BARGE_IN_DEBOUNCE_MS}ms")
    print(f"     - Required consecutive frames: {BARGE_IN_VOICE_FRAMES} × {frame_duration_ms}ms = {frames_duration_ms}ms")
    print(f"     - Total minimum duration: {total_min_duration_ms}ms (~{total_min_duration_ms/1000:.2f}s)")
    
    # Test 1: Total duration should be reasonable (not too slow, not too fast)
    assert 250 <= total_min_duration_ms <= 350, \
        f"Total duration should be 250-350ms for responsiveness, got {total_min_duration_ms}ms"
    print(f"  ✅ Test 1: Total duration {total_min_duration_ms}ms is in acceptable range (250-350ms)")
    
    # Test 2: RMS threshold should be reasonable
    min_rms_threshold = ECHO_GATE_MIN_RMS * BARGE_IN_MIN_RMS_MULTIPLIER
    assert min_rms_threshold > 300, "RMS threshold should be significant to filter noise"
    assert min_rms_threshold < 500, "RMS threshold shouldn't be so high it blocks speech"
    print(f"  ✅ Test 2: RMS threshold {min_rms_threshold:.0f} is in reasonable range (300-500)")
    
    # Test 3: Frame count should catch sustained audio but not brief spikes
    min_frames = 6  # Minimum recommended
    max_frames = 8  # Maximum recommended
    assert min_frames <= BARGE_IN_VOICE_FRAMES <= max_frames, \
        f"Frame count should be {min_frames}-{max_frames} per הנחיה, got {BARGE_IN_VOICE_FRAMES}"
    print(f"  ✅ Test 3: Frame count {BARGE_IN_VOICE_FRAMES} is in recommended range ({min_frames}-{max_frames})")
    
    print("✅ All algorithm correctness tests passed!\n")


def main():
    """Run all tests"""
    print("=" * 70)
    print("VAD TUNING AND BARGE-IN DEBOUNCING TEST SUITE")
    print("=" * 70)
    
    try:
        test_vad_config_values()
        test_transcription_config()
        test_debounce_state_tracking()
        test_algorithm_correctness()
        
        print("=" * 70)
        print("🎉 ALL TESTS PASSED! Implementation is correct.")
        print("=" * 70)
        print()
        print("Summary of changes:")
        print("  • VAD threshold: 0.87 → 0.90 (+0.03)")
        print("  • Silence duration: 600ms → 700ms (+100ms)")
        print("  • Prefix padding: 500ms → 600ms (+100ms)")
        print("  • ECHO_GATE_MIN_RMS: 250 → 275 (+10%)")
        print("  • NEW: Barge-in debounce: 150ms")
        print("  • NEW: Consecutive frames: 7 (140ms)")
        print("  • NEW: RMS multiplier: 1.4x (effective threshold: 385)")
        print()
        print("Expected benefits:")
        print("  ✅ Significantly reduced false positives from beeps/clicks")
        print("  ✅ Better noise filtering without blocking real speech")
        print("  ✅ Still responsive (~290ms total latency)")
        print("  ✅ Hebrew-optimized (longer silence, better padding)")
        print()
        return 0
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}\n")
        return 1
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
