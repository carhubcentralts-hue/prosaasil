"""
TTS Provider Service - Unified interface for OpenAI and Gemini TTS
Supports voice synthesis for prompt testing with provider abstraction
"""
import os
import logging
import io
from typing import Optional, Tuple, List, Dict, Any

logger = logging.getLogger(__name__)

# OpenAI TTS voices
OPENAI_TTS_VOICES = [
    {"id": "alloy", "name": "Alloy", "label": "אלוי", "gender": "neutral"},
    {"id": "ash", "name": "Ash", "label": "אש", "gender": "male"},
    {"id": "echo", "name": "Echo", "label": "הד", "gender": "male"},
    {"id": "shimmer", "name": "Shimmer", "label": "שימר", "gender": "female"},
    {"id": "nova", "name": "Nova", "label": "נובה", "gender": "female"},
    {"id": "onyx", "name": "Onyx", "label": "אוניקס", "gender": "male"},
    {"id": "fable", "name": "Fable", "label": "פייבל", "gender": "male"},
    {"id": "coral", "name": "Coral", "label": "קורל", "gender": "female"},
]

# Google/Gemini TTS voices (Hebrew)
GEMINI_TTS_VOICES = [
    {"id": "he-IL-Wavenet-A", "name": "Wavenet A", "label": "וייבנט א׳", "gender": "female"},
    {"id": "he-IL-Wavenet-B", "name": "Wavenet B", "label": "וייבנט ב׳", "gender": "male"},
    {"id": "he-IL-Wavenet-C", "name": "Wavenet C", "label": "וייבנט ג׳", "gender": "female"},
    {"id": "he-IL-Wavenet-D", "name": "Wavenet D", "label": "וייבנט ד׳", "gender": "male"},
    {"id": "he-IL-Standard-A", "name": "Standard A", "label": "סטנדרט א׳", "gender": "female"},
    {"id": "he-IL-Standard-B", "name": "Standard B", "label": "סטנדרט ב׳", "gender": "male"},
    {"id": "he-IL-Standard-C", "name": "Standard C", "label": "סטנדרט ג׳", "gender": "female"},
    {"id": "he-IL-Standard-D", "name": "Standard D", "label": "סטנדרט ד׳", "gender": "male"},
]


def get_available_voices(provider: str) -> List[Dict[str, Any]]:
    """Get list of available voices for a provider"""
    if provider == "openai":
        return OPENAI_TTS_VOICES
    elif provider == "gemini":
        return GEMINI_TTS_VOICES
    else:
        return OPENAI_TTS_VOICES  # Default to OpenAI


def get_default_voice(provider: str) -> str:
    """Get default voice ID for a provider"""
    if provider == "openai":
        return "alloy"
    elif provider == "gemini":
        return "he-IL-Wavenet-A"
    else:
        return "alloy"


def synthesize_openai(
    text: str,
    voice_id: str = "alloy",
    speed: float = 1.0
) -> Tuple[Optional[bytes], str]:
    """
    Synthesize speech using OpenAI TTS API
    Returns (audio_bytes, content_type) or (None, error_message)
    """
    try:
        from openai import OpenAI
        
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Validate voice
        valid_voices = [v["id"] for v in OPENAI_TTS_VOICES]
        if voice_id not in valid_voices:
            voice_id = "alloy"
        
        # Clamp speed to valid range
        speed = max(0.25, min(4.0, speed))
        
        response = client.audio.speech.create(
            model="tts-1",
            voice=voice_id,
            input=text,
            speed=speed,
            response_format="mp3"
        )
        
        # Get audio content
        audio_bytes = response.content
        
        logger.info(f"OpenAI TTS: Synthesized {len(audio_bytes)} bytes with voice={voice_id}")
        return audio_bytes, "audio/mpeg"
        
    except Exception as e:
        logger.error(f"OpenAI TTS error: {e}")
        return None, str(e)


def synthesize_gemini(
    text: str,
    voice_id: str = "he-IL-Wavenet-A",
    language: str = "he-IL",
    speed: float = 1.0
) -> Tuple[Optional[bytes], str]:
    """
    Synthesize speech using Google Cloud TTS (Gemini/GCP)
    Returns (audio_bytes, content_type) or (None, error_message)
    """
    try:
        # Check if Google is disabled
        if os.getenv("DISABLE_GOOGLE", "false").lower() == "true":
            return None, "Google TTS is disabled (DISABLE_GOOGLE=true)"
        
        from google.cloud import texttospeech
        import json
        
        # Try to create TTS client from service account JSON
        sa_json = os.getenv('GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON')
        if not sa_json:
            return None, "GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON not configured"
        
        credentials_info = json.loads(sa_json)
        client = texttospeech.TextToSpeechClient.from_service_account_info(credentials_info)
        
        # Validate voice - must be a valid Hebrew voice
        valid_voices = [v["id"] for v in GEMINI_TTS_VOICES]
        if voice_id not in valid_voices:
            voice_id = "he-IL-Wavenet-A"
        
        # Clamp speed to valid range
        speed = max(0.25, min(4.0, speed))
        
        # Configure synthesis
        synthesis_input = texttospeech.SynthesisInput(text=text)
        voice_selection = texttospeech.VoiceSelectionParams(
            language_code=language,
            name=voice_id
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=speed
        )
        
        # Synthesize speech
        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice_selection,
            audio_config=audio_config
        )
        
        audio_bytes = response.audio_content
        
        logger.info(f"Gemini TTS: Synthesized {len(audio_bytes)} bytes with voice={voice_id}")
        return audio_bytes, "audio/mpeg"
        
    except ImportError:
        logger.error("google-cloud-texttospeech not installed")
        return None, "Google Cloud TTS not available"
    except Exception as e:
        logger.error(f"Gemini TTS error: {e}")
        return None, str(e)


def synthesize(
    text: str,
    provider: str = "openai",
    voice_id: Optional[str] = None,
    language: str = "he-IL",
    speed: float = 1.0
) -> Tuple[Optional[bytes], str]:
    """
    Synthesize speech using the specified provider
    
    Args:
        text: Text to synthesize
        provider: TTS provider ("openai" or "gemini")
        voice_id: Voice ID (provider-specific)
        language: Language code (used by Gemini)
        speed: Speaking speed (0.25 - 4.0)
    
    Returns:
        Tuple of (audio_bytes, content_type) on success
        Tuple of (None, error_message) on failure
    """
    if not text or not text.strip():
        return None, "Text is required"
    
    # Default voice if not specified
    if not voice_id:
        voice_id = get_default_voice(provider)
    
    # Route to appropriate provider
    if provider == "gemini":
        return synthesize_gemini(text, voice_id, language, speed)
    else:
        # Default to OpenAI
        return synthesize_openai(text, voice_id, speed)


def get_sample_text(language: str = "he-IL") -> str:
    """Get sample text for voice preview"""
    if language.startswith("he"):
        return "שלום! אני העוזרת הוירטואלית שלך. איך אפשר לעזור לך היום?"
    else:
        return "Hello! I'm your virtual assistant. How can I help you today?"
