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
        # ⚡ RELIABLE OpenAI client with production timeout
        self.client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            timeout=3.5  # ✅ Production timeout - allows Hebrew responses with margin
        )
        self._cache = {}  # קאש פרומפטים לביצועים
        self._cache_timeout = 30  # ⚡ 30 שניות - קצר יותר למניעת בעיות multi-worker
        
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
            
            # ✅ שם עסק לשימוש ב-placeholders
            business_name = business.name if business else "העסק שלנו"
            
            # בחירת פרומפט חכמה - עם fallback ל-business.system_prompt
            system_prompt = ""
            if settings and settings.ai_prompt and settings.ai_prompt.strip():
                # יש פרומפט ב-settings - תמיד תשתמש בו! (ללא בדיקת אורך)
                import json
                try:
                    # נסיון לפרוס כ-JSON (פורמט חדש עם calls/whatsapp)
                    if settings.ai_prompt.strip().startswith('{'):
                        prompt_obj = json.loads(settings.ai_prompt)
                        # בחירת הפרומפט הנכון לפי channel
                        system_prompt = prompt_obj.get(channel, prompt_obj.get('calls', settings.ai_prompt))
                        logger.info(f"✅ Using {channel} prompt for business {business_id} from settings")
                        logger.info(f"🔍 DEBUG: Loaded prompt starts with: {system_prompt[:100]}...")
                    else:
                        # פרומפט טקסט פשוט (legacy)
                        system_prompt = settings.ai_prompt
                        logger.info(f"✅ Using legacy text prompt for business {business_id}")
                except json.JSONDecodeError:
                    # אם זה לא JSON תקין, השתמש בזה כטקסט
                    system_prompt = settings.ai_prompt
                    logger.info(f"✅ Using non-JSON prompt for business {business_id}")
            elif business and business.system_prompt and business.system_prompt.strip():
                # fallback לפרומפט המלא מטבלת business
                system_prompt = business.system_prompt
                logger.info(f"✅ Using fallback prompt from business.system_prompt for {business_id}")
            else:
                # fallback אחרון לפרומפט ברירת מחדל
                system_prompt = self._get_default_hebrew_prompt(business_name, channel)
                logger.info(f"⚠️ Using default prompt for business {business_id} - no custom prompt found")
            
            # ✅ החלפת placeholders דינמיים בפרומפט
            system_prompt = system_prompt.replace("{{business_name}}", business_name)
            system_prompt = system_prompt.replace("{{BUSINESS_NAME}}", business_name)
            logger.info(f"✅ Replaced {{{{business_name}}}} with '{business_name}'")
            
            if not settings:
                # ⚡ BUILD 109: Balanced - quality + speed
                prompt_data = {
                    "system_prompt": system_prompt,
                    "model": "gpt-4o-mini",  # Fast model
                    "max_tokens": 180,  # ⚡ BUILD 109: 180 tokens for quality Hebrew responses (3-4 sentences)
                    "temperature": 0.3  # Balanced temperature for natural responses
                }
            else:
                prompt_data = {
                    "system_prompt": system_prompt,
                    "model": settings.model,
                    "max_tokens": min(settings.max_tokens, 180),  # ⚡ BUILD 109: Cap at 180 for quality
                    "temperature": min(settings.temperature, 0.4)  # Balanced temperature
                }
            
            # שמירה בקאש
            self._cache[cache_key] = (prompt_data, now)
            return prompt_data
            
        except Exception as e:
            logger.error(f"Error loading business prompt {business_id}: {e}")
            # ⚡ FAST fallback - טעינת שם עסק מה-DB
            try:
                business = Business.query.get(business_id)
                business_name = business.name if business else "העסק שלנו"
            except:
                business_name = "העסק שלנו"
            
            return {
                "system_prompt": self._get_default_hebrew_prompt(business_name, channel),
                "model": "gpt-4o-mini",
                "max_tokens": 180,  # ⚡ BUILD 109: 180 tokens for quality
                "temperature": 0.3  # Balanced
            }
    
    def _get_default_hebrew_prompt(self, business_name: str = "העסק שלנו", channel: str = "calls") -> str:
        """פרומפט ברירת מחדל בעברית לנדל"ן - מותאם לערוץ - ✅ בלי שם hardcoded!"""
        if channel == "whatsapp":
            return f"""אתה העוזר הדיגיטלי של {business_name} ב-WhatsApp.

כללים חשובים:
- תענה בעברית, תשובות קצרות (עד 150 מילים)
- תהיה חם וידידותי בסגנון WhatsApp
- תבקש פרטים: אזור, סוג נכס, תקציב
- כשאתה מזכיר מחירים/תקציב - תמיד ציין "מיליון", "אלף", "מיליארד" (לא רק מספרים!)
- תציע לקבוע פגישה כשיש מידע מספיק
- ⚠️ אל תחזור על שמך בכל משפט! זה מעצבן ולא טבעי
- דבר ישר לעניין בלי להציג את עצמך כל פעם מחדש

**כשלקוח מסכים לזמן פגישה:**
🎯 **חזור על הזמן המדויק שהלקוח אמר!**
דוגמאות:
- לקוח: "מחר ב-10" → אתה: "מעולה! נקבע לך פגישה למחר בשעה 10:00."
- לקוח: "מחר ב-15" → אתה: "מעולה! נקבע לך פגישה למחר בשעה 15:00."
⚠️ **אל תשנה את השעה - חזור על מה שהלקוח אמר!**

תפקידך: לעזור למצוא נכס ולהוביל לפגישה."""
        else:
            # ✨ Calls - פרומפט מפורט לשיחות זורמות וטבעיות
            return f"""אתה העוזר הדיגיטלי של {business_name}. אתה כאן כדי לעזור ללקוחות למצוא את הנכס המושלם - דירות למכירה, דירות להשכרה, בתים, ומשרדים.

התנהלות בשיחה:
• דבר בעברית בלבד, בצורה טבעית וזורמת כמו שיחה רגילה בטלפון
• היה חם, ידידותי, אבל מקצועי - כמו סוכן נדל"ן מנוסה
• תשובות קצרות - 2-3 משפטים בכל תגובה (עד 200 מילים)
• דבר ישירות לעניין, בלי מילוי או סיפורים ארוכים
• ⚠️ חשוב מאוד: אל תחזור על שמך בכל משפט! זה לא טבעי ומעצבן
• הצג את עצמך רק בברכה הראשונה, אחר כך דבר ישר לעניין

איסוף מידע חכם:
שאל שאלה אחת בכל פעם, בסדר הזה:
1. תחילה: מה הלקוח מחפש? (דירה/בית/משרד, מכירה/השכרה)
2. אזור מבוקש או עיר (חשוב מאוד!)
3. תקציב או טווח מחירים - ⚠️ חשוב: תמיד הזכר את סדר הגודל! אמור "מיליון שקל", "מאה אלף שקל", "חצי מיליון" וכו'. לעולם אל תגיד רק את המספר (למשל "1000000") בלי להזכיר אם זה אלף/מיליון/מיליארד!
4. מספר חדרים / גודל
5. פרטי קשר: שם מלא ומייל אם לא ניתנו

מתי לקבוע פגישה:
כשיש לך לפחות: סוג נכס + אזור + תקציב → הצע לקבוע פגישה עם הסוכן. תגיד: "מעולה! יש לי כמה אפשרויות מצוינות. אשמח לקבוע לך פגישה עם אחד הסוכנים שלנו שיציג לך את הנכסים. מתי נוח לך?"

⚠️ **חשוב מאוד - כשהלקוח מסכים לזמן:**
🎯 **חוק ברזל: חזור על הזמן המדויק שהלקוח אמר - לא להמציא שעות!**

כשהלקוח אומר זמן ספציפי:
- לקוח: "מחר ב-10" → אתה: "מעולה! נקבע לך פגישה למחר בשעה 10:00."
- לקוח: "מחר ב-16" → אתה: "מעולה! נקבע לך פגישה למחר בשעה 16:00."
- לקוח: "יום שלישי ב-14:30" → אתה: "מעולה! נקבע לך פגישה ליום שלישי בשעה 14:30."

כשהלקוח אומר זמן כללי (בוקר/צהריים/אחה"צ):
- לקוח: "מחר בבוקר" → אתה: "מעולה! נקבע לך פגישה למחר בשעה 10:00."
- לקוח: "יום שלישי אחר הצהריים" → אתה: "מעולה! נקבע לך פגישה ליום שלישי בשעה 14:00."

⚠️ **אל תשנה את השעה שהלקוח אמר! אם הוא אמר 16 - תאשר 16, לא 10!**

חשוב: אל תמציא מידע! אם לא יודע משהו - הפנה לסוכן אנושי. אם הלקוח עצבני או מתלונן - היה אמפטי והצע דיבור עם מנהל."""

    def generate_response(self, message: str, business_id: int = 1, context: Optional[Dict[str, Any]] = None, channel: str = "calls") -> str:
        """יצירת תגובה מפרומפט דינמי + הקשר - לפי ערוץ (calls/whatsapp)"""
        try:
            # טעינת פרומפט עסק לפי ערוץ
            prompt_data = self.get_business_prompt(business_id, channel)
            
            # בניית הודעות
            messages: List[Dict[str, str]] = [
                {"role": "system", "content": prompt_data["system_prompt"]}
            ]
            
            # ✅ הוספת זמינות לוח שנה
            calendar_info = self._get_calendar_availability(business_id)
            if calendar_info:
                messages.append({
                    "role": "system",
                    "content": f"📅 לוח שנה:\n{calendar_info}\nכשהלקוח מוכן לפגישה, הצע תאריכים פנויים מהרשימה למעלה."
                })
            
            # הוספת הקשר אם קיים
            if context:
                # הוספת מידע בסיסי על הלקוח
                context_info = []
                if context.get("customer_name"):
                    context_info.append(f"שם הלקוח: {context['customer_name']}")
                if context.get("phone_number"):
                    context_info.append(f"טלפון: {context['phone_number']}")
                
                if context_info:
                    messages.append({
                        "role": "system", 
                        "content": "מידע על הלקוח:\n" + "\n".join(context_info)
                    })
                
                # ✅ BUILD 92: שליחת previous_messages כשיחה אמיתית - 10 הודעות לזיכרון מלא!
                if context.get("previous_messages"):
                    prev_msgs = context["previous_messages"][-10:]  # ✅ 10 הודעות אחרונות (לא 6!)
                    for msg in prev_msgs:
                        # ✅ המבנה הוא "לקוח: ..." או "עוזרת: ..." (או "לאה:" legacy)
                        if msg.startswith("לקוח:"):
                            messages.append({
                                "role": "user",
                                "content": msg.replace("לקוח:", "").strip()
                            })
                        elif msg.startswith("עוזרת:") or msg.startswith("לאה:"):  # ✅ תמיכה בשניהם!
                            content = msg.replace("עוזרת:", "").replace("לאה:", "").strip()
                            messages.append({
                                "role": "assistant",
                                "content": content
                            })
            
            # הוספת הודעת המשתמש הנוכחית
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
            return "שלום! איך אוכל לעזור לך?"  # ✅ כללי - לא חושף שם עסק שגוי
        elif any(word in message_lower for word in ["דירה", "בית", "נכס"]):
            return "אשמח לעזור לך! אתה מחפש לקניה או השכרה? באיזה אזור?"
        else:
            return "תודה על הפנייה! אחזור אליך בהקדם עם מענה מפורט."
    
    def _get_calendar_availability(self, business_id: int) -> str:
        """בדיקת זמינות בלוח השנה ל-7 ימים הקרובים"""
        try:
            from server.models_sql import Appointment
            from datetime import datetime, timedelta
            
            # טווח תאריכים: היום + 7 ימים
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            week_end = today + timedelta(days=7)
            
            # שליפת פגישות קיימות
            appointments = Appointment.query.filter(
                Appointment.business_id == business_id,
                Appointment.start_time >= today,
                Appointment.start_time < week_end,
                Appointment.status.in_(['confirmed', 'pending'])
            ).order_by(Appointment.start_time).all()
            
            # הצעת זמנים פנויים (9:00-17:00, כל יום, למעט שבת)
            available_slots = []
            for i in range(7):
                day = today + timedelta(days=i)
                # דלג על שבת (5 = שבת)
                if day.weekday() == 5:
                    continue
                    
                day_name = day.strftime("%A")
                day_name_he = {"Monday": "שני", "Tuesday": "שלישי", "Wednesday": "רביעי", 
                              "Thursday": "חמישי", "Friday": "שישי", "Sunday": "ראשון"}.get(day_name, day_name)
                
                # בדוק אם יש פגישות ביום הזה
                day_start = day.replace(hour=9, minute=0)
                day_end = day.replace(hour=17, minute=0)
                
                day_appointments = [apt for apt in appointments if day_start <= apt.start_time < day_end]
                
                if len(day_appointments) < 4:  # אם פחות מ-4 פגישות - עדיין יש מקום
                    date_str = day.strftime("%d/%m")
                    available_slots.append(f"יום {day_name_he} {date_str} (בוקר/אחה\"צ)")
            
            # בניית טקסט
            result = []
            if available_slots:
                result.append("✅ זמינות השבוע:")
                result.extend([f"  • {slot}" for slot in available_slots[:5]])  # רק 5 ראשונים
            else:
                result.append("⚠️ אין זמינות השבוע - הצע שבוע הבא")
            
            return "\n".join(result)
            
        except Exception as e:
            logger.error(f"Calendar check failed: {e}")
            return "📅 לוח השנה: נא לתאם ישירות עם הסוכן"
    
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

