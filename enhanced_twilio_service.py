"""
Enhanced Twilio Service with Advanced Call Handling
שירות Twilio מתקדם עם טיפול מלא בשיחות
"""

import os
import logging
import time
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from twilio.rest import Client
from twilio.twiml import TwiML
from models import Business, CallLog
from enhanced_ai_service import enhanced_ai_service
from app import db

logger = logging.getLogger(__name__)

class EnhancedTwilioService:
    """שירות Twilio מתקדם עם מעקב מלא אחר שיחות"""
    
    def __init__(self):
        self.client = Client(
            os.environ.get('TWILIO_ACCOUNT_SID'),
            os.environ.get('TWILIO_AUTH_TOKEN')
        )
        self.phone_number = os.environ.get('TWILIO_PHONE_NUMBER')
        self.recording_callbacks = {}
        self.call_timeouts = 600  # 10 דקות מקסימום לשיחה
        
    def handle_incoming_call(self, request_data: Dict[str, Any]) -> str:
        """טיפול בשיחה נכנסת עם יצירת TwiML מתקדם"""
        
        try:
            from_number = request_data.get('From', '')
            to_number = request_data.get('To', '')
            call_sid = request_data.get('CallSid', '')
            
            # מציאת עסק
            business = Business.query.filter_by(phone_number=to_number).first()
            if not business:
                logger.error(f"No business found for number {to_number}")
                return self._create_error_twiml("מצטער, המספר לא זמין כרגע.")
            
            # בדיקת הרשאות
            if not getattr(business, 'phone_permissions', True):
                logger.warning(f"Phone calls not permitted for business {business.id}")
                return self._create_error_twiml("שירות השיחות זמנית לא זמין.")
            
            # יצירת רשומת שיחה
            call_log = self._create_call_log(
                business_id=business.id,
                from_number=from_number,
                to_number=to_number,
                call_sid=call_sid,
                call_status='in-progress'
            )
            
            # הקלטת callback
            self.recording_callbacks[call_sid] = {
                'business_id': business.id,
                'call_log_id': call_log.id,
                'start_time': time.time()
            }
            
            # בניית TwiML מתקדם
            return self._build_greeting_twiml(business, call_sid)
            
        except Exception as e:
            logger.error(f"Error handling incoming call: {e}")
            return self._create_error_twiml("מצטער, אירעה שגיאה זמנית.")
    
    def handle_recording_callback(self, request_data: Dict[str, Any]) -> str:
        """טיפול ב-callback של הקלטה - FIXED COMPLETE IMPLEMENTATION"""
        try:
            call_sid = request_data.get('CallSid', '')
            recording_url = request_data.get('RecordingUrl', '')
            recording_duration = request_data.get('RecordingDuration', '0')
            
            logger.info(f"📞 Recording callback: {call_sid}, duration: {recording_duration}s")
            
            if not recording_url or not call_sid:
                logger.error("Missing recording URL or CallSid")
                return self._create_error_twiml("נתונים חסרים")
            
            # בדיקת משך הקלטה
            duration = int(recording_duration) if recording_duration.isdigit() else 0
            if duration < 1:
                logger.warning(f"Recording too short: {duration}s")
                return self._create_retry_twiml("דברו בבהירות אחרי הצפצוף")
            
            # עיבוד ההקלטה
            processing_result = self._process_recording(
                recording_url, 
                call_sid,
                self.recording_callbacks.get(call_sid, {}).get('business_id', 1),
                self.recording_callbacks.get(call_sid, {}).get('call_log_id', 1)
            )
            
            if processing_result.get('success'):
                ai_response = processing_result.get('ai_response', 'תודה על הפנייה')
                
                # בדיקה אם לסיים השיחה
                if processing_result.get('end_call', False):
                    return self._create_goodbye_twiml(ai_response)
                else:
                    return self._create_continue_twiml(ai_response)
            else:
                return self._create_retry_twiml(processing_result.get('message', 'לא הבנתי, תוכלו לחזור?'))
                
        except Exception as e:
            logger.error(f"Recording callback error: {e}")
            return self._create_error_twiml("שגיאה טכנית")
            
    def _create_continue_twiml(self, ai_response: str) -> str:
        """יצירת TwiML להמשך השיחה"""
        from hebrew_tts import HebrewTTSService
        tts_service = HebrewTTSService()
        response_audio = tts_service.synthesize_hebrew_audio(ai_response)
        
        base_url = "https://your-domain.replit.dev"  # Replace with actual domain
        
        twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{base_url}/static/voice_responses/{response_audio}</Play>
    <Pause length="1"/>
    <Say voice="alice" language="he-IL">יש עוד משהו?</Say>
    <Record 
        maxLength="10" 
        timeout="4" 
        playBeep="true"
        action="/webhook/handle_recording" 
        method="POST"
        transcribe="false"
        trim="do-not-trim"
        finishOnKey="*" />
