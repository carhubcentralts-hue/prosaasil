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


def log_gemini_tts_config():
    """
    Log Gemini TTS configuration at startup.
    Call this from server initialization to verify TTS setup.
    """
    tts_model = os.getenv('GEMINI_TTS_MODEL', 'gemini-2.5-flash-preview-tts')
    default_voice = get_default_voice("gemini")
    gemini_available = is_gemini_available()
    
    logger.info(
        f"[GEMINI_TTS] Startup config: model={tts_model}, default_voice={default_voice}, "
        f"available={gemini_available}"
    )
    
    if gemini_available:
        gemini_voices = _get_gemini_voices()
        logger.info(f"[GEMINI_TTS] Loaded {len(gemini_voices)} voices from catalog")
    else:
        logger.warning("[GEMINI_TTS] Not available - GEMINI_API_KEY not set")


# Log configuration when module is imported (once at startup)
log_gemini_tts_config()


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
        return "pulcherrima"  # 🔥 Default Gemini voice - matches voice_catalog.py
    else:
        return "alloy"


def is_gemini_available() -> bool:
    """
    Check if Gemini TTS is available (GEMINI_API_KEY is set).
    
    Returns:
        True if GEMINI_API_KEY is configured, False otherwise.
    
    Note: DISABLE_GOOGLE only affects old Google Cloud STT, NOT Gemini API!
    """
    from server.utils.gemini_key_provider import is_gemini_available as check_gemini
    return check_gemini()


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
        
        # Validate voice - use only voices supported by speech.create API
        try:
            from server.config.voices import SPEECH_CREATE_VOICES
            valid_voices = SPEECH_CREATE_VOICES
        except ImportError:
            valid_voices = ["alloy", "ash", "echo", "shimmer"]
        
        fallback_voice = "alloy"
        
        if voice_id not in valid_voices:
            logger.warning(f"[TTS][OPENAI] Voice '{voice_id}' not supported by speech.create API, using '{fallback_voice}'")
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
    voice_id: str = "pulcherrima",
    language: str = "he-IL",
    speed: float = 1.0
) -> Tuple[Optional[bytes], str]:
    """
    Synthesize speech using Gemini Speech Generation (Native TTS).
    
    Args:
        text: The text to convert to speech.
        voice_id: The Gemini voice name (lowercase, e.g., 'pulcherrima', 'charon', 'kore').
        language: Language code for synthesis (default 'he-IL').
        speed: Speaking speed from 0.25 to 4.0 (default 1.0).
    
    Returns:
        Tuple of (audio_bytes, content_type) on success,
        or (None, error_message) on failure.
    
    Environment:
        Requires GEMINI_API_KEY to be set.
        GEMINI_TTS_MODEL: Optional, defaults to 'gemini-2.5-flash-preview-tts'
    
    🔥 CRITICAL: Uses Gemini Native Speech Generation, NOT Google Cloud TTS!
    - Uses google-genai SDK (new unified SDK)
    - Model: Uses GEMINI_TTS_MODEL (default: gemini-2.5-flash-preview-tts)
    - response_modalities: ["AUDIO"] (uppercase) - MUST return AUDIO only
    - Returns PCM audio wrapped in WAV format
    - Voice names MUST be lowercase (e.g., "pulcherrima", not "Pulcherrima")
    - Strict guards: If no audio bytes → raise exception with detailed logging
    """
    try:
        # 🔥 NOTE: DISABLE_GOOGLE applies to old Google Cloud STT, NOT Gemini!
        # Gemini TTS/LLM is separate and controlled by GEMINI_API_KEY availability
        
        # 🔐 CRITICAL: Get Gemini key from ENV only
        from server.utils.gemini_key_provider import get_gemini_api_key
        gemini_api_key = get_gemini_api_key()
        if not gemini_api_key:
            logger.error(f"[GEMINI_TTS] GEMINI_API_KEY not set")
            return None, "Gemini TTS unavailable"
        
        # 🔒 Security: Validate language against whitelist
        if language not in ALLOWED_TTS_LANGUAGES:
            logger.warning(f"[GEMINI_TTS] Invalid language '{language}', falling back to he-IL")
            language = "he-IL"
        
        # 🔥 CRITICAL: Ensure voice_id is lowercase (Gemini API requirement)
        original_voice = voice_id
        voice_id = voice_id.lower() if voice_id else "pulcherrima"
        
        # 🔥 Get TTS model from environment (separate from LLM model)
        tts_model = os.getenv('GEMINI_TTS_MODEL', 'gemini-2.5-flash-preview-tts')
        
        # 🔥 Use Gemini Speech Generation with new google-genai SDK
        try:
            from google import genai
            from google.genai import types
            import struct
            
            # 🔥 CRITICAL: Validate voice against allowlist - must be a valid Gemini voice
            # Gemini TTS supports specific voices only. Using unsupported voice causes 400 errors.
            from server.config.voice_catalog import get_voice_by_id, is_valid_voice, GEMINI_VOICES
            
            # Create allowlist of valid Gemini voices
            valid_gemini_voices = [v['id'] for v in GEMINI_VOICES]
            
            if not is_valid_voice(voice_id, "gemini"):
                default_voice = get_default_voice("gemini")
                logger.warning(
                    f"[GEMINI_TTS] voice '{original_voice}' (normalized: '{voice_id}') not supported -> using '{default_voice}'. "
                    f"Valid voices: {', '.join(valid_gemini_voices[:10])}..."
                )
                voice_id = default_voice
            
            # Clamp speed to valid range
            speed = max(0.25, min(4.0, speed))
            
            # Get Gemini client (singleton - no per-call creation)
            from server.services.providers.google_clients import get_gemini_client
            client = get_gemini_client()
            if not client:
                raise RuntimeError("Gemini client not available")
            
            # 🔥 Log request start with key parameters
            logger.info(
                f"[GEMINI_TTS] request_start model={tts_model} voice={voice_id} text_len={len(text)} "
                f"language={language} speed={speed}"
            )
            
            # 🔥 CRITICAL: Use dedicated TTS model (NOT LLM model)
            # Generate speech using proper SDK with uppercase AUDIO
            # This MUST return AUDIO only, never text
            import time
            request_start_ms = int(time.time() * 1000)
            
            response = client.models.generate_content(
                model=tts_model,
                contents=text,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],  # 🔥 UPPERCASE - returns AUDIO only
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=voice_id
                            )
                        )
                    )
                )
            )
            
            latency_ms = int(time.time() * 1000) - request_start_ms
            
            latency_ms = int(time.time() * 1000) - request_start_ms
            
            # 🔥 GUARD #1: Check response exists
            if not response:
                logger.error(
                    f"[GEMINI_TTS] GUARD_FAILED: No response from API. "
                    f"model={tts_model}, voice={voice_id}, text_len={len(text)}"
                )
                raise RuntimeError("No response from Gemini TTS API")
            
            # 🔥 GUARD #2: Check candidates exist
            if not response.candidates or len(response.candidates) == 0:
                logger.error(
                    f"[GEMINI_TTS] GUARD_FAILED: No candidates in response. "
                    f"model={tts_model}, voice={voice_id}, text_len={len(text)}, "
                    f"response_keys={list(vars(response).keys()) if response else 'N/A'}"
                )
                raise RuntimeError("No candidates in Gemini TTS response - model may have generated text instead")
            
            # 🔥 GUARD #3: Extract audio data with detailed error logging
            audio_data = None
            try:
                candidate = response.candidates[0]
                audio_data = candidate.content.parts[0].inline_data.data
            except (AttributeError, IndexError) as e:
                logger.error(
                    f"[GEMINI_TTS] GUARD_FAILED: Failed to extract audio data. "
                    f"model={tts_model}, voice={voice_id}, text_len={len(text)}, "
                    f"error={str(e)}, candidate_keys={list(vars(candidate).keys()) if 'candidate' in locals() else 'N/A'}"
                )
                raise RuntimeError(f"Failed to extract audio from response: {e}")
            
            # 🔥 GUARD #4: Verify audio data is not empty
            if not audio_data or len(audio_data) == 0:
                logger.error(
                    f"[GEMINI_TTS] GUARD_FAILED: Empty audio data. "
                    f"model={tts_model}, voice={voice_id}, text_len={len(text)}, "
                    f"audio_data={'None' if audio_data is None else f'{len(audio_data)} bytes'}"
                )
                raise RuntimeError("Empty audio data from Gemini TTS - model returned AUDIO but no bytes")
            
            # 🔥 Convert PCM data to WAV format for browser playback
            # Gemini returns raw PCM16 at 24kHz, we need to wrap it with WAV header
            wav_data = _create_wav_header(audio_data)
            
            # 🔥 Success log with complete metrics
            logger.info(
                f"[GEMINI_TTS] request_ok bytes={len(wav_data)} latency_ms={latency_ms} "
                f"model={tts_model} voice={voice_id} text_len={len(text)}"
            )
            
            return wav_data, "audio/wav"
            
        except ImportError as imp_err:
            logger.error(f"[GEMINI_TTS] google-genai SDK not installed: {imp_err}")
            return None, "Gemini SDK not available - please install google-genai"
        except RuntimeError as runtime_err:
            # RuntimeError raised by our guard clauses - already logged with details
            logger.error(f"[GEMINI_TTS] Runtime error: {runtime_err}")
            return None, f"Gemini TTS error: {str(runtime_err)}"
        except Exception as api_error:
            # Catch-all for API errors (400 INVALID_ARGUMENT, etc.)
            error_msg = str(api_error)
            logger.error(
                f"[GEMINI_TTS] API_ERROR: {error_msg}. "
                f"model={tts_model if 'tts_model' in locals() else 'unknown'}, "
                f"voice={voice_id if 'voice_id' in locals() else 'unknown'}, "
                f"text_len={len(text)}"
            )
            
            # Check for common error patterns
            if "INVALID_ARGUMENT" in error_msg or "400" in error_msg:
                logger.error(
                    f"[GEMINI_TTS] INVALID_ARGUMENT detected - model may be generating text instead of audio. "
                    f"Verify: 1) response_modalities=['AUDIO'], 2) speech_config is set, 3) using TTS model"
                )
            
            return None, f"Gemini TTS API error: {error_msg}"
        
    except Exception as e:
        # 🔒 Security: Log full error server-side, return generic message to client
        logger.error(
            f"[GEMINI_TTS] synthesis_failed: {str(e)}. "
            f"voice={voice_id if 'voice_id' in locals() else 'unknown'}, "
            f"text_len={len(text)}"
        )
        import traceback
        logger.error(f"[GEMINI_TTS] Traceback: {traceback.format_exc()}")
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
