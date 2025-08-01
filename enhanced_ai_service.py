"""
Enhanced AI Service with Advanced Error Handling and Fallbacks
שירות AI מתקדם עם טיפול בשגיאות וגיבוי מתקדמים
"""

import os
import time
import json
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from openai import OpenAI
from models import Business, ConversationTurn
from datetime import timedelta
from app import db
import uuid

logger = logging.getLogger(__name__)

class EnhancedAIService:
    """שירות AI מתקדם עם טיפול מלא בשגיאות"""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
        self.timeout_seconds = 15
        self.max_retries = 2
        
    def process_conversation(self, user_message: str, business_id: int, 
                           conversation_id: str = None) -> Dict[str, Any]:
        """עיבוד שיחה מלא עם fallback ובדיקות איכות"""
        
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
        
        # בדיקות ראשוניות
        validation_result = self._validate_input(user_message)
        if not validation_result['valid']:
            return self._create_error_response(
                validation_result['error'], 
                conversation_id, 
                business_id
            )
        
        # קבלת הקשר עסקי
        business = Business.query.get(business_id)
        if not business:
            logger.error(f"Business {business_id} not found")
            return self._create_error_response(
                "מצטער, אירעה שגיאה במערכת. נסה שוב בעוד רגע.",
                conversation_id,
                business_id
            )
        
        try:
            # עיבוד עם GPT-4o
            gpt_response = self._call_gpt_with_timeout(
                user_message, business, conversation_id
            )
            
            if not gpt_response['success']:
                return self._handle_gpt_failure(
                    user_message, conversation_id, business_id
                )
            
            # שמירה במסד נתונים
            self._save_conversation_turn(
                conversation_id=conversation_id,
                business_id=business_id,
                user_message=user_message,
                ai_response=gpt_response['response'],
                intent=gpt_response.get('intent', 'unknown'),
                prompt_used=gpt_response.get('prompt', ''),
                processing_time=gpt_response.get('processing_time', 0)
            )
            
            return {
                'success': True,
                'response': gpt_response['response'],
                'intent': gpt_response.get('intent', 'unknown'),
                'conversation_id': conversation_id,
                'confidence': gpt_response.get('confidence', 0.8)
            }
            
        except Exception as e:
            logger.error(f"Unexpected error in process_conversation: {e}")
            return self._create_error_response(
                "מצטער, המערכת עמוסה כרגע. נסה שוב בעוד דקה.",
                conversation_id,
                business_id
            )
    
    def _validate_input(self, message: str) -> Dict[str, Any]:
        """אימות קלט המשתמש"""
        
        # בדיקת ריקנות
        if not message or not message.strip():
            return {
                'valid': False,
                'error': 'לא קיבלתי הודעה ברורה. תוכל לנסח שוב?'
            }
        
        # בדיקת אורך מינימלי
        if len(message.strip()) < 3:
            return {
                'valid': False,
                'error': 'ההודעה קצרה מדי. תוכל להרחיב קצת?'
            }
        
        # בדיקת ג'יבריש נפוצים מ-Whisper
        gibberish_patterns = [
            'dot', 'dott', 'got', 'hello', 'thank you', 'bye',
            '.', '..', '...', 'test', 'testing'
        ]
        
        if message.strip().lower() in gibberish_patterns:
            return {
                'valid': False,
                'error': 'לא הבנתי. תוכל לדבר בעברית בבקשה?'
            }
        
        # בדיקת שפה עברית בסיסית
        hebrew_chars = sum(1 for c in message if '\u0590' <= c <= '\u05FF')
        if len(message) > 10 and hebrew_chars < len(message) * 0.3:
            return {
                'valid': False,
                'error': 'אני מדבר עברית. תוכל לנסות שוב בעברית?'
            }
        
        return {'valid': True}
    
    def _call_gpt_with_timeout(self, message: str, business: Business, 
                             conversation_id: str) -> Dict[str, Any]:
        """קריאה ל-GPT עם timeout וניסיונות חוזרים"""
        
        start_time = time.time()
        
        # בניית prompt עסקי
        system_prompt = self._build_business_prompt(business)
        
        for attempt in range(self.max_retries + 1):
            try:
                logger.info(f"GPT attempt {attempt + 1} for conversation {conversation_id}")
                
                response = self.client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": message}
                    ],
                    timeout=self.timeout_seconds,
                    temperature=0.7,
                    max_tokens=300
                )
                
                ai_response = response.choices[0].message.content.strip()
                processing_time = time.time() - start_time
                
                # בדיקת איכות התשובה
                if not ai_response or len(ai_response) < 10:
                    if attempt < self.max_retries:
                        continue
                    return {'success': False, 'error': 'empty_response'}
                
                # חילוץ intent (אם קיים)
                intent = self._extract_intent(message, ai_response)
                
                return {
                    'success': True,
                    'response': ai_response,
                    'intent': intent,
                    'prompt': system_prompt,
                    'processing_time': processing_time,
                    'attempt': attempt + 1
                }
                
            except Exception as e:
                logger.warning(f"GPT attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries:
                    time.sleep(1)  # המתנה קצרה בין ניסיונות
                    continue
                
                return {
                    'success': False, 
                    'error': str(e),
                    'processing_time': time.time() - start_time
                }
        
        return {'success': False, 'error': 'max_retries_exceeded'}
    
    def _build_business_prompt(self, business: Business) -> str:
        """בניית prompt מותאם לעסק"""
        
        base_prompt = f"""
אתה עוזר AI ידידותי ומקצועי של {business.name}.

מידע על העסק:
- שם: {business.name}
- טלפון: {business.phone_number}
- {business.system_prompt if business.system_prompt else 'מספק שירות לקוחות מעולה'}

הנחיות:
1. תמיד תענה בעברית בלבד
2. היה ידידותי אך מקצועי
3. אם שואלים על תור - תציע זמנים אפשריים
4. אם לא יודע משהו - תבקש פרטים נוספים
5. אל תמציא מידע שלא קיים
6. שמור על שיחה קצרה ויעילה

תענה בצורה טבעית וידידותית.
"""
        return base_prompt.strip()
    
    def _extract_intent(self, user_message: str, ai_response: str) -> str:
        """חילוץ כוונת המשתמש מהשיחה"""
        
        appointment_keywords = [
            'תור', 'תורים', 'לקבוע', 'זמין', 'פנוי', 'מועד',
            'להיפגש', 'לבוא', 'ביום', 'בשעה'
        ]
        
        info_keywords = [
            'מידע', 'פרטים', 'שעות', 'מיקום', 'כתובת', 
            'טלפון', 'עלות', 'מחיר', 'שירות'
        ]
        
        complaint_keywords = [
            'תלונה', 'בעיה', 'לא מרוצה', 'שגיאה', 'טעות',
            'זה לא טוב', 'לא עובד'
        ]
        
        message_lower = user_message.lower()
        
        if any(keyword in message_lower for keyword in appointment_keywords):
            return 'appointment_request'
        elif any(keyword in message_lower for keyword in info_keywords):
            return 'information_request'
        elif any(keyword in message_lower for keyword in complaint_keywords):
            return 'complaint'
        else:
            return 'general_inquiry'
    
    def _handle_gpt_failure(self, user_message: str, conversation_id: str, 
                           business_id: int) -> Dict[str, Any]:
        """טיפול בכשל GPT עם תגובות חכמות"""
        
        # תגובות fallback לפי תוכן ההודעה
        if 'תור' in user_message.lower():
            fallback_response = "אשמח לעזור לך לקבוע תור. תוכל לספר לי באיזה יום ושעה מתאים לך?"
        elif any(word in user_message.lower() for word in ['שעות', 'מיקום', 'כתובת']):
            fallback_response = "אתה מבקש מידע על השירות שלנו. תוכל להיות יותר ספציפי?"
        else:
            fallback_response = "תוכל להסביר שוב במילים אחרות? רוצה לעזור לך כמיטב יכולתי."
        
        # שמירת כשל במסד נתונים
        self._save_conversation_turn(
            conversation_id=conversation_id,
            business_id=business_id,
            user_message=user_message,
            ai_response=fallback_response,
            intent='gpt_fallback',
            prompt_used='fallback_system',
            processing_time=0
        )
        
        return {
            'success': True,
            'response': fallback_response,
            'intent': 'gpt_fallback',
            'conversation_id': conversation_id,
            'confidence': 0.3
        }
    
    def _create_error_response(self, message: str, conversation_id: str, 
                             business_id: int) -> Dict[str, Any]:
        """יצירת תגובת שגיאה סטנדרטית"""
        
        self._save_conversation_turn(
            conversation_id=conversation_id,
            business_id=business_id,
            user_message="[SYSTEM_ERROR]",
            ai_response=message,
            intent='system_error',
            prompt_used='error_handler',
            processing_time=0
        )
        
        return {
            'success': True,
            'response': message,
            'intent': 'system_error',
            'conversation_id': conversation_id,
            'confidence': 1.0
        }
    
    def _save_conversation_turn(self, conversation_id: str, business_id: int,
                              user_message: str, ai_response: str, intent: str,
                              prompt_used: str, processing_time: float):
        """שמירת תור שיחה במסד נתונים"""
        
        try:
            conversation_turn = ConversationTurn(
                user_message=user_message,
                ai_response=ai_response,
                business_id=business_id,
                created_at=datetime.utcnow()
            )
            
            db.session.add(conversation_turn)
            db.session.commit()
            
            logger.info(f"Saved conversation turn: {conversation_id}")
            
        except Exception as e:
            logger.error(f"Failed to save conversation turn: {e}")
            db.session.rollback()

    def get_conversation_history(self, conversation_id: str) -> list:
        """קבלת היסטוריית שיחה"""
        
        try:
            turns = ConversationTurn.query.filter_by(
                conversation_id=conversation_id
            ).order_by(ConversationTurn.created_at.asc()).all()
            
            return [
                {
                    'user_message': turn.user_message,
                    'ai_response': turn.ai_response,
                    'intent': turn.intent_detected,
                    'timestamp': turn.created_at.isoformat(),
                    'processing_time': turn.processing_time
                }
                for turn in turns
            ]
            
        except Exception as e:
            logger.error(f"Failed to get conversation history: {e}")
            return []

# יצירת instance גלובלי
enhanced_ai_service = EnhancedAIService()