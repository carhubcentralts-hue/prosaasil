"""
OpenAI Realtime API Voice Configuration
Single Source of Truth for SUPPORTED Realtime voices ONLY

🔥 CRITICAL: Only voices that work with Realtime API are included
Unsupported voices (fable, nova, onyx) are REMOVED to prevent session.update timeouts

Preview Engines:
- "speech_create": Standard TTS API (speech.create) - works for most voices
- "realtime": Realtime API only - required for cedar and other Realtime-exclusive voices
"""

# ✅ REALTIME VOICES - Only voices supported by Realtime API
# This is the SINGLE SOURCE OF TRUTH for all voice validation
REALTIME_VOICES = [
    "alloy", "ash", "ballad", "coral", "echo", 
    "sage", "shimmer", "verse", "marin", "cedar"
]

# Metadata for all supported Realtime voices
OPENAI_VOICES_METADATA = {
    "alloy": {
        "id": "alloy",
        "name": "Alloy (Neutral, balanced)",
        "gender": "neutral",
        "description": "Balanced and versatile voice",
        "preview_engine": "speech_create"
    },
    "ash": {
        "id": "ash",
        "name": "Ash (Male, clear)",
        "gender": "male",
        "description": "Clear and professional male voice",
        "preview_engine": "speech_create"
    },
    "ballad": {
        "id": "ballad",
        "name": "Ballad (Male, warm)",
        "gender": "male",
        "description": "Warm and engaging male voice",
        "preview_engine": "realtime"
    },
    "cedar": {
        "id": "cedar",
        "name": "Cedar (Male, deep)",
        "gender": "male",
        "description": "Deep and authoritative male voice",
        "preview_engine": "realtime"
    },
    "coral": {
        "id": "coral",
        "name": "Coral (Female, warm)",
        "gender": "female",
        "description": "Warm and friendly female voice",
        "preview_engine": "realtime"
    },
    "echo": {
        "id": "echo",
        "name": "Echo (Male, resonant)",
        "gender": "male",
        "description": "Resonant and impactful male voice",
        "preview_engine": "speech_create"
    },
    "marin": {
        "id": "marin",
        "name": "Marin (Female, calm)",
        "gender": "female",
        "description": "Calm and soothing female voice",
        "preview_engine": "realtime"
    },
    "sage": {
        "id": "sage",
        "name": "Sage (Female, wise)",
        "gender": "female",
        "description": "Wise and reassuring female voice",
        "preview_engine": "realtime"
    },
    "shimmer": {
        "id": "shimmer",
        "name": "Shimmer (Female, soft)",
        "gender": "female",
        "description": "Soft and gentle female voice",
        "preview_engine": "speech_create"
    },
    "verse": {
        "id": "verse",
        "name": "Verse (Male, dynamic)",
        "gender": "male",
        "description": "Dynamic and expressive male voice",
        "preview_engine": "realtime"
    }
}

# All available OpenAI Realtime voices (list of IDs for validation)
# 🔥 MUST match REALTIME_VOICES exactly
OPENAI_VOICES = REALTIME_VOICES

# Default voice for new businesses
DEFAULT_VOICE = "cedar"
