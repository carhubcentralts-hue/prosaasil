"""
Gemini Voice Catalog - Discovery and management of Google TTS voices

🔒 CRITICAL RULES:
1. OpenAI voices are NOT managed here - don't touch them
2. API discovery if available; static fallback if not
3. Hebrew labels are for UI display only - voice_id unchanged

This module handles:
- Discovering available Gemini/Google TTS voices via API (if available)
- Falling back to static GEMINI_STATIC_VOICES if API fails
- Providing Hebrew display names for UI
- Caching discovered voices (24-hour TTL)

🛡️ FALLBACK STRATEGY:
- Try API discovery first (texttospeech.googleapis.com/v1/voices)
- If API fails → use GEMINI_STATIC_VOICES (known working voices from Google docs)
- This ensures the system never breaks due to API issues
"""
import os
import logging
import json
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Cache for discovered voices
_voice_cache: Dict = {
    "voices": [],
    "last_updated": None,
    "cache_duration_hours": 24,
    "source": None  # "api" or "static"
}

# 🛡️ STATIC FALLBACK: Known working Hebrew voices from Google Cloud TTS docs
# Used when API discovery fails - ensures system always works
GEMINI_STATIC_VOICES: List[Dict] = [
    {"id": "he-IL-Wavenet-A", "name": "Wavenet A", "language": "he-IL", "gender": "FEMALE"},
    {"id": "he-IL-Wavenet-B", "name": "Wavenet B", "language": "he-IL", "gender": "MALE"},
    {"id": "he-IL-Wavenet-C", "name": "Wavenet C", "language": "he-IL", "gender": "FEMALE"},
    {"id": "he-IL-Wavenet-D", "name": "Wavenet D", "language": "he-IL", "gender": "MALE"},
    {"id": "he-IL-Standard-A", "name": "Standard A", "language": "he-IL", "gender": "FEMALE"},
    {"id": "he-IL-Standard-B", "name": "Standard B", "language": "he-IL", "gender": "MALE"},
    {"id": "he-IL-Standard-C", "name": "Standard C", "language": "he-IL", "gender": "FEMALE"},
    {"id": "he-IL-Standard-D", "name": "Standard D", "language": "he-IL", "gender": "MALE"},
    {"id": "he-IL-Standard-E", "name": "Standard E", "language": "he-IL", "gender": "FEMALE"},
]

# Hebrew labels for known Google Hebrew voices
# These are applied ONLY for UI display, the actual voice_id sent to API is unchanged
HEBREW_VOICE_LABELS: Dict[str, Dict] = {
    # Wavenet voices (high quality)
    "he-IL-Wavenet-A": {
        "display_he": "נעמה — נשי איכותי",
        "tags_he": ["איכותי", "שירות לקוחות", "ברור"],
        "gender": "FEMALE"
    },
    "he-IL-Wavenet-B": {
        "display_he": "דוד — גברי איכותי",
        "tags_he": ["איכותי", "שירות לקוחות", "ברור"],
        "gender": "MALE"
    },
    "he-IL-Wavenet-C": {
        "display_he": "מיכל — נשי רשמי",
        "tags_he": ["רשמי", "מקצועי", "עסקי"],
        "gender": "FEMALE"
    },
    "he-IL-Wavenet-D": {
        "display_he": "יוסי — גברי רשמי",
        "tags_he": ["רשמי", "מקצועי", "עסקי"],
        "gender": "MALE"
    },
    # Standard voices (lower cost)
    "he-IL-Standard-A": {
        "display_he": "שרה — נשי בסיסי",
        "tags_he": ["בסיסי", "חסכוני"],
        "gender": "FEMALE"
    },
    "he-IL-Standard-B": {
        "display_he": "משה — גברי בסיסי",
        "tags_he": ["בסיסי", "חסכוני"],
        "gender": "MALE"
    },
    "he-IL-Standard-C": {
        "display_he": "רחל — נשי קליל",
        "tags_he": ["קליל", "ידידותי"],
        "gender": "FEMALE"
    },
    "he-IL-Standard-D": {
        "display_he": "אבי — גברי קליל",
        "tags_he": ["קליל", "ידידותי"],
        "gender": "MALE"
    },
    "he-IL-Standard-E": {
        "display_he": "לאה — נשי שירותי",
        "tags_he": ["שירותי", "מנומס"],
        "gender": "FEMALE"
    },
    # Neural2 voices (newest, highest quality)
    "he-IL-Neural2-A": {
        "display_he": "תמר — נשי מתקדם",
        "tags_he": ["מתקדם", "טבעי", "איכות גבוהה"],
        "gender": "FEMALE"
    },
    "he-IL-Neural2-B": {
        "display_he": "עומר — גברי מתקדם",
        "tags_he": ["מתקדם", "טבעי", "איכות גבוהה"],
        "gender": "MALE"
    },
    "he-IL-Neural2-C": {
        "display_he": "דנה — נשי חם",
        "tags_he": ["חם", "ידידותי", "מכירות"],
        "gender": "FEMALE"
    },
    "he-IL-Neural2-D": {
        "display_he": "גיא — גברי חם",
        "tags_he": ["חם", "ידידותי", "מכירות"],
        "gender": "MALE"
    },
    # Studio voices (most natural)
    "he-IL-Studio-O": {
        "display_he": "אורי — גברי סטודיו",
        "tags_he": ["סטודיו", "הכי טבעי", "פרימיום"],
        "gender": "MALE"
    },
    "he-IL-Studio-P": {
        "display_he": "נועה — נשי סטודיו",
        "tags_he": ["סטודיו", "הכי טבעי", "פרימיום"],
        "gender": "FEMALE"
    }
}


