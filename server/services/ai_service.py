"""
AI Service - Unified OpenAI Service for All Communication Channels
שירות AI מאוחד - מחבר פרומפטים דינמיים מהמסד נתונים עם OpenAI
"""
import os
import logging
from typing import Dict, Any, Optional, List
from openai import OpenAI
from server.models_sql import BusinessSettings, PromptRevisions, Business
from server.db import db
from datetime import datetime

logger = logging.getLogger(__name__)

class AIService:
    """מנגנון AI מרכזי שטוען פרומפטים מהמסד נתונים ומחבר עם OpenAI"""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self._cache = {}  # קאש פרומפטים לביצועים
        self._cache_timeout = 300  # 5 דקות
        
    def get_business_prompt(self, business_id: int) -> Dict[str, Any]:
        """טעינת פרומפט עסק מהמסד נתונים עם קאש"""
        cache_key = f"business_{business_id}"
        now = datetime.now().timestamp()
        
        # בדיקת קאש
        if cache_key in self._cache:
            cached_data, timestamp = self._cache[cache_key]
            if now - timestamp < self._cache_timeout:
                return cached_data
        
        try:
            # טעינת הגדרות עסק
            settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
            business = Business.query.get(business_id)
            
            if not settings:
                # ברירת מחדל אם אין הגדרות
                prompt_data = {
                    "system_prompt": self._get_default_hebrew_prompt(business.name if business else "שי דירות"),
                    "model": "gpt-4o-mini",  # המודל הנוכחי במערכת
                    "max_tokens": 150,
                    "temperature": 0.7
                }
            else:
                prompt_data = {
                    "system_prompt": settings.ai_prompt or self._get_default_hebrew_prompt(business.name if business else "שי דירות"),
                    "model": settings.model,
                    "max_tokens": settings.max_tokens,
                    "temperature": settings.temperature
                }
            
            # שמירה בקאש
            self._cache[cache_key] = (prompt_data, now)
            return prompt_data
            
        except Exception as e:
            logger.error(f"Error loading business prompt {business_id}: {e}")
            # Fallback לפרומפט ברירת מחדל
            return {
                "system_prompt": self._get_default_hebrew_prompt("שי דירות"),
                "model": "gpt-4o-mini",
                "max_tokens": 150,
                "temperature": 0.7
            }
    
    def _get_default_hebrew_prompt(self, business_name: str = "שי דירות") -> str:
        """פרומפט ברירת מחדל בעברית לנדל"ן"""
        return f"""אתה "לאה", סוכנת הנדל"ן הדיגיטלית של {business_name}.

אני עוזרת ללקוחות למצוא את הנכס המושלם - דירות, בתים ומשרדים.

כללים:
- תמיד תענה בעברית
- תשובות קצרות ועניינות (עד 150 מילים)
- תהיי מקצועית וידידותית
- תבקשי פרטים: אזור, סוג נכס, תקציב
- תציעי לקבוע פגישה כשיש מספיק מידע

תפקידך: לעזור, לאסוף מידע ולהוביל לפגישה."""

    def generate_response(self, message: str, business_id: int = 1, context: Dict[str, Any] = None) -> str:
        """יצירת תגובה מפרומפט דינמי + הקשר"""
        try:
            # טעינת פרומפט עסק
            prompt_data = self.get_business_prompt(business_id)
            
            # בניית הודעות
            messages = [
                {"role": "system", "content": prompt_data["system_prompt"]}
            ]
            
            # הוספת הקשר אם קיים
            if context:
                context_info = []
                if context.get("customer_name"):
                    context_info.append(f"שם הלקוח: {context['customer_name']}")
                if context.get("phone_number"):
                    context_info.append(f"טלפון: {context['phone_number']}")
                if context.get("previous_messages"):
                    context_info.append("הודעות קודמות בשיחה:")
                    for msg in context["previous_messages"][-3:]:  # רק 3 אחרונות
                        context_info.append(f"- {msg}")
                
                if context_info:
                    messages.append({
                        "role": "system", 
                        "content": "הקשר נוסף:\n" + "\n".join(context_info)
                    })
            
            # הוספת הודעת המשתמש
            messages.append({"role": "user", "content": message})
            
            # קריאה ל-OpenAI
            response = self.client.chat.completions.create(
                model=prompt_data["model"],
                messages=messages,
                max_tokens=prompt_data["max_tokens"],
                temperature=prompt_data["temperature"]
            )
            
            ai_response = response.choices[0].message.content.strip()
            logger.info(f"AI response generated for business {business_id}: {len(ai_response)} chars")
            return ai_response
            
        except Exception as e:
            logger.error(f"AI generation failed: {e}")
            return self._get_fallback_response(message)
    
    def _get_fallback_response(self, message: str) -> str:
        """תגובת חירום אם ה-AI נכשל"""
        message_lower = message.lower().strip()
        
        if any(word in message_lower for word in ["שלום", "היי", "הלו"]):
            return "שלום! אני לאה מצוות שי דירות ומשרדים. איך אוכל לעזור לך למצוא נכס?"
        elif any(word in message_lower for word in ["דירה", "בית", "נכס"]):
            return "אשמח לעזור לך! אתה מחפש לקניה או השכרה? באיזה אזור?"
        else:
            return "תודה על הפנייה! אחד הסוכנים שלנו יחזור אליך בהקדם עם מענה מפורט."
    
    def invalidate_cache(self, business_id: int):
        """מחיקת קאש עסק מסוים (לאחר עדכון פרומפט)"""
        cache_key = f"business_{business_id}"
        if cache_key in self._cache:
            del self._cache[cache_key]
            logger.info(f"Cache invalidated for business {business_id}")
    
    def save_conversation_history(self, business_id: int, phone_number: str, 
                                 message: str, response: str, channel: str = "whatsapp"):
        """שמירת היסטוריית שיחה למידע עתידי (אופציונלי)"""
        try:
            # כאן אפשר להוסיף לוגיקה לשמירת שיחות ארוכות
            # לצרכי הקשר עתידי או אנליטיקה
            pass
        except Exception as e:
            logger.error(f"Failed to save conversation history: {e}")

# Global instance
_ai_service = None

def get_ai_service() -> AIService:
    """קבלת instance יחיד של שירות ה-AI"""
    global _ai_service
    if _ai_service is None:
        _ai_service = AIService()
    return _ai_service

def generate_ai_response(message: str, business_id: int = 1, 
                        context: Dict[str, Any] = None) -> str:
    """פונקציה עזר לקריאה מהירה לשירות AI"""
    return get_ai_service().generate_response(message, business_id, context)

def invalidate_business_cache(business_id: int):
    """פונקציה עזר למחיקת קאש עסק"""
    service = get_ai_service()
    service.invalidate_cache(business_id)