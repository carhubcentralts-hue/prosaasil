"""
OpenAI Realtime API Voice Configuration
Single Source of Truth for SUPPORTED Realtime voices ONLY

🔥 CRITICAL: Only voices that work with Realtime API are included
Unsupported voices (fable, nova, onyx) are REMOVED to prevent session.update timeouts

Preview Engines:
- Voices with preview_engine="speech_create" work with client.audio.speech.create (TTS-1 model)
- Voices with preview_engine="realtime" require Realtime API for preview
"""

# ✅ REALTIME VOICES - Only voices supported by Realtime API
# This is the SINGLE SOURCE OF TRUTH for all voice validation
REALTIME_VOICES = [
    "alloy", "ash", "ballad", "coral", "echo", 
    "sage", "shimmer", "verse", "marin", "cedar"
]

# ✅ SPEECH.CREATE COMPATIBLE VOICES - Subset that works with TTS-1 API
# These voices can use the faster speech.create API for preview
SPEECH_CREATE_VOICES = ["alloy", "ash", "echo", "shimmer"]

# Metadata for all supported Realtime voices
OPENAI_VOICES_METADATA = {
    "alloy": {
        "id": "alloy",
        "name": "Alloy (Neutral, balanced)",
        "label": "אלוי",
        "gender": "neutral",
        "description": "Balanced and versatile voice",
        "preview_engine": "speech_create",
        "engine_support": {"realtime": True, "speech_create": True}
    },
    "ash": {
        "id": "ash",
        "name": "Ash (Male, clear)",
        "label": "אש",
        "gender": "male",
        "description": "Clear and professional male voice",
        "preview_engine": "speech_create",
        "engine_support": {"realtime": True, "speech_create": True}
    },
    "ballad": {
        "id": "ballad",
        "name": "Ballad (Male, warm)",
        "label": "בלאד",
        "gender": "male",
        "description": "Warm and engaging male voice",
        "preview_engine": "realtime",
        "engine_support": {"realtime": True, "speech_create": False}
    },
    "cedar": {
        "id": "cedar",
        "name": "Cedar (Male, deep)",
        "label": "סידר",
        "gender": "male",
        "description": "Deep and authoritative male voice",
        "preview_engine": "realtime",
        "engine_support": {"realtime": True, "speech_create": False}
    },
    "coral": {
        "id": "coral",
        "name": "Coral (Female, warm)",
        "label": "קורל",
        "gender": "female",
        "description": "Warm and friendly female voice",
        "preview_engine": "realtime",
        "engine_support": {"realtime": True, "speech_create": False}
    },
    "echo": {
        "id": "echo",
        "name": "Echo (Male, resonant)",
        "label": "הד",
        "gender": "male",
        "description": "Resonant and impactful male voice",
        "preview_engine": "speech_create",
        "engine_support": {"realtime": True, "speech_create": True}
    },
    "marin": {
        "id": "marin",
        "name": "Marin (Female, calm)",
        "label": "מרין",
        "gender": "female",
        "description": "Calm and soothing female voice",
        "preview_engine": "realtime",
        "engine_support": {"realtime": True, "speech_create": False}
    },
    "sage": {
        "id": "sage",
        "name": "Sage (Female, wise)",
        "label": "סייג׳",
        "gender": "female",
        "description": "Wise and reassuring female voice",
        "preview_engine": "realtime",
        "engine_support": {"realtime": True, "speech_create": False}
    },
    "shimmer": {
        "id": "shimmer",
        "name": "Shimmer (Female, soft)",
        "label": "שימר",
        "gender": "female",
        "description": "Soft and gentle female voice",
        "preview_engine": "speech_create",
        "engine_support": {"realtime": True, "speech_create": True}
    },
    "verse": {
        "id": "verse",
        "name": "Verse (Male, dynamic)",
        "label": "ורס",
        "gender": "male",
        "description": "Dynamic and expressive male voice",
        "preview_engine": "realtime",
        "engine_support": {"realtime": True, "speech_create": False}
    }
}

# All available OpenAI Realtime voices (list of IDs for validation)
# 🔥 MUST match REALTIME_VOICES exactly
OPENAI_VOICES = REALTIME_VOICES

# Default voice for new businesses
DEFAULT_VOICE = "cedar"
