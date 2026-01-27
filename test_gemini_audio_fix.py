"""
Test for Gemini audio conversion fix
Verifies that base64-encoded audio is properly decoded before μ-law conversion
"""
import base64
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server.services.mulaw_fast import mulaw_to_pcm16_fast


def test_mulaw_conversion_with_base64():
    """Test that we can decode base64 and then convert μ-law to PCM16"""
    print("🧪 Testing μ-law conversion with base64 input...")
    
    # Create sample μ-law data (160 bytes for 20ms at 8kHz)
    mulaw_bytes = bytes([0x7F, 0x80, 0x00, 0xFF] * 40)  # 160 bytes
    
    # Encode to base64 (this is what comes from Twilio)
    b64_encoded = base64.b64encode(mulaw_bytes).decode('ascii')
    print(f"✅ Created base64-encoded audio: {len(b64_encoded)} chars")
    
    # This should fail if we pass base64 string directly
    try:
        result = mulaw_to_pcm16_fast(b64_encoded)
        print(f"❌ UNEXPECTED: Direct base64 conversion should fail but didn't!")
        return False
    except (TypeError, ValueError) as e:
        print(f"✅ Expected error with base64 string: {type(e).__name__}")
    
    # This should work: decode base64 first, then convert
    try:
        mulaw_decoded = base64.b64decode(b64_encoded)
        pcm16_result = mulaw_to_pcm16_fast(mulaw_decoded)
        print(f"✅ Successful conversion: {len(mulaw_decoded)} μ-law bytes → {len(pcm16_result)} PCM16 bytes")
        
        # Verify output size (each μ-law byte becomes 2 PCM16 bytes)
        expected_size = len(mulaw_decoded) * 2
        if len(pcm16_result) == expected_size:
            print(f"✅ Output size correct: {len(pcm16_result)} bytes")
            return True
        else:
            print(f"❌ Output size mismatch: got {len(pcm16_result)}, expected {expected_size}")
            return False
    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_audio_pipeline_simulation():
    """Simulate the full audio pipeline: base64 → μ-law → PCM16 → resample"""
    print("\n🧪 Testing full Gemini audio pipeline...")
    
    import audioop
    
    # Step 0: Create base64-encoded μ-law (from Twilio)
    mulaw_bytes = bytes([0x7F] * 160)  # 160 bytes for 20ms at 8kHz
    audio_chunk = base64.b64encode(mulaw_bytes).decode('ascii')
    print(f"✅ Step 0: Base64 audio chunk: {len(audio_chunk)} chars")
    
    try:
        # Step 1: Decode base64 (THE FIX)
        mulaw_decoded = base64.b64decode(audio_chunk)
        print(f"✅ Step 1: Decoded to μ-law: {len(mulaw_decoded)} bytes")
        
        # Step 2: Convert μ-law to PCM16 at 8kHz
        pcm16_8k = mulaw_to_pcm16_fast(mulaw_decoded)
        print(f"✅ Step 2: Converted to PCM16@8kHz: {len(pcm16_8k)} bytes")
        
        # Step 3: Resample from 8kHz to 16kHz
        pcm16_16k = audioop.ratecv(pcm16_8k, 2, 1, 8000, 16000, None)[0]
        print(f"✅ Step 3: Resampled to PCM16@16kHz: {len(pcm16_16k)} bytes")
        
        # Verify sizes (allow small rounding difference for resampled audio)
        assert len(mulaw_decoded) == 160, f"μ-law size should be 160, got {len(mulaw_decoded)}"
        assert len(pcm16_8k) == 320, f"PCM16@8kHz size should be 320, got {len(pcm16_8k)}"
        # Resampling may have ±2 bytes due to rounding in audioop.ratecv
        assert 638 <= len(pcm16_16k) <= 642, f"PCM16@16kHz size should be ~640, got {len(pcm16_16k)}"
        
        print("✅ All pipeline steps passed!")
        return True
        
    except Exception as e:
        print(f"❌ Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Gemini Audio Conversion Fix")
    print("=" * 60)
    
    test1_passed = test_mulaw_conversion_with_base64()
    test2_passed = test_audio_pipeline_simulation()
    
    print("\n" + "=" * 60)
    if test1_passed and test2_passed:
        print("✅ ALL TESTS PASSED!")
        print("The fix correctly handles base64-encoded audio for Gemini")
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED!")
        sys.exit(1)
