"""
Realtime Prompt Builder - REFACTORED FOR PERFECT LAYER SEPARATION
=================================================================

🎯 MISSION: Zero collisions, zero duplicated rules, perfect dynamic flow

LAYER ARCHITECTURE:
1. SYSTEM PROMPT → Behavior rules only (universal, no content)
2. BUSINESS PROMPT → All flow, script, and domain content
3. TRANSCRIPT PROMPT → Recognition enhancement only
4. NLP PROMPT → Data extraction only (handled separately)

🔥 BUILD: PERFECT INBOUND & OUTBOUND SEPARATION
- build_inbound_system_prompt(): Full control settings + appointment scheduling
- build_outbound_system_prompt(): Pure prompt mode, no call control
- build_realtime_system_prompt(): Router that calls the correct builder
"""
import logging
from typing import Optional, Tuple, Dict, Any
from datetime import datetime
import pytz
import json
import re

logger = logging.getLogger(__name__)

_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"  # emoji/pictographs/symbols
    "\U00002700-\U000027BF"  # dingbats
    "]+",
    flags=re.UNICODE,
)
_BOX_DRAWING_RE = re.compile(r"[\u2500-\u257F\u2580-\u259F]")
_ARROWS_RE = re.compile(r"[\u2190-\u21FF]")
_MARKDOWN_FENCE_RE = re.compile(r"```[\s\S]*?```", flags=re.MULTILINE)


