"""
TTS Provider Service - Unified interface for OpenAI and Gemini TTS
Supports voice synthesis for prompt testing with provider abstraction

🔒 SECURITY:
- Never return raw exception messages to clients (may contain API keys)
- Use logger.exception() for detailed server-side logging
- Return generic error messages only

🔥 IMPORTANT:
- OpenAI voices: Use existing config from server/config/voices.py (DO NOT DUPLICATE)
- Gemini voices: Use voice_catalog.py for available voices (NOT gemini_voice_catalog.py)
"""
import os
import logging
import io
from typing import Optional, Tuple, List, Dict, Any

logger = logging.getLogger(__name__)

# 🔒 Security: Allowed TTS languages whitelist
ALLOWED_TTS_LANGUAGES = {"he-IL", "en-US", "ar-IL"}


def _get_openai_voices() -> List[Dict[str, Any]]:
    """
    Get OpenAI voices from existing config (DO NOT DUPLICATE).
    Uses server/config/voices.py as single source of truth.
    """
    try:
        from server.config.voices import OPENAI_VOICES_METADATA
        return [
            {
                "id": v["id"],
                "name": v["name"],
                "label": v["label"],
                "gender": v["gender"]
            }
            for v in OPENAI_VOICES_METADATA.values()
        ]
    except ImportError:
        logger.warning("Could not import OPENAI_VOICES_METADATA, using fallback")
        # Minimal fallback if import fails - matches existing config
        return [
            {"id": "alloy", "name": "Alloy", "label": "אלוי", "gender": "neutral"},
            {"id": "ash", "name": "Ash", "label": "אש", "gender": "male"},
            {"id": "echo", "name": "Echo", "label": "הד", "gender": "male"},
            {"id": "shimmer", "name": "Shimmer", "label": "שימר", "gender": "female"},
        ]


def _get_gemini_voices() -> List[Dict[str, Any]]:
    """
    Get Gemini voices from voice_catalog.
    Uses server/config/voice_catalog.py as single source of truth.
    """
    try:
        from server.config.voice_catalog import GEMINI_VOICES
        return GEMINI_VOICES
    except ImportError:
        logger.warning("Could not import GEMINI_VOICES from voice_catalog")
        return []


# Exported for backwards compatibility
OPENAI_TTS_VOICES = _get_openai_voices()
# Note: GEMINI_TTS_VOICES loaded dynamically from voice_catalog.py via _get_gemini_voices()


def get_available_voices(provider: str) -> List[Dict[str, Any]]:
    """Get list of available voices for a provider"""
    if provider == "openai":
        return _get_openai_voices()
    elif provider == "gemini":
        return _get_gemini_voices()
    else:
        return _get_openai_voices()  # Default to OpenAI


