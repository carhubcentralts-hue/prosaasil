"""
Live Call API - Browser-based voice chat (Web App only)
Real-time voice conversation directly in browser using WebAudio

🎯 Purpose:
- Live voice chat in Prompt Studio web interface
- NO phone calls, NO Twilio, NO dialing
- Browser-only: microphone → STT → OpenAI Chat → TTS → speakers

🔒 Security:
- Authentication required on all endpoints
- Rate limiting on expensive operations
- No raw audio storage
- Clean error messages only

📋 Architecture:
- Client-side VAD (Voice Activity Detection) with WebAudio
- STT: Speech-to-text conversion
- Chat: OpenAI for brain (always)
- TTS: OpenAI or Gemini (based on saved settings)
"""
from flask import Blueprint, request, jsonify, Response, current_app, g
from server.auth_api import require_api_auth
from server.extensions import csrf
from server.utils.api_guard import api_handler
from server.models_sql import Business, BusinessSettings, db
from server.services import tts_provider
from server.services.ai_service import AIService
import logging
import os
import base64
import io

logger = logging.getLogger(__name__)

live_call_bp = Blueprint('live_call', __name__)


def _get_limiter():
    """Get rate limiter from app extensions"""
    try:
        return current_app.extensions.get('limiter')
    except RuntimeError:
        return None


# 🔒 Security: Input size limits
MAX_AUDIO_SIZE = 10 * 1024 * 1024  # 10MB max audio
MAX_TEXT_LENGTH = 2000  # Max chars for chat


@live_call_bp.route('/api/live_call/stt', methods=['POST'])
@csrf.exempt
@require_api_auth
def live_call_stt():
    """
    Speech-to-Text for live call
    
    Expected input:
        - audio: base64-encoded audio data (webm, ogg, wav, mp3)
        - format: audio format (optional, default: webm)
    
    Returns:
        - text: transcribed text
        - language: detected language
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Missing request body'}), 400
        
        audio_base64 = data.get('audio')
        audio_format = data.get('format', 'webm')
        
        if not audio_base64:
            return jsonify({'error': 'Missing audio data'}), 400
        
        # Decode audio
        try:
            audio_bytes = base64.b64decode(audio_base64)
        except Exception as e:
            logger.error(f"Failed to decode audio: {e}")
            return jsonify({'error': 'Invalid audio encoding'}), 400
        
        # Check size
        if len(audio_bytes) > MAX_AUDIO_SIZE:
            return jsonify({'error': 'Audio too large'}), 413
        
        # Call OpenAI Whisper for STT
        from openai import OpenAI
        
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Create file-like object for Whisper API
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = f"audio.{audio_format}"
        
        # Transcribe
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="he"  # Hebrew
        )
        
        text = transcript.text.strip()
        
        logger.info(f"[LIVE_CALL][STT] Transcribed: {text[:100]}...")
        
        return jsonify({
            'text': text,
            'language': 'he'
        })
        
    except Exception as e:
        logger.exception("[LIVE_CALL][STT] Error")
        return jsonify({'error': 'STT processing failed'}), 500


@live_call_bp.route('/api/live_call/chat', methods=['POST'])
@csrf.exempt
@require_api_auth
def live_call_chat():
    """
    Chat processing for live call
    Uses the selected ai_provider for LLM (OpenAI or Gemini)
    
    Expected input:
        - text: user's transcribed text
        - conversation_history: array of previous messages (optional)
    
    Returns:
        - response: AI's text response
        - conversation_id: session identifier
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Missing request body'}), 400
        
        text = data.get('text', '').strip()
        conversation_history = data.get('conversation_history', [])
        
        if not text:
            return jsonify({'error': 'Missing text'}), 400
        
        if len(text) > MAX_TEXT_LENGTH:
            return jsonify({'error': 'Text too long'}), 413
        
        # Get business settings for prompt and provider
        business_id = g.business_id
        if not business_id:
            return jsonify({'error': 'missing_business_id'}), 401
        
        business = db.session.query(Business).filter_by(id=business_id).first()
        if not business:
            return jsonify({'error': 'Business not found'}), 404
        
        # Get AI provider selection
        ai_provider = getattr(business, 'ai_provider', 'openai') or 'openai'
        
        # Get AI service with business prompt
        ai_service = AIService(business_id=business_id)
        
        # Build messages from conversation history
        messages = []
        
        # Add system prompt (from saved business settings)
        system_prompt = ai_service.get_system_prompt(channel='calls')
        if system_prompt:
            messages.append({
                'role': 'system',
                'content': system_prompt
            })
        
        # Add conversation history
        for msg in conversation_history:
            messages.append(msg)
        
        # Add current user message
        messages.append({
            'role': 'user',
            'content': text
        })
        
        # Call LLM based on ai_provider
        if ai_provider == 'gemini':
            # Use Gemini for LLM
            try:
                from google import genai
                
                gemini_api_key = os.getenv('GEMINI_API_KEY')
                if not gemini_api_key:
                    logger.error("[LIVE_CALL][CHAT] Gemini requested but GEMINI_API_KEY not set")
                    return jsonify({'error': 'Gemini LLM unavailable - API key not configured'}), 503
                
                client = genai.Client(api_key=gemini_api_key)
                
                # Convert messages to Gemini format
                # Gemini expects a single prompt string, so combine messages
                prompt_parts = []
                for msg in messages:
                    role = msg.get('role', 'user')
                    content = msg.get('content', '')
                    if role == 'system':
                        prompt_parts.append(f"System: {content}")
                    elif role == 'user':
                        prompt_parts.append(f"User: {content}")
                    elif role == 'assistant':
                        prompt_parts.append(f"Assistant: {content}")
                
                full_prompt = "\n".join(prompt_parts)
                
                response = client.models.generate_content(
                    model="gemini-2.0-flash-exp",
                    contents=full_prompt
                )
                
                ai_response = response.text.strip()
                
            except Exception as gemini_err:
                logger.error(f"[LIVE_CALL][CHAT] Gemini error: {gemini_err}")
                return jsonify({'error': 'Gemini LLM processing failed'}), 500
        else:
            # Use OpenAI for LLM (default)
            from openai import OpenAI
            
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",  # Fast and efficient model
                messages=messages,
                max_tokens=500,
                temperature=0.7
            )
            
            ai_response = response.choices[0].message.content.strip()
        
        logger.info(f"[LIVE_CALL][CHAT] Provider: {ai_provider}, User: {text[:50]}... → AI: {ai_response[:50]}...")
        
        return jsonify({
            'response': ai_response,
            'conversation_id': f"live_call_{business_id}"
        })
        
    except Exception as e:
        logger.exception("[LIVE_CALL][CHAT] Error")
        return jsonify({'error': 'Chat processing failed'}), 500


