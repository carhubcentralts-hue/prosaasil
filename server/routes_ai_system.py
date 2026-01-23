"""
AI System Settings API - Voice Library and TTS Preview
Handles voice selection, preview, and system configuration
"""
from flask import Blueprint, request, jsonify, session, send_file, g
from server.models_sql import Business, db
from server.routes_admin import require_api_auth
from server.extensions import csrf
from server.utils.api_guard import api_handler
from server.config.voices import OPENAI_VOICES, OPENAI_VOICES_METADATA, DEFAULT_VOICE
from server.utils.cache import TTLCache
from datetime import datetime
from openai import OpenAI
import logging
import io
import os
import base64
import struct
import traceback

logger = logging.getLogger(__name__)

ai_system_bp = Blueprint('ai_system', __name__)

# 🔥 Cache for AI settings to prevent bottleneck at call start
# TTL: 120 seconds (2 minutes) - balances freshness with performance
# Max size: 2000 businesses - sufficient for most deployments
_ai_settings_cache = TTLCache(ttl_seconds=120, max_size=2000)


def get_cached_voice_for_business(business_id: int) -> str:
    """
    Get voice_id for business with caching to prevent bottleneck at call start.
    This function is optimized for high-frequency calls during conversation initialization.
    
    🔥 CRITICAL: Validates voice from cache AND database against REALTIME_VOICES
    
    Args:
        business_id: Business identifier
        
    Returns:
        voice_id string (e.g., "ash", "cedar")
        Falls back to DEFAULT_VOICE if business not found, voice not set, or voice invalid
    """
    from server.config.voices import REALTIME_VOICES
    
    if not business_id:
        return DEFAULT_VOICE
    
    # Check cache first
    cache_key = f"voice_{business_id}"
    cached_voice = _ai_settings_cache.get(cache_key)
    
    # 🔥 CRITICAL FIX: Always verify cache against DB to detect migrations/updates
    # This prevents stale voice cache from causing content filter issues
    # (e.g., when Migration 61 changed invalid voices to 'cedar')
    try:
        business = Business.query.get(business_id)
        if not business:
            logger.warning(f"[VOICE_CACHE] Business {business_id} not found")
            return DEFAULT_VOICE
        
        # Get voice_id with explicit fallback for None or empty string
        db_voice_id = getattr(business, 'voice_id', DEFAULT_VOICE) or DEFAULT_VOICE
        
        # 🔥 FIX: Validate voice from DB is in allowed list
        if db_voice_id not in REALTIME_VOICES:
            logger.warning(f"[VOICE_CACHE] Invalid DB voice '{db_voice_id}' for business {business_id} -> fallback to {DEFAULT_VOICE}")
            db_voice_id = DEFAULT_VOICE
        
        # 🔥 CRITICAL: Detect voice mismatch between cache and DB
        if cached_voice is not None and cached_voice != db_voice_id:
            logger.warning(
                f"[VOICE_CACHE] MISMATCH DETECTED for business {business_id}: "
                f"cached='{cached_voice}' vs db='{db_voice_id}' -> invalidating prompt cache!"
            )
            # Voice changed (e.g., by migration or external update) -> invalidate prompt cache
            try:
                from server.services.ai_service import invalidate_business_cache
                invalidate_business_cache(business_id)
                logger.info(f"[VOICE_CACHE] ✅ Prompt cache invalidated due to voice mismatch")
            except Exception as cache_err:
                logger.warning(f"[VOICE_CACHE] ⚠️ Failed to invalidate prompt cache: {cache_err}")
        
        # Update cache with DB value (source of truth)
        _ai_settings_cache.set(cache_key, db_voice_id)
        
        if cached_voice is None:
            logger.debug(f"[VOICE_CACHE] MISS - loaded from DB: {db_voice_id}")
        elif cached_voice == db_voice_id:
            logger.debug(f"[VOICE_CACHE] HIT (verified): {db_voice_id}")
        
        return db_voice_id
    except Exception as e:
        logger.error(f"[VOICE_CACHE] Failed to load voice for business {business_id}: {e}")
        return DEFAULT_VOICE