</Response>'''
        return twiml
        
    def _create_retry_twiml(self, message: str) -> str:
        """TwiML לנסיון חוזר"""
        twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice" language="he-IL">{message}</Say>
    <Record 
        maxLength="10" 
        timeout="4" 
        playBeep="true"
        action="/webhook/handle_recording" 
        method="POST"
        transcribe="false"
        trim="do-not-trim"
        finishOnKey="*" />
</Response>'''
        return twiml
        
    def _create_goodbye_twiml(self, message: str) -> str:
        """TwiML לסיום השיחה"""
        twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice" language="he-IL">{message}</Say>
    <Say voice="alice" language="he-IL">תודה על השיחה, יום טוב</Say>
    <Hangup/>
</Response>'''
        return twiml
        
    def _create_error_twiml(self, message: str) -> str:
        """TwiML לשגיאה"""
        twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice" language="he-IL">{message}</Say>
    <Hangup/>
</Response>'''
        return twiml
        
    def _process_recording(self, recording_url: str, call_sid: str, business_id: int, call_log_id: int) -> dict:
        """עיבוד ההקלטה עם Whisper ו-AI"""
        try:
            from whisper_handler import HebrewWhisperHandler
            from ai_service import AIService
            
            # תמלול עם Whisper
            whisper_handler = HebrewWhisperHandler()
            transcription = whisper_handler.transcribe_audio(recording_url)
            
            if not transcription or len(transcription.strip()) < 3:
                return {'success': False, 'message': 'לא הבנתי, תוכלו לחזור?'}
            
            # עיבוד עם AI
            ai_service = AIService()
            ai_response = ai_service.process_conversation(
                user_message=transcription,
                business_id=business_id,
                conversation_context={}
            )
            
            # בדיקה אם לסיים השיחה
            end_call = any(keyword in transcription.lower() for keyword in ['תודה', 'סיימתי', 'להתראות', 'ביי'])
            
            return {
                'success': True,
                'ai_response': ai_response,
                'transcription': transcription,
                'end_call': end_call
            }
            
        except Exception as e:
            logger.error(f"Recording processing error: {e}")
            return {'success': False, 'message': 'שגיאה בעיבוד ההקלטה'}
            
    def _build_greeting_twiml(self, business: Any, call_sid: str) -> str:
        """בניית TwiML לברכה ראשונית"""
        greeting = business.greeting_message or "שלום, איך אפשר לעזור?"
        
        twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice" language="he-IL">{greeting}</Say>
    <Record 
        maxLength="10" 
        timeout="4" 
        playBeep="true"
        action="/webhook/handle_recording" 
        method="POST"
        transcribe="false"
        trim="do-not-trim"
        finishOnKey="*" />
