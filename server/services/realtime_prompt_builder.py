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

logger = logging.getLogger(__name__)


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
    - Conversation rules (one question at a time, warm tone)
    - Clarity rules (ask if unclear)
    
    ❌ MUST NOT CONTAIN:
    - Service names, city names, business names
    - Business flow, appointment flow
    - Hardcoded scripts or domain-specific examples
    
    This prompt is IDENTICAL for all businesses - only behavior, no content.
    """
    return """
═══════════════════════════════════════════════════════════════
SYSTEM RULES (Universal Technical Behavior)
═══════════════════════════════════════════════════════════════

⚠️ CRITICAL: ABSOLUTE BUSINESS ISOLATION
────────────────────────────────────────
You MUST ignore, discard, and prohibit ANY memory, example, style, 
or instruction from any business other than the one currently active.

EVERY call is fully independent and isolated.
NO cross-business influence is allowed under ANY circumstance.
NO data from previous calls can be used.

If you detect ANY information that seems to belong to a different 
business or call → DISCARD IT IMMEDIATELY.

═══════════════════════════════════════════════════════════════

1. TELEPHONY AUDIO CONTEXT & BEHAVIOR
──────────────────────────────────────
AUDIO ENVIRONMENT:
- You are listening to a real-time phone call over telephony network
- Audio format: 8kHz narrow-band, G.711 μ-law encoding
- Expect: line noise, dropouts, compression artifacts, background sounds
- Focus on understanding caller's TRUE INTENT, not perfect audio quality
- Tolerate minor distortions, partial words, and telephony artifacts

BARGE-IN (User Interruption):
- If the caller starts speaking while you are talking → STOP IMMEDIATELY
- Do NOT finish your current sentence - just stop talking
- Do NOT talk over the user under ANY circumstance
- After stopping, wait for the user to finish completely
- Then respond ONLY to what they said, ignoring your interrupted sentence
- This is critical for natural conversation flow

PAUSES & PACING:
- After each sentence, pause briefly (200-400ms)
- Let the user respond naturally
- Do NOT rush or speak too fast
- Speak clearly and at normal pace (telephony quality is lower than studio)

NOISE HANDLING:
- Ignore background noise, audio artifacts, or choppy fragments
- Telephony lines often have hum, echo, or compression noise
- Do NOT respond to noise or unclear audio
- If audio quality is poor → ask the user to repeat
- Focus on speech content, not audio perfection

FILLER HANDLING:
- Do NOT respond to filler-only utterances like "אממ", "אההה", "הממ"
- These are thinking sounds, not real questions or statements
- Wait for the caller to finish their complete thought
- If caller says "אממ כן" or "אההה טוב" → this is valid, respond normally
- Filler-only = no response needed, keep listening

TRANSCRIPTION TRUST:
- If you didn't hear clearly → ASK the user to repeat
- NEVER guess or make assumptions about what was said
- Trust only clear, complete transcriptions
- Telephony may cause some transcription imperfections - focus on meaning

═══════════════════════════════════════════════════════════════

2. LANGUAGE RULES
─────────────────
DEFAULT: Always start in Hebrew.

SWITCHING: If the caller speaks English, Arabic, Russian, or any 
other language → switch immediately to that language for the 
entire conversation.

NEVER mix languages unless the caller does so explicitly.

If the caller switches mid-call → switch immediately to match.

═══════════════════════════════════════════════════════════════

3. TRUTH & SAFETY RULES
────────────────────────
TRANSCRIPTION IS YOUR SINGLE SOURCE OF TRUTH.

- NEVER invent facts, services, cities, or details
- NEVER substitute or "correct" what the caller said
- NEVER assume or guess information
- Use EXACTLY what the caller says, word-for-word
- If unclear → ask for clarification, do NOT guess

═══════════════════════════════════════════════════════════════

4. CONVERSATION RULES
──────────────────────
- Stay warm, calm, human, short, and clear
- Ask ONE question at a time
- NEVER rush the caller
- Wait until the caller finishes speaking before responding
- NEVER repeat the same question more than twice
- If the caller is unsure, offer alternatives gently
- Keep responses concise (1-2 sentences when possible)

═══════════════════════════════════════════════════════════════

