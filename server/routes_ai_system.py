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
    if cached_voice is not None:
        # 🔥 FIX: Validate cached voice is still valid (in case of old cached data)
        if cached_voice not in REALTIME_VOICES:
            logger.warning(f"[VOICE_CACHE] Invalid cached voice '{cached_voice}' for business {business_id} -> fallback to {DEFAULT_VOICE}")
            # Update cache with valid voice
            _ai_settings_cache.set(cache_key, DEFAULT_VOICE)
            return DEFAULT_VOICE
        
        logger.debug(f"[VOICE_CACHE] HIT for business {business_id}: {cached_voice}")
        return cached_voice
    
    # Cache miss - load from database
    try:
        business = Business.query.get(business_id)
        if not business:
            logger.warning(f"[VOICE_CACHE] Business {business_id} not found")
            return DEFAULT_VOICE
        
        # Get voice_id with explicit fallback for None or empty string
        # getattr handles missing attribute, `or` handles None/empty string
        voice_id = getattr(business, 'voice_id', DEFAULT_VOICE) or DEFAULT_VOICE
        
        # 🔥 FIX: Validate voice from DB is in allowed list
        if voice_id not in REALTIME_VOICES:
            logger.warning(f"[VOICE_CACHE] Invalid DB voice '{voice_id}' for business {business_id} -> fallback to {DEFAULT_VOICE}")
            voice_id = DEFAULT_VOICE
        
        # Store in cache
        _ai_settings_cache.set(cache_key, voice_id)
        logger.debug(f"[VOICE_CACHE] SET for business {business_id}: {voice_id}")
        
        return voice_id
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
    Returns: {"voice_id": "ash"}
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
    
    # Get voice_id, default to ash if not set
    voice_id = getattr(business, 'voice_id', DEFAULT_VOICE) or DEFAULT_VOICE
    
    logger.info(f"[AI_SETTINGS] Loaded AI settings for business {business_id}: voice={voice_id}")
    
    result = {
        "ok": True,
        "voice_id": voice_id
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
    Body: {"voice_id": "onyx"}
    """
    # Get business_id from session/JWT using robust resolution
    business_id = get_business_id_from_context()
    
    if not business_id:
        logger.warning("[AI_SETTINGS] No business context found - user not authenticated or missing tenant")
        return {"ok": False, "error": "business_id_required"}, 401
    
    data = request.get_json(force=True)
    voice_id = data.get('voice_id')
    
    if not voice_id:
        return {"ok": False, "error": "voice_id_required"}, 400
    
    # Validate voice_id
    if voice_id not in OPENAI_VOICES:
        logger.warning(f"[AI_SETTINGS] Invalid voice_id '{voice_id}' for business {business_id}")
        return {
            "ok": False, 
            "error": "invalid_voice_id",
            "message": f"Voice '{voice_id}' is not valid. Must be one of: {', '.join(OPENAI_VOICES)}"
        }, 400
    
    business = Business.query.get(business_id)
    if not business:
        logger.error(f"[AI_SETTINGS] Business {business_id} not found")
        return {"ok": False, "error": "business_not_found"}, 404
    
    # Update voice_id
    business.voice_id = voice_id
    business.updated_at = datetime.utcnow()
    
    try:
        db.session.commit()
        logger.info(f"[VOICE_LIBRARY] Updated voice for business {business_id}: {voice_id}")
        
        # 🔥 Invalidate both cache keys after update
        _ai_settings_cache.delete(f"ai_settings_{business_id}")
        _ai_settings_cache.delete(f"voice_{business_id}")
        logger.debug(f"[AI_SETTINGS] Cache INVALIDATED for business {business_id}")
    except Exception as e:
        db.session.rollback()
        logger.error(f"[VOICE_LIBRARY] Failed to update voice: {e}")
        return {"ok": False, "error": "database_error"}, 500
    
    return {
        "ok": True,
        "voice_id": voice_id
    }


async def _generate_preview_via_realtime(voice_id: str, text: str) -> bytes:
    """
    Generate TTS preview using OpenAI Realtime API
    Required for voices that don't support speech.create (e.g., cedar, ballad, coral, marin, sage, verse)
    
    Args:
        voice_id: Voice ID (e.g., "cedar")
        text: Text to convert to speech
        
    Returns:
        Audio bytes (mp3 format)
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
            await client.send_event({
                "type": "session.update",
                "session": {
                    "modalities": ["text", "audio"],
                    "voice": voice_id,
                    "output_audio_format": "mp3",
                    "turn_detection": None  # Disable turn detection for preview
                }
            })
            
            # Send text for conversion to speech
            await client.send_event({
                "type": "response.create",
                "response": {
                    "modalities": ["audio"],
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
        
        return b"".join(audio_chunks)
    
    except Exception as e:
        logger.error(f"[TTS_PREVIEW] Realtime API failed: {e}")
        raise


@ai_system_bp.route('/api/ai/tts/preview', methods=['POST'])
@api_handler
def preview_tts():
    """
    Preview TTS with specified text and voice
    Body: {"text": "שלום עולם", "voice_id": "cedar"}
    Returns: audio/mpeg (mp3) stream
    
    🔥 TWO PREVIEW ENGINES:
    1. speech.create (TTS-1): Fast, for voices in SPEECH_CREATE_VOICES (alloy, ash, echo, shimmer)
    2. Realtime API: For Realtime-only voices (cedar, ballad, coral, marin, sage, verse)
    
    🔥 CRITICAL: Returns binary audio/mpeg Response, NOT JSON
    """
    from server.config.voices import SPEECH_CREATE_VOICES
    
    # Get business_id from session/JWT using robust resolution
    business_id = get_business_id_from_context()
    
    if not business_id:
        logger.warning("[TTS_PREVIEW] No business context found - user not authenticated or missing tenant")
        return {"ok": False, "error": "business_id_required"}, 401
    
    data = request.get_json(force=True)
    text = data.get('text', '')
    voice_id = data.get('voice_id')
    
    # If voice_id not provided, use business default
    if not voice_id:
        business = Business.query.get(business_id)
        if business:
            voice_id = getattr(business, 'voice_id', DEFAULT_VOICE) or DEFAULT_VOICE
        else:
            voice_id = DEFAULT_VOICE
    
    # Validate voice_id is in REALTIME_VOICES
    if voice_id not in OPENAI_VOICES:
        logger.warning(f"[TTS_PREVIEW] Invalid voice_id '{voice_id}' for business {business_id}")
        return {
            "ok": False, 
            "error": "invalid_voice_id",
            "message": f"Voice '{voice_id}' is not supported. Must be one of: {', '.join(OPENAI_VOICES)}"
        }, 400
    
    # Validate text length (5-400 characters)
    if not text or len(text) < 5:
        return {"ok": False, "error": "text_too_short", "message": "Text must be at least 5 characters"}, 400
    
    if len(text) > 400:
        return {"ok": False, "error": "text_too_long", "message": "Text must be at most 400 characters"}, 400
    
    # Get voice metadata to determine preview engine
    voice_metadata = OPENAI_VOICES_METADATA.get(voice_id, {})
    preview_engine = voice_metadata.get("preview_engine", "realtime")
    
    # 🔥 CRITICAL: Double-check voice is in speech.create whitelist if using that engine
    if preview_engine == "speech_create" and voice_id not in SPEECH_CREATE_VOICES:
        logger.warning(f"[TTS_PREVIEW] Voice '{voice_id}' marked as speech_create but not in whitelist -> using Realtime")
        preview_engine = "realtime"
    
    # Log preview request
    logger.info(f"[AI][TTS_PREVIEW] business_id={business_id} voice={voice_id} engine={preview_engine} chars={len(text)}")
    
    try:
        audio_bytes = None
        
        if preview_engine == "speech_create":
            # Use standard speech.create API (fast, for compatible voices only)
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
            logger.info(f"[TTS_PREVIEW] speech.create success: {len(audio_bytes)} bytes")
        else:
            # Use Realtime API for cedar and other Realtime-only voices
            import asyncio
            audio_bytes = asyncio.run(_generate_preview_via_realtime(voice_id, text))
            logger.info(f"[TTS_PREVIEW] Realtime success: {len(audio_bytes)} bytes")
        
        # Create BytesIO object for send_file
        audio_io = io.BytesIO(audio_bytes)
        audio_io.seek(0)
        
        try:
            # 🔥 CRITICAL: Return binary audio/mpeg Response (NOT JSON)
            return send_file(
                audio_io,
                mimetype='audio/mpeg',
                as_attachment=False,
                download_name='preview.mp3'
            )
        finally:
            # Ensure audio stream is closed after sending
            audio_io.close()
        
    except Exception as e:
        logger.error(f"[AI][TTS_PREVIEW] Failed to generate preview: {e}")
        traceback.print_exc()
        return {"ok": False, "error": "tts_generation_failed", "message": str(e)}, 500
