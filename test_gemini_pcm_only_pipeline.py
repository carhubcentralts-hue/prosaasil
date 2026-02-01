"""
Test for Gemini PCM-only pipeline implementation
Tests the gemini_inline_to_pcm_bytes() function which implements the PCM-only pipeline principle.
"""
import pytest
import base64
from server.services.gemini_realtime_client import gemini_inline_to_pcm_bytes


class TestGeminiInlineToPcmBytes:
    """Test PCM-only pipeline conversion function"""
    
    def test_str_base64_complete_padding(self):
        """Test converting base64 string with correct padding to PCM bytes"""
        # "Hello World" as base64
        b64_str = "SGVsbG8gV29ybGQ="
        result = gemini_inline_to_pcm_bytes(b64_str)
        
        assert isinstance(result, bytes)
        assert result == b"Hello World"
    
    def test_str_base64_missing_padding(self):
        """Test converting base64 string missing padding to PCM bytes"""
        # "Hello World" without padding
        b64_str = "SGVsbG8gV29ybGQ"
        result = gemini_inline_to_pcm_bytes(b64_str)
        
        assert isinstance(result, bytes)
        assert result == b"Hello World"
    
    def test_bytes_base64_ascii(self):
        """Test converting bytes containing base64 ASCII to PCM bytes"""
        # "Hello World" as base64 bytes
        b64_bytes = b"SGVsbG8gV29ybGQ="
        result = gemini_inline_to_pcm_bytes(b64_bytes)
        
        assert isinstance(result, bytes)
        assert result == b"Hello World"
    
    def test_bytes_base64_ascii_missing_padding(self):
        """Test converting bytes containing base64 ASCII missing padding"""
        # "Hello World" as base64 bytes without padding
        b64_bytes = b"SGVsbG8gV29ybGQ"
        result = gemini_inline_to_pcm_bytes(b64_bytes)
        
        assert isinstance(result, bytes)
        assert result == b"Hello World"
    
    def test_raw_pcm_bytes(self):
        """Test that raw PCM bytes pass through unchanged"""
        # Raw binary data that doesn't look like ASCII
        raw_pcm = b'\x00\x01\x02\x03\xff\xfe\xfd\xfc'
        result = gemini_inline_to_pcm_bytes(raw_pcm)
        
        assert isinstance(result, bytes)
        assert result == raw_pcm
    
    def test_bytearray_base64(self):
        """Test converting bytearray containing base64 to PCM bytes"""
        # "Hello World" as base64 bytearray
        b64_bytearray = bytearray(b"SGVsbG8gV29ybGQ=")
        result = gemini_inline_to_pcm_bytes(b64_bytearray)
        
        assert isinstance(result, bytes)
        assert result == b"Hello World"
    
    def test_memoryview_raw_pcm(self):
        """Test converting memoryview containing raw PCM to PCM bytes"""
        # Raw PCM data as memoryview
        raw_pcm = b'\x00\x01\x02\x03\xff\xfe\xfd\xfc'
        memview = memoryview(raw_pcm)
        result = gemini_inline_to_pcm_bytes(memview)
        
        assert isinstance(result, bytes)
        assert result == raw_pcm
    
    def test_none_input(self):
        """Test that None input returns empty bytes"""
        result = gemini_inline_to_pcm_bytes(None)
        
        assert isinstance(result, bytes)
        assert result == b""
    
    def test_empty_string(self):
        """Test that empty string returns empty bytes"""
        result = gemini_inline_to_pcm_bytes("")
        
        assert isinstance(result, bytes)
        assert result == b""
    
    def test_whitespace_base64(self):
        """Test that whitespace is stripped from base64 string"""
        # "Hello World" with leading/trailing whitespace
        b64_str = "  SGVsbG8gV29ybGQ=  "
        result = gemini_inline_to_pcm_bytes(b64_str)
        
        assert isinstance(result, bytes)
        assert result == b"Hello World"
    
    def test_audio_pcm_16bit(self):
        """Test realistic 16-bit PCM audio data scenario"""
        # Simulate 16-bit PCM audio samples
        pcm_samples = b'\x00\x00\x10\x00\x20\x00\x30\x00\x40\x00'
        
        # Encode to base64 (as Gemini would send it)
        b64_audio = base64.b64encode(pcm_samples).decode('ascii')
        
        # Test with complete padding
        result = gemini_inline_to_pcm_bytes(b64_audio)
        assert isinstance(result, bytes)
        assert result == pcm_samples
        assert len(result) % 2 == 0  # Must be even length for 16-bit
        
        # Test with missing padding
        b64_audio_no_pad = b64_audio.rstrip('=')
        result = gemini_inline_to_pcm_bytes(b64_audio_no_pad)
        assert isinstance(result, bytes)
        assert result == pcm_samples
        assert len(result) % 2 == 0  # Must be even length for 16-bit
    
    def test_fallback_invalid_base64_as_raw(self):
        """Test that invalid base64 ASCII bytes fall back to raw bytes"""
        # Create bytes that look like ASCII but aren't valid base64
        invalid_b64 = b"!!!invalid!!!"
        result = gemini_inline_to_pcm_bytes(invalid_b64)
        
        # Should fallback to treating it as raw bytes
        assert isinstance(result, bytes)
        # The function will try to decode and fallback
        assert len(result) > 0
    
    def test_always_returns_bytes(self):
        """Test that function ALWAYS returns bytes, never str"""
        test_cases = [
            "SGVsbG8gV29ybGQ=",  # str
            b"SGVsbG8gV29ybGQ=",  # bytes
            bytearray(b"SGVsbG8gV29ybGQ="),  # bytearray
            None,  # None
            "",  # empty str
            b"",  # empty bytes
        ]
        
        for test_input in test_cases:
            result = gemini_inline_to_pcm_bytes(test_input)
            assert isinstance(result, bytes), f"Failed for input {test_input!r}: got {type(result)}"
    
    def test_pcm_only_pipeline_contract(self):
        """
        Test the PCM-only pipeline contract:
        1. Input can be str or bytes (base64) or raw PCM
        2. Output is ALWAYS bytes (PCM)
        3. No str/bytes mixing after this function
        """
        # Base64 string input → PCM bytes output
        b64_str = "SGVsbG8gV29ybGQ="
        pcm = gemini_inline_to_pcm_bytes(b64_str)
        assert isinstance(pcm, bytes)
        assert pcm == b"Hello World"
        
        # Base64 bytes input → PCM bytes output
        b64_bytes = b"SGVsbG8gV29ybGQ="
        pcm = gemini_inline_to_pcm_bytes(b64_bytes)
        assert isinstance(pcm, bytes)
        assert pcm == b"Hello World"
        
        # Raw PCM input → PCM bytes output (pass-through)
        raw_pcm = b'\x00\x01\x02\x03'
        pcm = gemini_inline_to_pcm_bytes(raw_pcm)
        assert isinstance(pcm, bytes)
        assert pcm == raw_pcm
        
        # None input → empty PCM bytes output
        pcm = gemini_inline_to_pcm_bytes(None)
        assert isinstance(pcm, bytes)
        assert pcm == b""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])