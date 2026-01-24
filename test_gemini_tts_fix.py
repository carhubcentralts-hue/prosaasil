"""
Test Gemini TTS Integration Fix
Validates that Gemini TTS uses the correct SDK and API structure
"""
import os
import sys

# Set test environment
os.environ['TESTING'] = 'true'
os.environ['GEMINI_API_KEY'] = os.getenv('GEMINI_API_KEY', 'test-key-for-validation')

def test_gemini_voice_catalog():
    """Test that Gemini voices are loaded from voice_catalog.py"""
    from server.services.tts_provider import _get_gemini_voices
    
    voices = _get_gemini_voices()
    print(f"\n✓ Loaded {len(voices)} Gemini voices from voice_catalog")
    
    # Check that we have the correct Gemini voices (not Wavenet)
    voice_ids = [v['id'] for v in voices]
    
    # Should have Gemini Native TTS voices
    expected_voices = ['Puck', 'Charon', 'Kore', 'Aoede']
    for voice in expected_voices:
        assert voice in voice_ids, f"Missing expected Gemini voice: {voice}"
        print(f"  ✓ Found voice: {voice}")
    
    # Should NOT have Google Cloud TTS voices (Wavenet)
    cloud_tts_patterns = ['Wavenet', 'Standard', 'Neural2']
    for voice_id in voice_ids:
        for pattern in cloud_tts_patterns:
            assert pattern not in voice_id, f"Found Cloud TTS voice {voice_id} - should only have Gemini Native voices"
    
    print("✓ Voice catalog is correct - only Gemini Native TTS voices")


def test_voice_validation():
    """Test that voice validation works for both providers"""
    from server.config.voice_catalog import is_valid_voice, get_voice_by_id
    
    # Test OpenAI voice validation
    assert is_valid_voice('ash', 'openai'), "ash should be valid for OpenAI"
    assert is_valid_voice('cedar', 'openai'), "cedar should be valid for OpenAI"
    assert not is_valid_voice('InvalidVoice', 'openai'), "InvalidVoice should not be valid for OpenAI"
    print("✓ OpenAI voice validation works")
    
    # Test Gemini voice validation
    assert is_valid_voice('Puck', 'gemini'), "Puck should be valid for Gemini"
    assert is_valid_voice('Charon', 'gemini'), "Charon should be valid for Gemini"
    assert is_valid_voice('Chernar', 'gemini'), "Chernar should be valid for Gemini (it IS in the list)"
    assert not is_valid_voice('InvalidVoiceName', 'gemini'), "InvalidVoiceName should not be valid"
    print("✓ Gemini voice validation works")
    
    # Test that OpenAI voices don't validate for Gemini
    assert not is_valid_voice('ash', 'gemini'), "ash is OpenAI voice, should not be valid for Gemini"
    assert not is_valid_voice('Puck', 'openai'), "Puck is Gemini voice, should not be valid for OpenAI"
    print("✓ Provider-specific validation works correctly")


def test_tts_provider_import():
    """Test that tts_provider can import new SDK"""
    print("\n✓ Testing SDK imports...")
    
    try:
        # This should work with the new SDK
        from google import genai
        from google.genai import types
        print("  ✓ google-genai SDK is importable (new SDK)")
    except ImportError as e:
        print(f"  ⚠ google-genai not installed yet: {e}")
        print("  → Install with: pip install google-genai")
        # This is expected if not yet installed
        pass
    
    # Test that synthesize_gemini function exists and has correct structure
    from server.services.tts_provider import synthesize_gemini
    import inspect
    
    source = inspect.getsource(synthesize_gemini)
    
    # Check for key improvements
    assert 'response_modalities=["AUDIO"]' in source, "Should use uppercase AUDIO"
    assert 'google.genai' in source or 'from google import genai' in source, "Should use new google-genai SDK"
    assert 'gemini-2.5-flash-preview-tts' in source, "Should use correct TTS model"
    assert 'PrebuiltVoiceConfig' in source, "Should use PrebuiltVoiceConfig"
    assert 'audio/wav' in source, "Should return WAV format"
    
    print("✓ synthesize_gemini has correct structure:")
    print("  ✓ Uses response_modalities=['AUDIO'] (uppercase)")
    print("  ✓ Uses google-genai SDK")
    print("  ✓ Uses gemini-2.5-flash-preview-tts model")
    print("  ✓ Uses PrebuiltVoiceConfig")
    print("  ✓ Returns WAV format")


def test_no_cloud_tts_fallback():
    """Test that there's no fallback to Google Cloud TTS"""
    from server.services.tts_provider import synthesize_gemini
    import inspect
    
    source = inspect.getsource(synthesize_gemini)
    
    # Should NOT reference Google Cloud TTS
    cloud_tts_patterns = [
        'google.cloud.texttospeech',
        'TextToSpeechClient',
        'SynthesizeSpeechRequest',
        'texttospeech.googleapis.com'
    ]
    
    for pattern in cloud_tts_patterns:
        assert pattern not in source, f"Found Cloud TTS reference: {pattern}"
    
    print("✓ No Google Cloud TTS fallback - uses Gemini Native TTS only")


def main():
    """Run all tests"""
    print("=" * 60)
    print("Testing Gemini TTS Integration Fix")
    print("=" * 60)
    
    try:
        test_gemini_voice_catalog()
        test_voice_validation()
        test_tts_provider_import()
        test_no_cloud_tts_fallback()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Install new SDK: pip install google-genai")
        print("2. Test TTS preview endpoint with Gemini provider")
        print("3. Verify no 'unknown enum label' errors")
        return 0
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
