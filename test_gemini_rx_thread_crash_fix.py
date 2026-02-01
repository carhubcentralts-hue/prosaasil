"""
Test for Gemini RX thread crash fix
Ensures that audio parsing errors don't crash the recv loop
"""
import pytest
import base64
from server.services.gemini_realtime_client import _fix_base64_padding


class TestGeminiRXThreadCrashFix:
    """Test that RX thread doesn't crash on malformed data"""
    
    def test_bytes_to_str_conversion_prevents_typeerror(self):
        """
        Test that bytes input is converted to str before padding,
        preventing TypeError: can't concat str to bytes
        """
        # This is the exact scenario that caused the crash:
        # bytes data + str padding ('=') = TypeError
        bytes_data = b"SGVsbG8gV29ybGQ"  # Missing padding
        
        # Old code would try: bytes_data += '=' which raises TypeError
        # New code converts to str first
        result = _fix_base64_padding(bytes_data)
        
        # Should return str, not bytes
        assert isinstance(result, str)
        assert result == "SGVsbG8gV29ybGQ="
        
        # Should be decodable
        decoded = base64.b64decode(result.encode("ascii"))
        assert decoded == b"Hello World"
    
    def test_mixed_type_scenario(self):
        """
        Test that function handles both str and bytes gracefully
        simulating Gemini sending different types in different frames
        """
        test_cases = [
            # (input, expected_output, decoded_value)
            ("SGVsbG8", "SGVsbG8=", b"Hello"),  # str input
            (b"SGVsbG8", "SGVsbG8=", b"Hello"),  # bytes input
            (bytearray(b"SGVsbG8"), "SGVsbG8=", b"Hello"),  # bytearray input
        ]
        
        for input_data, expected, decoded_expected in test_cases:
            result = _fix_base64_padding(input_data)
            assert result == expected
            assert isinstance(result, str)
            # Verify it's decodable
            decoded = base64.b64decode(result.encode("ascii"))
            assert decoded == decoded_expected
    
    def test_none_returns_empty_string(self):
        """Test that None returns empty string (not None)"""
        result = _fix_base64_padding(None)
        assert result == ""
        assert isinstance(result, str)
    
    def test_empty_bytes_returns_empty_string(self):
        """Test that empty bytes returns empty string"""
        result = _fix_base64_padding(b"")
        assert result == ""
        assert isinstance(result, str)
    
    def test_realistic_audio_chunk_bytes(self):
        """
        Test with realistic audio chunk data that Gemini might send as bytes
        This simulates the exact failure scenario from the problem statement
        """
        # Create a realistic audio chunk
        audio_data = b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f'
        b64_encoded = base64.b64encode(audio_data)
        
        # Simulate Gemini sending it without padding (as bytes)
        incomplete_b64 = b64_encoded.rstrip(b'=')
        
        # This should not raise TypeError
        fixed = _fix_base64_padding(incomplete_b64)
        
        # Should return str
        assert isinstance(fixed, str)
        
        # Should be decodable back to original audio data
        decoded = base64.b64decode(fixed.encode("ascii"))
        assert decoded == audio_data
    
    def test_unicode_decode_errors_handled(self):
        """
        Test that invalid UTF-8 bytes are handled gracefully
        using errors='ignore' in decode
        """
        # Invalid UTF-8 sequence (but valid base64 characters)
        invalid_utf8 = b'\xff\xfe'  # Not valid UTF-8
        
        # Should not crash, should handle with errors='ignore'
        result = _fix_base64_padding(invalid_utf8)
        
        # Should return a string (possibly empty or with replacement chars)
        assert isinstance(result, str)
    
    def test_consistent_str_output(self):
        """
        Test that function ALWAYS returns str regardless of input type
        This is the key fix to prevent TypeError in audio parsing
        """
        inputs = [
            "test",
            b"test",
            bytearray(b"test"),
            None,
            "",
            b"",
        ]
        
        for input_data in inputs:
            result = _fix_base64_padding(input_data)
            assert isinstance(result, str), f"Expected str for input {input_data!r}, got {type(result)}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