def get_business_id_from_context():
    """
    Get business_id from session/JWT using robust tenant context resolution.
    Returns: business_id (int or None)
    """
    # Try g.tenant first (set by middleware)
    business_id = g.get('tenant') or getattr(g, 'business_id', None)
    
    if not business_id:
        # Fallback to session
        user = session.get('user') or session.get('al_user') or {}
        business_id = session.get('impersonated_tenant_id') or (user.get('business_id') if isinstance(user, dict) else None)
    
    # Also try direct session.get('business_id') as a final fallback
    if not business_id:
        business_id = session.get('business_id')
    
    return business_id

@ai_system_bp.route('/api/system/ai/voices', methods=['GET'])
@api_handler
def get_voices():
    """
    Get list of available OpenAI voices with metadata
    Returns: {"default_voice": "ash", "voices": [{"id": "ash", "name": "Ash (Male, clear)", ...}, ...]}
    """
    voices = [OPENAI_VOICES_METADATA[voice_id] for voice_id in OPENAI_VOICES]
    
    return {
        "ok": True,
        "default_voice": DEFAULT_VOICE,
        "voices": voices
    }


@ai_system_bp.route('/api/business/settings/ai', methods=['GET'])
@api_handler
def get_business_ai_settings():
    """
    Get AI settings for current business (with caching to prevent bottlenecks)
    Returns: {
        "ok": True,
        "voice_id": "ash",  # Legacy field for compatibility
        "tts_provider": "openai",  # New field
        "tts_voice_id": "ash",  # New field
        "tts_language": "he-IL",
        "tts_speed": 1.0
    }
    """
    # Get business_id from session/JWT using robust resolution
    business_id = get_business_id_from_context()
    
    if not business_id:
        logger.warning("[AI_SETTINGS] No business context found - user not authenticated or missing tenant")
        return {"ok": False, "error": "business_id_required"}, 401
    
    # 🔥 Check cache first to avoid DB query
    cache_key = f"ai_settings_{business_id}"
    cached_settings = _ai_settings_cache.get(cache_key)
    if cached_settings is not None:
        logger.debug(f"[AI_SETTINGS] Cache HIT for business {business_id}")
        return cached_settings
    
    # Cache miss - load from database
    business = Business.query.get(business_id)
    if not business:
        logger.error(f"[AI_SETTINGS] Business {business_id} not found")
        return {"ok": False, "error": "business_not_found"}, 404
    
    # Get TTS settings with fallbacks
    tts_provider = getattr(business, 'tts_provider', 'openai') or 'openai'
    tts_voice_id = getattr(business, 'tts_voice_id', None)
    voice_id = getattr(business, 'voice_id', DEFAULT_VOICE) or DEFAULT_VOICE  # Legacy field
    tts_language = getattr(business, 'tts_language', 'he-IL') or 'he-IL'
    tts_speed = getattr(business, 'tts_speed', 1.0) or 1.0
    
    # If tts_voice_id not set, use voice_id as fallback
    if not tts_voice_id:
        tts_voice_id = voice_id
    
    logger.info(f"[AI_SETTINGS] Loaded AI settings for business {business_id}: provider={tts_provider}, voice={tts_voice_id}")
    
    result = {
        "ok": True,
        "voice_id": voice_id,  # Legacy for compatibility
        "tts_provider": tts_provider,
        "tts_voice_id": tts_voice_id,
        "tts_language": tts_language,
        "tts_speed": tts_speed
    }
    
    # 🔥 Store in cache for future requests
    _ai_settings_cache.set(cache_key, result)
    logger.debug(f"[AI_SETTINGS] Cache SET for business {business_id}")
    
    return result


