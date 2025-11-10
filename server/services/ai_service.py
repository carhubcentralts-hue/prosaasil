"""
AI Service - Unified OpenAI Service for All Communication Channels
שירות AI מאוחד - מחבר פרומפטים דינמיים מהמסד נתונים עם OpenAI
✨ BUILD 119: AgentKit integration for real actions (appointments, leads, WhatsApp)
"""
import os
import logging
import time
from typing import Dict, Any, Optional, List
from openai import OpenAI
from server.models_sql import BusinessSettings, PromptRevisions, Business, AgentTrace
from server.db import db
from datetime import datetime

# 🔥 CRITICAL: Import agent modules at TOP of file (not inside function!)
# This prevents re-importing on every call and speeds up response time
try:
    from server.agent_tools import get_agent, AGENTS_ENABLED
    from agents import Runner
    AGENT_MODULES_LOADED = True
    logger_temp = logging.getLogger(__name__)
    logger_temp.info("✅ Agent modules pre-loaded at module level")
except ImportError as e:
    AGENT_MODULES_LOADED = False
    AGENTS_ENABLED = False
    logger_temp = logging.getLogger(__name__)
    logger_temp.warning(f"⚠️ Agent modules not available: {e}")

logger = logging.getLogger(__name__)

# 🎯 Intent Router - Fast Hebrew intent detection (no LLM needed!)
def route_intent(message: str) -> str:
    """
    ⚡ FAST intent detection for Hebrew messages - determines routing
    
    Returns:
        'book' - Customer wants to schedule appointment
        'reschedule' - Change existing appointment
        'cancel' - Cancel appointment
        'info' - Asking for information (price, hours, location, etc.)
        'whatsapp' - Request WhatsApp message
        'human' - Want to speak to human
        'other' - General conversation
    """
    msg_lower = message.lower().strip()
    
    # Info intent - CHECK FIRST (before booking)
    # People asking about hours/price/location shouldn't trigger booking
    info_keywords = [
        "כמה עולה", "מחיר", "עלות", "תשלום", "כשר", "כשרות",
        "מיקום", "איפה", "כתובת", "חניה", "אזור", 
        "שעות פתיחה", "פתוח", "סגור", "עובדים", "מתי פתוחים",
        "גודל", "חדר", "אנשים", "מקסימום", "מה יש", "מה זה",
        "זמינים", "זמינות", "פנויים", "פתוחים בערב", "עובדים בשבת",
        "מה השעות", "עד מתי", "מה הזמינות", "תפריט", "שירותים"
    ]
    
    if any(kw in msg_lower for kw in info_keywords):
        return "info"
    
    # WhatsApp intent
    whatsapp_keywords = ["וואטסאפ", "whatsapp", "שלח לי", "קישור"]
    if any(kw in msg_lower for kw in whatsapp_keywords):
        return "whatsapp"
    
    # Human intent
    human_keywords = ["נציג", "בן אדם", "בנאדם", "לדבר עם", "מנהל"]
    if any(kw in msg_lower for kw in human_keywords):
        return "human"
    
    # Reschedule intent
    reschedule_keywords = ["להזיז", "להקדים", "לדחות", "להחליף", "לשנות תור"]
    if any(kw in msg_lower for kw in reschedule_keywords):
        return "reschedule"
    
    # Cancel intent
    cancel_keywords = ["לבטל", "תבטל", "לא מגיע", "לא יכול", "ביטול"]
    if any(kw in msg_lower for kw in cancel_keywords):
        return "cancel"
    
    # Booking intent - REQUIRES explicit scheduling action + time/day
    # Strong booking signals (explicit intent)
    strong_booking = ["לקבוע", "תור", "פגישה", "תיאום", "בדוק לי", 
                      "זמין", "פנוי", "יש מקום", "להזמין", "רוצה לקבוע"]
    
    # Time expressions (need these WITH day words)
    import re
    has_time = bool(re.search(r'\d{1,2}(:\d{2})?|\bב-\d|\bבשעה', msg_lower))
    
    # Day words (only booking if combined with time or strong intent)
    day_words = ["מחר", "היום", "ראשון", "שני", "שלישי", "רביעי", "חמישי", "שבת", "מוצ״ש"]
    has_day = any(day in msg_lower for day in day_words)
    
    # Classify as booking ONLY if:
    # 1. Strong booking keyword, OR
    # 2. Day word + time expression together
    if any(kw in msg_lower for kw in strong_booking):
        return "book"
    if has_day and has_time:
        return "book"
    
    return "other"

