"""
Test Gemini Input Audio Frame Alignment Fix

This test validates the audio conversion pipeline from Twilio to Gemini:
1. μ-law 8kHz (160 bytes) → PCM16 8kHz (320 bytes)
2. PCM16 8kHz → PCM16 16kHz (640 bytes via resampling)
3. Buffering to ensure exact 640-byte chunks
4. No 638-byte chunks (which cause "not a whole number of frames" errors)

This validates the fix implemented in media_ws_ai.py for sending audio to Gemini.
"""
import unittest
import audioop
import base64


class GeminiInputAudioConverter:
    """Isolated implementation of Twilio→Gemini audio conversion with buffering"""
    
    def __init__(self):
        self._gemini_input_buffer = bytearray()
        self._gemini_input_chunk_size = 640  # 20ms at 16kHz PCM16
        self._gemini_audio_bytes_sent = 0
        self._chunks_sent = []  # Track sent chunks for validation
    
    def process_twilio_frame(self, audio_chunk_base64):
        """
        Process Twilio audio frame and convert to Gemini format
        
        Args:
            audio_chunk_base64: Base64-encoded μ-law audio from Twilio (160 bytes)
        
        Returns:
            List of PCM16 16kHz chunks ready to send to Gemini (each 640 bytes)
        """
        # Step 0: Decode base64 to raw μ-law bytes
        mulaw_bytes = base64.b64decode(audio_chunk_base64)
        
        # Step 1: Convert μ-law 8kHz (160 bytes) to PCM16 8kHz (320 bytes)
        pcm16_8k = audioop.ulaw2lin(mulaw_bytes, 2)
        
        # Step 2: Resample from 8kHz to 16kHz (320 → 640 bytes)
        pcm16_16k, state = audioop.ratecv(pcm16_8k, 2, 1, 8000, 16000, None)
        
        # Step 3: Add to buffer
        self._gemini_input_buffer.extend(pcm16_16k)
        
        # Step 4: Extract complete chunks of exactly 640 bytes
        chunks_to_send = []
        buffer_len = len(self._gemini_input_buffer)
        chunk_size = self._gemini_input_chunk_size
        
        while buffer_len >= chunk_size:
            # Extract exactly chunk_size bytes
            chunk = bytes(self._gemini_input_buffer[:chunk_size])
            
            # Validate chunk size (MUST be multiple of 2 for PCM16)
            if len(chunk) % 2 != 0:
                raise ValueError(f"Invalid chunk size {len(chunk)} (not multiple of 2)")
            
            # Remove from buffer
            self._gemini_input_buffer = self._gemini_input_buffer[chunk_size:]
            buffer_len = len(self._gemini_input_buffer)
            
            # Track for validation
            self._gemini_audio_bytes_sent += len(chunk)
            self._chunks_sent.append(len(chunk))
            chunks_to_send.append(chunk)
        
        return chunks_to_send
    
    def get_buffer_size(self):
        """Get current buffer size"""
        return len(self._gemini_input_buffer)
    
    def get_total_bytes_sent(self):
        """Get total bytes sent"""
        return self._gemini_audio_bytes_sent
    
    def get_chunk_sizes(self):
        """Get list of chunk sizes sent"""
        return self._chunks_sent