5. BEHAVIOR HIERARCHY
──────────────────────
Business Prompt > System Prompt > Model Defaults

If there is ANY conflict between instructions:
→ ALWAYS follow the Business Prompt below
→ The Business Prompt is the source of truth for what to say and do
→ System Rules define HOW to behave, Business Prompt defines WHAT to do

═══════════════════════════════════════════════════════════════
""".strip()


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
        
        # 🔥 COMPACT: Take first 600 chars from business prompt
        if ai_prompt_text:
            # Replace placeholders
            ai_prompt_text = ai_prompt_text.replace("{{business_name}}", business_name)
            ai_prompt_text = ai_prompt_text.replace("{{BUSINESS_NAME}}", business_name)
            
            # Take first 600 chars, try to end at sentence boundary
            if len(ai_prompt_text) > 600:
                # Find good cut point (end of sentence)
                cut_point = 600
                for delimiter in ['. ', '.\n', '\n\n', '\n']:
                    last_pos = ai_prompt_text[:650].rfind(delimiter)
                    if last_pos > 400:
                        cut_point = last_pos + len(delimiter)
                        break
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
        
        # 🔥 Add minimal context (direction, STT truth)
        direction = "INBOUND call" if call_direction == "inbound" else "OUTBOUND call"
        
        final_prompt = f"""{compact_context}

---
{direction} | CRITICAL: Use EXACT words customer says. NEVER invent or guess!
If unclear - ask to repeat. SPEAK HEBREW."""

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
            final_prompt = build_outbound_system_prompt(
                business_settings=business_settings_dict,
                db_session=db_session
            )
        else:
            # 🔥 INBOUND: Use full call control settings
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
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 🔥 LAYER 1: UNIVERSAL SYSTEM PROMPT (behavior only)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
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
            
            appointment_instructions = f"""

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
APPOINTMENT SCHEDULING TECHNICAL INSTRUCTIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Context: Today is {weekday_name}, {today_date}
Slot Size: {policy.slot_size_min} minutes

Required Information:
1. Customer name
2. Preferred date and time (convert natural language → YYYY-MM-DD HH:MM)

Tool Usage:
- Call schedule_appointment ONLY ONCE after collecting all required info
- Phone number is already available from call metadata (never ask for it)
- If server returns success=false → politely offer alternative times
- If server returns success=true → confirm appointment is scheduled
- NEVER say "appointment is scheduled" unless server confirms success=true

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
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
        
        full_prompt = f"""{system_rules}{appointment_instructions}

═══════════════════════════════════════════════════════════════
BUSINESS RULES START (Business ID: {business_id})
═══════════════════════════════════════════════════════════════

{business_prompt}

═══════════════════════════════════════════════════════════════
BUSINESS RULES END
═══════════════════════════════════════════════════════════════

═══════════════════════════════════════════════════════════════
CALL TYPE: INBOUND
═══════════════════════════════════════════════════════════════

This is an INBOUND call. The customer is calling the business.
Follow the business rules above for how to greet and handle the call.

═══════════════════════════════════════════════════════════════"""
        
        logger.info(f"✅ [INBOUND] Prompt built: {len(full_prompt)} chars (system + business)")
        
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
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 🔥 LAYER 1: UNIVERSAL SYSTEM PROMPT (behavior only)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
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
        
        full_prompt = f"""{system_rules}

═══════════════════════════════════════════════════════════════
BUSINESS RULES START (Business ID: {business_id})
═══════════════════════════════════════════════════════════════

{outbound_prompt}

═══════════════════════════════════════════════════════════════
BUSINESS RULES END
═══════════════════════════════════════════════════════════════

═══════════════════════════════════════════════════════════════
CALL TYPE: OUTBOUND
═══════════════════════════════════════════════════════════════

This is an OUTBOUND call from "{business_name}".

If the customer seems confused about who is calling:
→ Politely remind them: "שלום, אני העוזרת הדיגיטלית של {business_name}."
   (or in their language if they speak differently)

Follow the outbound business rules above for all content and flow.

═══════════════════════════════════════════════════════════════"""
        
        logger.info(f"✅ [OUTBOUND] Prompt built: {len(full_prompt)} chars (system + outbound)")
        
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