@ai_system_bp.route('/api/business/settings/ai', methods=['PUT'])
@api_handler
def update_business_ai_settings():
    """
    Update AI settings for current business (with cache invalidation)
    Body: {
        "voice_id": "onyx",  # Legacy - still supported
        "tts_provider": "openai" | "gemini",  # New
        "tts_voice_id": "ash",  # New
        "tts_language": "he-IL",  # Optional
        "tts_speed": 1.0  # Optional
    }
    """
    # Get business_id from session/JWT using robust resolution
    business_id = get_business_id_from_context()
    
    if not business_id:
        logger.warning("[AI_SETTINGS] No business context found - user not authenticated or missing tenant")
        return {"ok": False, "error": "business_id_required"}, 401
    
    data = request.get_json(force=True)
    
    # Support both old (voice_id) and new (tts_provider + tts_voice_id) formats
    tts_provider = data.get('tts_provider', 'openai')
    tts_voice_id = data.get('tts_voice_id') or data.get('voice_id')  # Fallback to voice_id for compatibility
    tts_language = data.get('tts_language', 'he-IL')
    tts_speed = data.get('tts_speed', 1.0)
    
    if not tts_voice_id:
        return {"ok": False, "error": "voice_id_required"}, 400
    
    # Validate provider
    if tts_provider not in ['openai', 'gemini']:
        return {"ok": False, "error": "invalid_provider", "message": "Provider must be 'openai' or 'gemini'"}, 400
    
    # 🔥 FIX: Sanitize voice_id - strip whitespace and convert to lowercase for OpenAI
    if tts_provider == 'openai':
        tts_voice_id = str(tts_voice_id).strip().lower()
    
    # Validate voice_id based on provider
    from server.config.voice_catalog import is_valid_voice
    if not is_valid_voice(tts_voice_id, tts_provider):
        logger.warning(f"[AI_SETTINGS] Invalid voice_id '{tts_voice_id}' for provider '{tts_provider}' and business {business_id}")
        return {
            "ok": False, 
            "error": "invalid_voice_id",
            "message": f"Voice '{tts_voice_id}' is not valid for provider '{tts_provider}'"
        }, 400
    
    business = Business.query.get(business_id)
    if not business:
        logger.error(f"[AI_SETTINGS] Business {business_id} not found")
        return {"ok": False, "error": "business_not_found"}, 404
    
    # Update TTS settings
    business.tts_provider = tts_provider
    business.tts_voice_id = tts_voice_id
    business.tts_language = tts_language
    business.tts_speed = float(tts_speed)
    # Also update legacy voice_id for backward compatibility
    business.voice_id = tts_voice_id
    business.updated_at = datetime.utcnow()
    
    try:
        db.session.commit()
        logger.info(f"[VOICE_LIBRARY] Updated TTS settings for business {business_id}: provider={tts_provider}, voice={tts_voice_id}")
        
        # 🔥 Invalidate both cache keys after update
        _ai_settings_cache.delete(f"ai_settings_{business_id}")
        _ai_settings_cache.delete(f"voice_{business_id}")
        logger.debug(f"[AI_SETTINGS] Cache INVALIDATED for business {business_id}")
        
        # 🔥 CRITICAL: Invalidate prompt cache when voice changes
        # Voice change affects how prompts are cached and can cause content filter
        # This ensures prompt cache rebuilds with correct voice context
        try:
            from server.services.ai_service import invalidate_business_cache
            invalidate_business_cache(business_id)
            logger.info(f"[VOICE_LIBRARY] ✅ Prompt+Agent cache invalidated for business {business_id} after voice update")
        except Exception as cache_err:
            # Non-critical - log warning but don't fail the request
            logger.warning(f"[VOICE_LIBRARY] ⚠️ Failed to invalidate business cache: {cache_err}")
    except Exception as e:
        db.session.rollback()
        logger.error(f"[VOICE_LIBRARY] Failed to update TTS settings: {e}")
        return {"ok": False, "error": "database_error"}, 500
    
    return {
        "ok": True,
        "tts_provider": tts_provider,
        "tts_voice_id": tts_voice_id,
        "tts_language": tts_language,
        "tts_speed": tts_speed
    }


def _create_wav_header(pcm_data: bytes, sample_rate: int = 24000, bits_per_sample: int = 16, num_channels: int = 1) -> bytes:
    """
    Create a WAV file header for PCM16 audio data.
    
    Args:
        pcm_data: Raw PCM audio bytes
        sample_rate: Sample rate in Hz (24000 for Realtime API)
        bits_per_sample: Bits per sample (16 for pcm16)
        num_channels: Number of audio channels (1 for mono)
        
    Returns:
        Complete WAV file (header + data)
    """
    # Calculate sizes
    data_size = len(pcm_data)
    byte_rate = sample_rate * num_channels * bits_per_sample // 8
    block_align = num_channels * bits_per_sample // 8
    
    # Create WAV header (44 bytes)
    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF',                      # ChunkID
        36 + data_size,               # ChunkSize
        b'WAVE',                      # Format
        b'fmt ',                      # Subchunk1ID
        16,                           # Subchunk1Size (PCM)
        1,                            # AudioFormat (1 = PCM)
        num_channels,                 # NumChannels
        sample_rate,                  # SampleRate
        byte_rate,                    # ByteRate
        block_align,                  # BlockAlign
        bits_per_sample,              # BitsPerSample
        b'data',                      # Subchunk2ID
        data_size                     # Subchunk2Size
    )
    
    return header + pcm_data


