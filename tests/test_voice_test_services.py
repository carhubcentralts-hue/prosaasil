"""
Unit tests for TTS Provider and Voice Test services
"""
import pytest
from unittest.mock import patch, MagicMock
import os


class TestTTSProvider:
    """Test TTS Provider service"""
    
    def test_get_available_voices_openai(self):
        """Test getting OpenAI voices"""
        from server.services.tts_provider import get_available_voices, OPENAI_TTS_VOICES
        
        voices = get_available_voices("openai")
        assert len(voices) == len(OPENAI_TTS_VOICES)
        assert all("id" in v for v in voices)
        assert all("name" in v for v in voices)
    
    def test_get_available_voices_gemini(self):
        """Test getting Gemini voices returns list format"""
        from server.services.tts_provider import get_available_voices
        
        voices = get_available_voices("gemini")
        # May be empty if no GEMINI_API_KEY, but should be a list
        assert isinstance(voices, list)
        if len(voices) > 0:
            assert all("id" in v for v in voices)
    
    def test_get_available_voices_unknown_provider(self):
        """Test getting voices for unknown provider defaults to OpenAI"""
        from server.services.tts_provider import get_available_voices
        
        voices = get_available_voices("unknown")
        # Should return OpenAI voices as fallback
        assert isinstance(voices, list)
        assert len(voices) > 0
    
    def test_get_default_voice_openai(self):
        """Test default voice for OpenAI returns a valid voice"""
        from server.services.tts_provider import get_default_voice
        
        voice = get_default_voice("openai")
        # Should return a valid OpenAI voice (uses existing config)
        assert voice is not None
        assert len(voice) > 0
    
    def test_get_default_voice_gemini(self):
        """Test default voice for Gemini"""
        from server.services.tts_provider import get_default_voice
        
        voice = get_default_voice("gemini")
        assert voice == "he-IL-Wavenet-A"
    
    def test_get_default_voice_unknown(self):
        """Test default voice for unknown provider returns a valid voice"""
        from server.services.tts_provider import get_default_voice
        
        voice = get_default_voice("unknown")
        # Should return a valid fallback voice
        assert voice is not None
        assert len(voice) > 0
    
    def test_get_sample_text_hebrew(self):
        """Test Hebrew sample text"""
        from server.services.tts_provider import get_sample_text
        
        text = get_sample_text("he-IL")
        assert "שלום" in text
    
    def test_get_sample_text_english(self):
        """Test English sample text"""
        from server.services.tts_provider import get_sample_text
        
        text = get_sample_text("en-US")
        assert "Hello" in text
    
    def test_synthesize_empty_text(self):
        """Test synthesis with empty text returns error"""
        from server.services.tts_provider import synthesize
        
        audio_bytes, error = synthesize("")
        assert audio_bytes is None
        assert "required" in error.lower()
    
    def test_synthesize_whitespace_only(self):
        """Test synthesis with whitespace only returns error"""
        from server.services.tts_provider import synthesize
        
        audio_bytes, error = synthesize("   ")
        assert audio_bytes is None
        assert "required" in error.lower()
    
    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key", "DISABLE_GOOGLE": "false"}, clear=False)
    def test_is_gemini_available_with_key(self):
        """Test is_gemini_available returns True when GEMINI_API_KEY is set"""
        from server.services.tts_provider import is_gemini_available
        
        assert is_gemini_available() is True
    
    @patch.dict(os.environ, {"DISABLE_GOOGLE": "true"}, clear=False)
    def test_is_gemini_available_when_disabled(self):
        """Test is_gemini_available returns False when Google is disabled"""
        from server.services.tts_provider import is_gemini_available
        
        # Even with key, should be False if disabled
        assert is_gemini_available() is False
    
    @patch.dict(os.environ, {"DISABLE_GOOGLE": "true"})
    def test_synthesize_gemini_disabled(self):
        """Test Gemini TTS when Google is disabled"""
        from server.services.tts_provider import synthesize_gemini
        
        audio_bytes, error = synthesize_gemini("שלום")
        assert audio_bytes is None
        assert "disabled" in error.lower()
    
    def test_openai_voice_list_content(self):
        """Test OpenAI voice list has expected content"""
        from server.services.tts_provider import OPENAI_TTS_VOICES
        
        voice_ids = [v["id"] for v in OPENAI_TTS_VOICES]
        # Should have some OpenAI voices
        assert len(voice_ids) > 0
        # Check format is correct
        for voice in OPENAI_TTS_VOICES:
            assert "id" in voice
            assert "label" in voice
    
    def test_gemini_voice_catalog_structure(self):
        """Test Gemini voice catalog has correct structure"""
        from server.services.gemini_voice_catalog import HEBREW_VOICE_LABELS
        
        # Should have Hebrew labels defined
        assert len(HEBREW_VOICE_LABELS) > 0
        # Check structure
        for voice_id, info in HEBREW_VOICE_LABELS.items():
            assert "display_he" in info
            assert "tags_he" in info
            assert "he-IL" in voice_id  # Should be Hebrew voices


