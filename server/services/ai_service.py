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

logger = logging.getLogger(__name__)

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
            timeout=3.5  # ✅ Production timeout - allows Hebrew responses with margin
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
                    timeout=3.5  # ⚡ 3.5s timeout for real-time conversations
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
    
    def generate_response_with_agent(self, message: str, business_id: int = 1, 
                                     context: Optional[Dict[str, Any]] = None,
                                     channel: str = "calls",
                                     is_first_turn: bool = False,
                                     customer_phone: Optional[str] = None,
                                     customer_name: Optional[str] = None) -> str:
        """
        ✨ BUILD 119: Agent-enhanced response generation
        
        Uses AgentKit to perform real actions (appointments, leads, WhatsApp)
        Falls back to regular generate_response if agents are disabled
        
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
        
        # ⚡ Capture start time BEFORE try block for error logging
        start_time = time.time()
        
        try:
            print("📦 Importing agent modules...")
            logger.info("📦 Importing agent modules...")
            from server.agents import get_agent, AGENTS_ENABLED
            from agents import Runner
            print(f"✅ Agent modules imported. AGENTS_ENABLED={AGENTS_ENABLED}")
            logger.info(f"✅ Agent modules imported. AGENTS_ENABLED={AGENTS_ENABLED}")
            
            if not AGENTS_ENABLED:
                # Double-check - agents not available
                print("⚠️ AGENTS_ENABLED=False in module - using regular response")
                logger.warning("⚠️ AGENTS_ENABLED=False in module - using regular response")
                return self.generate_response(message, business_id, context, channel, is_first_turn)
            
            # Get business name
            business = Business.query.get(business_id)
            business_name = business.name if business else "העסק שלנו"
            
            # 🎯 BUILD 119: Load custom prompt from database!
            prompt_data = self.get_business_prompt(business_id, channel)
            custom_prompt = prompt_data.get("system_prompt", "")  # Extract just the prompt text
            logger.info(f"📋 Loaded prompt for business {business_id}: {len(custom_prompt)} chars")
            
            # Get booking agent with custom prompt and business_id
            print(f"🏗️  Creating agent: type=booking, business={business_name}, business_id={business_id}")
            logger.info(f"🏗️  Creating agent: type=booking, business={business_name}, business_id={business_id}")
            agent = get_agent(agent_type="booking", business_name=business_name, custom_instructions=custom_prompt, business_id=business_id)
            
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
            # Agent SDK needs conversation history in specific format
            conversation_messages = []
            if context and "previous_messages" in context:
                prev_msgs = context["previous_messages"]
                print(f"📚 Found {len(prev_msgs)} previous messages in context")
                
                # Convert to Agent SDK format
                # prev_msgs is list of strings like "לקוח: XXX" or "עוזר: YYY"
                for msg in prev_msgs:
                    if msg.startswith("לקוח:"):
                        # User message
                        conversation_messages.append({
                            "role": "user",
                            "content": msg.replace("לקוח:", "").strip()
                        })
                    elif msg.startswith("עוזר:"):
                        # Assistant message
                        conversation_messages.append({
                            "role": "assistant",
                            "content": msg.replace("עוזר:", "").strip()
                        })
                
                print(f"✅ Converted to {len(conversation_messages)} messages for Agent")
                
            # Add current message
            conversation_messages.append({
                "role": "user",
                "content": message
            })
            
            runner = Runner()
            print(f"🔄 Created Runner with {len(conversation_messages)-1} history messages, executing agent.run()...")
            
            # Use input parameter with conversation history
            result = loop.run_until_complete(
                runner.run(starting_agent=agent, input=conversation_messages, context=agent_context)
            )
            duration_ms = int((time.time() - start_time) * 1000)
            print(f"✅ Runner.run() completed in {duration_ms}ms")
            
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
                        # Try multiple ways to get tool name
                        tool_name = getattr(item, 'name', None)
                        if not tool_name:
                            tool_name = getattr(item, 'tool_name', None)
                        if not tool_name and hasattr(item, 'tool'):
                            tool_name = getattr(item.tool, 'name', None)
                        if not tool_name:
                            tool_name = 'unknown'
                        
                        print(f"  🔧 Tool call #{tool_count}: {tool_name}")
                        print(f"     📋 Item attributes: {dir(item)[:10]}...")  # First 10 attributes
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
                
                if tool_count > 0:
                    print(f"✅ Agent executed {tool_count} tool actions")
                    logger.info(f"✅ Agent executed {tool_count} tool actions")
                else:
                    print(f"⚠️ Agent DID NOT call any tools! (message: '{message[:50]}...')")
                    logger.warning(f"⚠️ Agent DID NOT call any tools! (message: '{message[:50]}...')")
            else:
                print(f"⚠️ Result has NO new_items or new_items is empty!")
            
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

