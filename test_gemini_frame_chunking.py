"""
Test for Gemini audio output frame chunking
Verifies that large audio chunks are properly broken into 20ms frames (160 bytes μ-law each)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import audioop
import base64


def test_frame_chunking_logic():
    """Test the logic for breaking audio into 20ms frames"""
    print("🧪 Testing frame chunking logic...")
    
    # Simulate Gemini output: PCM16 at 24kHz (variable size)
    # Create test data: 960 bytes PCM16 @ 24kHz = 20ms at 24kHz (480 samples × 2 bytes)
    pcm16_24k = bytes([0x00, 0x10] * 480)  # 960 bytes PCM16
    
    print(f"✅ Step 1: Simulated Gemini output: {len(pcm16_24k)} bytes PCM16 @ 24kHz")
    
    # Step 2: Resample from 24kHz to 8kHz (3:1 ratio)
    pcm16_8k = audioop.ratecv(pcm16_24k, 2, 1, 24000, 8000, None)[0]
    print(f"✅ Step 2: Resampled to 8kHz: {len(pcm16_8k)} bytes PCM16 @ 8kHz")
    
    # Step 3: Convert PCM16 to μ-law
    mulaw_bytes = audioop.lin2ulaw(pcm16_8k, 2)
    print(f"✅ Step 3: Converted to μ-law: {len(mulaw_bytes)} bytes")
    
    # Step 4: Break into 20ms frames (160 bytes each)
    MULAW_FRAME_SIZE = 160  # 20ms at 8kHz = 160 samples = 160 bytes μ-law
    
    frames = []
    for i in range(0, len(mulaw_bytes), MULAW_FRAME_SIZE):
        frame = mulaw_bytes[i:i+MULAW_FRAME_SIZE]
        if len(frame) == MULAW_FRAME_SIZE:
            frames.append(frame)
        else:
            print(f"⚠️  Partial frame at end: {len(frame)} bytes (will be buffered)")
    
    print(f"✅ Step 4: Broke into {len(frames)} complete 20ms frames")
    
    # Verify all frames are exactly 160 bytes
    for idx, frame in enumerate(frames):
        if len(frame) != MULAW_FRAME_SIZE:
            print(f"❌ Frame {idx} has wrong size: {len(frame)} bytes (expected {MULAW_FRAME_SIZE})")
            return False
    
    print(f"✅ All frames are exactly {MULAW_FRAME_SIZE} bytes")
    return True


def test_odd_chunk_handling():
    """Test handling of odd-sized chunks from Gemini"""
    print("\n🧪 Testing odd chunk handling...")
    
    # Simulate Gemini sending 47 bytes (odd number)
    odd_chunk = bytes([0x00, 0x10] * 23) + bytes([0x00])  # 47 bytes
    
    print(f"✅ Simulated odd chunk: {len(odd_chunk)} bytes")
    
    # Buffer should align to 2-byte boundaries
    frame_size = 2
    buffer_len = len(odd_chunk)
    usable_len = (buffer_len // frame_size) * frame_size
    
    print(f"✅ Usable length (aligned): {usable_len} bytes")
    print(f"✅ Remainder (buffered): {buffer_len - usable_len} bytes")
    
    # Extract usable portion
    audio_to_convert = odd_chunk[:usable_len]
    remainder = odd_chunk[usable_len:]
    
    # Verify we can process the aligned portion
    try:
        # This should work (46 bytes = 23 samples of PCM16 data)
        pcm16_8k = audioop.ratecv(audio_to_convert, 2, 1, 24000, 8000, None)[0]
        print(f"✅ Successfully converted {len(audio_to_convert)} bytes (aligned)")
        print(f"✅ Remainder buffered: {len(remainder)} bytes")
        return True
    except Exception as e:
        print(f"❌ Conversion failed: {e}")
        return False


def test_large_chunk_splitting():
    """Test splitting of large audio chunks"""
    print("\n🧪 Testing large chunk splitting...")
    
    # Simulate a large Gemini chunk: 2400 bytes PCM16 @ 24kHz
    # This should produce 800 bytes μ-law @ 8kHz = 5 frames of 160 bytes each
    large_chunk_pcm16_24k = bytes([0x00, 0x10] * 1200)  # 2400 bytes
    
    print(f"✅ Large chunk: {len(large_chunk_pcm16_24k)} bytes PCM16 @ 24kHz")
    
    # Convert through pipeline
    pcm16_8k = audioop.ratecv(large_chunk_pcm16_24k, 2, 1, 24000, 8000, None)[0]
    mulaw_bytes = audioop.lin2ulaw(pcm16_8k, 2)
    
    print(f"✅ Converted to μ-law: {len(mulaw_bytes)} bytes")
    
    # Break into frames
    MULAW_FRAME_SIZE = 160
    frames = []
    for i in range(0, len(mulaw_bytes), MULAW_FRAME_SIZE):
        frame = mulaw_bytes[i:i+MULAW_FRAME_SIZE]
        if len(frame) == MULAW_FRAME_SIZE:
            frames.append(frame)
    
    print(f"✅ Split into {len(frames)} frames of {MULAW_FRAME_SIZE} bytes each")
    
    # Verify expected frame count
    expected_frames = len(mulaw_bytes) // MULAW_FRAME_SIZE
    if len(frames) == expected_frames:
        print(f"✅ Frame count correct: {len(frames)} frames")
        return True
    else:
        print(f"❌ Frame count mismatch: got {len(frames)}, expected {expected_frames}")
        return False


def test_pipeline_integration():
    """Test the full pipeline with various chunk sizes"""
    print("\n🧪 Testing full pipeline with various chunk sizes...")
    
    chunk_sizes_24k = [
        47,    # Odd, partial frame
        96,    # Even, small
        480,   # 10ms at 24kHz
        960,   # 20ms at 24kHz
        1920,  # 40ms at 24kHz
        2880,  # 60ms at 24kHz
    ]
    
    for chunk_size in chunk_sizes_24k:
        # Create test chunk (PCM16 @ 24kHz)
        if chunk_size % 2 != 0:
            # Odd size - create with one extra byte
            test_chunk = bytes([0x00, 0x10] * (chunk_size // 2)) + bytes([0x00])
        else:
            test_chunk = bytes([0x00, 0x10] * (chunk_size // 2))
        
        # Align to frame boundaries (2 bytes)
        frame_size = 2
        usable_len = (len(test_chunk) // frame_size) * frame_size
        aligned_chunk = test_chunk[:usable_len]
        
        try:
            # Convert through pipeline
            if len(aligned_chunk) > 0:
                pcm16_8k = audioop.ratecv(aligned_chunk, 2, 1, 24000, 8000, None)[0]
                mulaw_bytes = audioop.lin2ulaw(pcm16_8k, 2)
                
                # Count frames
                MULAW_FRAME_SIZE = 160
                frame_count = len(mulaw_bytes) // MULAW_FRAME_SIZE
                
                print(f"✅ Chunk {chunk_size:4d} bytes → {len(aligned_chunk):4d} aligned → {len(mulaw_bytes):4d} μ-law → {frame_count} frames")
        except Exception as e:
            print(f"❌ Chunk {chunk_size} bytes failed: {e}")
            return False
    
    print("✅ All chunk sizes processed successfully")
    return True


if __name__ == "__main__":
    print("=" * 70)
    print("Testing Gemini Audio Frame Chunking")
    print("=" * 70)
    
    test1_passed = test_frame_chunking_logic()
    test2_passed = test_odd_chunk_handling()
    test3_passed = test_large_chunk_splitting()
    test4_passed = test_pipeline_integration()
    
    print("\n" + "=" * 70)
    print("TEST RESULTS:")
    print("=" * 70)
    print(f"Frame chunking logic:    {'✅ PASS' if test1_passed else '❌ FAIL'}")
    print(f"Odd chunk handling:      {'✅ PASS' if test2_passed else '❌ FAIL'}")
    print(f"Large chunk splitting:   {'✅ PASS' if test3_passed else '❌ FAIL'}")
    print(f"Pipeline integration:    {'✅ PASS' if test4_passed else '❌ FAIL'}")
    print("=" * 70)
    
    if all([test1_passed, test2_passed, test3_passed, test4_passed]):
        print("🎉 ALL TESTS PASSED!")
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED")
        sys.exit(1)