def is_gemini_available() -> bool:
    """
    Check if Gemini TTS is available (GEMINI_API_KEY is set).
    
    Note: DISABLE_GOOGLE only affects OLD Google Cloud TTS/STT, NOT Gemini!
    Gemini is a separate service with its own API and should always work when GEMINI_API_KEY is set.
    """
    gemini_key = os.getenv('GEMINI_API_KEY')
    return bool(gemini_key)


def discover_voices_via_api() -> Tuple[List[Dict], Optional[str]]:
    """
    Discover available voices using Google Cloud TTS API.
    
    Note: DISABLE_GOOGLE only affects OLD Google Cloud TTS/STT, NOT Gemini!
    This function should work when GEMINI_API_KEY is set, regardless of DISABLE_GOOGLE.
    
    Returns:
        Tuple of (voices_list, error_message)
        - On success: (list of voice dicts, None)
        - On error: ([], error_message)
    
    The API returns voices in format:
    {
        "voices": [
            {
                "languageCodes": ["he-IL"],
                "name": "he-IL-Wavenet-A",
                "ssmlGender": "FEMALE",
                "naturalSampleRateHertz": 24000
            },
            ...
        ]
    }
    """
    gemini_api_key = os.getenv('GEMINI_API_KEY')
    if not gemini_api_key:
        return [], "GEMINI_API_KEY not configured"
    
    try:
        import requests
        
        # Google Cloud TTS list voices endpoint
        url = f"https://texttospeech.googleapis.com/v1/voices?key={gemini_api_key}"
        
        response = requests.get(url, timeout=30)
        
        if response.status_code != 200:
            error_data = response.json() if response.text else {}
            error_msg = error_data.get('error', {}).get('message', f'HTTP {response.status_code}')
            logger.error(f"Gemini voices API error: {error_msg}")
            return [], f"API error: {error_msg}"
        
        data = response.json()
        all_voices = data.get('voices', [])
        
        # Filter to Hebrew voices only
        hebrew_voices = []
        for voice in all_voices:
            language_codes = voice.get('languageCodes', [])
            if 'he-IL' in language_codes or any(lc.startswith('he') for lc in language_codes):
                voice_id = voice.get('name', '')
                
                # Get Hebrew label if we have one, otherwise create a basic one
                label_info = HEBREW_VOICE_LABELS.get(voice_id, {})
                
                hebrew_voices.append({
                    "id": voice_id,
                    "name": voice_id,
                    "language": "he-IL",
                    "gender": voice.get('ssmlGender', 'NEUTRAL'),
                    "sample_rate": voice.get('naturalSampleRateHertz', 24000),
                    "display_he": label_info.get('display_he', voice_id),
                    "tags_he": label_info.get('tags_he', []),
                    "provider": "gemini"
                })
        
        logger.info(f"[VOICE] Gemini discovery: found {len(hebrew_voices)} Hebrew voices")
        return hebrew_voices, None
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Gemini voices discovery network error: {e}")
        return [], "Network error during voice discovery"
    except Exception as e:
        logger.error(f"Gemini voices discovery error: {e}")
        return [], "Failed to discover voices"


