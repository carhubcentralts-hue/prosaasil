"""
AI Service - Unified OpenAI Service for All Communication Channels
שירות AI מאוחד - מחבר פרומפטים דינמיים מהמסד נתונים עם OpenAI
✨ BUILD 119: AgentKit integration for real actions (appointments, leads, WhatsApp)
🚀 Phase 2K: Fast Intent Router - run AgentKit only for bookings (≤2s target)
"""
import os
import logging
import time
import re
from typing import Dict, Any, Optional, List, Literal
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

# Global AI service instance for cache sharing
_global_ai_service = None

# 🚀 Phase 2K: Intent Router Configuration
# ✅ ENABLED: FAQ fast-path with improved context and token limits
AGENTKIT_BOOKING_ONLY = os.getenv("AGENTKIT_BOOKING_ONLY", "1") == "1"  # Default ON
FAST_PATH_ENABLED = os.getenv("FAST_PATH_ENABLED", "1") == "1"  # Default ON

def route_intent_hebrew(text: str) -> Literal["book", "reschedule", "cancel", "info", "whatsapp", "human", "other"]:
    """
    🚀 Fast Hebrew intent detection - NO LLM!
    Returns intent category for routing decisions.
    Target: <10ms for classification
    
    Priority order: reschedule > cancel > whatsapp > human > info > book > other
    """
    text_lower = text.lower().strip()
    
    # 🔄 RESCHEDULE: Change appointment (CHECK FIRST - more specific)
    reschedule_patterns = [
        r'להזיז|להקדים|לדחות|להחליף.*שעה|לשנות.*תור',
        r'אפשר.*לשנות|אפשר.*להזיז'
    ]
    
    # ❌ CANCEL: Cancel appointment (CHECK SECOND - specific action)
    cancel_patterns = [
        r'לבטל|תבטל|ביטול.*תור|לא.*מגיע',
        r'אני.*לא.*יכול|אין.*אפשרות'
    ]
    
    # 📱 WHATSAPP: Send info via WhatsApp (CHECK THIRD - clear intent)
    whatsapp_patterns = [
        r'שלח.*לי|תשלח.*לי',
        r'וואטסאפ|whatsapp',
        r'הודעה|מסרון'
    ]
    
    # 👤 HUMAN: Transfer to agent (CHECK FOURTH - escalation)
    human_patterns = [
        r'נציג|בן.*אדם|איש.*אמיתי',
        r'לדבר.*עם|להעביר'
    ]
    
    # ℹ️ INFO: General information (CHECK AFTER booking pre-check!)
    # 🔥 TIGHTENED: These patterns now only match if NO booking verbs present
    info_patterns = [
        # 🔥 CRITICAL: Question words → info (אלה שאלות מידע!)
        # But: "מתי אפשר לקבוע?" → book (caught by pre-check)
        r'^(מה|איזה|איזו|כמה|למה|מדוע|איך|היכן|מתי)\s',  # Start with question word
        
        # 🔥 CRITICAL FIX: "יש..." questions - ONLY amenities (not rooms/services)
        r'יש\s+(אוכל|שתיי?ה|תפריט|מנות|אלכוהול|בר|משקאות|קפה|מזון)',
        r'יש\s+(חניה|חנייה|גישה|מיזוג|wifi|אינטרנט|מעלית)',
        r'יש\s+לכם\s+(אוכל|שתיי?ה|תפריט|חניה|wifi)',
        r'מה\s+יש\s+(לאכול|לשתות|בתפריט)',
        
        # Pricing (standalone - not with booking verbs)
        r'כמה.*עולה|מחיר(?!.*לקבוע)|עלות|תשלום(?!.*תור)',
        
        # Location
        r'איפה|מיקום|כתובת|היכן',
        
        # Hours
        r'שעות.*פתיחה|מתי.*פתוח|שעות.*עבודה|מה.*שעות',
        
        # Amenities & Services - REMOVED generic "חדר" patterns!
        r'כשר|כשרות',
        r'גודל.*חדר|כמה.*אנשים|כמה.*משתתפים',
        r'מה.*הכתובת|מה.*המיקום',
        
        # Menu/food (standalone)
        r'\b(תפריט|מנות|משקאות)\b',
    ]
    
    # 📅 BOOK: Scheduling keywords (CHECK LAST - most generic)
    # 🔥 FIX: Require scheduling VERB + time/day to avoid false positives
    book_patterns = [
        r'לקבוע|תיאום|להזמין|רוצה.*תור|אפשר.*תור',  # Explicit booking verbs
        r'יש.*מקום|יש.*זמן|יש.*פנוי|פנוי.*ל',  # Availability questions
        r'(לבוא|להגיע).*(מחר|היום|ב-\d+|בשעה)',  # "לבוא מחר"
        r'(רוצה|צריך).*(תור|פגישה|תיאום)',  # "רוצה תור"
    ]
    
    # 🔥 FIX: Check patterns in CORRECT priority order
    # Most specific first, most generic last
    
    for pattern in reschedule_patterns:
        if re.search(pattern, text_lower):
            return "reschedule"
    
    for pattern in cancel_patterns:
        if re.search(pattern, text_lower):
            return "cancel"
    
    for pattern in whatsapp_patterns:
        if re.search(pattern, text_lower):
            return "whatsapp"
    
    for pattern in human_patterns:
        if re.search(pattern, text_lower):
            return "human"
    
    # 🚨 CRITICAL PRE-CHECK: Booking verbs + time/day → BOOK (before info check!)
    # This fixes: "אפשר לקבוע חדר קריוקי למחר" → book (not info)
    booking_verbs = r'(לקבוע|לתאם|להזמין|אפשר.*תור|רוצה.*תור|צריך.*תור)'
    time_day_terms = r'(מחר|היום|מחרתיים|השבוע|החודש|ב-\d+|בשעה|ביום|בשני|בשלישי|ברביעי|בחמישי|בשישי|בשבת|בראשון)'
    availability_terms = r'(פנוי|זמין|זמן|מקום|תור|פגישה)'
    
    # If booking verb + (time/day OR availability) → it's a booking request!
    if re.search(booking_verbs, text_lower):
        if re.search(time_day_terms, text_lower) or re.search(availability_terms, text_lower):
            print(f"🎯 BOOKING_PRE_CHECK: Detected booking verb + time/availability")
            return "book"
    
    # 🔥 CHECK INFO (after booking pre-check!)
    for pattern in info_patterns:
        if re.search(pattern, text_lower):
            print(f"🎯 INTENT_MATCH: pattern='{pattern}' matched in '{text_lower[:50]}'")
            return "info"
    
    # Only check book patterns AFTER info has been ruled out
    for pattern in book_patterns:
        if re.search(pattern, text_lower):
            return "book"
    
    # 🔥 FIX: Default to "other" (Agent) for unmatched questions
    # Quality/experience questions ("האוכל קשה?") need full Agent conversation handling
    # Only explicit info patterns should trigger FAQ fast-path
    return "other"  # Agent handles ambiguous/quality questions correctly

