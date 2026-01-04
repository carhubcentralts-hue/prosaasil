"""
Test WAV header creation for TTS preview fix
Tests the _create_wav_header function without requiring Flask

Note: This duplicates the _create_wav_header function from routes_ai_system.py
for isolated unit testing without Flask dependencies. In production, the
implementation in routes_ai_system.py is used.
"""
import struct


def _create_wav_header(pcm_data: bytes, sample_rate: int = 24000, bits_per_sample: int = 16, num_channels: int = 1) -> bytes:
    """
    Create a WAV file header for PCM16 audio data.
    (Duplicated from routes_ai_system.py for isolated testing)
    """
    # Calculate sizes
    data_size = len(pcm_data)
    byte_rate = sample_rate * num_channels * bits_per_sample // 8
    block_align = num_channels * bits_per_sample // 8
    
    # Create WAV header (44 bytes)
    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF',                      # ChunkID
        36 + data_size,               # ChunkSize
        b'WAVE',                      # Format
        b'fmt ',                      # Subchunk1ID
        16,                           # Subchunk1Size (PCM)
        1,                            # AudioFormat (1 = PCM)
        num_channels,                 # NumChannels
        sample_rate,                  # SampleRate
        byte_rate,                    # ByteRate
        block_align,                  # BlockAlign
        bits_per_sample,              # BitsPerSample
        b'data',                      # Subchunk2ID
        data_size                     # Subchunk2Size
    )
    
    return header + pcm_data


def test_wav_header_structure():
    """Test that WAV header has correct structure"""
    print("\n🔧 Testing WAV Header Creation")
    print("=" * 60)
    
    # Create dummy PCM data (100 bytes)
    pcm_data = b'\x00\x01' * 50  # 100 bytes of dummy PCM16 data
    
    print("\n1️⃣ Test: WAV header creation")
    wav_data = _create_wav_header(pcm_data)
    
    # WAV should be header (44 bytes) + data (100 bytes) = 144 bytes
    expected_size = 44 + len(pcm_data)
    if len(wav_data) == expected_size:
        print(f"   ✅ WAV size correct: {len(wav_data)} bytes (44 header + {len(pcm_data)} data)")
    else:
        print(f"   ❌ Expected {expected_size} bytes, got {len(wav_data)}")
        return False
    
    print("\n2️⃣ Test: WAV header magic bytes")
    # Check RIFF magic bytes
    if wav_data[0:4] == b'RIFF':
        print("   ✅ RIFF magic bytes present")
    else:
        print(f"   ❌ Expected b'RIFF', got {wav_data[0:4]}")
        return False
    
    # Check WAVE format
    if wav_data[8:12] == b'WAVE':
        print("   ✅ WAVE format identifier present")
    else:
        print(f"   ❌ Expected b'WAVE', got {wav_data[8:12]}")
        return False
    
    print("\n3️⃣ Test: WAV format chunk")
    # Check fmt chunk
    if wav_data[12:16] == b'fmt ':
        print("   ✅ fmt chunk identifier present")
    else:
        print(f"   ❌ Expected b'fmt ', got {wav_data[12:16]}")
        return False
    
    # Parse audio format (should be 1 for PCM)
    audio_format = struct.unpack('<H', wav_data[20:22])[0]
    if audio_format == 1:
        print("   ✅ Audio format is PCM (1)")
    else:
        print(f"   ❌ Expected audio format 1, got {audio_format}")
        return False
    
    print("\n4️⃣ Test: Audio parameters")
    # Parse sample rate
    sample_rate = struct.unpack('<I', wav_data[24:28])[0]
    if sample_rate == 24000:
        print(f"   ✅ Sample rate: {sample_rate} Hz")
    else:
        print(f"   ❌ Expected 24000 Hz, got {sample_rate}")
        return False
    
    # Parse bits per sample
    bits_per_sample = struct.unpack('<H', wav_data[34:36])[0]
    if bits_per_sample == 16:
        print(f"   ✅ Bits per sample: {bits_per_sample}")
    else:
        print(f"   ❌ Expected 16, got {bits_per_sample}")
        return False
    
    print("\n5️⃣ Test: Data chunk")
    # Check data chunk identifier
    if wav_data[36:40] == b'data':
        print("   ✅ data chunk identifier present")
    else:
        print(f"   ❌ Expected b'data', got {wav_data[36:40]}")
        return False
    
    # Parse data size
    data_size = struct.unpack('<I', wav_data[40:44])[0]
    if data_size == len(pcm_data):
        print(f"   ✅ Data size: {data_size} bytes")
    else:
        print(f"   ❌ Expected {len(pcm_data)}, got {data_size}")
        return False
    
    print("\n6️⃣ Test: PCM data is appended")
    # Check that PCM data is correctly appended after header
    if wav_data[44:] == pcm_data:
        print("   ✅ PCM data correctly appended after header")
    else:
        print("   ❌ PCM data mismatch")
        return False
    
    print("\n" + "=" * 60)
    print("✅ All WAV header tests passed!")
    return True


def test_wav_with_different_sizes():
    """Test WAV header with different data sizes"""
    print("\n🔧 Testing WAV Header with Different Data Sizes")
    print("=" * 60)
    
    test_sizes = [100, 1000, 10000, 100000]
    
    for size in test_sizes:
        pcm_data = b'\x00' * size
        wav_data = _create_wav_header(pcm_data)
        
        expected_size = 44 + size
        if len(wav_data) == expected_size:
            print(f"   ✅ Size {size}: WAV header + data = {len(wav_data)} bytes")
        else:
            print(f"   ❌ Size {size}: Expected {expected_size}, got {len(wav_data)}")
            return False
    
    print("\n" + "=" * 60)
    print("✅ All size tests passed!")
    return True


if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("WAV HEADER CREATION - TEST SUITE")
    print("Tests the fix for TTS Preview audio format issue")
    print("=" * 60)
    
    success = True
    
    tests = [
        test_wav_header_structure,
        test_wav_with_different_sizes,
    ]
    
    for test_func in tests:
        try:
            if not test_func():
                success = False
        except Exception as e:
            print(f"\n❌ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            success = False
    
    print("\n" + "=" * 60)
    if success:
        print("✅ ALL TESTS PASSED!")
        print("\n📋 Summary:")
        print("   ✓ WAV header structure is correct")
        print("   ✓ Audio format is PCM (1)")
        print("   ✓ Sample rate is 24000 Hz")
        print("   ✓ Bits per sample is 16")
        print("   ✓ PCM data is correctly appended")
        print("\n💡 This fix allows Realtime API preview to work by:")
        print("   1. Using pcm16 format (supported by Realtime API)")
        print("   2. Wrapping pcm16 with WAV header for browser playback")
        print("   3. Returning audio/wav content-type for Realtime voices")
    else:
        print("❌ SOME TESTS FAILED")
    print("=" * 60)
    
    import sys
    sys.exit(0 if success else 1)
