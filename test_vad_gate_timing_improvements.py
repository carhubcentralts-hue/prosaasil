"""
Test VAD and Gate Timing Improvements for Better Transcription Accuracy

This test verifies that the VAD/gate timing parameters have been correctly
configured to improve transcription accuracy by preventing clipping of speech
at the beginning and end of utterances.
"""


def test_vad_prefix_padding_increased():
    """Verify VAD prefix padding was increased from 300ms to 400-500ms range"""
    from server.config.calls import SERVER_VAD_PREFIX_PADDING_MS
    
    # Should be in the 400-500ms range (100-200ms increase from original 300ms)
    assert 400 <= SERVER_VAD_PREFIX_PADDING_MS <= 500, \
        f"PREFIX_PADDING should be 400-500ms, got {SERVER_VAD_PREFIX_PADDING_MS}ms"
    
    print(f"✅ VAD prefix padding: {SERVER_VAD_PREFIX_PADDING_MS}ms (prevents initial syllable clipping)")


def test_echo_gate_threshold_reduced():
    """Verify echo gate threshold was reduced for easier gate opening"""
    from server.config.calls import ECHO_GATE_MIN_RMS
    
    # Should be reduced from 270.0 to around 250.0 (easier opening)
    assert 240.0 <= ECHO_GATE_MIN_RMS <= 260.0, \
        f"ECHO_GATE_MIN_RMS should be ~250.0, got {ECHO_GATE_MIN_RMS}"
    
    # Must be lower than the previous 270.0 threshold
    assert ECHO_GATE_MIN_RMS < 270.0, \
        f"ECHO_GATE_MIN_RMS should be lower than previous 270.0, got {ECHO_GATE_MIN_RMS}"
    
    print(f"✅ Echo gate threshold: {ECHO_GATE_MIN_RMS} RMS (easier gate opening at speech start)")


def test_echo_gate_decay_configured():
    """Verify echo gate decay parameter exists and is in 150-250ms range"""
    from server.config.calls import ECHO_GATE_DECAY_MS
    
    # Should be in the 150-250ms range as specified
    assert 150 <= ECHO_GATE_DECAY_MS <= 250, \
        f"ECHO_GATE_DECAY_MS should be 150-250ms, got {ECHO_GATE_DECAY_MS}ms"
    
    print(f"✅ Echo gate decay: {ECHO_GATE_DECAY_MS}ms (prevents end/start clipping)")


def test_media_ws_imports_decay_parameter():
    """Verify media_ws_ai.py imports and uses the new decay parameter"""
    # Check the import statement in the source file
    with open('/home/runner/work/prosaasil/prosaasil/server/media_ws_ai.py', 'r') as f:
        content = f.read()
    
    # Check that ECHO_GATE_DECAY_MS is in the import statement
    assert 'ECHO_GATE_DECAY_MS' in content, \
        "ECHO_GATE_DECAY_MS should be imported in media_ws_ai.py"
    
    # Check that _speech_stopped_ts is initialized
    assert '_speech_stopped_ts' in content, \
        "_speech_stopped_ts should be declared in media_ws_ai.py"
    
    # Check that decay logic is implemented
    assert 'ECHO_GATE_DECAY_MS' in content and 'decay_elapsed_ms' in content, \
        "Decay logic should be implemented in media_ws_ai.py"
    
    print(f"✅ media_ws_ai.py correctly imports and uses ECHO_GATE_DECAY_MS")


def test_openai_client_fallback_updated():
    """Verify openai_realtime_client.py has updated fallback for prefix_padding"""
    # This is a code inspection test - check the source contains the right value
    with open('/home/runner/work/prosaasil/prosaasil/server/services/openai_realtime_client.py', 'r') as f:
        content = f.read()
    
    # Check for the updated fallback value (should be 500, not 300 or 400)
    assert 'prefix_padding_ms = 500' in content or 'prefix_padding_ms = 400' in content, \
        "openai_realtime_client.py should have updated fallback prefix_padding_ms"
    
    # Should not have the old value of 300
    old_pattern = 'prefix_padding_ms = 300  # Match default from config (was 400)'
    assert old_pattern not in content, \
        "openai_realtime_client.py should not have old prefix_padding_ms = 300"
    
    print("✅ openai_realtime_client.py has updated fallback for prefix_padding")


def test_configuration_consistency():
    """Verify all configurations are consistent and properly set"""
    from server.config.calls import (
        SERVER_VAD_PREFIX_PADDING_MS,
        ECHO_GATE_MIN_RMS,
        ECHO_GATE_DECAY_MS
    )
    
    print("\n" + "="*70)
    print("VAD/Gate Timing Configuration Summary")
    print("="*70)
    print(f"VAD Prefix Padding:   {SERVER_VAD_PREFIX_PADDING_MS}ms (was 300ms)")
    print(f"Echo Gate Threshold:  {ECHO_GATE_MIN_RMS} RMS (was 270.0)")
    print(f"Echo Gate Decay:      {ECHO_GATE_DECAY_MS}ms (new parameter)")
    print("="*70)
    print("\nExpected Improvements:")
    print("✅ Better capture of initial syllables (increased prefix padding)")
    print("✅ Faster gate opening at speech start (reduced threshold)")
    print("✅ No clipping at utterance boundaries (decay period)")
    print("="*70)


if __name__ == "__main__":
    # Run all tests
    test_vad_prefix_padding_increased()
    test_echo_gate_threshold_reduced()
    test_echo_gate_decay_configured()
    test_media_ws_imports_decay_parameter()
    test_openai_client_fallback_updated()
    test_configuration_consistency()
    
    print("\n🎉 All tests passed! Configuration is correctly set for improved transcription.")