def extract_time_hebrew(text: str) -> Optional[Dict[str, Any]]:
    """
    🚀 Extract explicit date/time from Hebrew text
    Returns: {"day": "tomorrow", "time": "14:00"} or None
    """
    text_lower = text.lower()
    result = {}
    
    # Day extraction
    day_map = {
        "מחר": "tomorrow",
        "היום": "today",
        "ראשון": "sunday",
        "שני": "monday",
        "שלישי": "tuesday",
        "רביעי": "wednesday",
        "חמישי": "thursday",
        "שישי": "friday",
        "שבת": "saturday"
    }
    
    for heb, eng in day_map.items():
        if heb in text_lower:
            result["day"] = eng
            break
    
    # Time extraction
    # Format: "14:00", "2:30", "בשעה 12", "ב-3"
    time_patterns = [
        r'(\d{1,2}):(\d{2})',  # 14:00, 2:30
        r'בשעה?\s*(\d{1,2})',  # בשעה 12
        r'ב-(\d{1,2})',         # ב-3
        r'(\d{1,2})\s*(בבוקר|בצהריים|אחה״צ|בערב)',  # 3 בבוקר
    ]
    
    for pattern in time_patterns:
        match = re.search(pattern, text_lower)
        if match:
            hour = int(match.group(1))
            
            # Adjust for AM/PM context
            if len(match.groups()) > 1:
                context = match.group(2) if match.group(2) else ""
                if "בבוקר" in context and hour <= 8:
                    hour = hour  # Keep as is
                elif hour <= 8:  # Assume PM for 1-8 without context
                    hour += 12
            
            result["time"] = f"{hour:02d}:00"
            break
    
    return result if result else None

def get_ai_service():
    """Get or create global AI service instance"""
    global _global_ai_service
    if _global_ai_service is None:
        _global_ai_service = AIService()
        # ⚡ CRITICAL: Warmup cache at startup
        _warmup_ai_cache(_global_ai_service)
    return _global_ai_service

