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
import asyncio
import json
from typing import Dict, Any, Optional, List, Literal
from openai import OpenAI
from server.models_sql import BusinessSettings, PromptRevisions, Business, AgentTrace
from server.db import db
from datetime import datetime
from server.services.unified_lead_context_service import UnifiedLeadContextPayload, UnifiedLeadContextService

# 🔥 FIX E: LAZY agent imports to prevent schema errors from breaking WhatsApp
# Agents are loaded on-demand, so WhatsApp still works even if agent schema fails
AGENT_MODULES_LOADED = None  # None = not yet loaded, True = loaded, False = failed
AGENTS_ENABLED = False  # Will be set when agents load successfully
_agent_load_error = None  # Store error for debugging

def _ensure_agent_modules_loaded():
    """🔥 FIX E: Lazy load agent modules on first use
    
    This prevents WhatsApp from breaking if agent schema has errors.
    WhatsApp will continue to work, just without agents.
    
    Returns:
        bool: True if agents loaded successfully, False otherwise
    """
    global AGENT_MODULES_LOADED, AGENTS_ENABLED, _agent_load_error
    
    if AGENT_MODULES_LOADED is not None:
        return AGENT_MODULES_LOADED
    
    logger = logging.getLogger(__name__)
    
    try:
        # Try to import agent modules
        from server.agent_tools import get_agent, AGENTS_ENABLED as agents_flag
        from agents import Runner
        
        AGENT_MODULES_LOADED = True
        AGENTS_ENABLED = agents_flag
        logger.info("✅ Agent modules loaded successfully (lazy load)")
        return True
        
    except Exception as e:
        AGENT_MODULES_LOADED = False
        AGENTS_ENABLED = False
        _agent_load_error = str(e)
        logger.error(f"❌ Agent modules failed to load: {e}")
        logger.warning("⚠️ WhatsApp will continue to work, but without agent tools")
        return False

logger = logging.getLogger(__name__)

# Global AI service instance for cache sharing
_global_ai_service = None

# 🔥 Configuration: Maximum number of previous messages to include in conversation history
# Increased to 30 to support longer conversations (50+ messages) without losing context
# This ensures the bot maintains conversation context even after many exchanges
MAX_CONVERSATION_HISTORY_MESSAGES = 30

# 🚨 OBSOLETE: The following flags are no longer used after AgentKit Only implementation
# All messages now use AgentKit regardless of intent
# Left here for backward compatibility in case of rollback
AGENTKIT_BOOKING_ONLY = os.getenv("AGENTKIT_BOOKING_ONLY", "1") == "1"  # OBSOLETE
FAST_PATH_ENABLED = os.getenv("FAST_PATH_ENABLED", "1") == "1"  # OBSOLETE

