"""
Voice Catalog - Single Source of Truth for all TTS voices
OpenAI + Gemini voices with Hebrew display names

🔥 CRITICAL RULES:
1. OpenAI voice IDs remain unchanged (alloy, ash, etc.) - these are API identifiers
2. Hebrew display names (display_he) are for UI only - NOT translations
3. Gemini voice IDs match Google's exact names (Achird, Chernar, etc.)
4. All Hebrew names are authentic Israeli first names, not translations
"""

# OpenAI Realtime API Voices (10 voices)
OPENAI_VOICES = [
    {
        "provider": "openai",
        "id": "alloy",
        "gender": "neutral",
        "display_he": "אלי",
        "description_he": "קול מאוזן ורב-תכליתי"
    },
    {
        "provider": "openai",
        "id": "ash",
        "gender": "male",
        "display_he": "אשר",
        "description_he": "קול גברי ברור ומקצועי"
    },
    {
        "provider": "openai",
        "id": "ballad",
        "gender": "male",
        "display_he": "בן",
        "description_he": "קול גברי חם ומרתק"
    },
    {
        "provider": "openai",
        "id": "cedar",
        "gender": "male",
        "display_he": "ארז",
        "description_he": "קול גברי עמוק וסמכותי"
    },
    {
        "provider": "openai",
        "id": "coral",
        "gender": "female",
        "display_he": "קורל",
        "description_he": "קול נשי חם וידידותי"
    },
    {
        "provider": "openai",
        "id": "echo",
        "gender": "male",
        "display_he": "הדר",
        "description_he": "קול גברי מהדהד ומשפיע"
    },
    {
        "provider": "openai",
        "id": "marin",
        "gender": "female",
        "display_he": "מרינה",
        "description_he": "קול נשי רגוע ומרגיע"
    },
    {
        "provider": "openai",
        "id": "sage",
        "gender": "female",
        "display_he": "שירה",
        "description_he": "קול נשי חכם ומרגיע"
    },
    {
        "provider": "openai",
        "id": "shimmer",
        "gender": "female",
        "display_he": "שיר",
        "description_he": "קול נשי רך ועדין"
    },
    {
        "provider": "openai",
        "id": "verse",
        "gender": "male",
        "display_he": "ורד",
        "description_he": "קול גברי דינמי ומבטא"
    }
]

