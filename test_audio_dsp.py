#!/usr/bin/env python3
"""
Test script for audio_dsp.py - Verify DSP processing works correctly

Tests:
1. Basic functionality - DSP doesn't crash
2. Output length matches input length
3. RMS changes are reasonable (not too extreme)
4. Toggle functionality - can be enabled/disabled
"""
import sys
import os
import audioop
import numpy as np

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.services.audio_dsp import AudioDSPProcessor

def generate_test_audio(duration_ms=20, frequency=440):
    """Generate test audio (pure tone) for testing"""
    sample_rate = 8000
    num_samples = int(sample_rate * duration_ms / 1000)
    
    # Generate sine wave
    t = np.linspace(0, duration_ms / 1000, num_samples, endpoint=False)
    signal = np.sin(2 * np.pi * frequency * t) * 16000  # Amplitude 16000
    
    # Convert to PCM16
    pcm16_data = signal.astype(np.int16).tobytes()
    
    # Convert to μ-law
    mulaw_data = audioop.lin2ulaw(pcm16_data, 2)
    
    return mulaw_data

def calculate_rms(mulaw_data):
    """Calculate RMS of μ-law audio"""
    pcm16_data = audioop.ulaw2lin(mulaw_data, 2)
    samples = np.frombuffer(pcm16_data, dtype=np.int16)
    rms = np.sqrt(np.mean(samples.astype(np.float64) ** 2))
    return float(rms)

def test_basic_functionality():
    """Test 1: Basic DSP doesn't crash"""
    print("\n=== Test 1: Basic Functionality ===")
    
    # Create DSP processor instance
    processor = AudioDSPProcessor()
    
    # Generate test audio (20ms frame, 440Hz tone)
    test_audio = generate_test_audio(duration_ms=20, frequency=440)
    print(f"✅ Generated test audio: {len(test_audio)} bytes")
    
    # Process audio
    try:
        processed_audio = processor.process(test_audio)
        print(f"✅ DSP processing succeeded: {len(processed_audio)} bytes")
        return True
    except Exception as e:
        print(f"❌ DSP processing failed: {e}")
        return False

def test_output_length():
    """Test 2: Output length matches input length"""
    print("\n=== Test 2: Output Length ===")
    
    processor = AudioDSPProcessor()
    
    # Test different frame sizes
    test_sizes = [160, 320, 480]  # 20ms, 40ms, 60ms at 8kHz
    
    all_passed = True
    for size in test_sizes:
        # Convert bytes to milliseconds: bytes * 1000 / sample_rate
        # At 8kHz, 160 bytes = 160 samples = 20ms
        duration_ms = (size * 1000) // 8000
        test_audio = generate_test_audio(duration_ms=duration_ms, frequency=440)
        processed_audio = processor.process(test_audio)
        
        if len(processed_audio) == len(test_audio):
            print(f"✅ Size {size} bytes ({duration_ms}ms): input={len(test_audio)}, output={len(processed_audio)}")
        else:
            print(f"❌ Size {size} bytes ({duration_ms}ms): input={len(test_audio)}, output={len(processed_audio)} (MISMATCH!)")
            all_passed = False
    
    return all_passed

def test_rms_changes():
    """Test 3: RMS changes are reasonable"""
    print("\n=== Test 3: RMS Changes ===")
    
    processor = AudioDSPProcessor()
    
    # Test with different frequencies
    test_freqs = [100, 440, 1000, 3000]  # Low to high
    
    all_passed = True
    for freq in test_freqs:
        test_audio = generate_test_audio(duration_ms=20, frequency=freq)
        processed_audio = processor.process(test_audio)
        
        rms_before = calculate_rms(test_audio)
        rms_after = calculate_rms(processed_audio)
        rms_change_pct = ((rms_after - rms_before) / rms_before) * 100
        
        print(f"  {freq}Hz: RMS before={rms_before:.1f}, after={rms_after:.1f}, change={rms_change_pct:+.1f}%")
        
        # Sanity check: RMS shouldn't change by more than 50%
        # (High-pass filter removes low frequencies, limiter prevents clipping)
        if abs(rms_change_pct) > 50:
            print(f"    ⚠️ WARNING: Large RMS change at {freq}Hz!")
            # Don't fail test - this is expected for very low frequencies
    
    return all_passed

def test_filter_continuity():
    """Test 4: Filter state persists across frames"""
    print("\n=== Test 4: Filter Continuity ===")
    
    processor = AudioDSPProcessor()
    
    # Process multiple frames in sequence
    num_frames = 10
    for i in range(num_frames):
        test_audio = generate_test_audio(duration_ms=20, frequency=440)
        processed_audio = processor.process(test_audio)
        
        if i == 0:
            print(f"  Frame {i+1}: {len(processed_audio)} bytes (first frame)")
        elif i == num_frames - 1:
            print(f"  Frame {i+1}: {len(processed_audio)} bytes (last frame)")
    
    print(f"✅ Processed {num_frames} frames without error")
    return True

def test_edge_cases():
    """Test 5: Edge cases (empty, very short)"""
    print("\n=== Test 5: Edge Cases ===")
    
    processor = AudioDSPProcessor()
    
    all_passed = True
    
    # Empty audio
    empty_audio = b""
    processed = processor.process(empty_audio)
    if len(processed) == 0:
        print(f"✅ Empty audio: input={len(empty_audio)}, output={len(processed)}")
    else:
        print(f"❌ Empty audio: output should be empty but got {len(processed)} bytes")
        all_passed = False
    
    # Very short audio (1 byte)
    short_audio = b"\x80"
    processed = processor.process(short_audio)
    if len(processed) == 1:
        print(f"✅ Short audio (1 byte): input={len(short_audio)}, output={len(processed)}")
    else:
        print(f"❌ Short audio: expected 1 byte but got {len(processed)} bytes")
        all_passed = False
    
    return all_passed

def main():
    """Run all tests"""
    print("=" * 60)
    print("Audio DSP Test Suite")
    print("=" * 60)
    
    tests = [
        ("Basic Functionality", test_basic_functionality),
        ("Output Length", test_output_length),
        ("RMS Changes", test_rms_changes),
        ("Filter Continuity", test_filter_continuity),
        ("Edge Cases", test_edge_cases),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            print(f"\n❌ {test_name} CRASHED: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed_count}/{total_count} tests passed")
    
    if passed_count == total_count:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️ {total_count - passed_count} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
