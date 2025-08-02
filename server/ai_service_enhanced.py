"""
Enhanced AI Service with improved fallback and transfer logic
שירות AI מתקדם עם מנגנוני fallback ויכולת העברה לנציג אנושי
"""
import json
import logging
import os
import tempfile
import uuid
from uuid import uuid4
from openai import OpenAI
from gtts import gTTS
from datetime import datetime

logger = logging.getLogger(__name__)

class EnhancedAIService:
    def __init__(self):
        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key:
            self.client = OpenAI(api_key=api_key)
            self.api_available = True
        else:
            self.client = None
            self.api_available = False
            logger.warning("OpenAI API key not found - using fallback responses")
        
        # The newest OpenAI model is "gpt-4o" which was released May 13, 2024.
        # Do not change this unless explicitly requested by the user
        self.model = "gpt-4o"
    
    def _should_transfer_to_human(self, conversation_history):
        """בדיקה אם להעביר לנציג אנושי בהתבסס על דפוסי שיחה לא ברורים"""
        if len(conversation_history) < 3:
            return False
            
        # ספירת תגובות לא ברורות או חוזרות
        unclear_patterns = ['לא הבנתי', 'מצטער', 'לא ברור', 'נסה שוב', 'אחזור על']
        unclear_count = 0
        
        for turn in conversation_history[-3:]:  # בדיקת 3 התגובות האחרונות
            if turn.get('speaker') == 'ai':
                message = turn.get('message', '').lower()
                if any(pattern in message for pattern in unclear_patterns):
                    unclear_count += 1
        
        # אם יש 2+ תגובות לא ברורות ב-3 הודעות האחרונות
        return unclear_count >= 2
    
    def _test_api_connection(self):
        """בדיקת חיבור API עם timeout"""
        if not self.api_available:
            return False
            
        try:
            # בדיקה מהירה של API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5,
                timeout=5
            )
            return True
        except Exception as e:
            logger.error(f"API connection test failed: {e}")
            return False
    
    def _fallback_response_hebrew(self, user_input, business):
        """תגובת fallback עברית מתקדמת"""
        business_name = getattr(business, 'name', 'העסק') if business else 'העסק'
        
        # זיהוי כוונות בסיסיות
        user_lower = user_input.lower()
        
        # זיהוי כוונות מתקדמות
        if any(word in user_lower for word in ['חשבונית', 'חשבון', 'תשלום', 'לשלם']):
            return self._handle_payment_intent(user_input, business)
        elif any(word in user_lower for word in ['חוזה', 'הסכם', 'מסמך']):
            return self._handle_contract_intent(user_input, business)
        elif any(word in user_lower for word in ['הצעת מחיר', 'הצעה', 'מחיר', 'עלות']):
            return self._handle_quote_intent(user_input, business)
        elif any(word in user_lower for word in ['תור', 'זמן', 'תאריך', 'מחר', 'היום']):
            return f"אני יכול לעזור לכם לקבוע תור ב{business_name}. איזה תאריך מתאים לכם?"
        
        # תגובות ברירת מחדל
        responses = [
            f"שלום! אני עוזר ה-AI של {business_name}. איך אוכל לעזור לכם?",
            f"מצטער, לא הצלחתי להבין בדיוק. נסו לנסח את הבקשה אחרת או צרו קשר עם הצוות שלנו.",
            f"אני כאן לעזור! ספרו לי במה אתם מעוניינים ואעשה כמיני טוב לסייע."
        ]
        
        import random
        return random.choice(responses)
    
    def _handle_payment_intent(self, user_input, business):
        """טיפול בבקשות תשלום"""
        try:
            return f"""
💳 *תהליך תשלום*

אני יכול לעזור לכם ליצור קישור תשלום מאובטח.

נא ציינו:
• סכום התשלום
• מה עבור התשלום 
• שם מלא לחשבונית

לדוגמה: "אני רוצה לשלם 500 שקל עבור טיפול שיניים"

📞 לחילופין צרו קשר עם הצוות שלנו לעזרה נוספת
            """.strip()
            
        except Exception as e:
            logger.error(f"Error handling payment intent: {e}")
            return "אני יכול לעזור עם תשלומים. נא צרו קשר עם הצוות שלנו למידע נוסף."
    
    def _handle_contract_intent(self, user_input, business):
        """טיפול בבקשות חוזה"""
        try:
            return f"""
📋 *מסמכים וחוזים*

אני יכול לעזור לכם עם:
• יצירת חוזה שירותים
• חתימה דיגיטלית על מסמכים
• שליחת מסמכים דרך WhatsApp

📞 לקבלת חוזה או מסמך, צרו קשר עם הצוות שלנו
🔒 כל המסמכים חתומים דיגיטלית ומאובטחים
            """.strip()
            
        except Exception as e:
            logger.error(f"Error handling contract intent: {e}")
            return "אני יכול לעזור עם חוזים ומסמכים. נא צרו קשר עם הצוות שלנו."
    
    def _handle_quote_intent(self, user_input, business):
        """טיפול בבקשות הצעת מחיר"""
        try:
            business_name = getattr(business, 'name', 'העסק') if business else 'העסק'
            
            return f"""
💰 *הצעת מחיר*

אני יכול לעזור לכם לקבל הצעת מחיר ל{business_name}.

נא ציינו:
• איזה שירות אתם מעוניינים
• כמות או היקף העבודה
• מועד רצוי לביצוע

📞 הצוות שלנו יכין עבורכם הצעת מחיר מפורטת תוך 24 שעות
💌 ההצעה תישלח אליכם דרך WhatsApp
            """.strip()
            
        except Exception as e:
            logger.error(f"Error handling quote intent: {e}")
            return "אני יכול לעזור עם הצעות מחיר. נא צרו קשר עם הצוות שלנו למידע נוסף."
        else:
            return {
                'message': f'תודה שפנית ל{business_name}. איך אוכל לעזור לך היום? אוכל לסייע בקביעת תורים, מידע על תפריט ושעות פעילות.',
                'continue_conversation': True,
                'structured_data': {'intent': 'general_inquiry'}
            }
    
    def generate_response(self, user_input, business, conversation_history, caller_info):
        """יצירת תגובה מתקדמת עם fallback משופר"""
        try:
            logger.info(f"🧠 Generating AI response for: '{user_input}'")
            
            # בדיקת מגבלת הודעות (6 הודעות מקסימום)
            if len(conversation_history) >= 6:
                logger.warning("Message limit reached - transferring to human agent")
                return {
                    'message': 'נראה שאתם זקוקים לעזרה מעמיקה יותר. אעביר אתכם לנציג האנושי שלנו שיוכל לסייע בצורה מותאמת.',
                    'continue_conversation': False,
                    'structured_data': None,
                    'transfer_to_agent': True
                }
            
            # בדיקת העברה לנציג אנושי בהתבסס על דפוסי שיחה
            if self._should_transfer_to_human(conversation_history):
                logger.info("Transferring to human due to unclear conversation pattern")
                return {
                    'message': 'אני רוצה לוודא שתקבלו את השירות הטוב ביותר. אחבר אתכם לנציג האנושי שלנו.',
                    'continue_conversation': False,
                    'structured_data': None,
                    'transfer_to_agent': True
                }
            
            # טיפול במקרה של עסק לא תקין
            if not business:
                logger.error("Business object is None")
                return {
                    'message': 'מצטער, יש בעיה זמנית במערכת. אנא נסה שוב מאוחר יותר.',
                    'continue_conversation': False,
                    'structured_data': None
                }
            
            # בדיקת זמינות API ו-fallback מיידי
            if not self._test_api_connection():
                logger.warning("API not available - using fallback response")
                return self._fallback_response_hebrew(user_input, business)
            
            # בניית prompt מתקדם למודל
            business_name = getattr(business, 'name', 'העסק')
            business_type = getattr(business, 'business_type', 'עסק')
            system_prompt_text = getattr(business, 'system_prompt', 'שירות מקצועי')
            
            # בניית הקשר שיחה
            context = self._build_conversation_context(conversation_history)
            
            system_prompt = f"""
אתה עוזר AI מתקדם ברמה הגבוהה ביותר עבור {business_name} ({business_type}).
אתה מומחה בשירות לקוחות יוקרתי בעברית עם יכולות מתקדמות.

מידע על העסק:
{system_prompt_text}

🎯 המומחיות שלך:
1. הבנה מושלמת של כוונות לקוח בעברית (intent recognition)
2. ייעוץ מקצועי בתפריט עם המלצות אישיות
3. הזמנת תורים מדויקת עם אישור מיידי
4. טיפול בבקשות מיוחדות, אלרגיות וצרכים מיוחדים
5. מידע מדויק על מחירים, שעות ומיקום
6. עזרה בארגון אירועים וחגיגות פרטיות

⚡ כללי עבודה מחמירים:
- ענה תמיד בעברית מושלמת ומקצועית (ZERO אנגלית!)
- היה יעיל, מדויק ומועיל ב-50-80 מילים בלבד
- זהה כוונות הלקוח ותן פתרון מותאם אישית
- אם המידע לא ברור - שאל שאלה מפרטת אחת ויחידה
- החזר תמיד JSON valid עם המבנה הנדרש

📋 פורמט תגובה חובה:
{{
    "message": "התגובה בעברית",
    "continue_conversation": true/false,
    "structured_data": {{
        "intent": "appointment/menu/hours/general",
        "appointment_details": {{"date": "", "time": "", "service": ""}},
        "confidence": 0.0-1.0
    }}
}}

🕒 הקשר נוכחי: {context}
"""
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"לקוח אמר: {user_input}"}
            ]
            
            # קריאת API עם טיפול משופר בשגיאות
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=300,
                    temperature=0.7,
                    timeout=10
                )
                
                assistant_message = response.choices[0].message.content.strip()
                logger.info(f"✅ [GPT] Response generated successfully: {len(assistant_message)} chars")
                
                # ניתוח JSON משופר עם fallback
                try:
                    result = json.loads(assistant_message)
                    if isinstance(result, dict) and 'message' in result:
                        # וולידציה של התוכן
                        if not result['message'] or result['message'].strip() == '':
                            logger.warning("GPT returned empty message")
                            return self._fallback_response_hebrew(user_input, business)
                        return result
                    else:
                        logger.warning("GPT response missing required 'message' field")
                        return {
                            'message': str(result) if result else "מצטער, לא הבנתי. אנא נסח מחדש.",
                            'continue_conversation': True,
                            'structured_data': {'intent': 'unclear'}
                        }
                except json.JSONDecodeError as json_error:
                    logger.warning(f"GPT returned non-JSON response: {json_error}")
                    # שימוש בתגובה כטקסט רגיל אם יש תוכן
                    if assistant_message and len(assistant_message) > 10:
                        return {
                            'message': assistant_message,
                            'continue_conversation': True,
                            'structured_data': {'intent': 'general'}
                        }
                    else:
                        return self._fallback_response_hebrew(user_input, business)
                        
            except Exception as api_error:
                logger.error(f"❌ [GPT] OpenAI API Error: {api_error}")
                return self._fallback_response_hebrew(user_input, business)
                
        except Exception as e:
            logger.error(f"❌ [GPT] Unexpected error in generate_response: {e}")
            return self._fallback_response_hebrew(user_input, business)
    
    def _build_conversation_context(self, conversation_history):
        """בניית הקשר שיחה"""
        if not conversation_history:
            return "תחילת שיחה"
        
        context_parts = []
        for turn in conversation_history[-3:]:  # 3 הודעות אחרונות
            speaker = turn.get('speaker', 'unknown')
            message = turn.get('message', '')[:50]  # חיתוך הודעה ל-50 תווים
            context_parts.append(f"{speaker}: {message}")
        
        return " | ".join(context_parts)