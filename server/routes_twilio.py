"""
AgentLocator v42 - Twilio Routes
TwiML endpoints with proper Hebrew support and recording parameters
"""

from flask import Blueprint, request, Response
from twilio.twiml.voice_response import VoiceResponse
import logging

logger = logging.getLogger(__name__)
twilio_bp = Blueprint('twilio', __name__)

@twilio_bp.route('/incoming_call', methods=['POST'])
def incoming_call():
    """עיבוד שיחה נכנסת עם TwiML נכון"""
    try:
        # קבלת host מה-request
        host = request.headers.get('Host', 'localhost:5000')
        base_url = f"https://{host}" if 'replit' in host else f"http://{host}"
        
        # יצירת TwiML response
        resp = VoiceResponse()
        
        # השמעת ברכה בעברית
        resp.say("שלום! ברוכים הבאים לשי דירות ומשרדים. אנא השאירו הודעה אחרי הצפצוף.", 
                language="he-IL", voice="female")
        
        # הקלטה עם הפרמטרים הנכונים מ-AgentLocator v42
        resp.record(
            finish_on_key="*",  # סיום הקלטה עם *
            timeout=5,          # 5 שניות timeout
            max_length=30,      # מקסימום 30 שניות
            play_beep=True,     # צפצוף לפני הקלטה
            action=f"{base_url}/webhook/handle_recording",
            method="POST"
        )
        
        # fallback במידה וההקלטה לא עובדת
        resp.say("לא הצלחנו לקלוט את ההודעה. אנא נסו שוב מאוחר יותר.", 
                language="he-IL")
        
        logger.info("✅ TwiML generated successfully with Hebrew greeting")
        return Response(str(resp), mimetype="text/xml")
        
    except Exception as e:
        logger.error(f"Error in incoming_call: {e}")
        # TwiML פשוט במקרה של שגיאה
        resp = VoiceResponse()
        resp.say("מערכת לא זמינה כרגע. אנא נסו שוב מאוחר יותר.", language="he-IL")
        return Response(str(resp), mimetype="text/xml")

@twilio_bp.route('/handle_recording', methods=['POST'])
def handle_recording():
    """עיבוד הקלטה עם Whisper Hebrew + GPT + TTS"""
    try:
        # קבלת URL של ההקלטה
        recording_url = request.form.get('RecordingUrl', '')
        if not recording_url:
            logger.warning("No recording URL provided")
            return generate_fallback_response("לא התקבלה הקלטה")
        
        # Whisper Hebrew transcription
        try:
            from whisper_handler import transcribe_hebrew
            transcription = transcribe_hebrew(recording_url)
            if not transcription or len(transcription.strip()) < 3:
                return generate_fallback_response("לא הצלחנו להבין את ההודעה")
        except Exception as e:
            logger.error(f"Whisper transcription failed: {e}")
            return generate_fallback_response("שגיאה בזיהוי דיבור")
        
        # GPT response generation
        try:
            from ai_service import generate_response
            ai_response = generate_response(transcription, "real_estate")
        except Exception as e:
            logger.error(f"AI response generation failed: {e}")
            ai_response = "תודה על פנייתכם. נחזור אליכם בהקדם."
        
        # Hebrew TTS generation
        try:
            from tts_service import generate_hebrew_audio
            audio_url = generate_hebrew_audio(ai_response)
        except Exception as e:
            logger.error(f"TTS generation failed: {e}")
            # Fallback to text response
            return generate_fallback_response(ai_response)
        
        # TwiML response with generated audio
        resp = VoiceResponse()
        resp.play(audio_url)
        resp.say("תודה רבה. נחזור אליכם בהקדם.", language="he-IL")
        
        logger.info(f"✅ Recording processed successfully. Transcription: {transcription[:50]}...")
        return Response(str(resp), mimetype="text/xml")
        
    except Exception as e:
        logger.error(f"Error in handle_recording: {e}")
        return generate_fallback_response("שגיאה בעיבוד ההקלטה")

@twilio_bp.route('/call_status', methods=['POST'])
def call_status():
    """עדכון סטטוס שיחה - תמיד מחזיר 200"""
    try:
        call_sid = request.form.get('CallSid', '')
        call_status = request.form.get('CallStatus', '')
        
        logger.info(f"Call status update: {call_sid} -> {call_status}")
        
        # שמירה למסד נתונים אם נדרש
        if call_status in ['completed', 'busy', 'no-answer', 'failed']:
            try:
                # כאן נוכל לשמור למסד נתונים
                pass
            except Exception as e:
                logger.warning(f"Failed to save call status: {e}")
        
        return ("", 200)  # תמיד 200 כמו ב-AgentLocator v42
        
    except Exception as e:
        logger.error(f"Error in call_status: {e}")
        return ("", 200)  # תמיד 200 גם במקרה של שגיאה

def generate_fallback_response(message: str) -> Response:
    """יצירת תגובת fallback עם TwiML"""
    resp = VoiceResponse()
    resp.say(message, language="he-IL", voice="female")
    resp.say("תודה שפניתם אלינו.", language="he-IL")
    return Response(str(resp), mimetype="text/xml")