async def _generate_preview_via_realtime(voice_id: str, text: str) -> bytes:
    """
    Generate TTS preview using OpenAI Realtime API
    Required for voices that don't support speech.create (e.g., cedar, ballad, coral, marin, sage, verse)
    
    Args:
        voice_id: Voice ID (e.g., "cedar")
        text: Text to convert to speech
        
    Returns:
        Audio bytes (WAV format with pcm16 data)
        
    🔥 CRITICAL: Realtime API only supports pcm16/g711_ulaw/g711_alaw, NOT mp3
    """
    from server.services.openai_realtime_client import OpenAIRealtimeClient
    import asyncio
    
    audio_chunks = []
    
    try:
        # Create Realtime client with mini model for cost efficiency
        client = OpenAIRealtimeClient(model="gpt-4o-mini-realtime-preview")
        
        # Connect to Realtime API
        await client.connect()
        
        try:
            # Configure session with voice and audio format
            # 🔥 FIX: Use pcm16 instead of mp3 (Realtime doesn't support mp3)
            await client.send_event({
                "type": "session.update",
                "session": {
                    "modalities": ["text", "audio"],
                    "voice": voice_id,
                    "output_audio_format": "pcm16",  # 🔥 Changed from "mp3" to "pcm16"
                    "turn_detection": None  # Disable turn detection for preview
                }
            })
            
            # Send text for conversion to speech
            # 🔥 FIX: Realtime API requires modalities to be ["audio", "text"], not ["audio"] alone
            # Per OpenAI docs: "Supported combinations are: ['text'] and ['audio', 'text']"
            await client.send_event({
                "type": "response.create",
                "response": {
                    "modalities": ["audio", "text"],  # 🔥 Fixed: was ["audio"] which is invalid
                    "instructions": f"Say exactly: {text}"
                }
            })
            
            # Collect audio chunks with timeout
            timeout = 6.0  # 6 second timeout for preview generation
            start_time = asyncio.get_event_loop().time()
            
            async for event in client.recv_events():
                # Check timeout
                if asyncio.get_event_loop().time() - start_time > timeout:
                    raise RuntimeError("Preview generation timeout")
                
                event_type = event.get("type", "")
                
                if event_type == "response.audio.delta":
                    # Collect audio chunk
                    delta = event.get("delta", "")
                    if delta:
                        audio_chunks.append(base64.b64decode(delta))
                
                elif event_type == "response.done":
                    # Response complete
                    break
                
                elif event_type == "error":
                    error_msg = event.get("error", {}).get("message", "Unknown error")
                    raise RuntimeError(f"Realtime API error: {error_msg}")
        
        finally:
            # Always disconnect
            await client.disconnect()
        
        # Combine audio chunks
        if not audio_chunks:
            raise RuntimeError("No audio generated")
        
        pcm_data = b"".join(audio_chunks)
        
        # 🔥 FIX: Wrap PCM16 data with WAV header for browser playback
        wav_data = _create_wav_header(pcm_data, sample_rate=24000, bits_per_sample=16, num_channels=1)
        
        return wav_data
    
    except Exception as e:
        logger.error(f"[TTS_PREVIEW] Realtime API failed: {e}")
        raise