def _warmup_ai_cache(service: 'AIService'):
    """⚡ Preload cache for ALL active businesses to prevent first-turn latency"""
    try:
        import time
        from server.models import Business
        from server.app_factory import get_process_app
        
        start = time.time()
        
        # 🔥 MULTI-TENANT: Warmup ALL active businesses (up to 10)
        app = get_process_app()
        with app.app_context():
            businesses = Business.query.filter_by(is_active=True).limit(10).all()
            
            if not businesses:
                logger.warning("⚠️ WARMUP: No active businesses found")
                return
            
            logger.info(f"🔥 AI_CACHE_WARMUP: Found {len(businesses)} active businesses")
            
            for business in businesses:
                business_id = business.id
                for channel in ['calls', 'whatsapp']:
                    try:
                        service.get_business_prompt(business_id, channel)
                        logger.info(f"✅ WARMUP: Preloaded business {business_id} ({business.name}) {channel}")
                    except Exception as e:
                        logger.warning(f"⚠️ WARMUP failed for business {business_id} {channel}: {e}")
            
            warmup_time = time.time() - start
            logger.info(f"✅ AI_CACHE_WARMUP: Completed {len(businesses)} businesses in {warmup_time:.3f}s")
    except Exception as e:
        logger.error(f"❌ AI cache warmup failed: {e}")

