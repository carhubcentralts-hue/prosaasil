"""
Voice Test API - Endpoints for prompt voice testing
Provides STT, Chat, and TTS endpoints for browser-based voice testing
"""
from flask import Blueprint, request, jsonify, session, Response
from server.routes_admin import require_api_auth
from server.extensions import csrf
from server.utils.api_guard import api_handler
from server.models_sql import Business, BusinessSettings, db
from server.services import tts_provider
import logging
import io
import os

logger = logging.getLogger(__name__)

voice_test_bp = Blueprint('voice_test', __name__)


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


@voice_test_bp.route('/api/voice_test/stt', methods=['POST'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin'])
def voice_test_stt():
    """
    Speech-to-Text endpoint for voice testing
    Accepts multipart audio and returns transcribed text
    """
    try:
        # Check if audio file was uploaded
        if 'audio' not in request.files:
            return jsonify({"error": "נדרש קובץ אודיו"}), 400
        
        audio_file = request.files['audio']
        audio_data = audio_file.read()
        
        if len(audio_data) < 100:
            return jsonify({"error": "קובץ אודיו קצר מדי"}), 400
        
        # Use OpenAI Whisper for STT
        try:
            from openai import OpenAI
            
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            
            # Create a file-like object
            audio_io = io.BytesIO(audio_data)
            audio_io.name = "audio.webm"  # Whisper needs a file extension
            
            # Transcribe with Whisper
            transcription = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_io,
                language="he"
            )
            
            text = transcription.text.strip()
            
            logger.info(f"Voice test STT: Transcribed {len(text)} chars")
            
            return jsonify({
                "text": text,
                "language": "he"
            })
            
        except Exception as e:
            logger.error(f"STT error: {e}")
            return jsonify({"error": f"שגיאה בתמלול: {str(e)}"}), 500
        
    except Exception as e:
        logger.error(f"Voice test STT error: {e}")
        return jsonify({"error": "שגיאה בעיבוד האודיו"}), 500


@voice_test_bp.route('/api/voice_test/chat', methods=['POST'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin'])
def voice_test_chat():
    """
    Chat endpoint for voice testing
    Sends user message to AI with the current prompt and returns response
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "נדרשים נתונים"}), 400
        
        user_message = data.get('message', '').strip()
        if not user_message:
            return jsonify({"error": "נדרשת הודעה"}), 400
        
        conversation_history = data.get('history', [])
        prompt_text = data.get('prompt', '')
        
        # Get business ID for prompt lookup
        business_id = _get_business_id()
        
        # If no prompt provided, try to get from business settings
        if not prompt_text and business_id:
            try:
                settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
                if settings and settings.ai_prompt:
                    import json
                    try:
                        if settings.ai_prompt.startswith('{'):
                            prompts = json.loads(settings.ai_prompt)
                            prompt_text = prompts.get('calls', settings.ai_prompt)
                        else:
                            prompt_text = settings.ai_prompt
                    except:
                        prompt_text = settings.ai_prompt
            except Exception as e:
                logger.warning(f"Could not load business prompt: {e}")
        
        # Default prompt if none found
        if not prompt_text:
            prompt_text = "אתה נציג שירות מקצועי ואדיב. עזור ללקוחות במה שהם צריכים. ענה בקצרה וברורות."
        
        # Build messages for OpenAI
        messages = [
            {"role": "system", "content": prompt_text}
        ]
        
        # Add conversation history
        for turn in conversation_history[-10:]:  # Limit to last 10 turns
            role = turn.get('role', 'user')
            content = turn.get('content', '')
            if role in ['user', 'assistant'] and content:
                messages.append({"role": role, "content": content})
        
        # Add current user message
        messages.append({"role": "user", "content": user_message})
        
        # Call OpenAI Chat API
        try:
            from openai import OpenAI
            
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=300,
                temperature=0.7
            )
            
            reply_text = response.choices[0].message.content.strip()
            
            logger.info(f"Voice test chat: Response {len(reply_text)} chars")
            
            return jsonify({
                "reply": reply_text
            })
            
        except Exception as e:
            logger.error(f"Chat API error: {e}")
            return jsonify({"error": f"שגיאה בתגובת AI: {str(e)}"}), 500
        
    except Exception as e:
        logger.error(f"Voice test chat error: {e}")
        return jsonify({"error": "שגיאה בעיבוד ההודעה"}), 500


@voice_test_bp.route('/api/voice_test/tts', methods=['POST'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin'])
def voice_test_tts():
    """
    Text-to-Speech endpoint for voice testing
    Converts text to speech using the configured TTS provider
    Returns audio/mpeg data
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "נדרשים נתונים"}), 400
        
        text = data.get('text', '').strip()
        if not text:
            return jsonify({"error": "נדרש טקסט"}), 400
        
        # Get TTS settings from request or business settings
        provider = data.get('provider', 'openai')
        voice_id = data.get('voice_id')
        language = data.get('language', 'he-IL')
        speed = data.get('speed', 1.0)
        
        # Get business settings for defaults
        business_id = _get_business_id()
        if business_id and (not voice_id or provider is None):
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
    Get available TTS voices for each provider
    """
    try:
        return jsonify({
            "providers": [
                {
                    "id": "openai",
                    "name": "OpenAI",
                    "label": "OpenAI TTS",
                    "voices": tts_provider.OPENAI_TTS_VOICES
                },
                {
                    "id": "gemini",
                    "name": "Gemini",
                    "label": "Google Gemini TTS",
                    "voices": tts_provider.GEMINI_TTS_VOICES
                }
            ]
        })
    except Exception as e:
        logger.error(f"Get voices error: {e}")
        return jsonify({"error": "שגיאה בטעינת קולות"}), 500


@voice_test_bp.route('/api/voice_test/preview', methods=['POST'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin'])
def preview_voice():
    """
    Preview a voice with sample text
    """
    try:
        data = request.get_json() or {}
        
        provider = data.get('provider', 'openai')
        voice_id = data.get('voice_id')
        language = data.get('language', 'he-IL')
        speed = data.get('speed', 1.0)
        
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


@voice_test_bp.route('/api/voice_test/settings', methods=['GET'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin'])
def get_voice_settings():
    """
    Get current TTS settings for business
    """
    try:
        business_id = _get_business_id()
        if not business_id:
            return jsonify({"error": "לא נמצא עסק"}), 400
        
        business = Business.query.filter_by(id=business_id).first()
        if not business:
            return jsonify({"error": "עסק לא נמצא"}), 404
        
        return jsonify({
            "provider": business.tts_provider or "openai",
            "voice_id": business.tts_voice_id or "alloy",
            "language": business.tts_language or "he-IL",
            "speed": business.tts_speed or 1.0
        })
        
    except Exception as e:
        logger.error(f"Get voice settings error: {e}")
        return jsonify({"error": "שגיאה בטעינת הגדרות"}), 500


@voice_test_bp.route('/api/voice_test/settings', methods=['PUT'])
@csrf.exempt
@require_api_auth(['system_admin', 'owner', 'admin'])
def update_voice_settings():
    """
    Update TTS settings for business
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
            if provider in ['openai', 'gemini']:
                business.tts_provider = provider
        
        if 'voice_id' in data:
            business.tts_voice_id = data['voice_id']
        
        if 'language' in data:
            business.tts_language = data['language']
        
        if 'speed' in data:
            speed = float(data['speed'])
            business.tts_speed = max(0.25, min(4.0, speed))
        
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
