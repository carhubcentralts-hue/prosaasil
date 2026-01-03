"""
AI System Settings API - Voice Library and TTS Preview
Handles voice selection, preview, and system configuration
"""
from flask import Blueprint, request, jsonify, session, send_file
from server.models_sql import Business, db
from server.routes_admin import require_api_auth
from server.extensions import csrf
from server.utils.api_guard import api_handler
from server.config.voices import OPENAI_VOICES, DEFAULT_VOICE
from datetime import datetime
from openai import OpenAI
import logging
import io
import os
import base64
import traceback

logger = logging.getLogger(__name__)

ai_system_bp = Blueprint('ai_system', __name__)

@ai_system_bp.route('/api/system/ai/voices', methods=['GET'])
@api_handler
def get_voices():
    """
    Get list of available OpenAI voices
    Returns: {"default_voice": "ash", "voices": [{"id": "ash"}, ...]}
    """
    voices = [{"id": voice_id} for voice_id in OPENAI_VOICES]
    
    return {
        "ok": True,
        "default_voice": DEFAULT_VOICE,
        "voices": voices
    }


@ai_system_bp.route('/api/business/settings/ai', methods=['GET'])
@api_handler
def get_business_ai_settings():
    """
    Get AI settings for current business
    Returns: {"voice_id": "ash"}
    """
    # Get business_id from session
    business_id = session.get('business_id')
    if not business_id:
        return {"ok": False, "error": "business_id_required"}, 400
    
    business = Business.query.get(business_id)
    if not business:
        return {"ok": False, "error": "business_not_found"}, 404
    
    # Get voice_id, default to ash if not set
    voice_id = getattr(business, 'voice_id', DEFAULT_VOICE) or DEFAULT_VOICE
    
    return {
        "ok": True,
        "voice_id": voice_id
    }


@ai_system_bp.route('/api/business/settings/ai', methods=['PUT'])
@api_handler
def update_business_ai_settings():
    """
    Update AI settings for current business
    Body: {"voice_id": "onyx"}
    """
    # Get business_id from session
    business_id = session.get('business_id')
    if not business_id:
        return {"ok": False, "error": "business_id_required"}, 400
    
    data = request.get_json(force=True)
    voice_id = data.get('voice_id')
    
    if not voice_id:
        return {"ok": False, "error": "voice_id_required"}, 400
    
    # Validate voice_id
    if voice_id not in OPENAI_VOICES:
        return {
            "ok": False, 
            "error": "invalid_voice_id",
            "message": f"Voice '{voice_id}' is not valid. Must be one of: {', '.join(OPENAI_VOICES)}"
        }, 400
    
    business = Business.query.get(business_id)
    if not business:
        return {"ok": False, "error": "business_not_found"}, 404
    
    # Update voice_id
    business.voice_id = voice_id
    business.updated_at = datetime.utcnow()
    
    try:
        db.session.commit()
        logger.info(f"[VOICE_LIBRARY] Updated voice for business {business_id}: {voice_id}")
    except Exception as e:
        db.session.rollback()
        logger.error(f"[VOICE_LIBRARY] Failed to update voice: {e}")
        return {"ok": False, "error": "database_error"}, 500
    
    return {
        "ok": True,
        "voice_id": voice_id
    }


@ai_system_bp.route('/api/ai/tts/preview', methods=['POST'])
@api_handler
def preview_tts():
    """
    Preview TTS with specified text and voice
    Body: {"text": "שלום עולם", "voice_id": "cedar"}
    Returns: audio/mpeg (mp3) stream
    """
    # Get business_id from session
    business_id = session.get('business_id')
    if not business_id:
        return {"ok": False, "error": "business_id_required"}, 400
    
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
    
    # Validate voice_id
    if voice_id not in OPENAI_VOICES:
        return {
            "ok": False, 
            "error": "invalid_voice_id",
            "message": f"Voice '{voice_id}' is not valid"
        }, 400
    
    # Validate text length (5-400 characters)
    if not text or len(text) < 5:
        return {"ok": False, "error": "text_too_short", "message": "Text must be at least 5 characters"}, 400
    
    if len(text) > 400:
        return {"ok": False, "error": "text_too_long", "message": "Text must be at most 400 characters"}, 400
    
    # Log preview request
    logger.info(f"[AI][TTS_PREVIEW] business_id={business_id} voice={voice_id} chars={len(text)}")
    
    try:
        # Use OpenAI TTS API to generate preview
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
        
        # Create BytesIO object for send_file
        audio_io = io.BytesIO(audio_bytes)
        audio_io.seek(0)
        
        try:
            # Return audio file
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
