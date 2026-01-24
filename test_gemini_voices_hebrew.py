"""
Test Gemini Voice Catalog with Hebrew Names
Verifies the voice catalog matches requirements from problem statement
"""
import pytest
from server.config.voice_catalog import (
    GEMINI_VOICES, 
    get_voice_by_id, 
    is_valid_voice, 
    default_voice,
    get_voices_by_provider
)

# Expected voice list from requirements (30 voices, lowercase)
EXPECTED_VOICES = [
    "achernar", "achird", "algenib", "algieba", "alnilam",
    "aoede", "autonoe", "callirrhoe", "charon", "despina",
    "enceladus", "erinome", "fenrir", "gacrux", "iapetus",
    "kore", "laomedeia", "leda", "orus", "puck",
    "pulcherrima", "rasalgethi", "sadachbia", "sadaltager", "schedar",
    "sulafat", "umbriel", "vindemiatrix", "zephyr", "zubenelgenubi"
]

# Expected Hebrew mappings from requirements
EXPECTED_HEBREW_NAMES = {
    "achernar": "אור",
    "achird": "איתן",
    "algenib": "רון",
    "algieba": "שחר",
    "alnilam": "אייל",
    "aoede": "נועה",
    "autonoe": "הילה",
    "callirrhoe": "דנה",
    "charon": "עמית",
    "despina": "מאיה",
    "enceladus": "גיל",
    "erinome": "רוני",
    "fenrir": "לביא",
    "gacrux": "נועם",
    "iapetus": "יואב",
    "kore": "תמר",
    "laomedeia": "אלה",
    "leda": "יעל",
    "orus": "אדם",
    "puck": "בן",
    "pulcherrima": "ליה",
    "rasalgethi": "ארז",
    "sadachbia": "שיר",
    "sadaltager": "עומר",
    "schedar": "דן",
    "sulafat": "ליאור",
    "umbriel": "אורי",
    "vindemiatrix": "מיכל",
    "zephyr": "רועי",
    "zubenelgenubi": "נועית"
}


def test_gemini_voices_count():
    """Test that exactly 30 Gemini voices are defined"""
    assert len(GEMINI_VOICES) == 30, f"Expected 30 voices, got {len(GEMINI_VOICES)}"


def test_gemini_voices_lowercase():
    """Test that all Gemini voice IDs are lowercase"""
    for voice in GEMINI_VOICES:
        voice_id = voice["id"]
        assert voice_id == voice_id.lower(), f"Voice ID '{voice_id}' must be lowercase"
        assert voice_id.islower(), f"Voice ID '{voice_id}' contains uppercase characters"


def test_gemini_voices_match_expected():
    """Test that voice IDs match expected list exactly"""
    actual_ids = sorted([v["id"] for v in GEMINI_VOICES])
    expected_ids = sorted(EXPECTED_VOICES)
    
    assert actual_ids == expected_ids, (
        f"Voice list mismatch!\n"
        f"Missing: {set(expected_ids) - set(actual_ids)}\n"
        f"Extra: {set(actual_ids) - set(expected_ids)}"
    )


def test_gemini_hebrew_names():
    """Test that Hebrew display names match expected mappings"""
    for voice in GEMINI_VOICES:
        voice_id = voice["id"]
        hebrew_name = voice.get("display_he", "")
        expected_hebrew = EXPECTED_HEBREW_NAMES.get(voice_id)
        
        assert expected_hebrew, f"No expected Hebrew name for '{voice_id}'"
        assert hebrew_name == expected_hebrew, (
            f"Hebrew name mismatch for '{voice_id}': "
            f"expected '{expected_hebrew}', got '{hebrew_name}'"
        )


def test_gemini_voice_structure():
    """Test that each voice has required fields"""
    required_fields = ["provider", "id", "gender", "display_he", "description_he"]
    
    for voice in GEMINI_VOICES:
        for field in required_fields:
            assert field in voice, f"Voice {voice.get('id')} missing required field '{field}'"
        
        # Verify provider is always "gemini"
        assert voice["provider"] == "gemini", f"Voice {voice['id']} has wrong provider"


def test_default_voice():
    """Test that default Gemini voice is 'pulcherrima'"""
    default = default_voice("gemini")
    assert default == "pulcherrima", f"Default voice should be 'pulcherrima', got '{default}'"


def test_voice_validation():
    """Test voice validation functions"""
    # Valid voices should pass
    assert is_valid_voice("pulcherrima", "gemini") is True
    assert is_valid_voice("charon", "gemini") is True
    assert is_valid_voice("aoede", "gemini") is True
    
    # Invalid voices should fail
    assert is_valid_voice("invalid_voice", "gemini") is False
    assert is_valid_voice("Pulcherrima", "gemini") is False  # Uppercase should fail
    assert is_valid_voice("CHARON", "gemini") is False  # Uppercase should fail
    
    # OpenAI voices should not validate as Gemini
    assert is_valid_voice("alloy", "gemini") is False
    assert is_valid_voice("ash", "gemini") is False


def test_get_voice_by_id():
    """Test retrieving voice metadata by ID"""
    # Test valid voice
    voice = get_voice_by_id("pulcherrima", "gemini")
    assert voice is not None
    assert voice["id"] == "pulcherrima"
    assert voice["provider"] == "gemini"
    assert voice["display_he"] == "ליה"
    
    # Test another valid voice
    voice2 = get_voice_by_id("charon", "gemini")
    assert voice2 is not None
    assert voice2["display_he"] == "עמית"
    
    # Test invalid voice
    invalid = get_voice_by_id("invalid_voice", "gemini")
    assert invalid is None


def test_get_voices_by_provider():
    """Test retrieving all voices for Gemini provider"""
    voices = get_voices_by_provider("gemini")
    assert len(voices) == 30
    assert all(v["provider"] == "gemini" for v in voices)


def test_no_uppercase_voices():
    """Test that no uppercase voice IDs exist (regression prevention)"""
    for voice in GEMINI_VOICES:
        voice_id = voice["id"]
        assert not any(c.isupper() for c in voice_id), (
            f"Voice ID '{voice_id}' contains uppercase letters - "
            f"Gemini API requires lowercase names"
        )


def test_hebrew_names_not_empty():
    """Test that all Hebrew display names are non-empty"""
    for voice in GEMINI_VOICES:
        hebrew_name = voice.get("display_he", "")
        assert hebrew_name, f"Voice {voice['id']} has empty Hebrew name"
        assert len(hebrew_name) > 0, f"Voice {voice['id']} has empty Hebrew name"


def test_no_description_required():
    """Test that description_he can be empty (as per requirements)"""
    # Requirements state only Hebrew names are needed, not descriptions
    for voice in GEMINI_VOICES:
        # description_he field should exist but can be empty
        assert "description_he" in voice, f"Voice {voice['id']} missing description_he field"
        # Empty descriptions are allowed per requirements


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
