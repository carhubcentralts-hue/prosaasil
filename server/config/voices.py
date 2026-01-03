"""
OpenAI Realtime API Voice Configuration
Single Source of Truth for all available voices
"""

# All available OpenAI Realtime voices with metadata
OPENAI_VOICES_METADATA = {
    "alloy": {
        "id": "alloy",
        "name": "Alloy (Neutral, balanced)",
        "gender": "neutral",
        "description": "Balanced and versatile voice"
    },
    "ash": {
        "id": "ash",
        "name": "Ash (Male, clear)",
        "gender": "male",
        "description": "Clear and professional male voice"
    },
    "ballad": {
        "id": "ballad",
        "name": "Ballad (Male, warm)",
        "gender": "male",
        "description": "Warm and engaging male voice"
    },
    "cedar": {
        "id": "cedar",
        "name": "Cedar (Male, deep)",
        "gender": "male",
        "description": "Deep and authoritative male voice"
    },
    "coral": {
        "id": "coral",
        "name": "Coral (Female, warm)",
        "gender": "female",
        "description": "Warm and friendly female voice"
    },
    "echo": {
        "id": "echo",
        "name": "Echo (Male, resonant)",
        "gender": "male",
        "description": "Resonant and impactful male voice"
    },
    "fable": {
        "id": "fable",
        "name": "Fable (Neutral, expressive)",
        "gender": "neutral",
        "description": "Expressive and dynamic voice"
    },
    "marin": {
        "id": "marin",
        "name": "Marin (Female, calm)",
        "gender": "female",
        "description": "Calm and soothing female voice"
    },
    "nova": {
        "id": "nova",
        "name": "Nova (Female, bright)",
        "gender": "female",
        "description": "Bright and energetic female voice"
    },
    "onyx": {
        "id": "onyx",
        "name": "Onyx (Male, strong)",
        "gender": "male",
        "description": "Strong and confident male voice"
    },
    "sage": {
        "id": "sage",
        "name": "Sage (Female, wise)",
        "gender": "female",
        "description": "Wise and reassuring female voice"
    },
    "shimmer": {
        "id": "shimmer",
        "name": "Shimmer (Female, soft)",
        "gender": "female",
        "description": "Soft and gentle female voice"
    },
    "verse": {
        "id": "verse",
        "name": "Verse (Male, dynamic)",
        "gender": "male",
        "description": "Dynamic and expressive male voice"
    }
}

# All available OpenAI Realtime voices (list of IDs for validation)
OPENAI_VOICES = list(OPENAI_VOICES_METADATA.keys())

# Default voice for new businesses
DEFAULT_VOICE = "ash"
