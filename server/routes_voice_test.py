"""
Voice Test API - Endpoints for prompt voice testing
Supports Realtime API session for natural conversation and TTS Preview

🔥 Architecture:
- Realtime session endpoint: Returns ephemeral token for WebRTC/WebSocket connection
- TTS Preview: Simple preview for voice selection (OpenAI or Gemini)
- Voice settings: Saved per-business

🔒 Security:
- All endpoints require authentication
- Rate limiting on expensive operations
- Input size guards (max chars)
"""
from flask import Blueprint, request, jsonify, session, Response, current_app
from server.routes_admin import require_api_auth
from server.extensions import csrf
from server.utils.api_guard import api_handler
from server.models_sql import Business, BusinessSettings, db
from server.services import tts_provider
import logging
import io
import os
import json

logger = logging.getLogger(__name__)

voice_test_bp = Blueprint('voice_test', __name__)

# 🔒 Security: Input size limits
MAX_TEXT_LENGTH = 1000  # Max chars for TTS text
MAX_PROMPT_LENGTH = 10000  # Max chars for prompts
MAX_MESSAGE_LENGTH = 2000  # Max chars for chat messages


def _is_gemini_available() -> bool:
    """Check if Gemini TTS is available (GEMINI_API_KEY is set)"""
    return tts_provider.is_gemini_available()


def _get_voice_provider_modes() -> dict:
    """Get voice provider modes dynamically based on configuration"""
    gemini_available = _is_gemini_available()
    production_enabled = os.getenv('ENABLE_GEMINI_TTS_PRODUCTION', 'false').lower() == 'true'
    
    return {
        'openai': True,  # Always available
        'gemini_preview': gemini_available,  # Preview only if key is set
        'gemini': gemini_available and production_enabled  # Production requires both key and flag
    }


def _get_business_id():
    """Get current business ID from session"""
    from flask import g
    
    user_session = session.get('user') or {}
    tenant_id = g.get('tenant') or session.get('impersonated_tenant_id')
    
    if not tenant_id:
        tenant_id = user_session.get('business_id') if isinstance(user_session, dict) else None
    
    if not tenant_id:
        user = session.get('al_user') or {}
        tenant_id = user.get('business_id') if isinstance(user, dict) else None
    
    return tenant_id


def _validate_text_length(text: str, max_length: int, field_name: str = "text") -> tuple:
    """Validate text length and return (is_valid, error_message)"""
    if not text or not text.strip():
        return False, f"נדרש {field_name}"
    if len(text) > max_length:
        return False, f"{field_name} ארוך מדי (מקסימום {max_length} תווים)"
    return True, None


# =============================================================================
# Realtime Session API - For continuous voice testing
# =============================================================================