@live_call_bp.route('/api/live_call/tts', methods=['POST'])
@csrf.exempt
@require_api_auth
def live_call_tts():
    """
    Text-to-Speech for live call
    Uses saved voice settings (OpenAI or Gemini)
    
    Expected input:
        - text: text to synthesize
    
    Returns:
        - audio: binary audio data (MP3)
        - Content-Type: audio/mpeg
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Missing request body'}), 400
        
        text = data.get('text', '').strip()
        
        if not text:
            return jsonify({'error': 'Missing text'}), 400
        
        if len(text) > MAX_TEXT_LENGTH:
            return jsonify({'error': 'Text too long'}), 413
        
        # Get business settings for voice configuration
        business_id = g.business_id
        if not business_id:
            return jsonify({'error': 'missing_business_id'}), 401
        
        business = db.session.query(Business).filter_by(id=business_id).first()
        if not business:
            return jsonify({'error': 'Business not found'}), 404
        
        # Get voice settings from business
        # Voice settings are determined by ai_provider (unified provider selection)
        ai_provider = getattr(business, 'ai_provider', 'openai') or 'openai'
        voice_name = getattr(business, 'voice_name', None)
        
        # Fallback to legacy fields if new fields not set
        if not voice_name:
            voice_name = getattr(business, 'tts_voice_id', None) or getattr(business, 'voice_id', 'alloy') or 'alloy'
        
        speed = float(getattr(business, 'tts_speed', 1.0) or 1.0)
        language = getattr(business, 'tts_language', 'he-IL') or 'he-IL'
        
        # Check if Gemini is requested but not available
        if ai_provider == 'gemini' and not tts_provider.is_gemini_available():
            logger.error("[LIVE_CALL][TTS] Gemini requested but GEMINI_API_KEY not set")
            return jsonify({'error': 'Gemini TTS unavailable - API key not configured'}), 503
        
        # Synthesize speech using ai_provider
        audio_bytes, content_type_or_error = tts_provider.synthesize(
            text=text,
            provider=ai_provider,
            voice_id=voice_name,
            language=language,
            speed=speed
        )
        
        if audio_bytes is None:
            # Error occurred
            logger.error(f"[LIVE_CALL][TTS] Synthesis failed: {content_type_or_error}")
            return jsonify({'error': content_type_or_error}), 500
        
        logger.info(f"[LIVE_CALL][TTS] Synthesized {len(audio_bytes)} bytes with {ai_provider}/{voice_name}")
        
        # Return audio as binary response
        return Response(
            audio_bytes,
            mimetype=content_type_or_error,
            headers={
                'Content-Disposition': 'inline; filename="response.mp3"',
                'Cache-Control': 'no-cache'
            }
        )
        
    except Exception as e:
        logger.exception("[LIVE_CALL][TTS] Error")
        return jsonify({'error': 'TTS processing failed'}), 500


# Register blueprint in app factory
def register_live_call_routes(app):
    """Register live call blueprint with Flask app"""
    app.register_blueprint(live_call_bp)
    logger.info("✅ Live call routes registered")