# Global AI service instance for cache sharing
_global_ai_service = None

def get_ai_service():
    """Get or create global AI service instance"""
    global _global_ai_service
    if _global_ai_service is None:
        _global_ai_service = AIService()
        # ⚡ CRITICAL: Warmup cache at startup
        _warmup_ai_cache(_global_ai_service)
    return _global_ai_service

def _warmup_ai_cache(service: 'AIService'):
    """⚡ Preload cache for common business IDs to prevent first-turn latency"""
    try:
        import time
        start = time.time()
        
        # Warmup business 1 and 11 (most common)
        for business_id in [1, 11]:
            for channel in ['calls', 'whatsapp']:
                try:
                    service.get_business_prompt(business_id, channel)
                    logger.info(f"✅ WARMUP: Preloaded business {business_id} {channel}")
                except Exception as e:
                    logger.warning(f"⚠️ WARMUP failed for business {business_id} {channel}: {e}")
        
        warmup_time = time.time() - start
        logger.info(f"✅ AI_CACHE_WARMUP: Completed in {warmup_time:.3f}s")
    except Exception as e:
        logger.error(f"❌ AI cache warmup failed: {e}")

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
            timeout=2.5  # 🔥 REDUCED: 2.5s timeout for faster real-time conversations (was 3.5s)
        )
        self._cache = {}  # קאש פרומפטים לביצועים
        self._cache_timeout = 300  # ⚡ 5 דקות - מספיק ארוך לשיחה שלמה
        
    def get_business_prompt(self, business_id: int, channel: str = "calls") -> Dict[str, Any]:
        """טעינת פרומפט עסק מהמסד נתונים עם קאש - לפי ערוץ (calls/whatsapp)"""
        cache_key = f"business_{business_id}_{channel}"
        now = datetime.now().timestamp()
        
        # בדיקת קאש
        if cache_key in self._cache:
            cached_data, timestamp = self._cache[cache_key]
            if now - timestamp < self._cache_timeout:
                logger.info(f"✅ CACHE_HIT: business {business_id} {channel}")
                return cached_data
        
        try:
            # ⚡ CRITICAL: Measure DB query time
            import time
            db_start = time.time()
            
            # טעינת הגדרות עסק
            settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
            business = Business.query.get(business_id)
            
            db_time = time.time() - db_start
            logger.info(f"📊 DB_QUERY: {db_time:.3f}s for business {business_id}")
            
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
            
            # ⚡ BUILD 118: Warn if prompt is too long (causes OpenAI timeouts)
            if len(system_prompt) > 3000:
                logger.warning(f"⚠️ PROMPT_TOO_LONG: {len(system_prompt)} chars (recommended: <3000) - may cause OpenAI timeouts!")
            else:
                logger.info(f"✅ Prompt length OK: {len(system_prompt)} chars")
            
            if not settings:
                # ⚡ BUILD 117: INCREASED - allow complete sentences without truncation
                prompt_data = {
                    "system_prompt": system_prompt,
                    "model": "gpt-4o-mini",  # Fast model
                    "max_tokens": 350,  # ⚡ BUILD 117: 350 tokens for COMPLETE sentences (no mid-sentence cuts!)
                    "temperature": 0.3  # Balanced temperature for natural responses
                }
            else:
                prompt_data = {
                    "system_prompt": system_prompt,
                    "model": settings.model,
                    "max_tokens": min(settings.max_tokens, 350),  # ⚡ BUILD 117: Cap at 350 for complete sentences
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
                "max_tokens": 350,  # ⚡ BUILD 117: 350 tokens for COMPLETE sentences
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

    def generate_response(self, message: str, business_id: int = 1, context: Optional[Dict[str, Any]] = None, channel: str = "calls", is_first_turn: bool = False) -> str:
        """יצירת תגובה מפרומפט דינמי + הקשר - לפי ערוץ (calls/whatsapp)"""
        try:
            # טעינת פרומפט עסק לפי ערוץ
            prompt_data = self.get_business_prompt(business_id, channel)
            
            # ⚡ BUILD 117: First turn - NO SPECIAL LIMIT! Let AI finish complete sentences
            # User requirement: "אם היא צריכה להסביר דקה שתסביר דקה" - let it speak as long as needed
            if is_first_turn:
                # Don't reduce max_tokens for first turn - keep the default 350 for complete sentences
                logger.info(f"🎯 First turn - using full {prompt_data['max_tokens']} tokens for complete sentences")
            
            # בניית הודעות
            messages: List[Dict[str, str]] = [
                {"role": "system", "content": prompt_data["system_prompt"]}
            ]
            
            # ✅ הוספת זמינות לוח שנה (רק ל-WhatsApp - לא לטלפון בגלל latency!)
            if channel == "whatsapp":
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
            
            # ⚡ CRITICAL: Measure OpenAI call time
            import time
            openai_start = time.time()
            
            # ⚡ BUILD 118: Add explicit timeout to prevent long waits
            try:
                response = self.client.chat.completions.create(
                    model=prompt_data["model"],
                    messages=messages,  # type: ignore
                    max_tokens=prompt_data["max_tokens"],
                    temperature=prompt_data["temperature"],
                    timeout=2.5  # 🔥 REDUCED: 2.5s timeout for real-time conversations (was 3.5s)
                )
                
                openai_time = time.time() - openai_start
                logger.info(f"✅ OPENAI_SUCCESS: {openai_time:.3f}s")
                
                ai_response = response.choices[0].message.content
                if ai_response:
                    ai_response = ai_response.strip()
                else:
                    ai_response = "מצטער, לא הצלחתי לייצר תגובה כרגע."
                logger.info(f"AI response generated for business {business_id}: {len(ai_response)} chars")
                return ai_response
                
            except Exception as openai_error:
                openai_time = time.time() - openai_start
                error_type = type(openai_error).__name__
                logger.error(f"🔴 OPENAI_FAILED: {error_type} after {openai_time:.3f}s: {str(openai_error)[:200]}")
                raise  # Re-raise to outer exception handler
            
        except Exception as e:
            logger.error(f"🔴 AI_GENERATION_FAILED: {type(e).__name__}: {str(e)[:200]}")
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
            
            # ⚡ FAST: Limit query time with LIMIT
            # טווח תאריכים: היום + 7 ימים
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            week_end = today + timedelta(days=7)
            
            # שליפת פגישות קיימות (LIMIT 10 למהירות!)
            appointments = Appointment.query.filter(
                Appointment.business_id == business_id,
                Appointment.start_time >= today,
                Appointment.start_time < week_end,
                Appointment.status.in_(['confirmed', 'pending'])
            ).order_by(Appointment.start_time).limit(10).all()
            
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
    
    def _generate_faq_response(self, message: str, business_id: int, channel: str) -> str:
        """
        ⚡ FAST FAQ response without AgentKit (info/other intents)
        Uses lightweight GPT-4o-mini with business prompt, no tools
        ~0.8s latency
        """
        try:
            # Get business prompt for context
            prompt_data = self.get_business_prompt(business_id, channel)
            business_prompt = prompt_data.get("system_prompt", "")
            business_name = prompt_data.get("business_name", "העסק")
            
            # Build minimal system prompt
            system_msg = f"You are answering questions about {business_name}. Keep responses SHORT (1-2 sentences in Hebrew).\n\n{business_prompt[:500]}"
            
            # Quick OpenAI call - no tools, minimal tokens
            client = self.get_client()
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": message}
                ],
                max_tokens=50,  # Very short responses
                temperature=0.3
            )
            
            answer = response.choices[0].message.content.strip()
            print(f"⚡ FAQ_RESPONSE: {answer} ({len(answer)} chars)")
            return answer
            
        except Exception as e:
            logger.error(f"FAQ response failed: {e}")
            return "סליחה, יש לי בעיה טכנית. אפשר לנסות שוב?"
    
    def _handle_direct_booking(self, message: str, business_id: int, customer_phone: Optional[str] = None) -> Optional[str]:
        """
        ⚡ FAST-PATH: Direct booking for simple requests (e.g., "מחר ב-2")
        Bypasses AgentKit entirely - parses time with regex + calls calendar tools directly
        ~1.5s latency
        
        Returns:
            Hebrew confirmation string if successful, None if parsing failed (fallback to AgentKit)
        """
        import re
        from datetime import datetime, timedelta
        import pytz
        
        try:
            # Parse hour from message
            hour_match = re.search(r"(\d{1,2})(?::(\d{2}))?", message)
            if not hour_match:
                print("⚠️ FAST-PATH: No hour found, fallback to AgentKit")
                return None
            
            hour = int(hour_match.group(1))
            minute = int(hour_match.group(2) or 0)
            
            # Afternoon default for numbers 1-8
            if hour <= 8:
                hour += 12
            
            # Parse day
            tz = pytz.timezone("Asia/Jerusalem")
            target = datetime.now(tz)
            
            msg_lower = message.lower()
            if "מחר" in msg_lower:
                target += timedelta(days=1)
            elif "ראשון" in msg_lower:
                target += timedelta(days=(6 - target.weekday()) % 7)
            elif "שני" in msg_lower:
                target += timedelta(days=(7 - target.weekday()) % 7)
            # Add more day parsing as needed...
            
            target = target.replace(hour=hour, minute=minute, second=0, microsecond=0)
            date_iso = target.strftime("%Y-%m-%d")
            time_iso = target.strftime("%H:%M")
            
            print(f"⚡ FAST-PATH: Parsed time → {date_iso} {time_iso}")
            
            # Import calendar tools
            from server.agent_tools.tools_calendar import calendar_find_slots_impl, calendar_create_appointment_impl
            from flask import g
            
            # Build minimal context
            context = {
                "business_id": business_id,
                "customer_phone": customer_phone,
                "channel": "calls"
            }
            
            # Check availability
            slots_result = calendar_find_slots_impl(date_iso=date_iso, duration_min=60, context=context)
            
            if not slots_result.get("ok") or not slots_result.get("slots"):
                print(f"⚠️ FAST-PATH: No slots available for {date_iso} {time_iso}")
                return f"מצטער, אין זמינות ב-{time_iso}. רוצה שאבדוק שעה אחרת?"
            
            # Verify requested time is in available slots
            requested_datetime = target.strftime("%Y-%m-%d %H:%M")
            available_slots = [s["start"] for s in slots_result["slots"]]
            
            if requested_datetime not in available_slots:
                # Offer first 2 alternatives
                alternatives = available_slots[:2]
                alt_times = [s.split()[1] for s in alternatives]
                return f"אין זמינות ב-{time_iso}. יש {' או '.join(alt_times)}?"
            
            # Need phone before booking
            if not customer_phone:
                print(f"⚠️ FAST-PATH: Need phone number for booking")
                return None  # Fallback to AgentKit to collect phone
            
            # Create appointment
            # Note: This is simplified - full implementation would need customer_name too
            print(f"⚡ FAST-PATH: Attempting booking for {requested_datetime}")
            # For now, fallback to AgentKit for actual booking (needs name + phone collection)
            return None
            
        except Exception as e:
            logger.error(f"Fast-path booking failed: {e}")
            print(f"⚠️ FAST-PATH ERROR: {e}, fallback to AgentKit")
            return None  # Fallback to full AgentKit on any error
    
    def generate_response_with_agent(self, message: str, business_id: int = 1, 
                                     context: Optional[Dict[str, Any]] = None,
                                     channel: str = "calls",
                                     is_first_turn: bool = False,
                                     customer_phone: Optional[str] = None,
                                     customer_name: Optional[str] = None) -> str:
        """
        ✨ BUILD 119: Agent-enhanced response generation WITH SMART ROUTING
        
        Routes based on intent:
        - FAQ/Info → Lightweight GPT-4o-mini (~0.8s)
        - Simple booking → Fast-path with direct calendar calls (~1.5s)
        - Complex booking → Full AgentKit (~2-3s)
        
        Args:
            message: Customer's message
            business_id: Business ID
            context: Conversation context
            channel: calls/whatsapp
            is_first_turn: First message in conversation
            customer_phone: Customer phone for lead creation
            customer_name: Customer name for personalization
            
        Returns:
            AI response (potentially enhanced with tool actions)
        """
        # Check if agents are enabled (default: enabled)
        agents_enabled = os.getenv("AGENTS_ENABLED", "1") == "1"
        print(f"🎯 AGENTS_ENABLED = {agents_enabled}")
        logger.info(f"🎯 AGENTS_ENABLED = {agents_enabled}")
        
        if not agents_enabled:
            # Fallback to regular response
            print("⚠️ Agents disabled - using regular response")
            logger.warning("⚠️ Agents disabled - using regular response")
            return self.generate_response(message, business_id, context, channel, is_first_turn)
        
        # 🚀 AGENTKIT GATE - Detect intent and route accordingly
        agentkit_booking_only = os.getenv("AGENTKIT_BOOKING_ONLY", "1") == "1"
        fast_path_enabled = os.getenv("FAST_PATH_ENABLED", "1") == "1"
        
        intent = route_intent(message)
        print(f"🎯 INTENT_DETECTED: {intent} (booking_only={agentkit_booking_only}, fast_path={fast_path_enabled})")
        logger.info(f"🎯 Intent: {intent}, Message: '{message[:50]}...'")
        
        # Route 1: FAQ/Info Path - NO AgentKit needed (~0.8s)
        if agentkit_booking_only and intent in ['info', 'other', 'whatsapp', 'human']:
            print(f"⚡ ROUTE: FAQ path for '{intent}' intent")
            return self._generate_faq_response(message, business_id, channel)
        
        # Route 2: Fast-Path for simple booking (~1.5s)
        if fast_path_enabled and intent == 'book':
            print(f"⚡ ROUTE: Attempting fast-path for booking...")
            fast_result = self._handle_direct_booking(message, business_id, customer_phone)
            if fast_result:
                print(f"✅ FAST-PATH SUCCESS: {fast_result}")
                return fast_result
            else:
                print(f"⚠️ FAST-PATH FAILED: Fallback to AgentKit")
        
        # Route 3: Full AgentKit for complex booking/reschedule/cancel (~2-3s)
        print(f"🤖 ROUTE: Full AgentKit for '{intent}' intent")
        
        # ⚡ Capture start time BEFORE try block for error logging
        start_time = time.time()
        
        try:
            # 🔥 FIX: Modules now imported at top of file - no re-import needed!
            if not AGENT_MODULES_LOADED:
                # Double-check - agents not available
                print("⚠️ AGENTS_ENABLED=False in module - using regular response")
                logger.warning("⚠️ AGENTS_ENABLED=False in module - using regular response")
                return self.generate_response(message, business_id, context, channel, is_first_turn)
            
            # Get business name
            db_start = time.time()
            business = Business.query.get(business_id)
            business_name = business.name if business else "העסק שלנו"
            
            # 🎯 BUILD 119: Load custom prompt from database!
            prompt_data = self.get_business_prompt(business_id, channel)
            custom_prompt = prompt_data.get("system_prompt", "")  # Extract just the prompt text
            db_time = (time.time() - db_start) * 1000
            print(f"⏱️ DB query time: {db_time:.0f}ms")
            logger.info(f"📋 Loaded prompt for business {business_id}: {len(custom_prompt)} chars")
            
            # 🔥 NEW: Try to get cached agent first!
            from server.services.agent_cache import get_agent_cache
            agent_cache = get_agent_cache()
            
            agent_create_start = time.time()
            agent = agent_cache.get(business_id, channel)
            
            if agent:
                # Cache HIT - reuse existing agent!
                agent_create_time = (time.time() - agent_create_start) * 1000
                print(f"♻️  REUSING cached agent: business={business_name}, business_id={business_id}, channel={channel}")
                print(f"⏱️ Cache lookup time: {agent_create_time:.0f}ms")
                logger.info(f"♻️  Agent CACHE HIT for {business_name} ({channel})")
            else:
                # Cache MISS - create new agent and cache it
                print(f"🏗️  Creating NEW agent: type=booking, business={business_name}, business_id={business_id}, channel={channel}")
                logger.info(f"🏗️  Creating agent: type=booking, business={business_name}, business_id={business_id}, channel={channel}")
                agent = get_agent(agent_type="booking", business_name=business_name, custom_instructions=custom_prompt, business_id=business_id, channel=channel)
                agent_create_time = (time.time() - agent_create_start) * 1000
                print(f"⏱️ Agent creation time: {agent_create_time:.0f}ms")
                
                # Cache the new agent for future reuse
                if agent:
                    agent_cache.set(business_id, channel, agent, business_name)
                    print(f"💾 Agent cached for future reuse")
            
            if not agent:
                print("❌ Failed to create agent - falling back to regular response")
                logger.error("❌ Failed to create agent - falling back to regular response")
                return self.generate_response(message, business_id, context, channel, is_first_turn)
            
            print(f"✅ Agent created successfully: {agent.name}")
            logger.info(f"✅ Agent created successfully: {agent.name}")
            
            # Build enhanced context for agent
            agent_context = {
                "business_id": business_id,
                "business_name": business_name,
                "customer_phone": customer_phone,
                "customer_name": customer_name,
                "channel": channel,
                "is_first_turn": is_first_turn,
                **(context or {})
            }
            
            # 🔥 CRITICAL: Store context in Flask g so tools can access it!
            from flask import g
            g.agent_context = agent_context
            print(f"✅ Stored agent_context in Flask g: phone={customer_phone}, name={customer_name}")
            
            # Run agent using Runner (with proper async handling for eventlet threads)
            print(f"🤖 Running agent for business {business_id}, channel={channel}")
            print(f"   📝 User message: '{message[:100]}...'")
            print(f"   📋 Context: business_id={business_id}, phone={customer_phone}, name={customer_name}")
            logger.info(f"🤖 Running agent for business {business_id}, channel={channel}")
            logger.info(f"   📝 User message: '{message[:100]}...'")
            logger.info(f"   📋 Context: business_id={business_id}, phone={customer_phone}, name={customer_name}")
            
            import asyncio
            
            # Create new event loop for this thread (eventlet compatibility)
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                # No event loop in current thread - create one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # 🔥 BUILD CONVERSATION HISTORY for Agent SDK
            # ⚡ OPTIMIZATION: Keep last 8 messages - balances latency with booking context
            # (8 messages = 4 turns, enough for most booking flows while reducing tokens)
            history_start = time.time()
            conversation_messages = []
            if context and "previous_messages" in context:
                prev_msgs = context["previous_messages"][-8:]  # 🔥 8 messages = 4 full turns
                print(f"📚 Found {len(context['previous_messages'])} messages, using last {len(prev_msgs)} for latency")
                
                # Convert to Agent SDK format
                # prev_msgs is list of strings like "לקוח: XXX" or "עוזר: YYY"
                for msg in prev_msgs:
                    content = None
                    if msg.startswith("לקוח:"):
                        content = msg.replace("לקוח:", "").strip()[-250:]  # 🔥 Truncate long messages
                        conversation_messages.append({"role": "user", "content": content})
                    elif msg.startswith("עוזר:"):
                        content = msg.replace("עוזר:", "").strip()[-250:]  # 🔥 Truncate long messages
                        conversation_messages.append({"role": "assistant", "content": content})
                
                history_time = (time.time() - history_start) * 1000
                print(f"✅ Converted to {len(conversation_messages)} messages for Agent ({history_time:.0f}ms)")
                
            # Add current message
            conversation_messages.append({
                "role": "user",
                "content": message
            })
            
            runner = Runner()
            print(f"🔄 Created Runner with {len(conversation_messages)-1} history messages, executing agent.run()...")
            logger.info(f"⏱️ PERFORMANCE: Starting Runner.run() at {time.time()}")
            
            # Use input parameter with conversation history
            result = loop.run_until_complete(
                runner.run(starting_agent=agent, input=conversation_messages, context=agent_context)
            )
            duration_ms = int((time.time() - start_time) * 1000)
            print(f"✅ Runner.run() completed in {duration_ms}ms")
            logger.info(f"⏱️ PERFORMANCE: Runner.run() completed in {duration_ms}ms")
            
            # Extract response using final_output_as
            reply_text = result.final_output_as(str)
            print(f"📝 Agent final response: '{reply_text[:100] if reply_text else '(EMPTY!)'}...'")
            
            # ✅ CRITICAL: Validate that agent returned a response!
            if not reply_text or not reply_text.strip():
                print(f"❌ CRITICAL: Agent returned EMPTY response! Falling back...")
                logger.error(f"❌ Agent returned empty response for message: {message[:100]}")
                return self.generate_response(message, business_id, context, channel, is_first_turn)
            
            # DEBUG: Check result structure
            print(f"🔍 Result type: {type(result).__name__}")
            print(f"🔍 Has new_items: {hasattr(result, 'new_items')}")
            if hasattr(result, 'new_items'):
                print(f"🔍 new_items value: {result.new_items}")
                print(f"🔍 new_items length: {len(result.new_items) if result.new_items else 0}")
            
            # Extract tool calls from new_items
            tool_calls_data = []
            tool_count = 0
            booking_successful = False  # Track if booking actually succeeded
            
            if hasattr(result, 'new_items') and result.new_items:
                print(f"📊 Agent returned {len(result.new_items)} items")
                logger.info(f"📊 Agent returned {len(result.new_items)} items")
                # Filter for ToolCallItem types and extract tool names
                for idx, item in enumerate(result.new_items):
                    item_type = type(item).__name__
                    print(f"   - Item #{idx}: {item_type}")
                    logger.info(f"   - Item type: {item_type}")
                    
                    if item_type == 'ToolCallItem':
                        tool_count += 1
                        
                        # 🔍 FULL DEBUG: Print ALL attributes to find tool name
                        print(f"  🔍 DEBUG ToolCallItem #{tool_count}:")
                        all_attrs = [a for a in dir(item) if not a.startswith('_')]
                        print(f"     All attributes: {all_attrs}")
                        
                        # Try to access common attributes
                        for attr in ['name', 'tool_name', 'tool_call', 'function', 'tool']:
                            if hasattr(item, attr):
                                val = getattr(item, attr)
                                print(f"     {attr} = {val}")
                        
                        # Try multiple ways to get tool name
                        tool_name = getattr(item, 'name', None)
                        if not tool_name:
                            tool_name = getattr(item, 'tool_name', None)
                        if not tool_name and hasattr(item, 'tool_call'):
                            tc = getattr(item, 'tool_call')
                            if isinstance(tc, dict):
                                tool_name = tc.get('name') or tc.get('function', {}).get('name')
                            elif hasattr(tc, 'name'):
                                tool_name = tc.name
                            elif hasattr(tc, 'function'):
                                tool_name = getattr(tc.function, 'name', None)
                        if not tool_name and hasattr(item, 'tool'):
                            tool_obj = getattr(item, 'tool')
                            tool_name = getattr(tool_obj, 'name', None)
                        if not tool_name:
                            tool_name = 'unknown'
                        
                        print(f"  🔧 Tool call #{tool_count}: {tool_name}")
                        logger.info(f"  ✅ Tool call #{tool_count}: {tool_name}")
                        tool_calls_data.append({
                            "tool": tool_name,
                            "status": "success",
                            "result": None  # Result is in separate ToolCallOutputItem
                        })
                    
                    elif item_type == 'ToolCallOutputItem':
                        # Extract tool output/result
                        output = getattr(item, 'output', None)
                        print(f"  📤 Tool output: {str(output)[:200] if output else 'None'}...")
                        if output:
                            logger.info(f"     Tool returned: {str(output)[:100]}")
                            
                            # 🔍 CHECK if this is a successful booking
                            if isinstance(output, dict):
                                if output.get('ok') is True and output.get('appointment_id'):
                                    booking_successful = True
                                    print(f"     ✅ DETECTED SUCCESSFUL BOOKING: appointment_id={output.get('appointment_id')}")
                
                if tool_count > 0:
                    print(f"✅ Agent executed {tool_count} tool actions")
                    logger.info(f"✅ Agent executed {tool_count} tool actions")
                else:
                    print(f"⚠️ Agent DID NOT call any tools! (message: '{message[:50]}...')")
                    logger.warning(f"⚠️ Agent DID NOT call any tools! (message: '{message[:50]}...')")
            else:
                print(f"⚠️ Result has NO new_items or new_items is empty!")
            
            # 🚨 BUILD 138: VALIDATION - Detect "hallucinated bookings"
            # If agent claims action without executing tool, BLOCK response
            claim_words = ["קבעתי", "שלחתי", "יצרתי", "הפגישה נקבעה", "הפגישה קבועה", "סגרתי", "נקבע", "התור נקבע", "התור קבוע"]
            claimed_action = any(word in reply_text for word in claim_words)
            
            # Check if calendar_create_appointment was called (with or without _wrapped suffix)
            booking_tool_called = any(
                tc.get("tool") in ["calendar_create_appointment", "calendar_create_appointment_wrapped"]
                for tc in tool_calls_data
            )
            
            # 🔥 WORKAROUND: Also check if we detected a successful booking in the output
            # (in case tool name extraction failed but booking actually succeeded)
            print(f"  🔍 VALIDATION CHECK:")
            print(f"     claimed_action={claimed_action}")
            print(f"     booking_tool_called={booking_tool_called}")
            print(f"     booking_successful={booking_successful}")
            
            if claimed_action and not booking_tool_called and not booking_successful:
                print(f"🚨 BLOCKED HALLUCINATED BOOKING!")
                print(f"   Agent claimed: '{reply_text[:80]}...'")
                print(f"   But NO calendar_create_appointment was called AND no successful booking detected!")
                logger.error(f"🚨 Blocked hallucinated booking: agent claimed action without tool call")
                
                # Override response with corrective message
                reply_text = "אני עדיין צריך לבדוק זמינות. איזה יום ושעה היית רוצה?"
                print(f"   ✅ Replaced with: '{reply_text}'")
            
            # ✨ Save trace to database
            try:
                trace = AgentTrace(
                    business_id=business_id,
                    agent_type="booking",
                    channel=channel,
                    customer_phone=customer_phone,
                    customer_name=customer_name,
                    user_message=message[:1000],  # Limit length
                    agent_response=reply_text[:2000],
                    tool_calls=tool_calls_data if tool_calls_data else None,
                    tool_count=tool_count,
                    status="success",
                    duration_ms=duration_ms
                )
                db.session.add(trace)
                db.session.commit()
                logger.info(f"📊 Saved agent trace #{trace.id} (duration: {duration_ms}ms)")
            except Exception as trace_error:
                logger.error(f"Failed to save agent trace: {trace_error}")
                # Don't fail the whole request just because trace failed
                db.session.rollback()
            
            return reply_text
            
        except Exception as e:
            logger.error(f"Agent error (falling back to regular response): {e}")
            import traceback
            traceback.print_exc()
            
            # ✨ Save error trace with duration
            try:
                error_duration_ms = int((time.time() - start_time) * 1000)
                trace = AgentTrace(
                    business_id=business_id,
                    agent_type="booking",
                    channel=channel,
                    customer_phone=customer_phone,
                    customer_name=customer_name,
                    user_message=message[:1000],
                    agent_response=None,
                    tool_calls=None,
                    tool_count=0,
                    status="error",
                    error_message=str(e)[:500],
                    duration_ms=error_duration_ms
                )
                db.session.add(trace)
                db.session.commit()
                logger.info(f"📊 Saved error trace (duration: {error_duration_ms}ms)")
            except:
                db.session.rollback()
            
            # Fallback to regular response
            return self.generate_response(message, business_id, context, channel, is_first_turn)

def generate_ai_response(message: str, business_id: int = 1, 
                        context: Optional[Dict[str, Any]] = None, channel: str = "calls",
                        is_first_turn: bool = False) -> str:
    """פונקציה עזר לקריאה מהירה לשירות AI - לפי ערוץ"""
    return get_ai_service().generate_response(message, business_id, context, channel, is_first_turn)