# Gemini/Google TTS Voices (30 voices)
# IDs match Google's exact voice names
# Hebrew names are authentic Israeli first names
GEMINI_VOICES = [
    {
        "provider": "gemini",
        "id": "Chernar",
        "gender": "female",
        "display_he": "קרן",
        "description_he": "קול נשי בהיר"
    },
    {
        "provider": "gemini",
        "id": "Achird",
        "gender": "male",
        "display_he": "אחיר",
        "description_he": "קול גברי חזק"
    },
    {
        "provider": "gemini",
        "id": "Algenib",
        "gender": "male",
        "display_he": "גיל",
        "description_he": "קול גברי צעיר"
    },
    {
        "provider": "gemini",
        "id": "Algieba",
        "gender": "male",
        "display_he": "אלי",
        "description_he": "קול גברי מלא"
    },
    {
        "provider": "gemini",
        "id": "Alnilam",
        "gender": "male",
        "display_he": "ניל",
        "description_he": "קול גברי רך"
    },
    {
        "provider": "gemini",
        "id": "Aoede",
        "gender": "female",
        "display_he": "איה",
        "description_he": "קול נשי עדין"
    },
    {
        "provider": "gemini",
        "id": "Autonoe",
        "gender": "female",
        "display_he": "אורית",
        "description_he": "קול נשי בוטח"
    },
    {
        "provider": "gemini",
        "id": "Callirrhoe",
        "gender": "female",
        "display_he": "קליר",
        "description_he": "קול נשי זורם"
    },
    {
        "provider": "gemini",
        "id": "Charon",
        "gender": "male",
        "display_he": "כרם",
        "description_he": "קול גברי עשיר"
    },
    {
        "provider": "gemini",
        "id": "Despina",
        "gender": "female",
        "display_he": "דפנה",
        "description_he": "קול נשי מתוק"
    },
    {
        "provider": "gemini",
        "id": "Enceladus",
        "gender": "male",
        "display_he": "אלעד",
        "description_he": "קול גברי מעמיק"
    },
    {
        "provider": "gemini",
        "id": "Erinome",
        "gender": "female",
        "display_he": "רינה",
        "description_he": "קול נשי שמח"
    },
    {
        "provider": "gemini",
        "id": "Fenrir",
        "gender": "male",
        "display_he": "פנחס",
        "description_he": "קול גברי עוצמתי"
    },
    {
        "provider": "gemini",
        "id": "Gacrux",
        "gender": "female",
        "display_he": "גאיה",
        "description_he": "קול נשי טבעי"
    },
    {
        "provider": "gemini",
        "id": "Iapetus",
        "gender": "male",
        "display_he": "יפתח",
        "description_he": "קול גברי פותח"
    },
    {
        "provider": "gemini",
        "id": "Kore",
        "gender": "female",
        "display_he": "קורל",
        "description_he": "קול נשי צעיר"
    },
    {
        "provider": "gemini",
        "id": "Laomedeia",
        "gender": "female",
        "display_he": "לאה",
        "description_he": "קול נשי קלאסי"
    },
    {
        "provider": "gemini",
        "id": "Leda",
        "gender": "female",
        "display_he": "ליה",
        "description_he": "קול נשי קליל"
    },
    {
        "provider": "gemini",
        "id": "Orus",
        "gender": "male",
        "display_he": "אורי",
        "description_he": "קול גברי מואר"
    },
    {
        "provider": "gemini",
        "id": "Pulcherrima",
        "gender": "female",
        "display_he": "פולה",
        "description_he": "קול נשי יפה"
    },
    {
        "provider": "gemini",
        "id": "Puck",
        "gender": "male",
        "display_he": "פז",
        "description_he": "קול גברי זריז"
    },
    {
        "provider": "gemini",
        "id": "Rasalgethi",
        "gender": "male",
        "display_he": "רז",
        "description_he": "קול גברי מסתורי"
    },
    {
        "provider": "gemini",
        "id": "Sadachbia",
        "gender": "male",
        "display_he": "שדי",
        "description_he": "קול גברי שקט"
    },
    {
        "provider": "gemini",
        "id": "Sadaltager",
        "gender": "male",
        "display_he": "טל",
        "description_he": "קול גברי רענן"
    },
    {
        "provider": "gemini",
        "id": "Schedar",
        "gender": "male",
        "display_he": "שחר",
        "description_he": "קול גברי מבריק"
    },
    {
        "provider": "gemini",
        "id": "Sulafat",
        "gender": "female",
        "display_he": "סול",
        "description_he": "קול נשי מנגן"
    },
    {
        "provider": "gemini",
        "id": "Umbriel",
        "gender": "male",
        "display_he": "עומר",
        "description_he": "קול גברי צלול"
    },
    {
        "provider": "gemini",
        "id": "Vindemiatrix",
        "gender": "female",
        "display_he": "דנה",
        "description_he": "קול נשי חוזר"
    },
    {
        "provider": "gemini",
        "id": "Zephyr",
        "gender": "female",
        "display_he": "זוהר",
        "description_he": "קול נשי נושב"
    },
    {
        "provider": "gemini",
        "id": "Zubenelgenubi",
        "gender": "male",
        "display_he": "בן",
        "description_he": "קול גברי מאוזן"
    }
]


def get_all_voices():
    """
    Get all voices from both providers.
    Returns dict with 'openai' and 'gemini' keys.
    """
    return {
        "openai": OPENAI_VOICES,
        "gemini": GEMINI_VOICES
    }


def get_voice_by_id(voice_id: str, provider: str = None):
    """
    Get voice metadata by ID.
    If provider is specified, search only that provider.
    Otherwise search all providers.
    """
    voices_to_search = []
    
    if provider == "openai":
        voices_to_search = OPENAI_VOICES
    elif provider == "gemini":
        voices_to_search = GEMINI_VOICES
    else:
        voices_to_search = OPENAI_VOICES + GEMINI_VOICES
    
    for voice in voices_to_search:
        if voice["id"] == voice_id:
            return voice
    
    return None


def get_voices_by_provider(provider: str):
    """Get all voices for a specific provider."""
    if provider == "openai":
        return OPENAI_VOICES
    elif provider == "gemini":
        return GEMINI_VOICES
    else:
        return []


def is_valid_voice(voice_id: str, provider: str) -> bool:
    """Check if voice_id is valid for the given provider."""
    return get_voice_by_id(voice_id, provider) is not None


def get_voices(provider: str):
    """
    Get list of voices for a specific provider.
    Returns list of voice dictionaries.
    """
    return get_voices_by_provider(provider)


def default_voice(provider: str) -> str:
    """
    Get default voice ID for a provider.
    Returns voice ID string.
    """
    if provider == "openai":
        return "alloy"
    elif provider == "gemini":
        return "Puck"
    else:
        return "alloy"  # Fallback to OpenAI default
