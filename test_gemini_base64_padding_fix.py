"""
Test for Gemini Live API base64 padding fix
Fixes: binascii.Error: Incorrect padding when decoding audio chunks
"""
import pytest
import base64
from server.services.gemini_realtime_client import _fix_base64_padding


class TestBase64PaddingFix:
    """Test base64 padding correction"""
    
    def test_fix_padding_already_correct(self):
        """Test that correctly padded base64 is unchanged"""
        # Valid base64 with correct padding
        valid_b64 = "SGVsbG8gV29ybGQ="  # "Hello World"
        result = _fix_base64_padding(valid_b64)
        assert result == valid_b64
        
        # Verify it decodes successfully
        decoded = base64.b64decode(result)
        assert decoded == b"Hello World"
    
    def test_fix_padding_missing_one_char(self):
        """Test fixing base64 missing 1 padding character"""
        # Missing 1 '=' at the end
        incomplete_b64 = "SGVsbG8gV29ybGQ"
        result = _fix_base64_padding(incomplete_b64)
        assert result == "SGVsbG8gV29ybGQ="
        
        # Verify it decodes successfully
        decoded = base64.b64decode(result)
        assert decoded == b"Hello World"
    
    def test_fix_padding_missing_two_chars(self):
        """Test fixing base64 missing 2 padding characters"""
        # Valid base64 but missing padding
        incomplete_b64 = "aGVsbG8"  # "hello" without padding
        result = _fix_base64_padding(incomplete_b64)
        assert result == "aGVsbG8="
        
        # Verify it decodes successfully
        decoded = base64.b64decode(result)
        assert decoded == b"hello"
    
    def test_fix_padding_with_whitespace(self):
        """Test that whitespace is removed before fixing"""
        # Base64 with leading/trailing whitespace
        b64_with_space = "  SGVsbG8gV29ybGQ  "
        result = _fix_base64_padding(b64_with_space)
        assert result == "SGVsbG8gV29ybGQ="
        
        # Verify it decodes successfully
        decoded = base64.b64decode(result)
        assert decoded == b"Hello World"
    
    def test_fix_padding_no_padding_needed(self):
        """Test base64 that doesn't need padding"""
        # Length already divisible by 4
        no_padding_needed = "YWJjZA=="  # "abcd"
        result = _fix_base64_padding(no_padding_needed)
        assert result == no_padding_needed
        
        # Verify it decodes successfully
        decoded = base64.b64decode(result)
        assert decoded == b"abcd"
    
    def test_fix_audio_data_example(self):
        """Test with realistic audio data scenario"""
        # Simulate Gemini API audio data (small binary chunk encoded)
        audio_bytes = b'\x00\x01\x02\x03\x04\x05\x06\x07'
        correct_b64 = base64.b64encode(audio_bytes).decode('ascii')
        
        # Remove padding to simulate Gemini API issue
        incomplete_b64 = correct_b64.rstrip('=')
        
        # Fix and decode
        fixed_b64 = _fix_base64_padding(incomplete_b64)
        decoded = base64.b64decode(fixed_b64)
        
        # Verify we get original data back
        assert decoded == audio_bytes
    
    def test_empty_string(self):
        """Test with empty string"""
        result = _fix_base64_padding("")
        assert result == ""
    
    def test_valid_two_char_base64(self):
        """Test with two-character base64 (needs 2 padding chars)"""
        # "QQ==" is valid base64 for binary '01000001'
        result = _fix_base64_padding("QQ")
        assert result == "QQ=="
        
        # Verify it decodes successfully
        decoded = base64.b64decode(result)
        assert len(decoded) == 1  # Should decode to 1 byte
    
    def test_fix_padding_bytes_input(self):
        """Test that bytes input is handled correctly and returns str"""
        # Test with bytes that need padding
        incomplete_bytes = b"SGVsbG8gV29ybGQ"  # "Hello World" missing padding
        result = _fix_base64_padding(incomplete_bytes)
        # 🔥 FIX: Function now always returns str, not bytes
        assert result == "SGVsbG8gV29ybGQ="
        assert isinstance(result, str)
        
        # Verify it decodes successfully when encoded back to bytes
        decoded = base64.b64decode(result.encode("ascii"))
        assert decoded == b"Hello World"
    
    def test_fix_padding_bytes_correct(self):
        """Test that correctly padded bytes are converted to str"""
        correct_bytes = b"SGVsbG8gV29ybGQ="  # "Hello World" with correct padding
        result = _fix_base64_padding(correct_bytes)
        # 🔥 FIX: Function now always returns str, not bytes
        assert result == "SGVsbG8gV29ybGQ="
        assert isinstance(result, str)
        
        # Verify it decodes successfully when encoded back to bytes
        decoded = base64.b64decode(result.encode("ascii"))
        assert decoded == b"Hello World"
    
    def test_fix_padding_bytes_missing_two(self):
        """Test bytes missing 2 padding characters returns str"""
        incomplete_bytes = b"aGVsbG8"  # "hello" without padding
        result = _fix_base64_padding(incomplete_bytes)
        # 🔥 FIX: Function now always returns str, not bytes
        assert result == "aGVsbG8="
        assert isinstance(result, str)
        
        # Verify it decodes successfully when encoded back to bytes
        decoded = base64.b64decode(result.encode("ascii"))
        assert decoded == b"hello"
    
    def test_fix_padding_bytearray_input(self):
        """Test that bytearray input is handled correctly and returns str"""
        incomplete_bytearray = bytearray(b"SGVsbG8gV29ybGQ")
        result = _fix_base64_padding(incomplete_bytearray)
        # 🔥 FIX: Function now always returns str, not bytes
        assert result == "SGVsbG8gV29ybGQ="
        assert isinstance(result, str)
        
        # Verify it decodes successfully when encoded back to bytes
        decoded = base64.b64decode(result.encode("ascii"))
        assert decoded == b"Hello World"
    
    def test_fix_padding_none_input(self):
        """Test that None input returns empty string"""
        result = _fix_base64_padding(None)
        # 🔥 FIX: Function now returns "" for None instead of None
        assert result == ""
    
    def test_gemini_api_bytes_scenario(self):
        """Test realistic Gemini API scenario with bytes audio data"""
        # Simulate Gemini API sending audio data as bytes
        audio_bytes = b'\x00\x01\x02\x03\x04\x05\x06\x07'
        correct_b64_bytes = base64.b64encode(audio_bytes)
        
        # Remove padding to simulate Gemini API issue  
        incomplete_b64_bytes = correct_b64_bytes.rstrip(b'=')
        
        # Fix and decode
        fixed_b64 = _fix_base64_padding(incomplete_b64_bytes)
        # 🔥 FIX: Function now always returns str, not bytes
        assert isinstance(fixed_b64, str)
        # Encode back to bytes for b64decode
        decoded = base64.b64decode(fixed_b64.encode("ascii"))
        
        # Verify we get original data back
        assert decoded == audio_bytes


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