@ai_system_bp.route('/api/ai/tts/preview', methods=['POST'])
@api_handler
def preview_tts():
    """
    Preview TTS with specified text, voice, and provider
    Body: {
        "text": "שלום עולם", 
        "voice_id": "cedar",
        "provider": "openai" | "gemini"  # Optional, defaults to openai
    }
    Returns: audio/mpeg (mp3) or audio/wav depending on engine
    
    🔥 MULTI-PROVIDER SUPPORT:
    1. OpenAI: speech.create (TTS-1) or Realtime API
    2. Gemini: Google Cloud TTS with GEMINI_API_KEY
    
    🔥 CRITICAL: Returns binary audio Response (NOT JSON)
    """
    from server.config.voices import SPEECH_CREATE_VOICES
    from server.services.tts_provider import synthesize
    
    # Get business_id from session/JWT using robust resolution
    business_id = get_business_id_from_context()
    
    if not business_id:
        logger.warning("[TTS_PREVIEW] No business context found - user not authenticated or missing tenant")
        return {"ok": False, "error": "business_id_required"}, 401
    
    data = request.get_json(force=True)
    text = data.get('text', '')
    voice_id = data.get('voice_id')
    provider = data.get('provider', 'openai')  # Default to openai
    
    # If voice_id not provided, use business default
    if not voice_id:
        business = Business.query.get(business_id)
        if business:
            provider = getattr(business, 'tts_provider', 'openai') or 'openai'
            voice_id = getattr(business, 'tts_voice_id', None) or getattr(business, 'voice_id', DEFAULT_VOICE) or DEFAULT_VOICE
        else:
            voice_id = DEFAULT_VOICE
    
    # 🔥 FIX: Sanitize voice_id for OpenAI - strip whitespace and convert to lowercase
    # Gemini voices are case-sensitive, don't modify them
    if provider == 'openai':
        voice_id = str(voice_id).strip().lower()
    
    # Validate voice_id based on provider
    from server.config.voice_catalog import is_valid_voice
    if not is_valid_voice(voice_id, provider):
        logger.warning(f"[TTS_PREVIEW] Invalid voice_id '{voice_id}' for provider '{provider}' and business {business_id}")
        return {
            "ok": False, 
            "error": "invalid_voice_id",
            "message": f"Voice '{voice_id}' is not supported for provider '{provider}'"
        }, 400
    
    # Validate text length (5-400 characters)
    if not text or len(text) < 5:
        return {"ok": False, "error": "text_too_short", "message": "Text must be at least 5 characters"}, 400
    
    if len(text) > 400:
        return {"ok": False, "error": "text_too_long", "message": "Text must be at most 400 characters"}, 400
    
    # Log preview request
    logger.info(f"[AI][TTS_PREVIEW] business_id={business_id} provider={provider} voice={voice_id} chars={len(text)}")
    
    try:
        if provider == 'gemini':
            # Use Gemini/Google TTS via tts_provider service
            audio_bytes, error_or_content_type = synthesize(
                text=text,
                provider='gemini',
                voice_id=voice_id,
                language='he-IL',
                speed=1.0
            )
            
            if audio_bytes is None:
                logger.error(f"[TTS_PREVIEW] Gemini synthesis failed: {error_or_content_type}")
                return {"ok": False, "error": "tts_generation_failed", "message": error_or_content_type}, 500
            
            content_type = error_or_content_type  # Should be "audio/mpeg"
            file_extension = 'mp3'
            logger.info(f"[TTS_PREVIEW] Gemini success: {len(audio_bytes)} bytes (mp3)")
            
        else:
            # OpenAI provider
            # Get voice metadata to determine preview engine
            voice_metadata = OPENAI_VOICES_METADATA.get(voice_id, {})
            preview_engine = voice_metadata.get("preview_engine", "realtime")
            
            # 🔥 CRITICAL: Double-check voice is in speech.create whitelist if using that engine
            if preview_engine == "speech_create" and voice_id not in SPEECH_CREATE_VOICES:
                logger.warning(f"[TTS_PREVIEW] Voice '{voice_id}' marked as speech_create but not in whitelist -> using Realtime")
                preview_engine = "realtime"
            
            audio_bytes = None
            content_type = 'audio/mpeg'  # Default for speech.create
            file_extension = 'mp3'
            
            if preview_engine == "speech_create":
                # Use standard speech.create API (fast, for compatible voices only)
                # 🔥 Returns mp3 format
                client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
                
                # Generate speech using TTS-1 model with specified voice
                response = client.audio.speech.create(
                    model="tts-1",
                    voice=voice_id,
                    input=text,
                    response_format="mp3"
                )
                
                # Convert response to bytes
                audio_bytes = response.content
                content_type = 'audio/mpeg'
                file_extension = 'mp3'
                logger.info(f"[TTS_PREVIEW] speech.create success: {len(audio_bytes)} bytes (mp3)")
            else:
                # Use Realtime API for cedar and other Realtime-only voices
                # 🔥 Returns WAV format (pcm16 wrapped with WAV header)
                # 🔥 NEW: Fallback to speech.create if Realtime fails
                try:
                    import asyncio
                    audio_bytes = asyncio.run(_generate_preview_via_realtime(voice_id, text))
                    content_type = 'audio/wav'
                    file_extension = 'wav'
                    logger.info(f"[TTS_PREVIEW] Realtime success: {len(audio_bytes)} bytes (wav)")
                except Exception as realtime_error:
                    # 🔥 FALLBACK: If Realtime fails, try speech.create if voice is compatible
                    logger.warning(f"[TTS_PREVIEW] Realtime API failed for voice '{voice_id}': {realtime_error}")
                    
                    # Check if voice is compatible with speech.create for fallback
                    if voice_id in SPEECH_CREATE_VOICES:
                        logger.info(f"[TTS_PREVIEW] Falling back to speech.create for voice '{voice_id}'")
                        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
                        
                        response = client.audio.speech.create(
                            model="tts-1",
                            voice=voice_id,
                            input=text,
                            response_format="mp3"
                        )
                        
                        audio_bytes = response.content
                        content_type = 'audio/mpeg'
                        file_extension = 'mp3'
                        logger.info(f"[TTS_PREVIEW] speech.create fallback success: {len(audio_bytes)} bytes (mp3)")
                    else:
                        # Voice not compatible with speech.create - re-raise the original error
                        raise realtime_error
        
        # Create BytesIO object for send_file
        # 🔥 FIX: Don't close the stream in finally - Flask's send_file handles it
        # Closing early causes "I/O operation on closed file" error
        audio_io = io.BytesIO(audio_bytes)
        audio_io.seek(0)
        
        # 🔥 Return binary audio response with correct content type and headers
        response = send_file(
            audio_io,
            mimetype=content_type,
            as_attachment=False,
            download_name=f'preview.{file_extension}'
        )
        
        # Add cache control headers
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Content-Length'] = str(len(audio_bytes))
        
        return response
        
    except Exception as e:
        logger.error(f"[AI][TTS_PREVIEW] Failed to generate preview: {e}")
        traceback.print_exc()
        return {"ok": False, "error": "tts_generation_failed", "message": str(e)}, 500