def get_default_voice(provider: str) -> str:
    """Get default voice ID for a provider"""
    if provider == "openai":
        try:
            from server.config.voices import DEFAULT_VOICE
            return DEFAULT_VOICE
        except ImportError:
            return "alloy"
    elif provider == "gemini":
        return "Puck"  # Default Gemini voice - matches voice_catalog.py
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
                  Invalid voices fall back to default.
        speed: Speaking speed from 0.25 to 4.0 (default 1.0).
    
    Returns:
        Tuple of (audio_bytes, content_type) on success,
        or (None, error_message) on failure.
    """
    try:
        from openai import OpenAI
        
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Validate voice using existing config (DO NOT DUPLICATE)
        try:
            from server.config.voices import REALTIME_VOICES, DEFAULT_VOICE
            valid_voices = REALTIME_VOICES
            fallback_voice = DEFAULT_VOICE
        except ImportError:
            valid_voices = ["alloy", "ash", "echo", "shimmer"]
            fallback_voice = "alloy"
        
        if voice_id not in valid_voices:
            voice_id = fallback_voice
        
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


def _create_wav_header(pcm_data: bytes, sample_rate: int = 24000) -> bytes:
    """
    Create WAV file header for PCM16 mono audio.
    
    Args:
        pcm_data: Raw PCM audio bytes
        sample_rate: Sample rate in Hz (default 24000 for Gemini TTS)
        
    Returns:
        Complete WAV file (header + PCM data)
    """
    import struct
    
    data_size = len(pcm_data)
    byte_rate = sample_rate * 2  # 16-bit = 2 bytes per sample
    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF',
        36 + data_size,
        b'WAVE',
        b'fmt ',
        16,  # Subchunk1Size (PCM)
        1,   # AudioFormat (PCM)
        1,   # NumChannels (mono)
        sample_rate,
        byte_rate,
        2,   # BlockAlign
        16,  # BitsPerSample
        b'data',
        data_size
    )
    return header + pcm_data


def synthesize_gemini(
    text: str,
    voice_id: str = "Puck",
    language: str = "he-IL",
    speed: float = 1.0
) -> Tuple[Optional[bytes], str]:
    """
    Synthesize speech using Gemini Speech Generation (Native TTS).
    
    Args:
        text: The text to convert to speech.
        voice_id: The Gemini voice name (e.g., 'Puck', 'Charon', 'Kore').
        language: Language code for synthesis (default 'he-IL').
        speed: Speaking speed from 0.25 to 4.0 (default 1.0).
    
    Returns:
        Tuple of (audio_bytes, content_type) on success,
        or (None, error_message) on failure.
    
    Environment:
        Requires GEMINI_API_KEY to be set.
    
    🔥 CRITICAL: Uses Gemini Native Speech Generation, NOT Google Cloud TTS!
    - Uses google-genai SDK (new unified SDK)
    - Model: gemini-2.5-flash-preview-tts
    - response_modalities: ["AUDIO"] (uppercase)
    - Returns PCM audio wrapped in WAV format
    """
    try:
        # Check if Google is disabled
        if os.getenv("DISABLE_GOOGLE", "false").lower() == "true":
            return None, "Google TTS is disabled"
        
        # 🔐 CRITICAL: Use ONLY GEMINI_API_KEY
        gemini_api_key = os.getenv('GEMINI_API_KEY')
        if not gemini_api_key:
            return None, "Gemini TTS unavailable"
        
        # 🔒 Security: Validate language against whitelist
        if language not in ALLOWED_TTS_LANGUAGES:
            logger.warning(f"[TTS] Invalid language '{language}', falling back to he-IL")
            language = "he-IL"
        
        # Log that Gemini TTS is enabled
        logger.info(f"[VOICE] Gemini TTS enabled with voice={voice_id}")
        
        # 🔥 Use Gemini Speech Generation with new google-genai SDK
        try:
            from google import genai
            from google.genai import types
            import struct
            
            # Validate voice - must be a valid Gemini voice
            # Get voices from voice_catalog to validate
            from server.config.voice_catalog import get_voice_by_id
            voice_metadata = get_voice_by_id(voice_id, "gemini")
            if not voice_metadata:
                default_voice = get_default_voice("gemini")
                logger.warning(f"[TTS] Invalid Gemini voice '{voice_id}', falling back to {default_voice}")
                voice_id = default_voice
            
            # Clamp speed to valid range
            speed = max(0.25, min(4.0, speed))
            
            # Create Gemini client
            client = genai.Client(api_key=gemini_api_key)
            
            # 🔥 CRITICAL: Use gemini-2.5-flash-preview-tts model for TTS
            # Generate speech using proper SDK with uppercase AUDIO
            response = client.models.generate_content(
                model="gemini-2.5-flash-preview-tts",
                contents=text,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],  # 🔥 UPPERCASE, not lowercase
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=voice_id
                            )
                        )
                    )
                )
            )
            
            # Extract PCM audio data from response
            if not response or not response.candidates:
                return None, "No audio generated from Gemini"
            
            # Get audio data from first candidate
            audio_data = None
            try:
                audio_data = response.candidates[0].content.parts[0].inline_data.data
            except (AttributeError, IndexError) as e:
                logger.error(f"[TTS][GEMINI] Failed to extract audio: {e}")
                return None, "No audio data in Gemini response"
            
            if not audio_data:
                return None, "No audio data in Gemini response"
            
            # 🔥 Convert PCM data to WAV format for browser playback
            # Gemini returns raw PCM16 at 24kHz, we need to wrap it with WAV header
            wav_data = _create_wav_header(audio_data)
            
            logger.info(f"Gemini TTS: Synthesized {len(wav_data)} bytes WAV with voice={voice_id}")
            return wav_data, "audio/wav"
            
        except ImportError as imp_err:
            logger.error(f"[TTS][GEMINI] google-genai SDK not installed: {imp_err}")
            return None, "Gemini SDK not available - please install google-genai"
        except Exception as api_error:
            logger.exception(f"[TTS][GEMINI] API error")
            return None, f"Gemini TTS error: {str(api_error)}"
        
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