def sanitize_realtime_instructions(text: str, max_chars: int = 1000) -> str:
    """
    Sanitize text before sending to OpenAI Realtime `session.update.instructions`.

    Goals:
    - Remove heavy formatting / non-speech symbols that can confuse TTS
    - Flatten newlines (both actual and escaped) into spaces
    - Hard-cap size (Realtime is sensitive to large instructions)
    """
    if not text:
        return ""

    # Remove fenced code blocks entirely (rare but can appear in prompts)
    text = _MARKDOWN_FENCE_RE.sub(" ", text)

    # Normalize escaped newlines first, then real newlines
    text = text.replace("\\n", " ").replace("\n", " ")

    # Remove common "layout" unicode blocks (box drawing, arrows, emoji)
    text = _BOX_DRAWING_RE.sub(" ", text)
    text = _ARROWS_RE.sub(" ", text)
    text = _EMOJI_RE.sub(" ", text)

    # Strip common markdown-ish separators and list bullets
    text = re.sub(r"[`*_>#|]+", " ", text)
    text = re.sub(r"[•●▪▫◆◇■□]+", " ", text)

    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    if max_chars and len(text) > max_chars:
        cut = text[:max_chars]
        # Try to cut at a natural boundary, but don't over-trim.
        boundary = max(
            cut.rfind(". "),
            cut.rfind("? "),
            cut.rfind("! "),
            cut.rfind(" "),
        )
        if boundary >= int(max_chars * 0.6):
            text = cut[:boundary].strip()
        else:
            text = cut.strip()

    return text

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔥 PART 1: SYSTEM PROMPT - UNIVERSAL BEHAVIOR RULES ONLY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _build_universal_system_prompt() -> str:
    """
    🎯 UNIVERSAL SYSTEM PROMPT - Technical Behavior Rules ONLY
    
    ✅ MUST CONTAIN:
    - Realtime API rules (barge-in, pauses, noise)
    - Business isolation rules (ZERO cross-contamination)
    - Call isolation rules (each call independent)
    - Language rules (Hebrew default, auto-switch)
    - Truth & safety rules (transcription is truth)
    - Conversation rules (short, clear responses)
    
    ❌ MUST NOT CONTAIN:
    - Flow logic (comes from Business Prompt)
    - Service names, city names, business names
    - Domain-specific examples or scripts
    
    This prompt is IDENTICAL for all businesses - only behavior, no content.
    Written in English for optimal AI understanding.
    """
    # Keep this SHORT and purely operational for Realtime.
    # Target: <= ~900 chars, no markdown, no separators, no icons.
    return (
        "You are a professional male-voice phone agent for the currently active business only. "
        "Business isolation: every call is independent; ignore any info or style from other businesses/calls. "
        "Language: speak Hebrew by default; switch only if the caller explicitly asks. "
        "Barge-in: if the caller starts speaking, stop immediately and wait. "
        "Truth: use the transcript as the single source of truth; never invent details; if unclear, ask to repeat. "
        "Style: be warm, calm, and concise (1-2 sentences). Ask one question at a time. "
        "Follow the Business Prompt for content and flow."
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔥 PART 2: LEGACY FUNCTIONS (for backward compatibility)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def get_greeting_prompt_fast(business_id: int) -> Tuple[str, str]:
    """
    FAST greeting loader - minimal DB access for phase 1
    Returns (greeting_text, business_name)
    
    🔥 CRITICAL: All greetings must come from DB. No hardcoded fallbacks.
    """
    try:
        from server.models_sql import Business
        
        business = Business.query.get(business_id)
        if not business:
            logger.warning(f"⚠️ Business {business_id} not found - using minimal generic greeting")
            return ("", "")  # Return empty - let AI handle naturally
        
        business_name = business.name or ""
        greeting = business.greeting_message
        
        if greeting and greeting.strip():
            # Replace placeholder with actual business name
            final_greeting = greeting.strip().replace("{{business_name}}", business_name).replace("{{BUSINESS_NAME}}", business_name)
            logger.info(f"✅ [GREETING] Loaded from DB for business {business_id}: '{final_greeting[:50]}...'")
            return (final_greeting, business_name)
        else:
            logger.warning(f"⚠️ No greeting in DB for business {business_id} - AI will greet naturally")
            return ("", business_name)  # Let AI greet based on prompt
    except Exception as e:
        logger.error(f"❌ Fast greeting load failed: {e}")
        return ("", "")  # Return empty - let AI handle naturally


def build_compact_greeting_prompt(business_id: int, call_direction: str = "inbound") -> str:
    """
    🔥 REFACTORED: COMPACT version of full prompt for ultra-fast greeting
    
    Uses the SAME builders as full prompt (build_inbound_system_prompt / build_outbound_system_prompt)
    but with compact=True flag to extract only ~600-800 chars for sub-2s response.
    
    This ensures ZERO divergence between greeting and full prompt!
    
    Strategy:
    1. Call the correct builder (inbound/outbound) based on call_direction
    2. Extract first 600-800 chars from business prompt only (no system rules for greeting)
    3. Add minimal context reminder (direction, STT truth)
    
    Target: Under 800 chars for < 2 second greeting response.
    """
    try:
        from server.models_sql import Business, BusinessSettings
        import json
        
        business = Business.query.get(business_id)
        settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
        
        if not business:
            logger.warning(f"⚠️ [COMPACT] Business {business_id} not found")
            return "You are a professional service rep. SPEAK HEBREW to customer. Be brief and helpful."
        
        business_name = business.name or "Business"
        
        # 🔥 EXTRACT BUSINESS PROMPT based on direction
        if call_direction == "outbound":
            # Use outbound_ai_prompt
            ai_prompt_raw = settings.outbound_ai_prompt if (settings and settings.outbound_ai_prompt) else ""
            logger.info(f"📦 [COMPACT] Using OUTBOUND prompt for {business_name}")
        else:
            # Use regular ai_prompt
            ai_prompt_raw = settings.ai_prompt if settings else ""
            logger.info(f"📦 [COMPACT] Using INBOUND prompt for {business_name}")
        
        # Parse business prompt (handle JSON format)
        ai_prompt_text = ""
        if ai_prompt_raw and ai_prompt_raw.strip():
            raw_prompt = ai_prompt_raw.strip()
            
            # Handle JSON format (with 'calls' key)
            if raw_prompt.startswith('{'):
                try:
                    prompt_obj = json.loads(raw_prompt)
                    if 'calls' in prompt_obj:
                        ai_prompt_text = prompt_obj['calls']
                    elif 'whatsapp' in prompt_obj:
                        ai_prompt_text = prompt_obj['whatsapp']
                    else:
                        ai_prompt_text = raw_prompt
                except json.JSONDecodeError:
                    ai_prompt_text = raw_prompt
            else:
                ai_prompt_text = raw_prompt
        
        # 🔥 COMPACT: Keep first contact fast + clean (Realtime is sensitive to heavy/dirty instructions)
        if ai_prompt_text:
            # Replace placeholders
            ai_prompt_text = ai_prompt_text.replace("{{business_name}}", business_name)
            ai_prompt_text = ai_prompt_text.replace("{{BUSINESS_NAME}}", business_name)
            
            # 1) Sanitize FIRST (remove \\n/markdown/icons/separators), then 2) cut 300–400 chars
            ai_prompt_text = sanitize_realtime_instructions(ai_prompt_text, max_chars=5000)

            # Take first 300–400 chars (assume business opening is at start of business prompt)
            excerpt_max = 390
            excerpt_window = 440  # small lookahead for clean cut
            if len(ai_prompt_text) > excerpt_max:
                window = ai_prompt_text[: min(len(ai_prompt_text), excerpt_window)]

                # Prefer sentence boundary, else fallback to last space (never cut mid-word)
                cut_point = -1
                for delimiter in (". ", "? ", "! "):
                    pos = window.rfind(delimiter)
                    if pos != -1 and pos >= 220:
                        cut_point = pos + len(delimiter)
                        break

                if cut_point == -1:
                    # Last space within max region
                    cut_point = ai_prompt_text[:excerpt_max].rfind(" ")
                    if cut_point < 220:
                        cut_point = excerpt_max

                compact_context = ai_prompt_text[:cut_point].strip()
            else:
                compact_context = ai_prompt_text.strip()
            
            logger.info(f"✅ [COMPACT] Extracted {len(compact_context)} chars from {call_direction} prompt")
        else:
            # 🎯 MASTER DIRECTIVE 1: PROMPT FALLBACK logging
            # If missing → fallback ONCE and log
            compact_context = f"You are a professional service rep for {business_name}. SPEAK HEBREW to customer. Be brief and helpful."
            logger.warning(
                f"[PROMPT FALLBACK] missing business prompt business_id={business_id} direction={call_direction}"
            )
        
        # 🔥 COMPACT = short system + tone + business opening excerpt (and nothing more)
        direction = "INBOUND" if call_direction == "inbound" else "OUTBOUND"
        system_rules = _build_universal_system_prompt()
        tone = "Tone: warm, calm, human, concise. Speak Hebrew."

        final_prompt = (
            f"{system_rules} "
            f"{tone} "
            f"Call type: {direction}. "
            f"Business opening (use this to start the call): {compact_context}"
        )
        # Hard cap for Realtime instructions
        final_prompt = sanitize_realtime_instructions(final_prompt, max_chars=1000)

        logger.info(f"📦 [COMPACT] Final compact prompt: {len(final_prompt)} chars for {call_direction}")
        
        # 🔥 PROMPT_CONTEXT: Log that compact prompt is fully dynamic
        has_prompt = bool(ai_prompt_text and ai_prompt_text.strip())
        logger.info(
            "[PROMPT_CONTEXT] business_id=%s, prompt_source=%s, has_hardcoded_templates=False, mode=compact",
            business_id, "ui" if has_prompt else "fallback"
        )
        
        # 🔥 PROMPT DEBUG: Log compact prompt
        logger.info(
            "[PROMPT_DEBUG] direction=%s business_id=%s compact_prompt(lead)=%s...",
            call_direction, business_id, final_prompt[:400].replace("\n", " ")
        )
        
        return final_prompt
        
    except Exception as e:
        logger.error(f"❌ [COMPACT] Compact prompt error: {e}")
        import traceback
        traceback.print_exc()
        return "You are a professional service rep. SPEAK HEBREW to customer. Be brief and helpful."


def build_realtime_system_prompt(business_id: int, db_session=None, call_direction: str = "inbound", use_cache: bool = True) -> str:
    """
    🔥 ROUTER: Routes to correct prompt builder based on call direction
    
    This function is the main entry point and routes to:
    - build_inbound_system_prompt() for inbound calls
    - build_outbound_system_prompt() for outbound calls
    
    🔥 GREETING OPTIMIZATION: Uses prompt cache to eliminate DB/prompt building latency
    
    Args:
        business_id: Business ID
        db_session: Optional SQLAlchemy session (for transaction safety)
        call_direction: "inbound" or "outbound" - determines which prompt to use
        use_cache: Whether to use prompt cache (default: True)
    
    Returns:
        Complete system prompt for the AI assistant
    """
    try:
        from server.models_sql import Business, BusinessSettings
        
        # 🔥 CACHE CHECK: Try to get cached prompt first
        # 🔥 FIX: Include direction in cache key to prevent inbound/outbound prompt mixing
        if use_cache:
            from server.services.prompt_cache import get_prompt_cache
            cache = get_prompt_cache()
            cached = cache.get(business_id, direction=call_direction)
            if cached:
                logger.info(f"✅ [PROMPT CACHE HIT] Returning cached prompt for business {business_id} ({call_direction})")
                return cached.system_prompt
        
        logger.info(f"🔥 [PROMPT ROUTER] Called for business_id={business_id}, direction={call_direction}")
        
        # Load business and settings
        try:
            if db_session:
                business = db_session.query(Business).get(business_id)
                settings = db_session.query(BusinessSettings).filter_by(tenant_id=business_id).first()
            else:
                business = Business.query.get(business_id)
                settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
        except Exception as db_error:
            logger.error(f"❌ DB error loading business {business_id}: {db_error}")
            return _get_fallback_prompt(business_id)
        
        if not business:
            logger.error(f"❌ CRITICAL: Business {business_id} not found!")
            raise ValueError(f"CRITICAL: Business {business_id} not found - cannot build prompt")
        
        business_name = business.name or "Business"
        
        # 🔥 BUSINESS ISOLATION: Log business context to track cross-contamination
        logger.info(f"📋 [ROUTER] Building prompt for {business_name} (business_id={business_id}, direction={call_direction})")
        logger.info(f"[BUSINESS_ISOLATION] prompt_request business_id={business_id} direction={call_direction}")
        
        # 🔥 PREPARE BUSINESS SETTINGS DICT
        business_settings_dict = {
            "id": business_id,
            "name": business_name,
            "ai_prompt": settings.ai_prompt if settings else "",
            "outbound_ai_prompt": settings.outbound_ai_prompt if settings else "",
            "greeting_message": business.greeting_message or ""
        }
        
        # 🔥 ROUTE TO CORRECT BUILDER
        final_prompt = None
        if call_direction == "outbound":
            # 🔥 OUTBOUND: Use pure prompt mode (no call control settings)
            logger.info(f"📤 [PROMPT_ROUTER] Building OUTBOUND prompt for business {business_id}")
            final_prompt = build_outbound_system_prompt(
                business_settings=business_settings_dict,
                db_session=db_session
            )
        else:
            # 🔥 INBOUND: Use full call control settings
            logger.info(f"📞 [PROMPT_ROUTER] Building INBOUND prompt for business {business_id}")
            call_control_settings_dict = {
                "enable_calendar_scheduling": settings.enable_calendar_scheduling if (settings and hasattr(settings, 'enable_calendar_scheduling')) else True,
                "auto_end_after_lead_capture": settings.auto_end_after_lead_capture if (settings and hasattr(settings, 'auto_end_after_lead_capture')) else False,
                "auto_end_on_goodbye": settings.auto_end_on_goodbye if (settings and hasattr(settings, 'auto_end_on_goodbye')) else False,
                "smart_hangup_enabled": settings.smart_hangup_enabled if (settings and hasattr(settings, 'smart_hangup_enabled')) else True,
                "silence_timeout_sec": settings.silence_timeout_sec if (settings and hasattr(settings, 'silence_timeout_sec')) else 15,
                "silence_max_warnings": settings.silence_max_warnings if (settings and hasattr(settings, 'silence_max_warnings')) else 2,
            }
            
            final_prompt = build_inbound_system_prompt(
                business_settings=business_settings_dict,
                call_control_settings=call_control_settings_dict,
                db_session=db_session
            )
        
        # 🔥 BUSINESS ISOLATION VERIFICATION: Ensure prompt contains correct business context
        if final_prompt and business_name:
            # Log verification - prompt should contain business-specific content
            logger.info(f"[BUSINESS_ISOLATION] prompt_built business_id={business_id} contains_business_name={business_name in final_prompt}")
        
        # 🔥 CACHE STORE: Save to cache for future use
        # 🔥 FIX: Include direction in cache key to prevent inbound/outbound prompt mixing
        if use_cache and final_prompt:
            from server.services.prompt_cache import get_prompt_cache
            cache = get_prompt_cache()
            greeting_text = business_settings_dict.get("greeting_message", "")
            cache.set(
                business_id=business_id,
                system_prompt=final_prompt,
                greeting_text=greeting_text,
                direction=call_direction,
                language_config={}  # Can be extended later
            )
            logger.info(f"💾 [PROMPT CACHE STORE] Cached prompt for business {business_id} ({call_direction})")
        
        return final_prompt
        
    except Exception as e:
        logger.error(f"❌ Error building Realtime prompt: {e}")
        import traceback
        traceback.print_exc()
        return _get_fallback_prompt(business_id)


def _get_fallback_prompt(business_id: Optional[int] = None) -> str:
    """Minimal fallback prompt - tries to use business settings first"""
    try:
        if business_id:
            from server.models_sql import Business, BusinessSettings
            business = Business.query.get(business_id)
            settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
            
            # Try to get prompt from settings
            if settings and settings.ai_prompt and settings.ai_prompt.strip():
                return settings.ai_prompt
            
            # Try business.system_prompt
            if business and business.system_prompt and business.system_prompt.strip():
                return business.system_prompt
            
            # 🔥 BUILD 324: English fallback with business name
            if business and business.name:
                return f"You are a rep for {business.name}. SPEAK HEBREW to customer. Be brief and helpful."
    except:
        pass
    
    # 🔥 BUILD 324: Absolute minimal English fallback
    return "You are a professional service rep. SPEAK HEBREW to customer. Be brief and helpful."


def _build_hours_description(policy) -> str:
    """Build opening hours description in English"""
    if policy.allow_24_7:
        return "Open 24/7"
    
    hours = policy.opening_hours
    if not hours:
        return "Hours not defined"
    
    day_names = {
        "sun": "Sun", "mon": "Mon", "tue": "Tue", "wed": "Wed",
        "thu": "Thu", "fri": "Fri", "sat": "Sat"
    }
    
    parts = []
    for day_key in ["sun", "mon", "tue", "wed", "thu", "fri", "sat"]:
        windows = hours.get(day_key, [])
        if windows:
            time_ranges = ",".join([f"{w[0]}-{w[1]}" for w in windows])
            parts.append(f"{day_names[day_key]}:{time_ranges}")
    
    return "Hours: " + " | ".join(parts) if parts else "Hours not set"


def _build_slot_description(slot_size_min: int) -> str:
    """Build slot size description in English"""
    return f"Every {slot_size_min}min"


def _build_critical_rules_compact(business_name: str, today_date: str, weekday_name: str, greeting_text: str = "", call_direction: str = "inbound", enable_calendar_scheduling: bool = True) -> str:
    """
    🔥 LEGACY FUNCTION - NO LONGER USED!
    This function is kept for backward compatibility only.
    All new code should use build_inbound_system_prompt() or build_outbound_system_prompt().
    
    🔥 BUILD 333: PHASE-BASED FLOW - prevents mid-confirmation and looping
    🔥 BUILD 327: STT AS SOURCE OF TRUTH - respond only to what customer actually said
    🔥 BUILD 324: ALL ENGLISH instructions - AI speaks Hebrew to customer
    """
    logger.warning("[PROMPT_DEBUG] Legacy prompt builder _build_critical_rules_compact() was called! This should not happen.")
    direction_context = "INBOUND" if call_direction == "inbound" else "OUTBOUND"
    
    # Greeting line
    if greeting_text and greeting_text.strip():
        greeting_line = f'- Use this greeting once at the start: "{greeting_text.strip()}"'
    else:
        greeting_line = "- Greet warmly and introduce yourself as the business rep"
    
    # 🔥 BUILD 340: CLEAR SCHEDULING RULES with STRICT FIELD ORDER
    if enable_calendar_scheduling:
        scheduling_section = """
APPOINTMENT BOOKING (STRICT ORDER!):
1. FIRST ask for NAME: "מה השם שלך?" - get name before anything else
2. THEN ask for DATE/TIME: "לאיזה יום ושעה?" - get preferred date and time
3. WAIT for system to check availability (don't promise!)
4. ONLY AFTER slot is confirmed → ask for PHONE: "מה הטלפון שלך לאישור?"
- Phone is collected LAST, only after appointment time is locked!
- Only say "התור נקבע" AFTER system confirms booking success
- If slot taken: offer alternatives (system will provide)
- NEVER ask for phone before confirming date/time availability!"""
    else:
        scheduling_section = """
NO SCHEDULING: Do NOT offer appointments. If customer asks, promise a callback from human rep."""
    
    # 🔥 BUILD 336: COMPACT + CLEAR SYSTEM RULES
    return f"""AI Rep for "{business_name}" | {direction_context} call | {weekday_name} {today_date}

LANGUAGE: All instructions are in English. SPEAK HEBREW to customer.

STT IS TRUTH: Trust transcription 100%. NEVER change, substitute, or "correct" any word.

CALL FLOW:
1. GREET: {greeting_line} Ask ONE open question about their need.
2. COLLECT: One question at a time. Mirror their EXACT words.
3. CLOSE: Once you have the service and location, say: "מצוין, קיבלתי. בעל מקצוע יחזור אליך בהקדם. תודה ולהתראות." Then stay quiet.
{scheduling_section}

STRICT RULES:
- Hebrew speech only
- BE PATIENT: Wait for customer to respond. Don't rush or repeat questions too quickly.
- No loops, no repeating questions unless answer was unclear
- NO confirmations or summaries - just collect info and close naturally
- After customer says goodbye → one farewell and stay quiet
- Don't ask for multiple pieces of information at once - ONE question at a time!
"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔥 NEW: PERFECT INBOUND & OUTBOUND SEPARATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def build_inbound_system_prompt(
    business_settings: Dict[str, Any],
    call_control_settings: Dict[str, Any],
    db_session=None
) -> str:
    """
    🔥 REFACTORED: Perfect Separation - System + Business Prompts
    
    STRUCTURE:
    1. Universal System Prompt (behavior only)
    2. Appointment Instructions (if enabled)
    3. Business Prompt (all content and flow)
    
    ✅ NO hardcoded flow
    ✅ NO hardcoded greetings
    ✅ NO domain-specific content in system layer
    
    Args:
        business_settings: Dict with business info (id, name, ai_prompt)
        call_control_settings: Dict with call control (enable_calendar_scheduling, call_goal)
        db_session: Optional SQLAlchemy session
    
    Returns:
        Complete system prompt for inbound calls (2000-3500 chars)
    """
    try:
        business_id = business_settings.get("id")
        business_name = business_settings.get("name", "Business")
        ai_prompt_raw = business_settings.get("ai_prompt", "")
        
        # Extract call control settings
        enable_calendar_scheduling = call_control_settings.get("enable_calendar_scheduling", False)
        call_goal = call_control_settings.get("call_goal", "lead_only")
        
        logger.info(f"📋 [INBOUND] Building prompt: {business_name} (scheduling={enable_calendar_scheduling}, goal={call_goal})")
        
        # LAYER 1: UNIVERSAL SYSTEM PROMPT (behavior only)
        system_rules = _build_universal_system_prompt()
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 🔥 LAYER 2: APPOINTMENT INSTRUCTIONS (dynamic, technical only)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        appointment_instructions = ""
        if call_goal == 'appointment' and enable_calendar_scheduling:
            from server.policy.business_policy import get_business_policy
            policy = get_business_policy(business_id, prompt_text=None, db_session=db_session)
            
            tz = pytz.timezone(policy.tz)
            today = datetime.now(tz)
            today_date = today.strftime("%d/%m/%Y")
            weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            weekday_name = weekday_names[today.weekday()]
            
            appointment_instructions = (
                f"\n\nAPPOINTMENT SCHEDULING (technical): Today is {weekday_name} {today_date}. "
                f"Slot size: {policy.slot_size_min}min. "
                "Collect: (1) customer name, (2) preferred date+time. "
                "Call schedule_appointment once after collecting both. "
                "Do not ask for phone (already in metadata). "
                "Only confirm booking if server returns success=true; otherwise offer alternatives."
            )
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 🔥 LAYER 3: BUSINESS PROMPT (all content and flow)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        # Parse business prompt (handle JSON format)
        business_prompt = ""
        if ai_prompt_raw and ai_prompt_raw.strip():
            try:
                if ai_prompt_raw.strip().startswith('{'):
                    prompt_obj = json.loads(ai_prompt_raw)
                    business_prompt = prompt_obj.get('calls') or prompt_obj.get('whatsapp') or ai_prompt_raw
                else:
                    business_prompt = ai_prompt_raw
            except json.JSONDecodeError:
                business_prompt = ai_prompt_raw
        
        # Replace placeholders
        if business_prompt:
            business_prompt = business_prompt.replace("{{business_name}}", business_name)
            business_prompt = business_prompt.replace("{{BUSINESS_NAME}}", business_name)
        else:
            # Minimal fallback (should never happen in production)
            business_prompt = f"You are a professional service representative for {business_name}. Be helpful and collect customer information."
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 🔥 COMBINE ALL LAYERS
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        full_prompt = (
            f"{system_rules}{appointment_instructions}\n\n"
            f"BUSINESS PROMPT (Business ID: {business_id}):\n{business_prompt}\n\n"
            "CALL TYPE: INBOUND. The customer called the business. Follow the business prompt for greeting and flow."
        )
        
        logger.info(f"✅ [INBOUND] Prompt built: {len(full_prompt)} chars (system + business)")
        logger.info(f"🔍 [PROMPT_VERIFICATION] business_id={business_id}, direction=INBOUND, call_type_in_prompt={'CALL TYPE: INBOUND' in full_prompt}")
        
        # 🔥 PROMPT_CONTEXT: Log that prompt is fully dynamic with no hardcoded templates
        has_business_prompt = bool(ai_prompt_raw and ai_prompt_raw.strip())
        logger.info(
            "[PROMPT_CONTEXT] business_id=%s, prompt_source=%s, has_hardcoded_templates=False",
            business_id, "ui" if has_business_prompt else "fallback"
        )
        
        # 🔥 PROMPT DEBUG: Log the actual prompt content (first 400 chars)
        logger.info(
            "[PROMPT_DEBUG] direction=inbound business_id=%s business_name=%s final_system_prompt(lead)=%s...",
            business_id, business_name, full_prompt[:400].replace("\n", " ")
        )
        
        return full_prompt
        
    except Exception as e:
        logger.error(f"❌ [INBOUND] Error: {e}")
        import traceback
        traceback.print_exc()
        return f"You are a professional assistant for {business_settings.get('name', 'the business')}. Speak Hebrew. Be helpful."


def build_outbound_system_prompt(
    business_settings: Dict[str, Any],
    db_session=None
) -> str:
    """
    🔥 REFACTORED: Perfect Separation - System + Outbound Business Prompt
    
    STRUCTURE:
    1. Universal System Prompt (behavior only)
    2. Outbound-specific note (identity reminder)
    3. Outbound Business Prompt (all content and flow)
    
    ✅ NO hardcoded flow
    ✅ NO hardcoded greetings
    ✅ NO domain-specific content in system layer
    
    Args:
        business_settings: Dict with business info (id, name, outbound_ai_prompt)
        db_session: Optional SQLAlchemy session
    
    Returns:
        Complete system prompt for outbound calls (2000-3500 chars)
    """
    try:
        business_id = business_settings.get("id")
        business_name = business_settings.get("name", "Business")
        outbound_prompt_raw = business_settings.get("outbound_ai_prompt", "")
        
        logger.info(f"📋 [OUTBOUND] Building prompt: {business_name} (id={business_id})")
        
        # LAYER 1: UNIVERSAL SYSTEM PROMPT (behavior only)
        system_rules = _build_universal_system_prompt()
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 🔥 LAYER 2: OUTBOUND-SPECIFIC CONTEXT (now integrated in final prompt)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 🔥 LAYER 3: OUTBOUND BUSINESS PROMPT (all content and flow)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        outbound_prompt = ""
        if outbound_prompt_raw and outbound_prompt_raw.strip():
            outbound_prompt = outbound_prompt_raw.strip()
            logger.info(f"✅ [OUTBOUND] Using outbound_ai_prompt ({len(outbound_prompt)} chars)")
        else:
            # Minimal fallback (should never happen in production)
            outbound_prompt = f"You are a professional outbound representative for {business_name}. Be brief, polite, and helpful."
            logger.warning(f"⚠️ [OUTBOUND] No outbound_ai_prompt - using fallback")
        
        # Replace placeholders
        outbound_prompt = outbound_prompt.replace("{{business_name}}", business_name)
        outbound_prompt = outbound_prompt.replace("{{BUSINESS_NAME}}", business_name)
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 🔥 COMBINE ALL LAYERS
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        full_prompt = (
            f"{system_rules}\n\n"
            f"BUSINESS PROMPT (Business ID: {business_id}):\n{outbound_prompt}\n\n"
            f'CALL TYPE: OUTBOUND from "{business_name}". If confused, briefly identify the business and continue per the outbound prompt.'
        )
        
        logger.info(f"✅ [OUTBOUND] Prompt built: {len(full_prompt)} chars (system + outbound)")
        logger.info(f"🔍 [PROMPT_VERIFICATION] business_id={business_id}, direction=OUTBOUND, call_type_in_prompt={'CALL TYPE: OUTBOUND' in full_prompt}")
        
        # 🔥 PROMPT_CONTEXT: Log that prompt is fully dynamic with no hardcoded templates
        has_outbound_prompt = bool(outbound_prompt_raw and outbound_prompt_raw.strip())
        logger.info(
            "[PROMPT_CONTEXT] business_id=%s, prompt_source=%s, has_hardcoded_templates=False",
            business_id, "ui" if has_outbound_prompt else "fallback"
        )
        
        # 🔥 PROMPT DEBUG: Log the actual prompt content (first 400 chars)
        logger.info(
            "[PROMPT_DEBUG] direction=outbound business_id=%s business_name=%s final_system_prompt(lead)=%s...",
            business_id, business_name, full_prompt[:400].replace("\n", " ")
        )
        
        return full_prompt
        
    except Exception as e:
        logger.error(f"❌ [OUTBOUND] Error: {e}")
        import traceback
        traceback.print_exc()
        return f"You are a professional representative for {business_settings.get('name', 'the business')}. Speak Hebrew. Be helpful."