@ai_system_bp.route('/api/ai/voices', methods=['GET'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin'])
def get_all_voices():
    """
    Get all available TTS voices from both OpenAI and Gemini providers.
    
    Returns unified voice catalog with Hebrew display names.
    Gemini voices are ALWAYS returned - if API key missing, gemini_available=False
    but voices list is still provided for UI display.
    
    🔥 CRITICAL: This is for TTS (voice) only, NOT for LLM (brain).
    Brain is always OpenAI, voice can be OpenAI or Gemini.
    
    Returns:
        {
            "openai": [...],  # Always available
            "gemini": [...],  # Always returned, even if API key missing
            "gemini_available": bool  # True only if GEMINI_API_KEY is set
        }
    """
    try:
        from server.config.voice_catalog import OPENAI_VOICES
        from server.services.gemini_voice_catalog import get_cached_voices
        
        # Check if Gemini API key is configured
        # Use exact env var name: GEMINI_API_KEY (no aliases, no fallbacks)
        gemini_api_key = os.getenv('GEMINI_API_KEY')
        gemini_available = bool(gemini_api_key and gemini_api_key.strip())
        
        # Get Gemini voices from the proper source (with real Google TTS voice IDs)
        gemini_voices = get_cached_voices()
        
        return jsonify({
            "openai": OPENAI_VOICES,
            "gemini": gemini_voices,
            "gemini_available": gemini_available
        })
    
    except Exception as e:
        logger.error(f"[AI][VOICES] Failed to get voice catalog: {e}")
        return jsonify({"error": "Failed to load voices"}), 500