def get_cached_voices() -> List[Dict]:
    """Get cached voices, refreshing if needed"""
    global _voice_cache
    
    # Check if cache is valid
    if _voice_cache["voices"] and _voice_cache["last_updated"]:
        cache_age = datetime.now() - _voice_cache["last_updated"]
        if cache_age < timedelta(hours=_voice_cache["cache_duration_hours"]):
            return _voice_cache["voices"]
    
    # Refresh cache - try API discovery first
    voices, error = discover_voices_via_api()
    
    if voices:
        _voice_cache["voices"] = voices
        _voice_cache["last_updated"] = datetime.now()
        _voice_cache["source"] = "api"
        logger.info(f"[VOICE] Using API-discovered voices ({len(voices)} voices)")
        return voices
    
    # Return old cache if discovery failed but we have cached data
    if _voice_cache["voices"]:
        logger.warning("Voice discovery failed, using cached data")
        return _voice_cache["voices"]
    
    # 🛡️ FALLBACK: Use static voice list if API discovery fails
    # This ensures the system always works even if API is unavailable
    logger.warning(f"[VOICE] API discovery failed ({error}), using static fallback")
    fallback_voices = _get_static_fallback_voices()
    _voice_cache["voices"] = fallback_voices
    _voice_cache["last_updated"] = datetime.now()
    _voice_cache["source"] = "static"
    return fallback_voices


def _get_static_fallback_voices() -> List[Dict]:
    """
    Get static fallback voices with Hebrew labels applied.
    Used when API discovery fails.
    """
    voices = []
    for voice in GEMINI_STATIC_VOICES:
        voice_id = voice["id"]
        label_info = HEBREW_VOICE_LABELS.get(voice_id, {})
        voices.append({
            "id": voice_id,
            "name": voice.get("name", voice_id),
            "language": voice.get("language", "he-IL"),
            "gender": voice.get("gender", "NEUTRAL"),
            "display_he": label_info.get("display_he", voice_id),
            "tags_he": label_info.get("tags_he", []),
            "provider": "gemini",
            "source": "static"  # Mark as static for debugging
        })
    return voices


def get_gemini_voices_for_ui() -> Dict:
    """
    Get Gemini voices formatted for UI consumption.
    
    Returns:
        {
            "gemini_available": bool,
            "voices": [...],
            "default_voice": str,
            "last_updated": str or None,
            "error": str or None
        }
    """
    if not is_gemini_available():
        return {
            "gemini_available": False,
            "voices": [],
            "default_voice": "he-IL-Wavenet-A",
            "last_updated": None,
            "error": "GEMINI_API_KEY not configured"
        }
    
    voices = get_cached_voices()
    
    if not voices:
        # Try direct discovery
        voices, error = discover_voices_via_api()
        if error:
            return {
                "gemini_available": True,
                "voices": [],
                "default_voice": "he-IL-Wavenet-A",
                "last_updated": None,
                "error": error
            }
    
    # Sort by quality tier (Studio > Neural2 > Wavenet > Standard)
    def voice_sort_key(v):
        name = v.get("id", "")
        if "Studio" in name:
            tier = 0
        elif "Neural2" in name:
            tier = 1
        elif "Wavenet" in name:
            tier = 2
        else:
            tier = 3
        return (tier, v.get("display_he", name))
    
    voices.sort(key=voice_sort_key)
    
    return {
        "gemini_available": True,
        "voices": voices,
        "default_voice": voices[0]["id"] if voices else "he-IL-Wavenet-A",
        "last_updated": _voice_cache["last_updated"].isoformat() if _voice_cache["last_updated"] else None,
        "error": None
    }


def validate_voice_id(voice_id: str) -> bool:
    """
    Validate that a voice ID exists in the discovered voices.
    
    Returns True if the voice ID is valid, False otherwise.
    """
    voices = get_cached_voices()
    return any(v["id"] == voice_id for v in voices)


def get_default_voice() -> str:
    """Get the default Gemini voice ID"""
    return "he-IL-Wavenet-A"