def route_intent_hebrew(text: str) -> Literal["book", "reschedule", "cancel", "info", "whatsapp", "human", "other"]:
    """
    🚨 OBSOLETE: Intent detection is no longer used after AgentKit Only implementation
    All messages now go to AgentKit regardless of detected intent
    Left here for backward compatibility in case of rollback
    
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
        
        # Hours
        r'שעות.*פתיחה|מתי.*פתוח|שעות.*עבודה|מה.*שעות',
        
        # Amenities & Services - REMOVED generic "חדר" patterns!
        r'כשר|כשרות',
        r'גודל.*חדר|כמה.*אנשים|כמה.*משתתפים',
        
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
            logger.info(f"🎯 BOOKING_PRE_CHECK: Detected booking verb + time/availability")
            return "book"
    
    # 🔥 CHECK INFO (after booking pre-check!)
    for pattern in info_patterns:
        if re.search(pattern, text_lower):
            logger.info(f"🎯 INTENT_MATCH: pattern='{pattern}' matched in '{text_lower[:50]}'")
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
        # ⚡ Warmup will be called separately by lazy_services after app is ready
    return _global_ai_service

def _warmup_ai_cache(service: 'AIService'):
    """⚡ Preload cache for ALL active businesses to prevent first-turn latency"""
    try:
        import time
        from server.models_sql import Business
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
    
    # 2. 🔥 CRITICAL: Clear PromptCache (realtime_prompt_builder)
    # This cache stores pre-built prompts for inbound/outbound calls
    # Must be cleared when voice or prompt changes to prevent stale cache
    try:
        from server.services.prompt_cache import get_prompt_cache
        prompt_cache = get_prompt_cache()
        prompt_cache.invalidate(business_id)  # Invalidates both inbound and outbound
        logger.info(f"✅ PromptCache (realtime) invalidated for business {business_id}")
    except Exception as e:
        logger.warning(f"⚠️ Failed to invalidate PromptCache: {e}")
    
    # 3. 🔥 NEW: Clear agent cache (agent_factory)
    try:
        from server.agent_tools.agent_factory import invalidate_agent_cache
        invalidate_agent_cache(business_id)
        logger.info(f"✅ Agent cache invalidated for business {business_id}")
    except Exception as e:
        logger.error(f"⚠️ Failed to invalidate agent cache: {e}")

class AIService:
    """מנגנון AI מרכזי שטוען פרומפטים מהמסד נתונים ומחבר עם OpenAI וGemini"""
    
    def __init__(self, business_id: Optional[int] = None):
        """
        Initialize AI Service
        
        Args:
            business_id: Optional business ID for context. If provided, this service
                        will be scoped to that business. If None, business_id must be
                        passed to methods that require it.
        """
        # ⚡ RELIABLE OpenAI client with production timeout
        self.client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            timeout=2.5  # 🔥 REDUCED: 2.5s timeout for faster real-time conversations (was 3.5s)
        )
        self._cache = {}  # קאש פרומפטים לביצועים
        self._cache_timeout = 30  # ⚡ 30 שניות - מתעדכן מהר כשמשנים פרומפט ב-DB
        self.business_id = business_id  # 🔥 NEW: Store business context for live calls
        
        # 🔥 NEW: Gemini client (lazy loaded when needed)
        self._gemini_client = None
    
    def _get_gemini_client(self):
        """Lazy load Gemini client when needed (uses singleton)"""
        if self._gemini_client is None:
            try:
                # Import moved to top of google_clients.py for performance
                # This just retrieves the singleton, no heavy imports here
                from server.services.providers.google_clients import get_gemini_llm_client
                
                self._gemini_client = get_gemini_llm_client()
                logger.info(f"✅ Gemini LLM client (singleton) ready for business={self.business_id}")
            except RuntimeError as init_error:
                logger.error(f"❌ Failed to get Gemini LLM client: {init_error}")
                raise
        return self._gemini_client
    
    def _get_ai_provider(self, business_id: int) -> str:
        """Get AI provider for a business (openai or gemini)"""
        try:
            business = Business.query.get(business_id)
            if business:
                ai_provider = getattr(business, 'ai_provider', 'openai') or 'openai'
                logger.info(f"[AI_SERVICE] Business {business_id} uses provider: {ai_provider}")
                return ai_provider
        except Exception as e:
            logger.error(f"Failed to get ai_provider for business {business_id}: {e}")
        return 'openai'  # Default fallback
        
    def get_business_prompt(self, business_id: int, channel: str = "calls") -> Dict[str, Any]:
        """טעינת פרומפט עסק מהמסד נתונים עם קאש - לפי ערוץ (calls/whatsapp)
        
        🆕 For WhatsApp: Uses business.whatsapp_system_prompt if available (prompt-only mode)
        Falls back to BusinessSettings.ai_prompt if not set.
        """
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
            
            # 🔥 BUILD 186 FIX: Handle missing columns gracefully
            settings = None
            try:
                settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
            except Exception as db_err:
                logger.warning(f"⚠️ Could not load BusinessSettings for {business_id} (DB schema issue): {db_err}")
            
            business = Business.query.get(business_id)
            
            db_time = time.time() - db_start
            logger.info(f"📊 DB_QUERY: {db_time:.3f}s for business {business_id}")
            
            # ✅ שם עסק לשימוש ב-placeholders
            business_name = business.name if business else "העסק שלנו"
            
            # 🆕 PROMPT-ONLY MODE: Load WhatsApp prompt from business.whatsapp_system_prompt
            system_prompt = ""
            model = "gpt-4o-mini"
            temperature = 0.0
            max_tokens = 350
            
            if channel == "whatsapp":
                # 🆕 Priority 1: Use business.whatsapp_system_prompt if available (prompt-only mode)
                if business and hasattr(business, 'whatsapp_system_prompt') and business.whatsapp_system_prompt and business.whatsapp_system_prompt.strip():
                    system_prompt = business.whatsapp_system_prompt
                    # Load WhatsApp-specific settings if available
                    if hasattr(business, 'whatsapp_temperature') and business.whatsapp_temperature is not None:
                        temperature = business.whatsapp_temperature
                    if hasattr(business, 'whatsapp_model') and business.whatsapp_model:
                        model = business.whatsapp_model
                    if hasattr(business, 'whatsapp_max_tokens') and business.whatsapp_max_tokens:
                        max_tokens = business.whatsapp_max_tokens
                    
                    logger.info(f"✅ Loaded WhatsApp prompt from DB: business_id={business_id} chars={len(system_prompt)} model={model} temp={temperature}")
                    
                # Priority 2: Fall back to BusinessSettings.ai_prompt if set
                elif settings and settings.ai_prompt and settings.ai_prompt.strip():
                    import json
                    try:
                        # Try JSON format with channel-specific keys
                        if settings.ai_prompt.strip().startswith('{'):
                            prompt_obj = json.loads(settings.ai_prompt)
                            if 'whatsapp' in prompt_obj:
                                system_prompt = prompt_obj['whatsapp']
                                logger.info(f"✅ Using whatsapp prompt from BusinessSettings for business {business_id}")
                            else:
                                logger.warning(f"⚠️ Missing 'whatsapp' key in ai_prompt JSON, using default")
                                system_prompt = self._get_default_hebrew_prompt(business_name, "whatsapp")
                        else:
                            # Legacy text prompt
                            system_prompt = settings.ai_prompt
                            logger.info(f"✅ Using legacy text prompt from BusinessSettings for {business_id}")
                    except json.JSONDecodeError:
                        system_prompt = settings.ai_prompt
                        logger.info(f"✅ Using non-JSON prompt from BusinessSettings for {business_id}")
                
                # Priority 3: Fall back to business.system_prompt
                elif business and business.system_prompt and business.system_prompt.strip():
                    system_prompt = business.system_prompt
                    logger.info(f"⚠️ Using fallback business.system_prompt for WhatsApp (business {business_id})")
                
                # Priority 4: NO DEFAULT FALLBACK - If no prompt configured, ERROR
                else:
                    logger.error(f"❌ CRITICAL: No WhatsApp prompt configured for business {business_id} - CANNOT RESPOND")
                    # Return empty prompt - this will cause AI to fail and skip sending
                    system_prompt = ""
            
            else:
                # Calls channel - use existing logic
                if settings and settings.ai_prompt and settings.ai_prompt.strip():
                    # יש פרומפט ב-settings - תמיד תשתמש בו! (ללא בדיקת אורך)
                    import json
                    try:
                        # נסיון לפרוס כ-JSON (פורמט חדש עם calls/whatsapp)
                        if settings.ai_prompt.strip().startswith('{'):
                            prompt_obj = json.loads(settings.ai_prompt)
                            # בחירת הפרומפט הנכון לפי channel
                            # ✅ STRICT: Require channel-specific key
                            if channel in prompt_obj:
                                system_prompt = prompt_obj[channel]
                                logger.info(f"✅ Using {channel} prompt for business {business_id} from settings")
                            else:
                                # ⚠️ STRICT MODE: Missing channel key
                                logger.error(f"❌ Missing '{channel}' key in ai_prompt JSON for business {business_id}. Available keys: {list(prompt_obj.keys())}")
                                # Use default prompt as fallback but log error
                                system_prompt = self._get_default_hebrew_prompt(business_name, channel)
                                logger.warning(f"⚠️ Using default prompt due to missing '{channel}' key")
                            
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
            
            # 🔥 SANITIZE business prompt (remove URLs, normalize punctuation, clean IDs)
            # 🆕 FIX: Increased limit from 3000 to 20000 chars to allow full WhatsApp prompts
            from server.services.prompt_sanitizer import sanitize_prompt_text
            # Maximum 20000 characters - reasonable limit to prevent abuse while allowing large prompts
            sanitized_result = sanitize_prompt_text(system_prompt, max_length=20000)
            system_prompt = sanitized_result["sanitized_text"]
            flags = sanitized_result["flags"]
            
            # Log sanitization flags (NOT values - only boolean flags)
            if any(flags.values()):
                logger.info(f"🧹 Sanitized business prompt - flags: {flags}")
            
            # 🔥 REMOVED: Dynamic policy info no longer added automatically!
            # ⚠️ CRITICAL: All appointment logic must come from DB prompt!
            # If you need appointment info, add it to whatsapp_system_prompt in DB.
            # DO NOT add hardcoded appointment logic here!
            
            # Log prompt length for monitoring
            logger.info(f"✅ Prompt length: {len(system_prompt)} chars - no artificial limits applied")
            
            # Build prompt_data with channel-specific or fallback settings
            if channel == "whatsapp":
                # Use WhatsApp-specific settings loaded above
                prompt_data = {
                    "system_prompt": system_prompt,
                    "business_name": business_name,
                    "model": model,
                    "max_tokens": max_tokens,
                    "temperature": temperature
                }
            elif not settings:
                # ⚡ BUILD 117: INCREASED - allow complete sentences without truncation
                prompt_data = {
                    "system_prompt": system_prompt,
                    "business_name": business_name,  # 🔥 FIX: Include business name for FAQ handler
                    "model": "gpt-4o-mini",  # Fast model
                    "max_tokens": 350,  # ⚡ BUILD 117: 350 tokens for COMPLETE sentences (no mid-sentence cuts!)
                    "temperature": 0.0  # 🔥 FIX: Temperature 0.0 for deterministic responses
                }
            else:
                prompt_data = {
                    "system_prompt": system_prompt,
                    "business_name": business_name,  # 🔥 FIX: Include business name for FAQ handler
                    "model": settings.model,
                    "max_tokens": min(settings.max_tokens, 350),  # ⚡ BUILD 117: Cap at 350 for complete sentences
                    "temperature": 0.0  # 🔥 FIX: Temperature 0.0 (ignore DB setting for consistency)
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
                "temperature": 0.0  # 🔥 FIX: Temperature 0.0 for deterministic responses
            }
    
    def get_system_prompt(self, channel: str = "calls") -> Optional[str]:
        """
        Get system prompt using the business_id set in __init__.
        
        This is a convenience method for live calls where business context
        is set once during initialization.
        
        Args:
            channel: Communication channel ('calls', 'whatsapp', etc.)
            
        Returns:
            System prompt string, or None if business_id not set
            
        Raises:
            ValueError: If business_id was not provided in __init__
        """
        if self.business_id is None:
            raise ValueError("business_id must be provided in __init__ to use get_system_prompt()")
        
        prompt_data = self.get_business_prompt(self.business_id, channel)
        return prompt_data.get("system_prompt")
    
    def _get_default_hebrew_prompt(self, business_name: str = "העסק שלנו", channel: str = "calls") -> str:
        """פרומפט ברירת מחדל בעברית - מינימלי וכללי!
        
        ⚠️ CRITICAL: זה רק fallback חירום - כל הלוגיקה צריכה לבוא מה-DB!
        אין כאן לוגיקה של פגישות, שירותים, או כל דבר ספציפי!
        """
        if channel == "whatsapp":
            return f"""אתה העוזר הדיגיטלי של {business_name} ב-WhatsApp.