def invalidate_business_cache(business_id: int):
    """🔥 CRITICAL: Invalidate cache for business - called after prompt updates"""
    service = get_ai_service()
    
    # 1. Clear prompt cache (AIService)
    cache_keys_to_remove = [
        f"business_{business_id}_calls",
        f"business_{business_id}_whatsapp"
    ]
    for key in cache_keys_to_remove:
        if key in service._cache:
            del service._cache[key]
            logger.info(f"✅ Prompt cache invalidated: {key}")
    
    # 2. 🔥 NEW: Clear agent cache (agent_factory)
    try:
        from server.agent_tools.agent_factory import invalidate_agent_cache
        invalidate_agent_cache(business_id)
        logger.info(f"✅ Agent cache invalidated for business {business_id}")
    except Exception as e:
        logger.error(f"⚠️ Failed to invalidate agent cache: {e}")

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
                    "business_name": business_name,  # 🔥 FIX: Include business name for FAQ handler
                    "model": "gpt-4o-mini",  # Fast model
                    "max_tokens": 350,  # ⚡ BUILD 117: 350 tokens for COMPLETE sentences (no mid-sentence cuts!)
                    "temperature": 0.3  # Balanced temperature for natural responses
                }
            else:
                prompt_data = {
                    "system_prompt": system_prompt,
                    "business_name": business_name,  # 🔥 FIX: Include business name for FAQ handler
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
                "business_name": business_name,  # 🔥 FIX: Include business name for FAQ handler
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
    
    def _generate_faq_response(self, message: str, faq_answer: str, business_id: int, channel: str) -> Optional[str]:
        """
        🚀 Generate FAQ fast-path response using lightweight LLM
        Uses gpt-4o-mini with max_tokens=80, temp=0.3 for <1.5s responses
        
        Args:
            message: Customer question
            faq_answer: Matched FAQ answer from database
            business_id: Business ID
            channel: Communication channel (phone/whatsapp)
            
        Returns:
            Natural Hebrew response or None if generation failed
        """
        start = time.time()
        
        try:
            # Get business name
            business = Business.query.get(business_id)
            business_name = business.name if business else "העסק"
            
            # Mini prompt for FAQ responses - focus on natural rephrasing
            faq_prompt = f"""אתה עוזר דיגיטלי עבור {business_name}.
לקוח שאל שאלה, ונמצאה התאמה במאגר השאלות הנפוצות.

משימתך: השב בעברית טבעית וקצרה (1-2 משפטים) על סמך התשובה שנמצאה.

שאלת הלקוח: {message}
תשובה מהמאגר: {faq_answer}

חוקים:
1. השב בעברית פשוטה וטבעית
2. קצר - מקסימום 2 משפטים
3. אל תוסיף מידע שלא בתשובה המקורית
4. אל תאמר "לפי המידע" או "נמצא במאגר"
5. אל תציין שזאת שאלה נפוצה

תשובה:"""
            
            # Call OpenAI with FAQ-optimized settings
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "user", "content": faq_prompt}
                ],
                max_tokens=80,
                temperature=0.3,
                timeout=4.0
            )
            
            reply = response.choices[0].message.content.strip()
            
            elapsed = (time.time() - start) * 1000
            print(f"⚡ FAQ response generated in {elapsed:.0f}ms")
            logger.info(f"⚡ FAQ fast-path total time: {elapsed:.0f}ms")
            
            return reply
            
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            print(f"❌ FAQ response generation failed after {elapsed:.0f}ms: {e}")
            logger.error(f"FAQ response generation failed: {e}")
            return None
    
    def _handle_lightweight_intent(self, intent: str, message: str, business_id: int, 
                                   channel: str, context: Optional[Dict], customer_phone: Optional[str]) -> Optional[str]:
        """
        🚀 Fast FAQ/Info handler - NO AgentKit!
        Target latency: ~1.0-1.5s
        
        Returns:
            str: Fast response
            None: Signal to fallback to AgentKit
        """
        start = time.time()
        
        try:
            # Get business prompt for FAQ info
            prompt_data = self.get_business_prompt(business_id, channel)
            system_prompt = prompt_data.get("system_prompt", "")
            business_name = prompt_data.get("business_name", "העסק")
            
            response = None
            
            if intent == "info":
                # Extract FAQ from prompt - lightweight LLM call
                response = self._get_faq_response(message, system_prompt, business_name)
                
                # 🔥 FIX: If FAQ failed (returned None), signal fallback to AgentKit
                if response is None:
                    logger.warning(f"FAQ failed for info query, falling back to AgentKit")
                    return None
            
            else:  # Should not reach here (only "info" uses fast path now)
                logger.warning(f"Unexpected intent in fast path: {intent}")
                return None
            
            latency = (time.time() - start) * 1000
            print(f"⚡ FAST_PATH_LATENCY: {latency:.0f}ms (intent={intent})")
            logger.info(f"⚡ Fast path response: {latency:.0f}ms")
            
            return response
            
        except Exception as e:
            logger.error(f"❌ Fast path failed: {e}")
            # Return None to signal fallback to AgentKit
            return None
    
    def _extract_faq_facts(self, question: str, full_prompt: str) -> Optional[str]:
        """
        🔥 ARCHITECT-REVIEWED FIX: Keyword-based topic matching
        Extracts ONLY sections relevant to the question, not all sections blindly.
        
        Strategy:
        1. Parse prompt into labeled sections (pricing, menu, location, hours, description)
        2. Map question keywords to relevant section labels
        3. Return only matching sections (max 500 chars)
        4. Return None if no relevant section → fallback to Agent
        """
        try:
            import re
            
            question_lower = question.lower()
            
            # Parse all sections once into a dict
            sections = {}
            
            # Pricing section (💰)
            pricing_match = re.search(r'💰\s*מחירים:.*?(?=\n\n|$)', full_prompt, re.DOTALL)
            if pricing_match:
                sections['pricing'] = pricing_match.group(0)
            
            # Menu/food section (🍕, 🍴, or keywords)
            menu_match = re.search(r'(🍕|🍴|תפריט|אוכל|משקאות|מנות).*?(?=\n\n|$)', full_prompt, re.DOTALL | re.IGNORECASE)
            if menu_match:
                sections['menu'] = menu_match.group(0)
            
            # Hours/schedule (⏰, 🕒, or "פתוחים")
            hours_match = re.search(r'(⏰|🕒|פתוחים|שעות).*?(?=\n\n|$)', full_prompt, re.DOTALL | re.IGNORECASE)
            if hours_match:
                sections['hours'] = hours_match.group(0)
            
            # Location (📍 or keywords)
            location_match = re.search(r'(📍|ממוקם|מיקום|כתובת|רחוב).*?(?=\n\n|$)', full_prompt, re.DOTALL)
            if location_match:
                sections['location'] = location_match.group(0)
            
            # General description
            desc_match = re.search(r'^(.*?)(?=\n💰|\n🔥|\n💬|$)', full_prompt, re.DOTALL)
            if desc_match and len(desc_match.group(0).strip()) > 50:
                sections['description'] = desc_match.group(0)[:500]
            
            # Topic keyword mapping
            # 🔥 FIX: Only match INFORMATION questions, not quality/experience questions
            topic_keywords = {
                'pricing': r'(מחיר|כמה עולה|כמה זה|עלות|תשלום|עולה)',
                'menu': r'(יש.*אוכל|יש.*תפריט|מה.*תפריט|מה.*לאכול|מה.*לשתות|תפריט|מנות|משקאות|שתיה|בר|קפה)',
                'hours': r'(מתי.*פתוח|שעות.*פתיחה|שעות.*עבודה|מה.*שעות)',
                'location': r'(איפה|מיקום|כתובת|היכן|רחוב|אזור)',
            }
            
            # Find matching sections
            matched_sections = []
            
            for topic, pattern in topic_keywords.items():
                if re.search(pattern, question_lower) and topic in sections:
                    matched_sections.append(sections[topic])
                    print(f"✅ FAQ_MATCH: topic='{topic}' matched in question")
            
            # If no topic match, return general description if it exists
            if not matched_sections and 'description' in sections:
                matched_sections.append(sections['description'])
                print(f"ℹ️ FAQ_FALLBACK: Using general description (no topic match)")
            
            # If still no match, return None → Agent fallback
            if not matched_sections:
                print(f"⚠️ FAQ_NO_MATCH: No relevant section found, routing to Agent")
                return None
            
            # Combine matched sections (max 500 chars)
            result = "\n\n".join(matched_sections)
            if len(result) > 500:
                result = result[:500] + "..."
            
            print(f"✅ FAQ_EXTRACTED: {len(matched_sections)} section(s), {len(result)} chars")
            return result
                
        except Exception as e:
            logger.error(f"FAQ fact extraction failed: {e}")
            # Fallback to Agent
            return None
    
    def _get_faq_response(self, question: str, system_prompt: str, business_name: str) -> Optional[str]:
        """
        🚀 Fast FAQ using optimized LLM call
        Target: ~1.0-1.5s with FACTUAL prompt context (no guard-rails)
        
        🔥 ARCHITECT-REVIEWED FIX (Phase 2O):
        - Extract ONLY factual sections (pricing/hours/location) - NO guard-rails!
        - Use FULL factual context (up to 3000 chars)
        - Increase max_tokens: 80 → 180 for complete Hebrew answers
        - Increase timeout: 1.5s → 2.2s for reliability
        - Add retry logic for robustness
        """
        import time
        faq_start = time.time()
        
        try:
            # 🔥 CRITICAL FIX: Extract ONLY relevant facts based on question!
            print(f"\n📚 FAQ: Extracting facts from prompt ({len(system_prompt)} chars)")
            extract_start = time.time()
            faq_facts = self._extract_faq_facts(question, system_prompt) if system_prompt else None
            
            # If no relevant facts found, return None → Agent fallback
            if faq_facts is None:
                print(f"⚠️ FAQ: No relevant facts found, routing to Agent")
                return None
            
            extract_time = (time.time() - extract_start) * 1000
            print(f"⏱️  FAQ: Fact extraction took {extract_time:.0f}ms")
            print(f"📊 FAQ: Extracted {len(faq_facts)} chars of facts")
            print(f"📝 FAQ: Facts preview: {faq_facts[:200]}...")
            
            # 🔥 CRITICAL FIX: ULTRA-MINIMAL prompt - just answer the question!
            faq_system = f"""השב בקצרה (2 משפטים)."""
            
            # 🔥 FIX: First attempt with full token budget
            try:
                print(f"🤖 FAQ: Calling OpenAI (model=gpt-4o-mini, max_tokens=80, timeout=4.0s)")
                llm_start = time.time()
                
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": faq_system},
                        {"role": "user", "content": f"{faq_facts}\n\n{question}"}
                    ],
                    temperature=0.3,  # ⚡ Balanced for speed vs quality
                    max_tokens=80,  # ⚡ SPEED: Reduced from 150 to 80 for faster FAQ
                    timeout=4.0  # ⚡ Consistent with Agent timeout (was 2.0s)
                )
                
                llm_time = (time.time() - llm_start) * 1000
                print(f"⏱️  FAQ: OpenAI call took {llm_time:.0f}ms")
                
                # 🔥 FIX: Safely handle None content
                answer = response.choices[0].message.content
                if answer:
                    answer = answer.strip()
                else:
                    answer = ""
                
                # 🔥 ARCHITECT-REVIEWED: Detect guard-rail responses and reject them
                guard_rail_phrases = [
                    "אני כאן רק לעזור",
                    "שאלות שקשורות לעסק",
                    "לא יכול לעזור",
                    "לא קשור לעסק"
                ]
                is_guard_rail = any(phrase in answer for phrase in guard_rail_phrases) if answer else False
                
                # Validate answer is not generic/empty/guard-rail
                if answer and len(answer) > 10 and "אשמח לעזור" not in answer and not is_guard_rail:
                    total_time = (time.time() - faq_start) * 1000
                    print(f"✅ FAQ SUCCESS! Total time: {total_time:.0f}ms")
                    print(f"📝 FAQ Answer: {answer[:100]}...")
                    logger.info(f"✅ FAQ success: {answer[:50]}...")
                    return answer
                else:
                    print(f"⚠️  FAQ: Generic/guard-rail answer detected!")
                    print(f"   Answer: {answer}")
                    print(f"   is_guard_rail={is_guard_rail}")
                    logger.warning(f"FAQ gave generic/guard-rail answer: {answer}")
                    raise ValueError("Generic/guard-rail answer - retry needed")
                    
            except Exception as retry_err:
                # 🔥 FIX: Quick retry with shorter response
                logger.warning(f"FAQ first attempt failed, retrying: {retry_err}")
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": faq_system},
                        {"role": "user", "content": f"{faq_facts[:400]}\n\n{question}"}
                    ],
                    temperature=0.3,
                    max_tokens=60,  # ⚡ Even shorter for retry
                    timeout=2.5  # ⚡ Shorter timeout for retry
                )
                # 🔥 ARCHITECT FIX: Apply guard-rail detection to retry path too!
                answer = response.choices[0].message.content
                if answer:
                    answer = answer.strip()
                else:
                    answer = ""
                
                # Detect guard-rail responses
                guard_rail_phrases = [
                    "אני כאן רק לעזור",
                    "שאלות שקשורות לעסק",
                    "לא יכול לעזור",
                    "לא קשור לעסק"
                ]
                is_guard_rail = any(phrase in answer for phrase in guard_rail_phrases) if answer else False
                
                # If still guard-rail → return None to fallback to AgentKit
                if is_guard_rail or not answer or len(answer) < 10:
                    logger.warning(f"FAQ retry also gave guard-rail/generic answer - falling back to AgentKit")
                    return None
                
                return answer
            
        except Exception as e:
            total_time = (time.time() - faq_start) * 1000
            print(f"❌ FAQ FAILED! Total time: {total_time:.0f}ms")
            print(f"   Error: {type(e).__name__}: {str(e)[:200]}")
            logger.error(f"❌ FAQ LLM failed after retry: {e}")
            import traceback
            traceback.print_exc()
            # Return None to signal fallback to AgentKit needed
            return None
    
    def generate_response_with_agent(self, message: str, business_id: int = 1, 
                                     context: Optional[Dict[str, Any]] = None,
                                     channel: str = "calls",
                                     is_first_turn: bool = False,
                                     customer_phone: Optional[str] = None,
                                     customer_name: Optional[str] = None) -> str:
        """
        ✨ BUILD 119: Agent-enhanced response generation
        🚀 Phase 2K: Intent-based routing - AgentKit only for bookings (≤2s target)
        
        Uses AgentKit to perform real actions (appointments, leads, WhatsApp)
        Falls back to FAQ/lightweight responses for info questions
        
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
        
        # 🚀 Phase 2K: INTENT ROUTING GATE
        # ⚠️ FAQ Fast-Path is HARDCODED for real-estate/restaurant patterns!
        # It will NOT work for other business types (tech, retail, etc.)
        # Check if business has FAQ enabled before routing
        
        intent = route_intent_hebrew(message)
        print(f"🎯 INTENT_DETECTED: {intent} (message: {message[:50]}...)")
        logger.info(f"🎯 Intent detected: {intent}")
        
        # ⚡ FAQ Fast-Path - Database-backed FAQ matching with embeddings
        # 🔥 BUILD 99: FAQ ONLY FOR PHONE CALLS (NOT WhatsApp!)
        # WhatsApp uses AgentKit exclusively for all messages
        
        if intent == "info" and channel != "whatsapp":
            # FAQ fast-path for phone calls only (channel="calls")
            try:
                from server.services.faq_cache import faq_cache
                
                faq_match = faq_cache.find_best_match(business_id, message)
                
                if faq_match:
                    print(f"🎯 FAQ MATCH FOUND (calls): score={faq_match['score']:.3f}")
                    print(f"   Question: {faq_match['question']}")
                    print(f"   Answer: {faq_match['answer'][:100]}...")
                    logger.info(f"🎯 FAQ fast-path activated: score={faq_match['score']:.3f}")
                    
                    faq_response = self._generate_faq_response(
                        message=message,
                        faq_answer=faq_match['answer'],
                        business_id=business_id,
                        channel=channel
                    )
                    
                    if faq_response:
                        print(f"✅ FAQ fast-path response generated (calls)")
                        return faq_response
                    else:
                        print("⚠️ FAQ response generation failed, falling back to AgentKit")
                else:
                    print(f"❌ No FAQ match found for: '{message[:50]}...'")
            except Exception as e:
                print(f"⚠️ FAQ fast-path error: {e}, falling back to AgentKit")
                logger.warning(f"FAQ fast-path error: {e}")
        elif intent == "info" and channel == "whatsapp":
            # WhatsApp always uses AgentKit (no FAQ fast-path)
            print(f"📱 WhatsApp message - skipping FAQ, using AgentKit")
            logger.info(f"📱 WhatsApp 'info' intent - routing to AgentKit (no FAQ)")
        
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
            
            # 🔥 CRITICAL FIX: Use get_or_create_agent (singleton cache) instead of get_agent (legacy)!
            from server.agent_tools.agent_factory import get_or_create_agent
            
            agent_create_start = time.time()
            agent = get_or_create_agent(
                business_id=business_id,
                channel=channel,
                business_name=business_name,
                custom_instructions=custom_prompt
            )
            agent_create_time = (time.time() - agent_create_start) * 1000
            
            if agent_create_time < 100:
                # Cache HIT - agent was already warmed!
                print(f"♻️  CACHE HIT: Agent already warmed! ({agent_create_time:.0f}ms)")
                logger.info(f"♻️  Agent CACHE HIT for {business_name} ({channel}): {agent_create_time:.0f}ms")
            elif agent_create_time < 2000:
                # Cache MISS but creation was fast
                print(f"🆕 NEW Agent created in {agent_create_time:.0f}ms (business={business_name}, channel={channel})")
                logger.info(f"🆕 Agent created: {agent_create_time:.0f}ms")
            else:
                # SLOW creation - log warning!
                print(f"⚠️  SLOW AGENT CREATION: {agent_create_time:.0f}ms (expected <2000ms)")
                logger.warning(f"⚠️  SLOW AGENT CREATION: {agent_create_time:.0f}ms for business={business_id}, channel={channel}")
            
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
            
            # 🔥 FIX: ALWAYS create new event loop to avoid CurrentThreadExecutor crash
            # Don't reuse ASGI/main thread executor - it gets torn down mid-request
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # 🔥 BUILD 99: LIMIT CONVERSATION HISTORY to last 4 exchanges (8 messages)
            # Why: 10 messages = ~4.5K tokens = 27s latency in Runner.run()
            #      4 exchanges (8 messages) = ~1.2K tokens = 1.2s latency ✅
            history_start = time.time()
            conversation_messages = []
            if context and "previous_messages" in context:
                prev_msgs = context["previous_messages"]
                print(f"📚 Found {len(prev_msgs)} previous messages in context")
                
                # 🔥 CRITICAL PERFORMANCE FIX: Keep only last 8 messages (4 user + 4 assistant)
                # This reduces prompt from ~4.5K tokens to ~1.2K tokens
                if len(prev_msgs) > 8:
                    prev_msgs = prev_msgs[-8:]
                    print(f"⚡ PERFORMANCE: Limited to last 8 messages (4 exchanges) to reduce latency")
                    logger.info(f"⚡ Truncated history from {len(context['previous_messages'])} to 8 messages")
                
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
                
                history_time = (time.time() - history_start) * 1000
                print(f"✅ Converted to {len(conversation_messages)} messages for Agent ({history_time:.0f}ms)")
                
            # Add current message
            conversation_messages.append({
                "role": "user",
                "content": message
            })
            
            # 🔥 FIX: Runner is a static class - use Runner.run() directly!
            from agents import Runner
            
            print(f"🔄 Starting Runner.run() with {len(conversation_messages)-1} history messages...")
            logger.info(f"⏱️ PERFORMANCE: Starting Runner.run() at {time.time()}")
            
            # Use Runner.run() directly (it's a static method, not an instance!)
            try:
                result = loop.run_until_complete(
                    Runner.run(starting_agent=agent, input=conversation_messages, context=agent_context)
                )
                duration_ms = int((time.time() - start_time) * 1000)
                print(f"✅ Runner.run() completed in {duration_ms}ms")
                logger.info(f"⏱️ PERFORMANCE: Runner.run() completed in {duration_ms}ms")
            finally:
                # 🔥 CRITICAL: Close event loop to prevent FD leak!
                loop.close()
            
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
                                    # Store appointment details for WhatsApp validation
                                    if not hasattr(result, 'appointment_details'):
                                        result.appointment_details = output
                
                if tool_count > 0:
                    print(f"✅ Agent executed {tool_count} tool actions")
                    logger.info(f"✅ Agent executed {tool_count} tool actions")
                else:
                    print(f"⚠️ Agent DID NOT call any tools! (message: '{message[:50]}...')")
                    logger.warning(f"⚠️ Agent DID NOT call any tools! (message: '{message[:50]}...')")
            else:
                print(f"⚠️ Result has NO new_items or new_items is empty!")
            
            # 🚨 BUILD 138+: VALIDATION - Detect "hallucinated bookings" AND "hallucinated availability"
            # If agent claims action without executing tool, BLOCK response
            claim_words = ["קבעתי", "שלחתי", "יצרתי", "הפגישה נקבעה", "הפגישה קבועה", "סגרתי", "נקבע", "התור נקבע", "התור קבוע"]
            claimed_action = any(word in reply_text for word in claim_words)
            
            # 🔥 NEW: Detect "hallucinated availability" (saying "busy/available" without checking)
            # 🚨 FIX: Only flag if saying "NO availability" or "YES available" (absolute claims)
            # Saying "15:00 תפוס אבל 17:00 פנוי" is VALID after tool call!
            # 🔥 FIX #3: Added "תפוס" and "פנוי" to catch simple hallucinations
            hallucinated_availability_words = ["אין זמנים פנויים", "אין זמינות", "הכל תפוס", "לא פנוי", "לא זמין", "תפוס", "פנוי", "תפוס ב"]
            claimed_availability = any(word in reply_text for word in hallucinated_availability_words)
            
            # Check if calendar_create_appointment was called (with or without _wrapped suffix)
            booking_tool_called = any(
                tc.get("tool") in ["calendar_create_appointment", "calendar_create_appointment_wrapped"]
                for tc in tool_calls_data
            )
            
            # 🔥 FALLBACK: If tool name extraction failed, check output structure
            # If we see {'appointment_id': ...} in ANY tool output → calendar_create_appointment was called
            if not booking_tool_called and tool_count > 0:
                for item in result.new_items if hasattr(result, 'new_items') else []:
                    if type(item).__name__ == 'ToolCallOutputItem':
                        output = getattr(item, 'output', None)
                        if isinstance(output, dict) and 'appointment_id' in output:
                            print(f"  🔥 FALLBACK: Detected calendar_create_appointment from output structure (has 'appointment_id' key)")
                            booking_tool_called = True
                            break
            
            # Check if calendar_find_slots was called
            check_availability_called = any(
                tc.get("tool") in ["calendar_find_slots", "calendar_find_slots_wrapped"]
                for tc in tool_calls_data
            )
            
            # 🔥 FALLBACK: If tool name extraction failed, check output structure
            # If we see {'slots': [...]} in ANY tool output → calendar_find_slots was called
            if not check_availability_called and tool_count > 0:
                for item in result.new_items if hasattr(result, 'new_items') else []:
                    if type(item).__name__ == 'ToolCallOutputItem':
                        output = getattr(item, 'output', None)
                        if isinstance(output, dict) and 'slots' in output:
                            print(f"  🔥 FALLBACK: Detected calendar_find_slots from output structure (has 'slots' key)")
                            check_availability_called = True
                            break
            
            # Check if whatsapp_send was called (for phone channel only)
            whatsapp_sent = any(
                tc.get("tool") == "whatsapp_send"
                for tc in tool_calls_data
            )
            
            # 🔥 WORKAROUND: Also check if we detected a successful booking in the output
            # (in case tool name extraction failed but booking actually succeeded)
            print(f"  🔍 VALIDATION CHECK:")
            print(f"     claimed_action={claimed_action}")
            print(f"     claimed_availability={claimed_availability}")
            print(f"     booking_tool_called={booking_tool_called}")
            print(f"     check_availability_called={check_availability_called}")
            print(f"     booking_successful={booking_successful}")
            
            # 🚨 BLOCK 1: Hallucinated booking
            if claimed_action and not booking_tool_called and not booking_successful:
                print(f"🚨 BLOCKED HALLUCINATED BOOKING!")
                print(f"   Agent claimed: '{reply_text[:80]}...'")
                print(f"   But NO calendar_create_appointment was called AND no successful booking detected!")
                logger.error(f"🚨 Blocked hallucinated booking: agent claimed action without tool call")
                
                # Override response with corrective message
                reply_text = "אני עדיין צריך לבדוק זמינות. איזה יום ושעה היית רוצה?"
                print(f"   ✅ Replaced with: '{reply_text}'")
            
            # 🚨 BLOCK 2: Hallucinated availability (NEW!)
            elif claimed_availability and not check_availability_called:
                print(f"🚨 BLOCKED HALLUCINATED AVAILABILITY!")
                print(f"   Agent claimed: '{reply_text[:80]}...'")
                print(f"   But NO calendar_find_slots was called!")
                logger.error(f"🚨 Blocked hallucinated availability: agent claimed busy/free without checking")
                
                # Override response with corrective message
                reply_text = "באיזה יום ושעה נוח לך?"
                print(f"   ✅ Replaced with: '{reply_text}'")
            
            # 🚨 BLOCK 3: Missing WhatsApp confirmation (NEW!)
            elif booking_successful and channel == "phone" and not whatsapp_sent:
                print(f"⚠️  WARNING: Booking successful but NO WhatsApp sent!")
                print(f"   Agent should have called whatsapp_send but didn't")
                logger.warning(f"⚠️  Missing WhatsApp confirmation after successful booking")
                # Don't block - just log warning (WhatsApp is nice-to-have, not critical)
            
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

