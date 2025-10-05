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

# Global AI service instance for cache sharing
_global_ai_service = None

def get_ai_service():
    """Get or create global AI service instance"""
    global _global_ai_service
    if _global_ai_service is None:
        _global_ai_service = AIService()
    return _global_ai_service

def invalidate_business_cache(business_id: int):
    """🔥 CRITICAL: Invalidate cache for business - called after prompt updates"""
    service = get_ai_service()
    cache_keys_to_remove = [
        f"business_{business_id}_calls",
        f"business_{business_id}_whatsapp"
    ]
    for key in cache_keys_to_remove:
        if key in service._cache:
            del service._cache[key]
            logger.info(f"✅ Cache invalidated: {key}")

class AIService:
    """מנגנון AI מרכזי שטוען פרומפטים מהמסד נתונים ומחבר עם OpenAI"""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self._cache = {}  # קאש פרומפטים לביצועים
        self._cache_timeout = 300  # 5 דקות
        
    def get_business_prompt(self, business_id: int, channel: str = "calls") -> Dict[str, Any]:
        """טעינת פרומפט עסק מהמסד נתונים עם קאש - לפי ערוץ (calls/whatsapp)"""
        cache_key = f"business_{business_id}_{channel}"
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
            
            # בחירת פרומפט חכמה - עם fallback ל-business.system_prompt
            system_prompt = ""
            if settings and settings.ai_prompt and len(settings.ai_prompt.strip()) > 20:
                # יש פרומפט ב-settings - צריך לבדוק אם זה JSON או טקסט
                import json
                try:
                    # נסיון לפרוס כ-JSON (פורמט חדש עם calls/whatsapp)
                    if settings.ai_prompt.strip().startswith('{'):
                        prompt_obj = json.loads(settings.ai_prompt)
                        # בחירת הפרומפט הנכון לפי channel
                        system_prompt = prompt_obj.get(channel, prompt_obj.get('calls', settings.ai_prompt))
                        logger.info(f"✅ Using {channel} prompt for business {business_id}")
                    else:
                        # פרומפט טקסט פשוט (legacy)
                        system_prompt = settings.ai_prompt
                except json.JSONDecodeError:
                    # אם זה לא JSON תקין, השתמש בזה כטקסט
                    system_prompt = settings.ai_prompt
            elif business and business.system_prompt and len(business.system_prompt.strip()) > 20:
                # fallback לפרומפט המלא מטבלת business
                system_prompt = business.system_prompt
                logger.info(f"✅ Using fallback prompt from business.system_prompt for {business_id}")
            else:
                # fallback אחרון לפרומפט ברירת מחדל
                system_prompt = self._get_default_hebrew_prompt(business.name if business else "שי דירות", channel)
            
            if not settings:
                # ברירת מחדל אם אין הגדרות
                prompt_data = {
                    "system_prompt": system_prompt,
                    "model": "gpt-4o-mini",  # המודל הנוכחי במערכת
                    "max_tokens": 150,
                    "temperature": 0.7
                }
            else:
                prompt_data = {
                    "system_prompt": system_prompt,
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
                "system_prompt": self._get_default_hebrew_prompt("שי דירות", channel),
                "model": "gpt-4o-mini",
                "max_tokens": 150,
                "temperature": 0.7
            }
    
    def _get_default_hebrew_prompt(self, business_name: str = "שי דירות", channel: str = "calls") -> str:
        """פרומפט ברירת מחדל בעברית לנדל"ן - מותאם לערוץ"""
        if channel == "whatsapp":
            return f"""אתה "לאה", סוכנת WhatsApp של {business_name}.

כללים:
- תענה בעברית, תשובות קצרות (עד 100 מילים)
- תהיי חמה וידידותית בסגנון WhatsApp
- תבקשי פרטים: אזור, סוג נכס, תקציב
- תציעי לקבוע פגישה כשיש מידע מספיק

תפקידך: לעזור למצוא נכס ולהוביל לפגישה."""
        else:
            # Calls default
            return f"""אתה "לאה", סוכנת הנדל"ן הדיגיטלית של {business_name}.

אני עוזרת ללקוחות למצוא את הנכס המושלם - דירות, בתים ומשרדים.

כללים:
- תמיד תענה בעברית
- תשובות קצרות ועניינות (עד 150 מילים)
- תהיי מקצועית וידידותית
- תבקשי פרטים: אזור, סוג נכס, תקציב
- תציעי לקבוע פגישה כשיש מספיק מידע

תפקידך: לעזור, לאסוף מידע ולהוביל לפגישה."""

    def generate_response(self, message: str, business_id: int = 1, context: Optional[Dict[str, Any]] = None, channel: str = "calls") -> str:
        """יצירת תגובה מפרומפט דינמי + הקשר - לפי ערוץ (calls/whatsapp)"""
        try:
            # טעינת פרומפט עסק לפי ערוץ
            prompt_data = self.get_business_prompt(business_id, channel)
            
            # בניית הודעות
            messages: List[Dict[str, str]] = [
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
                messages=messages,  # type: ignore
                max_tokens=prompt_data["max_tokens"],
                temperature=prompt_data["temperature"]
            )
            
            ai_response = response.choices[0].message.content
            if ai_response:
                ai_response = ai_response.strip()
            else:
                ai_response = "מצטער, לא הצלחתי לייצר תגובה כרגע."
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

def generate_ai_response(message: str, business_id: int = 1, 
                        context: Optional[Dict[str, Any]] = None, channel: str = "calls") -> str:
    """פונקציה עזר לקריאה מהירה לשירות AI - לפי ערוץ"""
    return get_ai_service().generate_response(message, business_id, context, channel)