</Response>'''
        return twiml
        
    def _create_call_log(self, business_id: int, from_number: str, to_number: str, call_sid: str, call_status: str) -> Any:
        """יצירת רשומת שיחה"""
        try:
            from models import CallLog
            from datetime import datetime
            
            call_log = CallLog(
                business_id=business_id,
                from_number=from_number,
                to_number=to_number,
                call_sid=call_sid,
                call_status=call_status,
                created_at=datetime.utcnow()
            )
            
            db.session.add(call_log)
            db.session.commit()
            
            return call_log
            
        except Exception as e:
            logger.error(f"Error creating call log: {e}")
            return None
                logger.warning(f"Unknown call SID: {call_sid}")
                return self._create_error_twiml("תקלה במערכת. נסה שוב.")
            
            callback_data = self.recording_callbacks[call_sid]
            
            # בדיקת timeout
            if time.time() - callback_data['start_time'] > self.call_timeouts:
                logger.warning(f"Call timeout for {call_sid}")
                del self.recording_callbacks[call_sid]
                return self._create_hangup_twiml("השיחה הסתיימה עקב חריגה מזמן מותר.")
            
            # בדיקת URL תקין
            if not recording_url or len(recording_url) < 10:
                logger.warning(f"Invalid recording URL for {call_sid}")
                return self._create_retry_twiml("לא שמעתי בבירור. תוכל לחזור?")
            
            # עיבוד ההקלטה
            processing_result = self._process_recording(
                recording_url=recording_url,
                business_id=callback_data['business_id'],
                call_log_id=callback_data['call_log_id']
            )
            
            if not processing_result['success']:
                # ניסיון חוזר או סיום
                if processing_result.get('retry', False):
                    return self._create_retry_twiml(processing_result['message'])
                else:
                    return self._create_hangup_twiml(processing_result['message'])
            
            # יצירת TwiML עם התגובה
            return self._create_response_twiml(
                response_text=processing_result['ai_response'],
                call_sid=call_sid,
                continue_conversation=processing_result.get('continue', True)
            )
            
        except Exception as e:
            logger.error(f"Error in recording callback: {e}")
            return self._create_error_twiml("אירעה שגיאה. השיחה תסתיים.")
    
    def _process_recording(self, recording_url: str, business_id: int, 
                          call_log_id: int) -> Dict[str, Any]:
        """עיבוד הקלטה עם Whisper ו-AI"""
        
        try:
            # תמלול עם Whisper
            transcription_result = self._transcribe_with_whisper(recording_url)
            
            if not transcription_result['success']:
                return {
                    'success': False,
                    'retry': True,
                    'message': 'לא שמעתי בבירור. תוכל לדבר שוב?'
                }
            
            user_message = transcription_result['text']
            
            # בדיקת תוכן התמלול
            if len(user_message.strip()) < 3:
                return {
                    'success': False,
                    'retry': True,
                    'message': 'דבר בבהירות אחרי הצפצוף, בבקשה.'
                }
            
            # עיבוד עם AI
            ai_result = enhanced_ai_service.process_conversation(
                user_message=user_message,
                business_id=business_id,
                conversation_id=f"call_{call_log_id}"
            )
            
            if not ai_result['success']:
                return {
                    'success': False,
                    'retry': False,
                    'message': 'מצטער, אני לא זמין כרגע. תתקשר מאוחר יותר.'
                }
            
            # עדכון רשומת שיחה
            self._update_call_log(
                call_log_id=call_log_id,
                user_message=user_message,
                ai_response=ai_result['response'],
                intent=ai_result.get('intent', 'unknown')
            )
            
            # בדיקה האם לסיים שיחה
            should_end = self._should_end_call(
                user_message, ai_result.get('intent', '')
            )
            
            return {
                'success': True,
                'ai_response': ai_result['response'],
                'continue': not should_end,
                'intent': ai_result.get('intent')
            }
            
        except Exception as e:
            logger.error(f"Error processing recording: {e}")
            return {
                'success': False,
                'retry': False,
                'message': 'אירעה שגיאה במערכת. השיחה תסתיים.'
            }
    
    def _transcribe_with_whisper(self, recording_url: str) -> Dict[str, Any]:
        """תמלול עם Whisper"""
        
        try:
            # הורדת הקלטה זמנית
            import requests
            import tempfile
            
            response = requests.get(recording_url, timeout=30)
            if response.status_code != 200:
                return {'success': False, 'error': 'Failed to download recording'}
            
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_file.write(response.content)
                temp_file.flush()
                
                # תמלול עם Whisper
                from openai import OpenAI
                client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
                
                with open(temp_file.name, 'rb') as audio_file:
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language="he"
                    )
                
                # מחיקת קובץ זמני
                os.unlink(temp_file.name)
                
                logger.info(f"Whisper transcription: {transcript.text}")
                
                return {
                    'success': True,
                    'text': transcript.text.strip()
                }
                
        except Exception as e:
            logger.error(f"Whisper transcription error: {e}")
            return {'success': False, 'error': str(e)}
    
    def _build_greeting_twiml(self, business: Business, call_sid: str) -> str:
        """בניית TwiML ברכה"""
        
        greeting_text = f"שלום, התקשרת ל{business.name}. אשמח לעזור לך."
        
        response = TwiML()
        response.say(greeting_text, language='he-IL', voice='Polly.Ayelet')
        response.record(
            max_length=30,
            timeout=10,
            play_beep=True,
            transcribe=False,
            action=f"/webhook/handle_recording",
            method='POST'
        )
        
        return str(response)
    
    def _create_response_twiml(self, response_text: str, call_sid: str, 
                             continue_conversation: bool = True) -> str:
        """יצירת TwiML תגובה"""
        
        response = TwiML()
        response.say(response_text, language='he-IL', voice='Polly.Ayelet')
        
        if continue_conversation:
            response.record(
                max_length=30,
                timeout=10,
                play_beep=True,
                transcribe=False,
                action="/webhook/handle_recording",
                method='POST'
            )
        else:
            response.say("תודה על השיחה. יום טוב!", language='he-IL', voice='Polly.Ayelet')
            response.hangup()
        
        return str(response)
    
    def _create_retry_twiml(self, message: str) -> str:
        """TwiML לניסיון חוזר"""
        
        response = TwiML()
        response.say(message, language='he-IL', voice='Polly.Ayelet')
        response.record(
            max_length=30,
            timeout=10,
            play_beep=True,
            transcribe=False,
            action="/webhook/handle_recording",
            method='POST'
        )
        
        return str(response)
    
    def _create_error_twiml(self, message: str) -> str:
        """TwiML שגיאה"""
        
        response = TwiML()
        response.say(message, language='he-IL', voice='Polly.Ayelet')
        response.hangup()
        
        return str(response)
    
    def _create_hangup_twiml(self, message: str) -> str:
        """TwiML סיום שיחה"""
        
        response = TwiML()
        response.say(message, language='he-IL', voice='Polly.Ayelet')
        response.hangup()
        
        return str(response)
    
    def _should_end_call(self, user_message: str, intent: str) -> bool:
        """בדיקה האם לסיים שיחה"""
        
        goodbye_keywords = [
            'תודה', 'תודה רבה', 'להתראות', 'שלום', 'סיימתי', 
            'זה הכל', 'די', 'תסיים', 'סגור'
        ]
        
        message_lower = user_message.lower()
        
        # בדיקת מילות פרידה
        if any(keyword in message_lower for keyword in goodbye_keywords):
            return True
        
        # בדיקת intent
        if intent in ['goodbye', 'end_call', 'completed']:
            return True
        
        return False
    
    def _create_call_log(self, business_id: int, from_number: str, 
                        to_number: str, call_sid: str, call_status: str) -> CallLog:
        """יצירת רשומת שיחה"""
        
        call_log = CallLog(
            business_id=business_id,
            from_number=from_number,
            to_number=to_number,
            call_sid=call_sid,
            call_status=call_status,
            start_time=datetime.utcnow()
        )
        
        db.session.add(call_log)
        db.session.commit()
        
        return call_log
    
    def _update_call_log(self, call_log_id: int, user_message: str, 
                        ai_response: str, intent: str):
        """עדכון רשומת שיחה"""
        
        try:
            call_log = CallLog.query.get(call_log_id)
            if call_log:
                call_log.transcript = user_message
                call_log.ai_response = ai_response
                call_log.intent_detected = intent
                call_log.end_time = datetime.utcnow()
                db.session.commit()
                
        except Exception as e:
            logger.error(f"Failed to update call log: {e}")
            db.session.rollback()
    
    def send_alert(self, message: str, business_id: int):
        """שליחת התרעה לעסק"""
        
        try:
            business = Business.query.get(business_id)
            if business and business.alert_phone:
                
                self.client.messages.create(
                    body=f"התרעה ממערכת שיחות: {message}",
                    from_=self.phone_number,
                    to=business.alert_phone
                )
                
                logger.info(f"Alert sent to business {business_id}")
                
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
    
    def cleanup_old_callbacks(self, hours: int = 2):
        """ניקוי callbacks ישנים"""
        
        current_time = time.time()
        cutoff = current_time - (hours * 3600)
        
        old_callbacks = [
            call_sid for call_sid, data in self.recording_callbacks.items()
            if data['start_time'] < cutoff
        ]
        
        for call_sid in old_callbacks:
            del self.recording_callbacks[call_sid]
        
        if old_callbacks:
            logger.info(f"Cleaned up {len(old_callbacks)} old callbacks")

# יצירת instance גלובלי
enhanced_twilio_service = EnhancedTwilioService()