class TestGeminiInputFrameAlignment(unittest.TestCase):
    """Test input frame alignment for Twilio → Gemini audio conversion"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.converter = GeminiInputAudioConverter()
    
    def test_initialization(self):
        """Test that converter is properly initialized"""
        self.assertEqual(self.converter.get_buffer_size(), 0)
        self.assertEqual(self.converter.get_total_bytes_sent(), 0)
        self.assertEqual(len(self.converter.get_chunk_sizes()), 0)
    
    def test_single_twilio_frame_produces_640_bytes(self):
        """Test that a single Twilio frame is buffered until we have 640 bytes"""
        # Create a valid Twilio frame: 160 bytes of μ-law audio
        mulaw_frame = b'\xFF' * 160  # Silence in μ-law
        audio_b64 = base64.b64encode(mulaw_frame).decode('utf-8')
        
        # Process first frame - produces 638 bytes, not enough for a 640-byte chunk
        chunks = self.converter.process_twilio_frame(audio_b64)
        
        # Should NOT produce a chunk yet (638 < 640)
        self.assertEqual(len(chunks), 0)
        
        # Buffer should have 638 bytes
        self.assertEqual(self.converter.get_buffer_size(), 638)
        
        # Process second frame - adds another 638 bytes (total 1276)
        chunks2 = self.converter.process_twilio_frame(audio_b64)
        
        # Should produce exactly one 640-byte chunk
        self.assertEqual(len(chunks2), 1)
        self.assertEqual(len(chunks2[0]), 640)
        
        # Buffer should have 636 bytes remaining (1276 - 640)
        self.assertEqual(self.converter.get_buffer_size(), 636)
        
        # Total bytes sent should be 640
        self.assertEqual(self.converter.get_total_bytes_sent(), 640)
    
    def test_multiple_frames_produce_640_byte_chunks(self):
        """Test that multiple Twilio frames produce 640-byte chunks through buffering"""
        # Create 5 Twilio frames (each produces 638 bytes)
        mulaw_frame = b'\xFF' * 160
        audio_b64 = base64.b64encode(mulaw_frame).decode('utf-8')
        
        total_chunks = 0
        for i in range(5):
            chunks = self.converter.process_twilio_frame(audio_b64)
            total_chunks += len(chunks)
        
        # 5 frames × 638 bytes = 3190 bytes total
        # 3190 ÷ 640 = 4 complete chunks (2560 bytes)
        # 3190 - 2560 = 630 bytes remaining in buffer
        self.assertEqual(total_chunks, 4)
        
        # All chunks should be 640 bytes
        chunk_sizes = self.converter.get_chunk_sizes()
        self.assertEqual(len(chunk_sizes), 4)
        for size in chunk_sizes:
            self.assertEqual(size, 640)
        
        # Total bytes sent should be 2560 (4 * 640)
        self.assertEqual(self.converter.get_total_bytes_sent(), 2560)
        
        # Buffer should have 630 bytes (3190 - 2560)
        self.assertEqual(self.converter.get_buffer_size(), 630)
    
    def test_no_638_byte_chunks(self):
        """Test that we NEVER produce 638-byte chunks (the bug we're fixing)"""
        # Process many frames to ensure we don't hit edge cases
        mulaw_frame = b'\xFF' * 160
        audio_b64 = base64.b64encode(mulaw_frame).decode('utf-8')
        
        for i in range(100):
            self.converter.process_twilio_frame(audio_b64)
        
        # Check that NO chunk was 638 bytes (the problematic size)
        chunk_sizes = self.converter.get_chunk_sizes()
        self.assertNotIn(638, chunk_sizes)
        
        # All chunks should be exactly 640 bytes
        for size in chunk_sizes:
            self.assertEqual(size, 640, f"Expected 640 bytes, got {size}")
    
    def test_all_chunks_are_multiple_of_2(self):
        """Test that all chunks are multiples of 2 (PCM16 requirement)"""
        mulaw_frame = b'\xFF' * 160
        audio_b64 = base64.b64encode(mulaw_frame).decode('utf-8')
        
        for i in range(50):
            chunks = self.converter.process_twilio_frame(audio_b64)
            for chunk in chunks:
                self.assertEqual(len(chunk) % 2, 0, f"Chunk size {len(chunk)} is not multiple of 2")
    
    def test_buffer_alignment(self):
        """Test that buffer correctly handles partial chunks from resampling"""
        # Each Twilio frame produces 638 bytes (not 640!)
        # This is why we need buffering
        mulaw_frame = b'\xFF' * 160
        audio_b64 = base64.b64encode(mulaw_frame).decode('utf-8')
        
        # First frame: 638 bytes (no chunk sent, buffer = 638)
        chunks1 = self.converter.process_twilio_frame(audio_b64)
        self.assertEqual(len(chunks1), 0)
        self.assertEqual(self.converter.get_buffer_size(), 638)
        
        # Second frame: 638 + 638 = 1276 bytes (1 chunk sent, buffer = 636)
        chunks2 = self.converter.process_twilio_frame(audio_b64)
        self.assertEqual(len(chunks2), 1)
        self.assertEqual(self.converter.get_buffer_size(), 636)
        
        # Third frame: 636 + 638 = 1274 bytes (1 chunk sent, buffer = 634)
        chunks3 = self.converter.process_twilio_frame(audio_b64)
        self.assertEqual(len(chunks3), 1)
        self.assertEqual(self.converter.get_buffer_size(), 634)
    
    def test_chunk_size_consistency(self):
        """Test that all chunks are consistently 640 bytes"""
        mulaw_frame = b'\xFF' * 160
        audio_b64 = base64.b64encode(mulaw_frame).decode('utf-8')
        
        # Process multiple frames
        for i in range(10):
            self.converter.process_twilio_frame(audio_b64)
        
        # All chunks should be exactly 640 bytes
        chunk_sizes = self.converter.get_chunk_sizes()
        self.assertTrue(all(size == 640 for size in chunk_sizes))
    
    def test_total_bytes_is_multiple_of_640(self):
        """Test that total bytes sent is always a multiple of 640"""
        mulaw_frame = b'\xFF' * 160
        audio_b64 = base64.b64encode(mulaw_frame).decode('utf-8')
        
        # Process various numbers of frames
        for num_frames in [1, 5, 10, 20, 50]:
            converter = GeminiInputAudioConverter()
            
            for i in range(num_frames):
                converter.process_twilio_frame(audio_b64)
            
            total_bytes = converter.get_total_bytes_sent()
            self.assertEqual(total_bytes % 640, 0, 
                           f"Total bytes {total_bytes} is not multiple of 640")
    
    def test_conversion_produces_valid_pcm16(self):
        """Test that conversion produces valid PCM16 data"""
        # Create a non-silence frame for better validation
        mulaw_frame = bytes([i % 256 for i in range(160)])
        audio_b64 = base64.b64encode(mulaw_frame).decode('utf-8')
        
        # First frame won't produce a chunk (638 < 640)
        chunks1 = self.converter.process_twilio_frame(audio_b64)
        self.assertEqual(len(chunks1), 0)
        
        # Second frame will produce a chunk
        chunks2 = self.converter.process_twilio_frame(audio_b64)
        self.assertEqual(len(chunks2), 1)
        chunk = chunks2[0]
        
        # Chunk should be 640 bytes (320 samples * 2 bytes/sample)
        self.assertEqual(len(chunk), 640)
        
        # Should be valid PCM16 (can convert to array of int16)
        import struct
        samples = struct.unpack(f'<{len(chunk)//2}h', chunk)
        
        # Should have exactly 320 samples
        self.assertEqual(len(samples), 320)


def run_tests():
    """Run all tests"""
    suite = unittest.TestLoader().loadTestsFromTestCase(TestGeminiInputFrameAlignment)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    import sys
    sys.exit(0 if success else 1)