תענה בעברית, תהיה חם ואדיב, ועזור ללקוח בהתאם לצרכיו."""
        
        # Calls channel - also minimal
        return f"""אתה העוזר הדיגיטלי של {business_name}.

תענה בעברית, תהיה חם ואדיב, ועזור ללקוח בהתאם לצרכיו."""
    
    def generate_response(self, message: str, business_id: int = None, context: Optional[Dict[str, Any]] = None, channel: str = "calls", is_first_turn: bool = False) -> str:
        """יצירת תגובה מפרומפט דינמי + הקשר - לפי ערוץ (calls/whatsapp)"""
        try:
            # 🔥 NEW: WhatsApp uses the new Prompt Stack architecture
            if channel == "whatsapp":
                from server.services.whatsapp_prompt_stack import (
                    build_whatsapp_prompt_stack,
                    get_db_prompt_for_whatsapp,
                    validate_prompt_stack_usage
                )
                
                # Load DB prompt (single source of truth)
                db_prompt = get_db_prompt_for_whatsapp(business_id)
                
                # Build prompt stack with clean separation
                messages = build_whatsapp_prompt_stack(
                    business_id=business_id,
                    db_prompt=db_prompt,
                    context=context
                )
                
                # Add current user message
                messages.append({"role": "user", "content": message})
                
                # Validate stack (logs warnings/errors)
                validation = validate_prompt_stack_usage(messages)
                if not validation["valid"]:
                    logger.error(f"❌ Invalid prompt stack: {validation['errors']}")
                if validation["warnings"]:
                    for warning in validation["warnings"]:
                        logger.warning(f"⚠️ Prompt stack: {warning}")
                
                logger.info(f"✅ WhatsApp prompt stack: {validation['stats']}")
                
                # 🔥 DEBUG: Log full prompt stack structure for debugging
                logger.info(f"[PROMPT-STACK] Total messages in stack: {len(messages)}")
                for idx, msg in enumerate(messages):
                    role = msg.get('role', 'unknown')
                    content_preview = msg.get('content', '')[:100]
                    logger.info(f"[PROMPT-STACK] [{idx}] role={role} content={content_preview}...")
                
                # Load WhatsApp-specific settings
                prompt_data = self.get_business_prompt(business_id, channel)
                
            else:
                # Calls channel - use existing logic (unchanged)
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
                
                # הוספת הקשר אם קיים
                if context:
                    # 🆕 CUSTOMER MEMORY: Add unified memory context (when available)
                    if context.get("customer_memory"):
                        memory_text = context["customer_memory"]
                        messages.append({
                            "role": "system",
                            "content": f"🧠 זיכרון לקוח (מכל הערוצים):\n{memory_text}"
                        })
                        logger.info(f"[MEMORY] Added customer memory to AI context ({len(memory_text)} chars)")
                    
                    # 🆕 RETURNING CUSTOMER: Ask if they want to continue or start fresh
                    if context.get("ask_continue_or_fresh"):
                        messages.append({
                            "role": "system",
                            "content": """⚠️ לקוח חוזר! אתה צריך לשאול: "שלום! רוצה שנמשיך מאיפה שעצרנו או להתחיל מחדש?"
