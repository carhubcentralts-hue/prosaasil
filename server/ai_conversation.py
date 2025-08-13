"""
Hebrew AI Conversation Handler
מטפל בשיחות AI בעברית עם תמלול, תשובות, ושמירה במסד נתונים
"""

import os
import requests
import openai
from datetime import datetime
from whisper_handler import transcribe_hebrew
from hebrew_tts import HebrewTTSService
import logging
import json

logger = logging.getLogger(__name__)

# Fallback data for when database is not available
FALLBACK_BUSINESS_DATA = {
    'name': 'שי דירות ומשרדים בע״מ',
    'type': 'real_estate',
    'ai_prompt': None,
    'greeting': None
}

class HebrewAIConversation:
    def __init__(self):
        self.openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.tts_service = HebrewTTSService()
        
    def get_business_context(self, business_id: int = 1):
        """קבלת הקשר העסק לתשובות AI"""
        # Use fallback data for now since database models are not available
        return {
            'name': FALLBACK_BUSINESS_DATA['name'],
            'type': FALLBACK_BUSINESS_DATA['type'],
            'ai_prompt': self.get_default_prompt('real_estate'),
            'greeting': FALLBACK_BUSINESS_DATA['greeting']
        }
    
    def get_default_prompt(self, business_type: str) -> str:
        """פרומפט ברירת מחדל לפי סוג העסק"""
        prompts = {
            'real_estate': """אתה סוכן נדל"ן מקצועי וחברותי של שי דירות ומשרדים בע"מ.
אתה מומחה בשוק הנדל"ן הישראלי, מכיר מחירים עדכניים ואזורים טובים.
תפקידך לעזור ללקוחות למצוא נכסים מתאימים, להעריך נכסים, ולתת ייעוץ נדל"ן מקצועי.
התנהג בצורה חמה ומקצועית. שאל שאלות רלוונטיות כמו: סוג הנכס, אזור מועדף, תקציב, מועד.
אל תמציא מחירים או נכסים ספציפיים - הפנה לפגישה אישית לפרטים מדויקים.""",
            
            'restaurant': """אתה נציג חברותי של המסעדה. עזור ללקוחות עם הזמנות, שאלות על התפריט,
שעות פתיחה, ועריכת אירועים. התנהג בצורה חמה ומזמינה.""",
            
            'clinic': """אתה מזכירה מקצועית של המרפאה. עזור ללקוחות עם תיאום תורים,
מידע על טיפולים, והכנה לבדיקות. התנהג בצורה מקצועית ומרגיעה.""",
        }
        return prompts.get(business_type, prompts['real_estate'])
    
    def generate_ai_response(self, user_input: str, conversation_history: list, business_context: dict) -> str:
        """יצירת תשובת AI מותאמת אישית"""
        try:
            # בניית הקשר שיחה
            messages = [
                {
                    "role": "system", 
                    "content": f"""{business_context['ai_prompt']}
                    
שם העסק: {business_context['name']}
סוג העסק: {business_context['type']}

חוקים חשובים:
1. ענה רק בעברית
2. היה קצר ומדויק (עד 50 מילים)
3. שאל שאלה אחת רלוונטית בכל תשובה  
4. אם הלקוח רוצה לסיים ("ביי", "תודה ולהתראות", "זה הכל"), ענה בנימוס ותסיים
5. אל תמציא פרטים ספציפיים - הפנה לפגישה או לאיש קשר
6. היה חמ ומקצועי"""
                }
            ]
            
            # הוספת היסטוריית שיחה
            for turn in conversation_history:
                if turn.user_input:
                    messages.append({"role": "user", "content": turn.user_input})
                if turn.ai_response:
                    messages.append({"role": "assistant", "content": turn.ai_response})
            
            # הוספת הקלט החדש
            messages.append({"role": "user", "content": user_input})
            
            # קריאה ל-OpenAI
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",  # הדגם העדכני ביותר
                messages=messages,
                max_tokens=150,
                temperature=0.7,
                frequency_penalty=0.3,
                presence_penalty=0.3
            )
            
            ai_response = response.choices[0].message.content
            if ai_response:
                ai_response = ai_response.strip()
            logger.info(f"✅ AI Response generated: {ai_response[:50]}...")
            return ai_response
            
        except Exception as e:
            logger.error(f"❌ OpenAI API Error: {e}")
            return "סליחה, אני לא שומע טוב עכשיו. אפשר לחזור על השאלה?"
    
    def check_conversation_end(self, user_input: str, ai_response: str) -> bool:
        """בדיקה אם הלקוח רוצה לסיים את השיחה"""
        end_words = ['ביי', 'בי בי', 'להתראות', 'תודה ולהתראות', 'זה הכל', 'תודה רבה ולהתראות']
        user_wants_end = any(word in user_input.lower() for word in end_words)
        
        ai_says_goodbye = any(word in ai_response.lower() for word in ['להתראות', 'יום נעים', 'נשמח לעזור שוב'])
        
        return user_wants_end or ai_says_goodbye
    
    def process_conversation_turn(self, call_sid: str, recording_url: str, turn_number: int) -> dict:
        """עיבוד תור שיחה מלא: תמלול → AI → TTS → שמירה"""
        logger.info(f"🎙️ Processing turn {turn_number} for call {call_sid}")
        
        try:
            # 1. חיפוש או יצירת רשומת שיחה
            call_log = CallLog.query.filter_by(call_sid=call_sid).first()
            if not call_log:
                # יצירת רשומת שיחה חדשה
                call_log = CallLog(
                    call_sid=call_sid,
                    business_id=1,  # שי דירות ומשרדים בע״מ
                    customer_phone="",
                    call_status="in_progress",
                    start_time=datetime.now()
                )
                db.session.add(call_log)
                db.session.commit()
                logger.info(f"📝 Created new call log for {call_sid}")
            
            # 2. תמלול ההקלטה
            user_input = ""
            if recording_url:
                try:
                    user_input = transcribe_hebrew(recording_url)
                    logger.info(f"🎤 Transcription: {user_input}")
                except Exception as e:
                    logger.error(f"❌ Transcription failed: {e}")
                    user_input = "[תמלול נכשל]"
            
            # 3. קבלת היסטוריית שיחה
            conversation_history = ConversationTurn.query.filter_by(
                call_log_id=call_log.id
            ).order_by(ConversationTurn.turn_number).all()
            
            # 4. בדיקה מוקדמת לסיום שיחה
            should_end = self.check_conversation_end(user_input, "")
            
            # 5. יצירת הקשר עסקי
            business_context = self.get_business_context(call_log.business_id)
            
            # 6. יצירת תשובת AI
            ai_response = ""
            if not should_end and user_input and user_input != "[תמלול נכשל]":
                ai_response = self.generate_ai_response(
                    user_input, 
                    conversation_history, 
                    business_context
                )
                
                # בדיקה נוספת לסיום לאחר תשובת AI  
                should_end = self.check_conversation_end(user_input, ai_response)
            
            # 7. יצירת קובץ TTS
            response_audio_url = None
            if ai_response:
                try:
                    audio_filename = self.tts_service.create_tts_file(ai_response)
                    if audio_filename:
                        response_audio_url = f"https://ai-crmd.replit.app/static/voice_responses/{audio_filename}"
                        logger.info(f"🔊 TTS created: {audio_filename}")
                except Exception as e:
                    logger.error(f"❌ TTS failed: {e}")
                    response_audio_url = "https://ai-crmd.replit.app/static/voice_responses/processing.mp3"
            
            # 8. שמירת התור במסד נתונים
            conversation_turn = ConversationTurn(
                call_log_id=call_log.id,
                turn_number=turn_number,
                user_input=user_input,
                ai_response=ai_response,
                timestamp=datetime.now(),
                audio_url=recording_url,
                response_audio_url=response_audio_url
            )
            db.session.add(conversation_turn)
            
            # 9. עדכון סטטוס שיחה
            if should_end:
                call_log.call_status = "completed"
                call_log.end_time = datetime.now()
                logger.info(f"✅ Call {call_sid} completed after {turn_number} turns")
            
            db.session.commit()
            
            return {
                'success': True,
                'user_input': user_input,
                'ai_response': ai_response,
                'response_audio_url': response_audio_url,
                'should_end': should_end,
                'turn_number': turn_number,
                'call_sid': call_sid
            }
            
        except Exception as e:
            logger.error(f"❌ Error processing conversation turn: {e}")
            db.session.rollback()
            return {
                'success': False,
                'error': str(e),
                'should_end': False,
                'response_audio_url': 'https://ai-crmd.replit.app/static/voice_responses/processing.mp3'
            } 
                business_context
            )
            logger.info(f"💬 AI Response: {ai_response}")
            
            # 6. שמירת התור במסד הנתונים  
            turn = ConversationTurn()
            turn.call_log_id = call_log.id
            turn.turn_number = turn_number
            turn.user_input = transcription
            turn.ai_response = ai_response
            turn.recording_url = recording_url
            turn.timestamp = datetime.utcnow()
            db.session.add(turn)
            
            # 7. בדיקת סיום שיחה
            should_end = self.check_conversation_end(transcription, ai_response)
            
            # 8. עדכון רשומת השיחה
            call_log.transcription = transcription
            call_log.ai_response = ai_response
            call_log.updated_at = datetime.utcnow()
            if should_end:
                call_log.call_status = 'completed'
                call_log.ended_at = datetime.utcnow()
            
            db.session.commit()
            logger.info("✅ Turn saved to database")
            
            return {
                'success': True,
                'transcription': transcription,
                'ai_response': ai_response,
                'end_conversation': should_end,
                'turn_number': turn_number
            }
            
        except Exception as e:
            logger.error(f"❌ Error processing conversation turn: {e}")
            db.session.rollback()
            return {
                'success': False,
                'message': 'סליחה, יש לי בעיה טכנית. אפשר לנסות שוב?',
                'end_conversation': False
            }

# Global instance
ai_conversation = HebrewAIConversation()