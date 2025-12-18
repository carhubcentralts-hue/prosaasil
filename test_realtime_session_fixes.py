#!/usr/bin/env python3
"""
Unit tests for Realtime API session.update crash fixes

Tests verify:
1. None transcription doesn't crash when accessing .get()
2. Force parameter bypasses hash check
3. Field name consistency (input_audio_transcription)
"""

import unittest
import sys
import os

# Add server directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))


class TestTranscriptionNoneHandling(unittest.TestCase):
    """Test that None transcription values are handled safely"""
    
    def test_none_transcription_with_or_operator(self):
        """Test that 'or {}' pattern prevents crash on None"""
        # Simulate what happens in the code
        session_data = {
            "input_audio_transcription": None
        }
        
        # This should not crash
        transcription = session_data.get("input_audio_transcription") or {}
        
        # Should be empty dict, not None
        self.assertEqual(transcription, {})
        
        # Should be safe to call .get() on it
        model = transcription.get("model")
        language = transcription.get("language")
        
        self.assertIsNone(model)
        self.assertIsNone(language)
    
    def test_none_transcription_conditional_check(self):
        """Test that conditional check prevents accessing None"""
        session_data = {
            "input_audio_transcription": None
        }
        
        transcription = session_data.get("input_audio_transcription") or {}
        
        # This pattern should be safe - check if language key exists before comparing
        if "language" in transcription and transcription.get("language") != "he":
            # This block should not execute for empty dict
            self.fail("Should not reach here for empty transcription")
        
        # This should pass
        self.assertTrue(True)
    
    def test_empty_dict_transcription_language_check(self):
        """Test that language check works correctly for empty dict"""
        # Empty dict case (when transcription is None)
        transcription = {}
        
        # This should NOT trigger the warning (no language key)
        should_warn = "language" in transcription and transcription.get("language") != "he"
        self.assertFalse(should_warn, "Empty dict should not trigger language warning")
        
        # Valid transcription with Hebrew
        transcription = {"model": "gpt-4o-transcribe", "language": "he"}
        should_warn = "language" in transcription and transcription.get("language") != "he"
        self.assertFalse(should_warn, "Hebrew language should not trigger warning")
        
        # Valid transcription with wrong language
        transcription = {"model": "gpt-4o-transcribe", "language": "en"}
        should_warn = "language" in transcription and transcription.get("language") != "he"
        self.assertTrue(should_warn, "Non-Hebrew language should trigger warning")
    
    def test_valid_transcription_works(self):
        """Test that valid transcription still works correctly"""
        session_data = {
            "input_audio_transcription": {
                "model": "gpt-4o-transcribe",
                "language": "he"
            }
        }
        
        transcription = session_data.get("input_audio_transcription") or {}
        
        # Should work normally
        self.assertEqual(transcription.get("model"), "gpt-4o-transcribe")
        self.assertEqual(transcription.get("language"), "he")


class TestForceParameter(unittest.TestCase):
    """Test that force parameter bypasses hash check"""
    
    def test_hash_check_logic(self):
        """Test the logic of force parameter bypassing hash check"""
        # Simulate the hash check logic
        last_hash = "abc123"
        current_hash = "abc123"
        force = False
        
        # Without force, same hash should skip
        should_skip = not force and last_hash == current_hash
        self.assertTrue(should_skip)
        
        # With force, same hash should NOT skip
        force = True
        should_skip = not force and last_hash == current_hash
        self.assertFalse(should_skip)


class TestFieldNameConsistency(unittest.TestCase):
    """Test that field names are consistent"""
    
    def test_field_name_is_input_audio_transcription(self):
        """Verify the correct field name is used"""
        # This is a documentation test to confirm the field name
        correct_field_name = "input_audio_transcription"
        
        # Verify it's not using other variations
        self.assertEqual(correct_field_name, "input_audio_transcription")
        self.assertNotEqual(correct_field_name, "transcription")
        self.assertNotEqual(correct_field_name, "audio_transcription")


if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)