אם הלקוח אומר "מהתחלה" או "איפוס" - התעלם מהזיכרון הקודם והתחל שיחה חדשה."""
                        })
                        logger.info(f"[MEMORY] Instructed AI to ask continue/fresh for returning customer")
                    
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
                    
                    # ✅ FIX: Improved conversation history - 12 messages for better context retention
                    # Increased from 10 to 12 to prevent context loss after 5th message
                    if context.get("previous_messages"):
                        prev_msgs = context["previous_messages"][-12:]  # ✅ 12 הודעות אחרונות לזיכרון משופר!
                        for msg in prev_msgs:
                            # ✅ המבנה הוא "לקוח: ..." או "עוזרת: ..." או "עוזר:" (WhatsApp)
                            if msg.startswith("לקוח:"):
                                messages.append({
                                    "role": "user",
                                    "content": msg.replace("לקוח:", "").strip()
                                })
                            elif msg.startswith("עוזרת:"):
                                # Legacy support for "עוזרת:" prefix
                                content = msg.replace("עוזרת:", "").strip()
                                messages.append({
                                    "role": "assistant",
                                    "content": content
                                })
                            elif msg.startswith("לאה:"):
                                # Legacy support for specific assistant name
                                content = msg.replace("לאה:", "").strip()
                                messages.append({
                                    "role": "assistant",
                                    "content": content
                                })
                            elif msg.startswith("עוזר:"):
                                # 🔥 FIX: Support for WhatsApp assistant messages
                                content = msg.replace("עוזר:", "").strip()
                                messages.append({
                                    "role": "assistant",
                                    "content": content
                                })
                
                # הוספת הודעת המשתמש הנוכחית
                messages.append({"role": "user", "content": message})
            
            # 🔥 NEW: Check which AI provider to use
            ai_provider = self._get_ai_provider(business_id) if business_id else 'openai'
            
            # ⚡ CRITICAL: Measure LLM call time
            import time
            llm_start = time.time()
            
            # ⚡ BUILD 118: Add explicit timeout to prevent long waits
            try:
                if ai_provider == 'gemini':
                    # Use Gemini for LLM
                    logger.info(f"[AI_SERVICE] Using Gemini LLM for business {business_id}")
                    
                    # Convert messages to Gemini format
                    # Gemini doesn't support separate system/user/assistant roles in the same way
                    # We'll combine them into a single prompt
                    prompt_parts = []
                    for msg in messages:
                        role = msg.get('role', 'user')
                        content = msg.get('content', '')
                        if role == 'system':
                            prompt_parts.append(f"System: {content}")
                        elif role == 'user':
                            prompt_parts.append(f"User: {content}")
                        elif role == 'assistant':
                            prompt_parts.append(f"Assistant: {content}")
                    
                    full_prompt = "\n\n".join(prompt_parts)
                    
                    # Call Gemini
                    gemini_client = self._get_gemini_client()
                    response = gemini_client.models.generate_content(
                        model="gemini-2.0-flash",
                        contents=full_prompt
                    )
                    
                    llm_time = time.time() - llm_start
                    logger.info(f"✅ GEMINI_SUCCESS: {llm_time:.3f}s")
                    
                    # Extract text from response with proper validation
                    if hasattr(response, 'text') and response.text:
                        ai_response = response.text.strip()
                    elif hasattr(response, 'candidates') and response.candidates:
                        # Fallback: Extract from candidates structure
                        try:
                            ai_response = response.candidates[0].content.parts[0].text.strip()
                        except (AttributeError, IndexError) as e:
                            logger.error(f"Failed to extract text from Gemini candidates: {e}")
                            ai_response = str(response).strip()
                    else:
                        logger.warning("Gemini response has unexpected format")
                        ai_response = str(response).strip() if response else ""
                    
                else:
                    # Use OpenAI for LLM (default)
                    logger.info(f"[AI_SERVICE] Using OpenAI LLM for business {business_id}")
                    
                    response = self.client.chat.completions.create(
                        model=prompt_data["model"],
                        messages=messages,  # type: ignore
                        max_tokens=prompt_data["max_tokens"],
                        temperature=prompt_data["temperature"],
                        timeout=2.5  # 🔥 REDUCED: 2.5s timeout for real-time conversations (was 3.5s)
                    )
                    
                    llm_time = time.time() - llm_start
                    logger.info(f"✅ OPENAI_SUCCESS: {llm_time:.3f}s")
                    
                    ai_response = response.choices[0].message.content
                
                if ai_response:
                    ai_response = ai_response.strip()
                else:
                    ai_response = ""  # Empty - let caller handle
                logger.info(f"AI response generated for business {business_id}: {len(ai_response)} chars")
                return ai_response
                
            except Exception as llm_error:
                llm_time = time.time() - llm_start
                error_type = type(llm_error).__name__
                provider_label = "GEMINI" if ai_provider == 'gemini' else "OPENAI"
                logger.error(f"🔴 {provider_label}_FAILED: {error_type} after {llm_time:.3f}s: {str(llm_error)[:200]}")
                raise  # Re-raise to outer exception handler
            
        except Exception as e:
            logger.error(f"🔴 AI_GENERATION_FAILED: {type(e).__name__}: {str(e)[:200]}")
            return self._get_fallback_response(message)
    
    def _get_fallback_response(self, message: str, business_id: int = None) -> str:
        """Emergency fallback if AI fails - uses business settings"""
        try:
            if business_id:
                from server.models_sql import Business
                business = Business.query.get(business_id)
                if business:
                    fallback = business.greeting_message or business.whatsapp_greeting
                    if fallback and fallback.strip():
                        return fallback
                    # Use business name as absolute minimum
                    if business.name:
                        return business.name
        except:
            pass
        return None  # Return None to signal caller to skip/handle
    
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
    
    def _generate_conversation_id(self, business_id: int, context: Optional[Dict[str, Any]], customer_phone: Optional[str]) -> str:
        """
        Generate a unique conversation_id for OpenAI Agents SDK.
        
        The conversation_id is used by OpenAI to manage conversation history on their servers.
        It must be unique per customer/conversation but consistent across messages.
        
        Args:
            business_id: Business ID (can be 0 for system business)
            context: Context dict (may contain remote_jid)
            customer_phone: Customer phone number
            
        Returns:
            Sanitized conversation_id string (alphanumeric + underscores only)
        """
        conversation_id = ""  # Initialize to empty string for clarity
        
        if context:
            # Try to get remote_jid first (most unique for WhatsApp)
            remote_jid = context.get('remote_jid')
            if remote_jid:
                # Sanitize JID to remove all special characters
                sanitized_jid = re.sub(r'[^a-zA-Z0-9_]', '_', remote_jid)
                conversation_id = f"wa_{business_id}_{sanitized_jid}"
            elif customer_phone:
                # Fallback to phone number - sanitize to remove all special characters
                sanitized_phone = re.sub(r'[^a-zA-Z0-9]', '', customer_phone)
                conversation_id = f"wa_{business_id}_{sanitized_phone}"
        
        if not conversation_id and business_id is not None:
            # Last resort: use business_id only (not ideal but better than nothing)
            conversation_id = f"wa_{business_id}_default"
            logger.warning(f"[AGENTKIT] No remote_jid or phone found, using default conversation_id")
        
        return conversation_id
    
    def generate_response_with_agent(self, message: str, business_id: int = None, 
                                     context: Optional[Dict[str, Any]] = None, 
                                     channel: str = "whatsapp",
                                     customer_phone: str = None,
                                     customer_name: str = None,
                                     is_first_turn: bool = False) -> Dict[str, Any]:
        """
        🔥 AGENTKIT: Generate AI response with agent support for WhatsApp
        
        This method connects to AgentKit for AI responses with action capabilities.
        Falls back to regular generate_response if AgentKit is unavailable.
        
        Args:
            message: User message
            business_id: Business ID
            context: Context dict with customer info, history, etc.
            channel: Communication channel (whatsapp, calls, etc.)
            customer_phone: Customer phone number
            customer_name: Customer name
            is_first_turn: Whether this is the first turn
            
        Returns:
            Dict with 'text' and optionally 'actions' keys
        """
        logger.info(f"[AGENTKIT] generate_response_with_agent called: business_id={business_id}, channel={channel}")
        
        try:
            # 🔥 CRITICAL FIX: Ensure agent modules are loaded
            if not _ensure_agent_modules_loaded():
                logger.warning("[AGENTKIT] Agent modules not available, falling back to regular response")
                response_text = self.generate_response(message, business_id, context, channel, is_first_turn)
                return {
                    "text": response_text,
                    "actions": []
                }
            
            # If agents are available, try to use them
            if not AGENTS_ENABLED:
                logger.info("[AGENTKIT] Agents disabled, using regular response")
                response_text = self.generate_response(message, business_id, context, channel, is_first_turn)
                return {
                    "text": response_text,
                    "actions": []
                }
            
            # Import agent modules (already loaded by _ensure_agent_modules_loaded)
            from server.agent_tools import get_agent
            from agents import Runner  # Required for running agents synchronously
            
            # Get agent for this business
            logger.info(f"[AGENTKIT] Getting agent for business {business_id}")
            agent = get_agent(business_id=business_id, channel=channel)
            
            if not agent:
                logger.warning(f"[AGENTKIT] No agent available for business {business_id}, using regular response")
                response_text = self.generate_response(message, business_id, context, channel, is_first_turn)
                return {
                    "text": response_text,
                    "actions": []
                }
            
            # Prepare agent context
            agent_context = context or {}
            if customer_phone:
                agent_context['phone'] = customer_phone
            if customer_name:
                agent_context['customer_name'] = customer_name
            
            # 🔥 NEW: Inject unified lead context if available
            if context and context.get('lead_context'):
                lead_ctx = context['lead_context']
                agent_context['lead_context'] = lead_ctx
                logger.info(f"[AGENTKIT] 🎧 Injected lead context: lead_id={lead_ctx.get('lead_id')}, "
                          f"notes={len(lead_ctx.get('recent_notes', []))}, "
                          f"next_apt={'Yes' if lead_ctx.get('next_appointment') else 'No'}")
            
            # 🔥 FIX: Pass conversation history to agent for context retention
            # The agent needs full message history to maintain conversation context
            # and avoid repeating introductions or losing track of what was discussed
            # Context metadata is handled by agent_context parameter
            
            # Generate conversation_id for monitoring/tracking purposes only
            conversation_id = self._generate_conversation_id(business_id, context, customer_phone)
            
            # Set flask.g.agent_context so tools like whatsapp_send work properly
            try:
                from flask import g
                
                # 🔥 CRITICAL FIX: Extract phone_e164 from lead_context if available
                # This ensures tools get the actual E.164 phone number, not @lid JID
                # NOTE: Assumes UnifiedLeadContextService returns properly formatted E.164 numbers
                phone_e164 = None
                if context and context.get('lead_context'):
                    lead_ctx = context['lead_context']
                    phone_e164 = lead_ctx.get('lead_phone')  # E.164 format from lead (trusted source)
                
                # Fallback to context['phone'] if available (should also be E.164)
                if not phone_e164 and context:
                    phone_e164 = context.get('phone')
                
                # Last resort: use customer_phone (may be @lid, but better than nothing)
                if not phone_e164:
                    phone_e164 = customer_phone
                
                g.agent_context = {
                    "phone": phone_e164,  # 🔥 FIX: Use E.164 phone, not @lid
                    "phone_e164": phone_e164,  # Explicit E.164 field for tools
                    "customer_phone": customer_phone,  # Original for reference
                    "whatsapp_from": customer_phone,  # WhatsApp conversation key
                    "remote_jid": agent_context.get('remote_jid'),  # JID for replies
                    "business_id": business_id,
                    "lead_id": agent_context.get('lead_id'),
                    "conversation_key": customer_phone,
                    "channel": channel
                }
                logger.info(f"[AGENTKIT] ✅ Set g.agent_context for tools: phone_e164={phone_e164}, jid={agent_context.get('remote_jid', 'N/A')[:30]}")
            except Exception as g_err:
                logger.warning(f"[AGENTKIT] ⚠️ Could not set g.agent_context (tools may fail): {g_err}")
            
            logger.info(f"[AGENTKIT] 🔑 tracking_id={conversation_id}, message='{message[:50]}...'")
            logger.info(f"[AGENTKIT] 📊 Context: business_id={business_id}, channel={channel}")
            
            # 🔥 FIX: Convert previous_messages to OpenAI message format for conversation history
            # Previous_messages comes as strings like "לקוח: text" or "עוזר: text"
            messages = []
            if context and context.get('previous_messages'):
                previous_messages = context['previous_messages']
                # Defensive: Ensure previous_messages is a list before slicing
                if isinstance(previous_messages, list):
                    # Keep last N messages for context (avoid token limits)
                    for msg_str in previous_messages[-MAX_CONVERSATION_HISTORY_MESSAGES:]:
                        # Defensive: Ensure msg_str is a string before processing
                        if isinstance(msg_str, str):
                            if msg_str.startswith("לקוח:"):
                                # Customer message
                                content = msg_str.replace("לקוח:", "", 1).strip()
                                messages.append({"role": "user", "content": content})
                            elif msg_str.startswith("עוזר:"):
                                # Assistant message
                                content = msg_str.replace("עוזר:", "", 1).strip()
                                messages.append({"role": "assistant", "content": content})
                            # Ignore messages that don't match format
                    
                    logger.info(f"[AGENTKIT] 📚 Converted {len(messages)} previous messages to conversation history")
                else:
                    logger.warning(f"[AGENTKIT] ⚠️ previous_messages is not a list, type={type(previous_messages)}")
            
            # 🔥 FIX: Only add current message if it's not already the last message in history
            # This prevents duplicate messages when the current message was already saved to DB
            # before loading the conversation history
            should_add_current = True
            if messages and len(messages) > 0:
                last_msg = messages[-1]
                if last_msg.get("role") == "user" and last_msg.get("content", "").strip() == message.strip():
                    logger.info(f"[AGENTKIT] 🔄 Current message already in history, skipping duplicate")
                    should_add_current = False
            
            if should_add_current:
                messages.append({"role": "user", "content": message})
                logger.info(f"[AGENTKIT] ➕ Added current message to conversation")
            else:
                logger.info(f"[AGENTKIT] ✓ Using existing message from history")
            
            # 🔥 NEW: Inject lead context as system message if available
            # 🔥 CRITICAL CHECK: Validate lead_context is loaded when lead_id exists
            if context and context.get('lead_id'):
                if not context.get('lead_context'):
                    logger.error(f"[CONTEXT] ❌ CRITICAL: lead_id={context.get('lead_id')} exists but lead_context is None! "
                               f"This breaks single source of truth. Check UnifiedLeadContextService.")
            
            if context and context.get('lead_context'):
                try:
                    lead_ctx_dict = context['lead_context']
                    lead_ctx = UnifiedLeadContextPayload(**lead_ctx_dict)
                    
                    if lead_ctx.found:
                        service = UnifiedLeadContextService(business_id)
                        context_text = service.format_context_for_prompt(lead_ctx)
                        
                        if context_text:
                            # Prepend lead context as system message
                            messages.insert(0, {
                                "role": "system",
                                "content": f"📋 **מידע על הלקוח (יש לך גישה מלאה למידע הזה - השתמש בו לצורך מענה מדויק):**\n\n{context_text}\n\n⚠️ **חשוב:** אל תציין ללקוח שיש לך מערכת או מידע - פשוט ענה בצורה טבעית על בסיס המידע המופיע למעלה."
                            })
                            
                            # 🔥 CRITICAL: Add another system message AFTER history to override past errors
                            messages.append({
                                "role": "system", 
                                "content": "🔥 **עדכון חשוב:** כעת יש לך גישה מלאה למידע הלקוח (ראה למעלה). אם בתשובות קודמות אמרת שיש 'בעיה טכנית' - התעלם מזה עכשיו. המידע זמין ותקין. השתמש בו!"
                            })
                            
                            logger.info(f"[AGENTKIT] 🎧 Prepended lead context to conversation ({len(context_text)} chars)")
                            logger.info(f"[AGENTKIT] 📄 CONTEXT CONTENT:\n{context_text[:500]}...")  # 🔥 DEBUG: Print first 500 chars
                except Exception as ctx_err:
                    logger.warning(f"[AGENTKIT] Failed to format lead context: {ctx_err}")
            
            # 🔥 CRITICAL: Log complete payload before LLM call (Hebrew labels requirement)
            # This ensures we can verify that all labels are in Hebrew as required
            try:
                # Configuration for logging
                MAX_SUMMARY_LENGTH = 100  # For summaries and notes
                MAX_TEXT_LENGTH = 150  # For general text truncation
                
                # Helper functions to mask sensitive data for logging
                def mask_phone(phone: str) -> str:
                    """
                    Mask phone number for privacy with robust handling
                    Examples:
                        +972501234567 → +972***4567
                        050123456 → 050***456
                        123 → 123 (too short, return as-is)
                    """
                    if not phone:
                        return phone
                    phone_str = str(phone).strip()
                    if len(phone_str) < 6:  # Too short to mask meaningfully
                        return phone_str
                    # Mask middle portion, keep prefix and suffix
                    prefix_len = min(4, len(phone_str) // 3)
                    suffix_len = min(4, len(phone_str) // 3)
                    return phone_str[:prefix_len] + "***" + phone_str[-suffix_len:]
                
                def mask_email(email: str) -> str:
                    """Mask email for privacy: user@example.com → u***@example.com"""
                    if not email or '@' not in email:
                        return email
                    local, domain = email.split('@', 1)
                    masked_local = local[0] + '***' if len(local) > 1 else local
                    return f"{masked_local}@{domain}"
                
                def truncate_text(text: str, max_length: int) -> str:
                    """Truncate text for logging (explicit max_length required)"""
                    if not text:
                        return text
                    if len(text) <= max_length:
                        return text
                    return text[:max_length] + "..."
                
                payload_debug = {
                    "business_id": business_id,
                    "channel": channel,
                    "conversation_id": conversation_id,
                    "messages_count": len(messages),
                    "agent_context_keys": list(agent_context.keys()) if agent_context else [],
                    "lead_context": None,
                    "appointments": None,
                    "lead_status": None,
                    "calendar_status": None,
                    "notes": None,
                    "tags": None,
                    "last_messages": None,
                    "custom_fields": None
                }
                
                # Extract lead context for logging if available
                if context and context.get('lead_context'):
                    lead_ctx_dict = context['lead_context']
                    payload_debug["lead_context"] = {
                        "lead_id": lead_ctx_dict.get('lead_id'),
                        "lead_name": lead_ctx_dict.get('lead_name'),  # Names are okay to log
                        "lead_phone": mask_phone(lead_ctx_dict.get('lead_phone')) if lead_ctx_dict.get('lead_phone') else None,
                        "current_status": lead_ctx_dict.get('current_status'),
                        "lead_source": lead_ctx_dict.get('lead_source'),
                        "tags": lead_ctx_dict.get('tags'),
                        "summary": truncate_text(lead_ctx_dict.get('summary'), MAX_SUMMARY_LENGTH) if lead_ctx_dict.get('summary') else None
                    }
                    payload_debug["lead_status"] = {
                        "current_status": lead_ctx_dict.get('current_status'),
                        "current_status_id": lead_ctx_dict.get('current_status_id'),
                        "current_status_label_he": lead_ctx_dict.get('current_status_label_he'),  # 🔥 KEY: Verify Hebrew label
                        "pipeline_stage": lead_ctx_dict.get('pipeline_stage'),
                        "status_history_count": len(lead_ctx_dict.get('status_history', []))
                    }
                    payload_debug["appointments"] = {
                        "next_appointment": {
                            "title": next_apt.get('title') if (next_apt := lead_ctx_dict.get('next_appointment')) else None,
                            "status": next_apt.get('status') if next_apt else None,
                            "calendar_status_label_he": next_apt.get('calendar_status_label_he') if next_apt else None,  # 🔥 KEY: Verify Hebrew label
                            "start": next_apt.get('start', '')[:19] if next_apt else None
                        } if lead_ctx_dict.get('next_appointment') else None,
                        "past_appointments_count": len(lead_ctx_dict.get('past_appointments', []))
                    }
                    payload_debug["notes"] = {
                        "recent_notes_count": len(lead_ctx_dict.get('recent_notes', [])),
                        "last_call_summary": truncate_text(lead_ctx_dict.get('last_call_summary'), MAX_SUMMARY_LENGTH) if lead_ctx_dict.get('last_call_summary') else None,
                        "last_whatsapp_summary": truncate_text(lead_ctx_dict.get('last_whatsapp_summary'), MAX_SUMMARY_LENGTH) if lead_ctx_dict.get('last_whatsapp_summary') else None
                    }
                    payload_debug["tags"] = lead_ctx_dict.get('tags', [])
                    
                    # 🔥 Extract custom fields from appointments
                    custom_fields_found = []
                    next_apt = lead_ctx_dict.get('next_appointment')
                    if next_apt and next_apt.get('custom_fields'):
                        custom_fields_found.append({
                            "appointment": "next",
                            "fields": next_apt['custom_fields']
                        })
                    
                    past_apts = lead_ctx_dict.get('past_appointments', [])
                    for idx, apt in enumerate(past_apts[:2]):  # First 2 past appointments
                        if apt.get('custom_fields'):
                            custom_fields_found.append({
                                "appointment": f"past_{idx}",
                                "fields": apt['custom_fields']
                            })
                    
                    payload_debug["custom_fields"] = custom_fields_found if custom_fields_found else None
                
                # Log as pretty JSON
                logger.info(f"🔍 [PAYLOAD_DEBUG] Complete payload before LLM call:")
                logger.info(f"{json.dumps(payload_debug, ensure_ascii=False, indent=2)}")
                
            except Exception as log_err:
                logger.error(f"❌ Failed to log payload debug info: {log_err}")
            
            # Run agent using Runner.run_sync() (correct API for openai-agents SDK)
            logger.info(f"🔙 About to call Runner.run_sync with {len(messages)} messages")
            logger.info(f"📨 [DEBUG] Messages array:")
            for i, msg in enumerate(messages):
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')[:150]
                logger.info(f"   [{i}] {role}: {content}...")
            
            result = Runner.run_sync(agent, input=messages, context=agent_context)
            
            # Extract response text from result
            # The OpenAI Agents SDK can return different result types:
            # - output_text: Most common (standard agent response)
            # - final_output: Alternative format in some configurations
            # - text/response: Legacy formats for backward compatibility
            reply_text = ""
            if hasattr(result, 'output_text') and result.output_text:
                reply_text = str(result.output_text)
            elif hasattr(result, 'final_output') and result.final_output:
                reply_text = str(result.final_output)
            elif hasattr(result, 'text') and result.text:
                reply_text = result.text
            elif hasattr(result, 'response') and result.response:
                reply_text = result.response
            else:
                # Fallback: log warning and return empty
                logger.warning(f"[AGENTKIT] Unable to extract text from result type: {type(result)}")
                reply_text = ""
            
            logger.info(f"[AGENTKIT] ✅ Agent response generated: {len(reply_text)} chars")
            logger.info(f"[AGENTKIT] 📝 Response preview: {reply_text[:100] if reply_text else '(empty)'}...")
            
            # Anti-loop detection (logging only - no retry with hardcoded instructions)
            # The DB prompt should handle anti-repetition rules
            if context and context.get('last_agent_message'):
                last_agent_message = context.get('last_agent_message', '')
                if last_agent_message and reply_text:
                    # Compare first 40 characters to detect repetition
                    response_start = reply_text[:40].strip()
                    last_start = last_agent_message[:40].strip()
                    
                    if response_start and last_start and response_start == last_start:
                        logger.warning(f"[AGENTKIT] ⚠️ Agent may be repeating response! Last: '{last_start}...', New: '{response_start}...'")
                        logger.warning(f"[AGENTKIT] Consider adding anti-repetition rules to the DB prompt")
            
            # Track conversation turn for debugging
            try:
                from server.agent_tools.agent_factory import track_conversation_turn
                track_conversation_turn(conversation_id, message, reply_text)
            except Exception as track_err:
                logger.debug(f"Could not track conversation turn: {track_err}")
            
            logger.info(f"🔙 About to return from generate_response_with_agent()")
            
            # Return structured response
            return {
                "text": reply_text.strip() if reply_text else "",
                "actions": []  # Actions would be extracted from result.new_items if needed
            }
            
        except Exception as e:
            logger.error(f"[AGENTKIT] Agent error (falling back to regular response): {e}")
            import traceback
            traceback.print_exc()
            
            # Fallback to regular response
            response_text = self.generate_response(message, business_id, context, channel, is_first_turn)
            return {
                "text": response_text,
                "actions": []
            }
    
    def save_conversation_history(self, business_id: int, phone_number: str, 
                                 message: str, response: str, channel: str = "whatsapp"):
        """שמירת היסטוריית שיחה למידע עתידי (אופציונלי)"""
        try:
            # כאן אפשר להוסיף לוגיקה לשמירת שיחות ארוכות
            # לצרכי הקשר עתידי או אנליטיקה
            pass
        except Exception as e:
            logger.error(f"Failed to save conversation history: {e}")
            logger.error(f"❌ FAQ LLM failed after retry: {e}")
            # Realtime phone calls use media_ws_ai.py with separate tool handling
            tool_calls_data = []
            tool_count = 0
            booking_successful = False  # Track if booking actually succeeded
            # For WhatsApp hardening: if any tool returns user_message on error, we can force it verbatim.
            forced_user_message: Optional[str] = None
            
            if hasattr(result, 'new_items') and result.new_items:
                logger.info(f"📊 Agent returned {len(result.new_items)} items")
                logger.info(f"📊 [AGENTKIT] Agent returned {len(result.new_items)} items")
                # Filter for ToolCallItem types and extract tool names
                for idx, item in enumerate(result.new_items):
                    item_type = type(item).__name__
                    logger.info(f"   - Item #{idx}: {item_type}")
                    logger.info(f"   - Item type: {item_type}")
                    
                    if item_type == 'ToolCallItem':
                        tool_count += 1
                        
                        # 🔍 DEBUG: Print ALL attributes to find tool name
                        logger.debug(f"  🔍 DEBUG ToolCallItem #{tool_count}:")
                        all_attrs = [a for a in dir(item) if not a.startswith('_')]
                        logger.info(f"     All attributes: {all_attrs}")
                        
                        # Try to access common attributes
                        for attr in ['name', 'tool_name', 'tool_call', 'function', 'tool']:
                            if hasattr(item, attr):
                                val = getattr(item, attr)
                                logger.info(f"     {attr} = {val}")
                        
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
                        
                        logger.info(f"  🔧 Tool call #{tool_count}: {tool_name}")
                        logger.info(f"  ✅ [AGENTKIT] Tool call #{tool_count}: {tool_name}")
                        tool_calls_data.append({
                            "tool": tool_name,
                            "status": "success",
                            "result": None  # Result is in separate ToolCallOutputItem
                        })
                    
                    elif item_type == 'ToolCallOutputItem':
                        # Extract tool output/result
                        output = getattr(item, 'output', None)
                        logger.info(f"  📤 Tool output: {str(output)[:200] if output else 'None'}...")
                        if output:
                            logger.info(f"     [AGENTKIT] Tool returned: {str(output)[:100]}")
                            
                            # 🔍 CHECK if this is a successful booking
                            if isinstance(output, dict):
                                # Unified success detection (calendar_* returns ok, WhatsApp tools return success)
                                appt_id = output.get('appointment_id')
                                if appt_id and (output.get('ok') is True or output.get('success') is True):
                                    booking_successful = True
                                    logger.info(f"     ✅ DETECTED SUCCESSFUL BOOKING: appointment_id={appt_id}")
                                    # Store appointment details for WhatsApp validation
                                    if not hasattr(result, 'appointment_details'):
                                        result.appointment_details = output
                                # Capture deterministic user_message from tool errors (WhatsApp must echo verbatim)
                                if output.get("success") is False and output.get("user_message") and not forced_user_message:
                                    forced_user_message = str(output.get("user_message"))
                
                if tool_count > 0:
                    logger.info(f"✅ [AGENTKIT] Agent executed {tool_count} tool actions")
                    logger.info(f"✅ [AGENTKIT] Agent executed {tool_count} tool actions")
                else:
                    logger.warning(f"⚠️ [AGENTKIT] Agent DID NOT call any tools! (message: '{message[:50]}...')")
                    logger.warning(f"⚠️ [AGENTKIT] Agent DID NOT call any tools! (message: '{message[:50]}...')")
            else:
                logger.warning(f"⚠️ [AGENTKIT] Result has NO new_items or new_items is empty!")
            
            # ✅ RESTORED: Tool validation for AgentKit (non-realtime flows)
            # If agent claims action without executing tool, BLOCK response
            claim_words = ["קבעתי", "שלחתי", "יצרתי", "הפגישה נקבעה", "הפגישה קבועה", "סגרתי", "נקבע", "התור נקבע", "התור קבוע"]
            claimed_action = any(word in reply_text for word in claim_words)
            
            # Detect "hallucinated availability" (saying "busy/available" without checking)
            hallucinated_availability_words = ["אין זמנים פנויים", "אין זמינות", "הכל תפוס", "לא פנוי", "לא זמין", "תפוס", "פנוי", "תפוס ב"]
            claimed_availability = any(word in reply_text for word in hallucinated_availability_words)
            
            # ✅ RESTORED: Tool call validation for AgentKit (non-realtime flows)
            # Check if calendar_create_appointment was called (with or without _wrapped suffix)
            booking_tool_called = any(
                tc.get("tool") in [
                    "calendar_create_appointment",
                    "calendar_create_appointment_wrapped",
                    # WhatsApp unified endpoint (AgentKit)
                    "schedule_appointment",
                ]
                for tc in tool_calls_data
            )
            
            # 🔥 FALLBACK: If tool name extraction failed, check output structure
            # If we see {'appointment_id': ...} in ANY tool output → calendar_create_appointment was called
            if not booking_tool_called and tool_count > 0:
                for item in result.new_items if hasattr(result, 'new_items') else []:
                    if type(item).__name__ == 'ToolCallOutputItem':
                        output = getattr(item, 'output', None)
                        if isinstance(output, dict) and 'appointment_id' in output:
                            logger.info(f"  🔥 FALLBACK: Detected calendar_create_appointment from output structure (has 'appointment_id' key)")
                            booking_tool_called = True
                            break
            
            # Check if calendar_find_slots was called
            check_availability_called = any(
                tc.get("tool") in [
                    "calendar_find_slots",
                    "calendar_find_slots_wrapped",
                    # WhatsApp unified endpoint (AgentKit)
                    "check_availability",
                ]
                for tc in tool_calls_data
            )
            
            # 🔥 FALLBACK: If tool name extraction failed, check output structure
            # If we see {'slots': [...]} in ANY tool output → calendar_find_slots was called
            if not check_availability_called and tool_count > 0:
                for item in result.new_items if hasattr(result, 'new_items') else []:
                    if type(item).__name__ == 'ToolCallOutputItem':
                        output = getattr(item, 'output', None)
                        if isinstance(output, dict) and 'slots' in output:
                            logger.info(f"  🔥 FALLBACK: Detected calendar_find_slots from output structure (has 'slots' key)")
                            check_availability_called = True
                            break
            
            # Check if whatsapp_send was called (for phone channel only)
            whatsapp_sent = any(
                tc.get("tool") == "whatsapp_send"
                for tc in tool_calls_data
            )
            
            # ✅ RESTORED: Hallucination detection for AgentKit (non-realtime flows)
            # 🔥 WORKAROUND: Also check if we detected a successful booking in the output
            # (in case tool name extraction failed but booking actually succeeded)
            logger.info(f"  🔍 [AGENTKIT] VALIDATION CHECK:")
            logger.info(f"     claimed_action={claimed_action}")
            logger.info(f"     claimed_availability={claimed_availability}")
            logger.info(f"     booking_tool_called={booking_tool_called}")
            logger.info(f"     check_availability_called={check_availability_called}")
            logger.info(f"     booking_successful={booking_successful}")
            
            # 🔥 BUILD 110: HARD BLOCK - Agent CANNOT claim success without tool execution!
            # Regex patterns for detecting false claims
            import re
            booking_claims = re.compile(r'(קבעתי|קבענו|שריינתי|תיאמתי|נקבעה פגישה|נקבע לך)', re.IGNORECASE)
            # WhatsApp claims - match BOTH directions (verb-noun AND noun-verb)
            whatsapp_claims = re.compile(
                r'((שלחתי|שולח|נשלח).*(אישור|הודעה|וואטסאפ|whatsapp))|'
                r'((אישור|הודעה|וואטסאפ|whatsapp).*(שלחתי|נשלח))',
                re.IGNORECASE
            )
            
            # Check if agent is lying about booking
            claims_booking = bool(booking_claims.search(reply_text))
            claims_whatsapp = bool(whatsapp_claims.search(reply_text))
            
            logger.info(f"🔍 [AGENTKIT] HARD VALIDATION:")
            logger.info(f"   claims_booking={claims_booking}, booking_tool_called={booking_tool_called}")
            logger.info(f"   claims_whatsapp={claims_whatsapp}")
            
            # 🚨 BLOCK 1: Hallucinated booking - STRICT ENFORCEMENT
            if claims_booking and not booking_tool_called and not booking_successful:
                logger.info(f"🚨 [AGENTKIT] HARD BLOCKED BOOKING LIE!")
                logger.info(f"   Agent claimed: '{reply_text[:80]}...'")
                logger.info(f"   But NO calendar_create_appointment was called!")
                logger.error(f"🚨 [AGENTKIT] HARD BLOCK: Blocked booking lie without tool call")
                
                # 🔥 OVERRIDE: Agent cannot claim booking without tool!
                reply_text = "מה השעה המועדפת שלך? אבדוק זמינות ואקבע."
                logger.info(f"   ✅ HARD OVERRIDE: '{reply_text}'")
            
            # 🚨 BLOCK 2: Hallucinated WhatsApp send
            elif claims_whatsapp and not whatsapp_sent and channel == "calls":
                logger.info(f"🚨 [AGENTKIT] HARD BLOCKED WHATSAPP LIE!")
                logger.info(f"   Agent claimed: '{reply_text[:80]}...'")
                logger.info(f"   But NO whatsapp_send was called!")
                logger.error(f"🚨 [AGENTKIT] HARD BLOCK: Blocked WhatsApp send lie without tool call")
                
                # 🔥 OVERRIDE: Be HONEST - did NOT send WhatsApp!
                reply_text = "מעולה! הפרטים נרשמו. ניצור קשר בהמשך עם פרטי הפגישה."
                logger.info(f"   ✅ HARD OVERRIDE: '{reply_text}'")
            
            # 🚨 BLOCK 3: Hallucinated availability
            elif claimed_availability and not check_availability_called:
                logger.info(f"🚨 [AGENTKIT] BLOCKED HALLUCINATED AVAILABILITY!")
                logger.info(f"   Agent claimed: '{reply_text[:80]}...'")
                logger.info(f"   But NO calendar_find_slots was called!")
                logger.error(f"🚨 [AGENTKIT] Blocked hallucinated availability: agent claimed busy/free without checking")
                
                # Override response with corrective message
                reply_text = "באיזה יום ושעה נוח לך?"
                logger.info(f"   ✅ Replaced with: '{reply_text}'")
            
            # ⚠️  LOG: Missing WhatsApp confirmation (not blocking)
            elif booking_successful and channel == "calls" and not whatsapp_sent:
                logger.warning(f"⚠️  [AGENTKIT] INFO: Booking successful but NO WhatsApp sent (agent didn't try)")
                logger.info(f"⚠️  [AGENTKIT] Booking successful without WhatsApp confirmation")
                # Don't block - just log (WhatsApp is nice-to-have, not critical)

            # ✅ WhatsApp hardening: if a tool returned user_message on error, force the reply to it verbatim.
            # This prevents improvisation and ensures consistent UX with Realtime.
            if channel == "whatsapp" and forced_user_message and not booking_successful:
                logger.info(f"WHATSAPP_APPT forcing user_message verbatim: '{forced_user_message[:120]}'")
                reply_text = forced_user_message
            
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
            
            # 🔥 BUILD 118: Serialize new_items to preserve FULL metadata (not stringified summaries)
            def make_json_safe(obj):
                """Recursively convert object to JSON-safe primitives"""
                if obj is None or isinstance(obj, (bool, int, float, str)):
                    return obj
                elif isinstance(obj, dict):
                    return {k: make_json_safe(v) for k, v in obj.items()}
                elif isinstance(obj, (list, tuple)):
                    return [make_json_safe(item) for item in obj]
                elif hasattr(obj, 'model_dump'):
                    return make_json_safe(obj.model_dump())
                elif hasattr(obj, 'dict'):
                    return make_json_safe(obj.dict())
                elif hasattr(obj, '__dict__'):
                    return make_json_safe({k: v for k, v in obj.__dict__.items() if not k.startswith('_')})
                else:
                    # Last resort: convert to string
                    return str(obj)
            
            def serialize_run_items(items):
                """Convert RunItems to JSON-serializable dicts"""
                serialized = []
                for item in (items or []):
                    try:
                        # Try Pydantic model_dump() first (AgentKit uses Pydantic)
                        if hasattr(item, 'model_dump'):
                            raw_dict = item.model_dump()
                        # Try to_dict() method
                        elif hasattr(item, 'to_dict'):
                            raw_dict = item.to_dict()
                        # Try dict() for Pydantic v1
                        elif hasattr(item, 'dict'):
                            raw_dict = item.dict()
                        # Fallback: dataclasses.asdict
                        else:
                            from dataclasses import asdict, is_dataclass
                            if is_dataclass(item):
                                raw_dict = asdict(item)
                            else:
                                # Last resort: filter __dict__ for JSON-safe fields
                                raw_dict = {k: v for k, v in item.__dict__.items() if not k.startswith('_')}
                        
                        # 🔥 CRITICAL: Make nested objects JSON-safe
                        safe_dict = make_json_safe(raw_dict)
                        serialized.append(safe_dict)
                    except Exception as e:
                        logger.error(f"⚠️ Failed to serialize item {type(item).__name__}: {e}")
                        serialized.append({"type": type(item).__name__, "error": str(e)})
                return serialized
            
            # 🔥 BUILD 118: Return structured response (preserves metadata for analytics + transcripts)
            # Convert RunOutput to dict with FULL new_items structure (not stringified summaries)
            response_payload = {
                "text": reply_text,  # Use (possibly truncated) text
                "usage": {
                    "prompt_tokens": getattr(result, 'prompt_tokens', 0),
                    "completion_tokens": getattr(result, 'completion_tokens', 0),
                    "total_tokens": getattr(result, 'total_tokens', 0)
                },
                "actions": serialize_run_items(result.new_items) if hasattr(result, 'new_items') else [],
                "booking_successful": booking_successful
            }
            logger.info(f"✅ Returning structured response: {len(reply_text)} chars text, {len(response_payload['actions'])} serialized actions")
            logger.info(f"🔙 About to return from generate_response_with_agent()")
            return response_payload
            
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

def generate_ai_response(message: str, business_id: int = None, 
                        context: Optional[Dict[str, Any]] = None, channel: str = "calls",
                        is_first_turn: bool = False) -> str:
    """פונקציה עזר לקריאה מהירה לשירות AI - לפי ערוץ"""
    return get_ai_service().generate_response(message, business_id, context, channel, is_first_turn)

# 🔥 FIX: Alias for routes_whatsapp.py compatibility
def get_ai_response(business_id: int, user_message: str, channel: str = "whatsapp") -> Optional[str]:
    """Wrapper function for WhatsApp AI responses - alias for generate_ai_response
    
    Returns:
        str: AI response text, or None if generation fails (caller should handle None)
    """
    try:
        response = generate_ai_response(user_message, business_id, None, channel)
        if response:
            return response
        logger.warning(f"[AI_SERVICE] get_ai_response returned empty response")
        return None
    except Exception as e:
        logger.error(f"[AI_SERVICE] get_ai_response error: {e}")
        import traceback
        traceback.print_exc()
        return None