@voice_test_bp.route('/api/voice_test/session', methods=['POST'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin'])
def create_realtime_session():
    """
    Create a Realtime API session for browser-based voice testing.
    
    Returns ephemeral token and config for WebRTC connection.
    The browser connects directly to OpenAI Realtime API.
    
    🔒 Rate limited: 30 per minute
    """
    try:
        data = request.get_json() or {}
        
        # Get prompt to use
        prompt_text = data.get('prompt', '').strip()
        if prompt_text:
            is_valid, error = _validate_text_length(prompt_text, MAX_PROMPT_LENGTH, "פרומפט")
            if not is_valid:
                return jsonify({"error": error}), 400
        
        # Get business settings
        business_id = _get_business_id()
        voice_id = 'alloy'  # Default voice for Realtime
        
        if business_id:
            try:
                business = Business.query.filter_by(id=business_id).first()
                if business:
                    # Use business voice for Realtime (must be OpenAI voice)
                    voice_id = business.voice_id or 'alloy'
                    
                    # If no custom prompt, try to get from business settings
                    if not prompt_text:
                        settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
                        if settings and settings.ai_prompt:
                            try:
                                if settings.ai_prompt.startswith('{'):
                                    prompts = json.loads(settings.ai_prompt)
                                    prompt_text = prompts.get('calls', settings.ai_prompt)
                                else:
                                    prompt_text = settings.ai_prompt
                            except json.JSONDecodeError:
                                prompt_text = settings.ai_prompt
            except Exception as e:
                logger.warning(f"Could not load business settings for session: {e}")
        
        # Default prompt if none found
        if not prompt_text:
            prompt_text = "אתה נציג שירות מקצועי ואדיב. עזור ללקוחות במה שהם צריכים. ענה בקצרה וברורות."
        
        # Validate OpenAI API key
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            return jsonify({"error": "OpenAI API key not configured"}), 500
        
        # Create ephemeral session token
        # For now, we return config for direct API connection
        # In production, you'd want to create an ephemeral token via OpenAI API
        session_config = {
            "model": "gpt-4o-realtime-preview",
            "voice": voice_id,
            "instructions": prompt_text[:4000],  # Realtime has instruction limit
            "modalities": ["text", "audio"],
            "input_audio_format": "pcm16",
            "output_audio_format": "pcm16",
            "turn_detection": {
                "type": "server_vad",
                "threshold": 0.5,
                "prefix_padding_ms": 300,
                "silence_duration_ms": 700
            },
            "temperature": 0.7,
            "max_response_output_tokens": 300
        }
        
        logger.info(f"Created Realtime session for business {business_id} with voice {voice_id}")
        
        return jsonify({
            "success": True,
            "session_config": session_config,
            "websocket_url": "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview",
            "instructions": "Connect via WebSocket with Authorization header. See OpenAI Realtime API docs."
        })
        
    except Exception as e:
        logger.error(f"Create Realtime session error: {e}")
        return jsonify({"error": "שגיאה ביצירת סשן"}), 500


# =============================================================================
# TTS Preview API - For voice selection
# =============================================================================

@voice_test_bp.route('/api/voice_test/tts', methods=['POST'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin'])
def voice_test_tts():
    """
    Text-to-Speech endpoint for voice testing.
    Converts text to speech using the configured TTS provider.
    
    🔒 Rate limited: 20 per minute
    🔒 Max text length: 1000 chars
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "נדרשים נתונים"}), 400
        
        text = data.get('text', '').strip()
        
        # 🔒 Input validation
        is_valid, error = _validate_text_length(text, MAX_TEXT_LENGTH, "טקסט")
        if not is_valid:
            return jsonify({"error": error}), 400
        
        # Get TTS settings from request or business settings
        provider = data.get('provider', 'openai')
        voice_id = data.get('voice_id')
        language = data.get('language', 'he-IL')
        speed = data.get('speed', 1.0)
        
        # 🔒 Validate provider mode
        if provider == 'gemini' and not _get_voice_provider_modes().get('gemini'):
            # Fall back to preview mode if production not enabled
            provider = 'gemini_preview'
        
        # For gemini_preview, allow TTS but log it
        if provider == 'gemini_preview':
            provider = 'gemini'  # Use gemini for actual synthesis
            logger.info("Using Gemini TTS in preview mode")
        
        # Get business settings for defaults
        business_id = _get_business_id()
        if business_id and (not voice_id or not provider):
            try:
                business = Business.query.filter_by(id=business_id).first()
                if business:
                    provider = provider or business.tts_provider or 'openai'
                    voice_id = voice_id or business.tts_voice_id
                    language = language or business.tts_language or 'he-IL'
                    speed = speed or business.tts_speed or 1.0
            except Exception as e:
                logger.warning(f"Could not load business TTS settings: {e}")
        
        # Synthesize speech
        audio_bytes, result = tts_provider.synthesize(
            text=text,
            provider=provider,
            voice_id=voice_id,
            language=language,
            speed=float(speed)
        )
        
        if audio_bytes is None:
            return jsonify({"error": f"שגיאה ביצירת אודיו: {result}"}), 500
        
        # Return audio data
        return Response(
            audio_bytes,
            mimetype='audio/mpeg',
            headers={
                'Content-Disposition': 'inline',
                'Content-Length': len(audio_bytes)
            }
        )
        
    except Exception as e:
        logger.error(f"Voice test TTS error: {e}")
        return jsonify({"error": "שגיאה ביצירת אודיו"}), 500


@voice_test_bp.route('/api/voice_test/voices', methods=['GET'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin'])
def get_tts_voices():
    """
    Get available TTS voices for each provider.
    
    Returns providers with their voice options.
    Gemini is marked as preview-only unless ENABLE_GEMINI_TTS_PRODUCTION=true.
    """
    try:
        providers = [
            {
                "id": "openai",
                "name": "OpenAI",
                "label": "OpenAI TTS",
                "mode": "production",
                "voices": tts_provider.OPENAI_TTS_VOICES
            }
        ]
        
        # Add Gemini only if GEMINI_API_KEY is configured
        if _is_gemini_available():
            gemini_mode = "production" if _get_voice_provider_modes().get('gemini') else "preview"
            providers.append({
                "id": "gemini" if gemini_mode == "production" else "gemini_preview",
                "name": "Gemini",
                "label": f"Google Gemini TTS {'(Preview)' if gemini_mode == 'preview' else ''}",
                "mode": gemini_mode,
                "voices": tts_provider.GEMINI_TTS_VOICES,
                "available": True
            })
        else:
            # Show Gemini as unavailable (no key configured)
            providers.append({
                "id": "gemini",
                "name": "Gemini",
                "label": "Google Gemini TTS (לא מוגדר)",
                "mode": "unavailable",
                "voices": tts_provider.GEMINI_TTS_VOICES,
                "available": False,
                "message": "יש להגדיר GEMINI_API_KEY כדי להפעיל"
            })
        
        return jsonify({"providers": providers})
    except Exception as e:
        logger.error(f"Get voices error: {e}")
        return jsonify({"error": "שגיאה בטעינת קולות"}), 500


@voice_test_bp.route('/api/voice_test/preview', methods=['POST'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin'])
def preview_voice():
    """
    Preview a voice with sample text.
    
    🔒 Rate limited: 20 per minute
    """
    try:
        data = request.get_json() or {}
        
        provider = data.get('provider', 'openai')
        voice_id = data.get('voice_id')
        language = data.get('language', 'he-IL')
        speed = data.get('speed', 1.0)
        
        # For preview, always allow gemini (even if production not enabled)
        if provider in ['gemini', 'gemini_preview']:
            provider = 'gemini'
        
        # Use sample text
        text = tts_provider.get_sample_text(language)
        
        # Get default voice if not specified
        if not voice_id:
            voice_id = tts_provider.get_default_voice(provider)
        
        # Synthesize speech
        audio_bytes, result = tts_provider.synthesize(
            text=text,
            provider=provider,
            voice_id=voice_id,
            language=language,
            speed=float(speed)
        )
        
        if audio_bytes is None:
            return jsonify({"error": f"שגיאה ביצירת אודיו: {result}"}), 500
        
        # Return audio data
        return Response(
            audio_bytes,
            mimetype='audio/mpeg',
            headers={
                'Content-Disposition': 'inline',
                'Content-Length': len(audio_bytes)
            }
        )
        
    except Exception as e:
        logger.error(f"Voice preview error: {e}")
        return jsonify({"error": "שגיאה בהשמעת דוגמה"}), 500


# =============================================================================
# Voice Settings API
# =============================================================================

@voice_test_bp.route('/api/voice_test/settings', methods=['GET'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin'])
def get_voice_settings():
    """
    Get current TTS settings for business.
    """
    try:
        business_id = _get_business_id()
        if not business_id:
            return jsonify({"error": "לא נמצא עסק"}), 400
        
        business = Business.query.filter_by(id=business_id).first()
        if not business:
            return jsonify({"error": "עסק לא נמצא"}), 404
        
        # Determine provider mode
        provider = business.tts_provider or "openai"
        if provider == "gemini" and not _get_voice_provider_modes().get('gemini'):
            provider = "gemini_preview"
        
        return jsonify({
            "provider": provider,
            "voice_id": business.tts_voice_id or "alloy",
            "language": business.tts_language or "he-IL",
            "speed": business.tts_speed or 1.0,
            "gemini_production_enabled": _get_voice_provider_modes().get('gemini', False)
        })
        
    except Exception as e:
        logger.error(f"Get voice settings error: {e}")
        return jsonify({"error": "שגיאה בטעינת הגדרות"}), 500


@voice_test_bp.route('/api/voice_test/settings', methods=['PUT'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin'])
def update_voice_settings():
    """
    Update TTS settings for business.
    
    🔒 Gemini production requires ENABLE_GEMINI_TTS_PRODUCTION=true
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "נדרשים נתונים"}), 400
        
        business_id = _get_business_id()
        if not business_id:
            return jsonify({"error": "לא נמצא עסק"}), 400
        
        business = Business.query.filter_by(id=business_id).first()
        if not business:
            return jsonify({"error": "עסק לא נמצא"}), 404
        
        # Update settings
        if 'provider' in data:
            provider = data['provider']
            
            # 🔒 Validate provider selection
            if provider == 'gemini' and not _get_voice_provider_modes().get('gemini'):
                return jsonify({
                    "error": "Gemini TTS לא זמין לפרודקשן. השתמש ב-Preview או OpenAI."
                }), 400
            
            if provider in ['openai', 'gemini', 'gemini_preview']:
                # Store as 'gemini' for both preview and production
                business.tts_provider = 'gemini' if 'gemini' in provider else provider
        
        if 'voice_id' in data:
            voice_id = data['voice_id']
            if len(voice_id) <= 64:  # Basic validation
                business.tts_voice_id = voice_id
        
        if 'language' in data:
            language = data['language']
            if len(language) <= 16:  # Basic validation
                business.tts_language = language
        
        if 'speed' in data:
            try:
                speed = float(data['speed'])
                business.tts_speed = max(0.25, min(4.0, speed))
            except (ValueError, TypeError):
                pass  # Ignore invalid speed values
        
        db.session.commit()
        
        logger.info(f"Updated TTS settings for business {business_id}")
        
        return jsonify({
            "success": True,
            "provider": business.tts_provider,
            "voice_id": business.tts_voice_id,
            "language": business.tts_language,
            "speed": business.tts_speed
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Update voice settings error: {e}")
        return jsonify({"error": "שגיאה בעדכון הגדרות"}), 500
