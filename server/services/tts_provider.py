"""
TTS Provider Service - Unified interface for OpenAI and Gemini TTS
Supports voice synthesis for prompt testing with provider abstraction

🔒 SECURITY:
- Never return raw exception messages to clients (may contain API keys)
- Use logger.exception() for detailed server-side logging
- Return generic error messages only
"""
import os
import logging
import io
from typing import Optional, Tuple, List, Dict, Any

logger = logging.getLogger(__name__)

# 🔒 Security: Allowed TTS languages whitelist
ALLOWED_TTS_LANGUAGES = {"he-IL", "en-US", "ar-IL"}

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


def is_gemini_available() -> bool:
    """
    Check if Gemini TTS is available (GEMINI_API_KEY is set).
    
    Returns:
        True if GEMINI_API_KEY is configured, False otherwise.
    """
    gemini_key = os.getenv('GEMINI_API_KEY')
    is_disabled = os.getenv("DISABLE_GOOGLE", "false").lower() == "true"
    return bool(gemini_key) and not is_disabled


def synthesize_openai(
    text: str,
    voice_id: str = "alloy",
    speed: float = 1.0
) -> Tuple[Optional[bytes], str]:
    """
    Synthesize speech using OpenAI TTS API.
    
    Args:
        text: The text to convert to speech.
        voice_id: The OpenAI voice ID (e.g., 'alloy', 'echo', 'shimmer').
                  Invalid voices fall back to 'alloy'.
        speed: Speaking speed from 0.25 to 4.0 (default 1.0).
    
    Returns:
        Tuple of (audio_bytes, content_type) on success,
        or (None, error_message) on failure.
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
        # 🔒 Security: Log full error server-side, return generic message to client
        logger.exception("[TTS][OPENAI] synthesis failed")
        return None, "TTS synthesis failed"


def synthesize_gemini(
    text: str,
    voice_id: str = "he-IL-Wavenet-A",
    language: str = "he-IL",
    speed: float = 1.0
) -> Tuple[Optional[bytes], str]:
    """
    Synthesize speech using Google/Gemini TTS API.
    
    Args:
        text: The text to convert to speech.
        voice_id: The Google voice ID (e.g., 'he-IL-Wavenet-A').
                  Invalid voices fall back to 'he-IL-Wavenet-A'.
        language: Language code for synthesis (default 'he-IL').
        speed: Speaking speed from 0.25 to 4.0 (default 1.0).
    
    Returns:
        Tuple of (audio_bytes, content_type) on success,
        or (None, error_message) on failure.
    
    Environment:
        Requires GEMINI_API_KEY to be set.
    """
    try:
        # Check if Google is disabled
        if os.getenv("DISABLE_GOOGLE", "false").lower() == "true":
            return None, "Google TTS is disabled"
        
        # 🔐 CRITICAL: Use ONLY GEMINI_API_KEY - no fallback to other names
        gemini_api_key = os.getenv('GEMINI_API_KEY')
        if not gemini_api_key:
            return None, "Gemini TTS unavailable"
        
        # 🔒 Security: Validate language against whitelist
        if language not in ALLOWED_TTS_LANGUAGES:
            logger.warning(f"[TTS] Invalid language '{language}', falling back to he-IL")
            language = "he-IL"
        
        # Log that Gemini TTS is enabled (don't log the key value!)
        logger.info("[VOICE] Gemini TTS enabled")
        
        # Use Google Cloud TTS with API key
        try:
            from google.cloud import texttospeech_v1 as texttospeech
            from google.api_core import client_options
            
            # Create client with API key
            opts = client_options.ClientOptions(
                api_key=gemini_api_key
            )
            client = texttospeech.TextToSpeechClient(client_options=opts)
            
        except ImportError:
            # Fallback: Try using REST API directly if google-cloud not installed
            import requests
            
            # Validate voice
            valid_voices = [v["id"] for v in GEMINI_TTS_VOICES]
            if voice_id not in valid_voices:
                voice_id = "he-IL-Wavenet-A"
            
            # Clamp speed
            speed = max(0.25, min(4.0, speed))
            
            # Google TTS REST API endpoint
            url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={gemini_api_key}"
            
            payload = {
                "input": {"text": text},
                "voice": {
                    "languageCode": language,
                    "name": voice_id
                },
                "audioConfig": {
                    "audioEncoding": "MP3",
                    "speakingRate": speed
                }
            }
            
            response = requests.post(url, json=payload, timeout=30)
            
            if response.status_code != 200:
                error_msg = response.json().get('error', {}).get('message', 'Unknown error')
                logger.error(f"Gemini TTS API error: {error_msg}")
                return None, f"Gemini TTS error: {error_msg}"
            
            import base64
            audio_content = response.json().get('audioContent', '')
            if not audio_content:
                return None, "No audio content in response"
            
            audio_bytes = base64.b64decode(audio_content)
            logger.info(f"Gemini TTS: Synthesized {len(audio_bytes)} bytes with voice={voice_id}")
            return audio_bytes, "audio/mpeg"
        
        # Using google-cloud library
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
        
    except Exception as e:
        # 🔒 Security: Log full error server-side, return generic message to client
        logger.exception("[TTS][GEMINI] synthesis failed")
        return None, "TTS synthesis failed"


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