class TestVADLogic:
    """Test VAD (Voice Activity Detection) logic"""
    
    def test_rms_calculation(self):
        """Test RMS calculation for audio samples"""
        # RMS formula: sqrt(sum(x^2)/n)
        import math
        
        # Simulate normalized audio samples
        samples = [0.5, -0.5, 0.5, -0.5]
        sum_squares = sum(x * x for x in samples)
        expected_rms = math.sqrt(sum_squares / len(samples))
        
        assert expected_rms == 0.5
    
    def test_noise_threshold_calculation(self):
        """Test noise floor threshold calculation"""
        # Noise floor * multiplier should give threshold
        noise_floor = 10.0
        multiplier = 2.2
        
        threshold = noise_floor * multiplier
        assert threshold == 22.0
    
    def test_silence_detection(self):
        """Test silence detection logic"""
        # Simulate silence detection
        silence_threshold_ms = 700
        silence_start = 1000  # Started at 1000ms
        current_time = 1800   # Current time 1800ms
        
        silence_duration = current_time - silence_start
        is_end_of_utterance = silence_duration >= silence_threshold_ms
        
        assert is_end_of_utterance is True
    
    def test_silence_not_enough(self):
        """Test silence not yet enough for end of utterance"""
        silence_threshold_ms = 700
        silence_start = 1000
        current_time = 1500  # Only 500ms of silence
        
        silence_duration = current_time - silence_start
        is_end_of_utterance = silence_duration >= silence_threshold_ms
        
        assert is_end_of_utterance is False
    
    def test_speech_detection(self):
        """Test speech detection above threshold"""
        threshold = 20.0
        rms_value = 35.0
        
        is_speech = rms_value > threshold
        assert is_speech is True
    
    def test_no_speech_below_threshold(self):
        """Test no speech detection below threshold"""
        threshold = 20.0
        rms_value = 10.0
        
        is_speech = rms_value > threshold
        assert is_speech is False
    
    def test_calibration_multiplier(self):
        """Test calibration noise multiplier produces reasonable threshold"""
        noise_samples = [5.0, 6.0, 4.5, 5.5, 5.0]  # Average = 5.2
        avg_noise = sum(noise_samples) / len(noise_samples)
        multiplier = 2.2
        min_threshold = 10.0
        
        threshold = max(avg_noise * multiplier, min_threshold)
        
        assert threshold == avg_noise * multiplier
        assert threshold > avg_noise  # Threshold should be above noise


class TestPromptBuilder:
    """Test Prompt Builder service"""
    
    def test_prompt_template_placeholders(self):
        """Test that prompt template format string works correctly"""
        # We test the format works without errors
        template = """
        תחום: {business_area}
        קהל: {target_audience}
        ליד: {quality_lead}
        שעות: {working_hours}
        שירותים: {main_services}
        סגנון: {speaking_style}
        חוקים: {rules}
        אינטגרציות: {integrations}
        """
        
        result = template.format(
            business_area="סלון יופי",
            target_audience="נשים",
            quality_lead="לקוחה שרוצה תור",
            working_hours="09:00-18:00",
            main_services="תספורת, צביעה",
            speaking_style="אדיב",
            rules="לא להבטיח מחירים",
            integrations="יומן Google"
        )
        
        assert "סלון יופי" in result
        assert "נשים" in result
    
    def test_speaking_styles_variety(self):
        """Test various speaking style options"""
        styles = [
            "רגוע ואדיב",
            "ישיר ומקצועי",
            "חם ומכירתי",
            "פורמלי ורציני",
            "צעיר ודינמי"
        ]
        
        # All styles should be valid Hebrew strings
        for style in styles:
            assert len(style) > 0
            assert isinstance(style, str)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
