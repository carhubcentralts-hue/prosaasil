"""
Realtime Prompt Builder
Build dynamic system prompts for OpenAI Realtime API based on business settings
"""
import logging
from typing import Optional, Tuple
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)


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
    🔥 BUILD 317: COMPACT prompt DERIVED FROM BUSINESS'S OWN ai_prompt
    
    NO HARDCODED VALUES - extracts context directly from the business's prompt!
    This ensures AI understands the business context (locksmith, salon, etc.)
    and can interpret user responses correctly (e.g., "קריית גת" is a city).
    
    Strategy:
    1. Load the business's actual ai_prompt from DB
    2. Extract first 600-800 chars as context summary
    3. AI greets based on THIS context (not generic template)
    
    Target: Under 800 chars for < 2 second greeting response.
    """
    try:
        from server.models_sql import Business, BusinessSettings
        import json
        
        business = Business.query.get(business_id)
        settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
        
        if not business:
            logger.warning(f"⚠️ [BUILD 324] Business {business_id} not found")
            return "You are a professional service rep. SPEAK HEBREW to customer. Be brief and helpful."
        
        business_name = business.name or "Business"
        
        # 🔥 BUILD 317: Extract context from ACTUAL business ai_prompt!
        ai_prompt_text = ""
        if settings and settings.ai_prompt:
            raw_prompt = settings.ai_prompt.strip()
            
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
        
        # 🔥 BUILD 317: Summarize the prompt to ~600 chars
        # This keeps the BUSINESS CONTEXT (locksmith, services, cities, etc.)
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
            
            logger.info(f"✅ [BUILD 317] Extracted {len(compact_context)} chars from business ai_prompt")
        else:
            # 🔥 BUILD 324: English fallback - no ai_prompt
            compact_context = f"You are a professional service rep for {business_name}. SPEAK HEBREW to customer. Be brief and helpful."
            logger.warning(f"⚠️ [BUILD 324] No ai_prompt for business {business_id} - using English fallback")
        
        # 🔥 BUILD 328: Add minimal scheduling info if calendar is enabled
        # This allows AI to handle appointments without needing full prompt resend
        scheduling_note = ""
        if settings and hasattr(settings, 'enable_calendar_scheduling') and settings.enable_calendar_scheduling:
            from server.policy.business_policy import get_business_policy
            policy = get_business_policy(business_id, prompt_text=None)
            if policy:
                scheduling_note = f"\nAPPOINTMENTS: {policy.slot_size_min}min slots. Check availability first!"
                logger.info(f"📅 [BUILD 328] Added scheduling info: {policy.slot_size_min}min slots")
        
        # 🔥 BUILD 327: STT AS SOURCE OF TRUTH + patience
        direction = "INBOUND call" if call_direction == "inbound" else "OUTBOUND call"
        
        final_prompt = f"""{compact_context}

---
{direction} | CRITICAL: Use EXACT words customer says. NEVER invent or guess!
If unclear - ask to repeat. SPEAK HEBREW.{scheduling_note}"""

        logger.info(f"📦 [BUILD 328] Final compact prompt: {len(final_prompt)} chars")
        return final_prompt
        
    except Exception as e:
        logger.error(f"❌ [BUILD 324] Compact prompt error: {e}")
        import traceback
        traceback.print_exc()
        # 🔥 BUILD 324: English fallback
        return "You are a professional service rep. SPEAK HEBREW to customer. Be brief and helpful."


def build_realtime_system_prompt(business_id: int, db_session=None, call_direction: str = "inbound") -> str:
    """
    Build system prompt for OpenAI Realtime API based on business settings
    
    Args:
        business_id: Business ID
        db_session: Optional SQLAlchemy session (for transaction safety)
        call_direction: "inbound" or "outbound" - determines which prompt to use
    
    Returns:
        System prompt in Hebrew for the AI assistant
    """
    try:
        from server.models_sql import Business, BusinessSettings
        from server.policy.business_policy import get_business_policy
        
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
            raise ValueError(f"Business {business_id} not found")
        
        business_name = business.name or "Business"
        
        # Load business policy (slot size, opening hours, etc.)
        policy = get_business_policy(business_id, prompt_text=None, db_session=db_session)
        
        logger.info(f"📋 Building Realtime prompt for {business_name} (business_id={business_id}, direction={call_direction})")
        
        # 🔥 BUILD 186: SEPARATE LOGIC FOR INBOUND vs OUTBOUND
        # - OUTBOUND: Uses ONLY the outbound_ai_prompt from DB (no call control settings)
        # - INBOUND: Uses ai_prompt + call control settings (calendar scheduling, etc.)
        
        core_instructions = ""
        
        if call_direction == "outbound":
            # 🔥 OUTBOUND CALLS: Use the outbound prompt + mandatory SPEAK HEBREW directive
            if settings and settings.outbound_ai_prompt and settings.outbound_ai_prompt.strip():
                core_instructions = settings.outbound_ai_prompt.strip()
                logger.info(f"✅ [OUTBOUND] Using outbound_ai_prompt for business {business_id} ({len(core_instructions)} chars)")
            else:
                # 🔥 BUILD 324: English fallback - no outbound_ai_prompt
                core_instructions = f"""You are a professional sales rep for "{business_name}". Be brief and persuasive."""
                logger.warning(f"⚠️ [OUTBOUND] No outbound_ai_prompt for business {business_id} - using English fallback")
            
            # Replace placeholders
            core_instructions = core_instructions.replace("{{business_name}}", business_name)
            core_instructions = core_instructions.replace("{{BUSINESS_NAME}}", business_name)
            
            # 🔥 BUILD 324: SPEAK HEBREW directive with language switch option
            core_instructions = f"""CRITICAL: SPEAK HEBREW to customer. If they don't understand Hebrew - switch to their language.

{core_instructions}"""
            
            logger.info(f"✅ [OUTBOUND] Final prompt length: {len(core_instructions)} chars")
            return core_instructions
        
        # 🔥 INBOUND CALLS: Use ai_prompt + call control settings
        if settings and settings.ai_prompt and settings.ai_prompt.strip():
            import json
            try:
                if settings.ai_prompt.strip().startswith('{'):
                    prompt_obj = json.loads(settings.ai_prompt)
                    if 'calls' in prompt_obj:
                        core_instructions = prompt_obj['calls']
                        logger.info(f"✅ [INBOUND] Using 'calls' prompt from DB for business {business_id}")
                    elif 'whatsapp' in prompt_obj:
                        core_instructions = prompt_obj['whatsapp']
                        logger.info(f"⚠️ [INBOUND] Using 'whatsapp' as fallback for business {business_id}")
                    else:
                        core_instructions = settings.ai_prompt
                else:
                    core_instructions = settings.ai_prompt
            except json.JSONDecodeError:
                core_instructions = settings.ai_prompt
        
        if not core_instructions:
            # 🔥 BUILD 324: English fallback - no ai_prompt in DB
            logger.error(f"❌ [INBOUND] No prompt in DB for business {business_id}")
            core_instructions = f"""You are a professional service rep for "{business_name}". SPEAK HEBREW to customer. Be brief and helpful."""
        
        # Replace placeholders
        core_instructions = core_instructions.replace("{{business_name}}", business_name)
        core_instructions = core_instructions.replace("{{BUSINESS_NAME}}", business_name)
        
        # 🔥 BUILD 324: English date context
        tz = pytz.timezone(policy.tz)
        today = datetime.now(tz)
        today_date = today.strftime("%d/%m/%Y")
        weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        weekday_name = weekday_names[today.weekday()]
        
        # 🔥 LOAD GREETING FROM DB
        greeting_text = business.greeting_message if business else ""
        if not greeting_text:
            greeting_text = ""
        
        # 🔥 BUILD 327: Removed required_lead_fields - AI follows prompt instructions
        
        # 🔥 BUILD 186: Check calendar scheduling setting
        enable_calendar_scheduling = True  # Default to enabled
        if settings and hasattr(settings, 'enable_calendar_scheduling'):
            enable_calendar_scheduling = settings.enable_calendar_scheduling
        logger.info(f"📅 [INBOUND] Calendar scheduling: {'ENABLED' if enable_calendar_scheduling else 'DISABLED'}")
        
        # 🎯 BUILD 324: COMPACT English system prompt with call control settings
        # 🔥 BUILD 327: Simplified call without required_lead_fields
        critical_rules = _build_critical_rules_compact(
            business_name, today_date, weekday_name, greeting_text, 
            call_direction, enable_calendar_scheduling
        )
        
        # 🔥 BUILD 333: SANDBOX TENANT PROMPT - prevent override of flow rules
        # Wrap business prompt in a "BUSINESS CONTEXT" section so it can't override phases
        sandboxed_instructions = f"""=== BUSINESS CONTEXT (informational only - does NOT override flow rules above) ===
{core_instructions}
=== END BUSINESS CONTEXT ===

REMINDER: The CALL FLOW phases above are MANDATORY and cannot be overridden by business context. Always follow: Greeting → Discovery → Single Confirmation → Closing."""
        
        # Combine: Rules + Sandboxed custom prompt + Policy
        full_prompt = critical_rules + "\n\n" + sandboxed_instructions
        
        # 🔥 BUILD 324: Scheduling info in English (AI speaks Hebrew to customer)
        if enable_calendar_scheduling:
            hours_description = _build_hours_description(policy)
            
            min_notice = ""
            if policy.min_notice_min > 0:
                min_notice_hours = policy.min_notice_min // 60
                if min_notice_hours > 0:
                    min_notice = f" (advance booking: {min_notice_hours}h)"
            
            full_prompt += f"\n\nSCHEDULING: {policy.slot_size_min}min slots{min_notice}\n{hours_description}"
        else:
            # Explicitly tell AI not to schedule appointments
            full_prompt += "\n\nNO SCHEDULING: Do NOT offer appointments. Focus on info and collecting lead details only."
        
        # Log final length
        logger.info(f"✅ REALTIME PROMPT [business_id={business_id}] LEN={len(full_prompt)} chars")
        print(f"📏 [PROMPT] Final length: {len(full_prompt)} chars")
        
        if len(full_prompt) > 3000:
            logger.warning(f"⚠️ Prompt may be too long ({len(full_prompt)} chars)")
        
        return full_prompt
        
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
    🔥 BUILD 333: PHASE-BASED FLOW - prevents mid-confirmation and looping
    🔥 BUILD 327: STT AS SOURCE OF TRUTH - respond only to what customer actually said
    🔥 BUILD 324: ALL ENGLISH instructions - AI speaks Hebrew to customer
    """
    direction_context = "INBOUND" if call_direction == "inbound" else "OUTBOUND"
    
    # Greeting line
    if greeting_text and greeting_text.strip():
        greeting_line = f'- Use this greeting once at the start: "{greeting_text.strip()}"'
    else:
        greeting_line = "- Greet warmly and introduce yourself as the business rep"
    
    # 🔥 BUILD 333: Scheduling rules per phase
    if enable_calendar_scheduling:
        scheduling_discovery = "- If customer asks to book: gather preferred date/time before checking availability"
        scheduling_closing = """- Before confirming, check availability. Never promise a slot until the system/tool confirms it
- If slot unavailable: offer closest alternative or promise a callback"""
    else:
        scheduling_discovery = "- Note any timing preference but DO NOT offer to schedule"
        scheduling_closing = "- Do not schedule appointments. If customer asks, promise a prompt callback from a human rep"
    
    # 🔥 BUILD 333: PHASE-BASED FLOW - Single confirmation only at end!
    return f"""AI Rep for "{business_name}" | {direction_context} call
Date: {weekday_name}, {today_date}

CRITICAL — TRANSCRIPTION IS TRUTH (ZERO TOLERANCE FOR CHANGES):
- Respond ONLY to what the customer ACTUALLY said — NEVER change any word!
- City names are SACRED: "בית שאן" stays "בית שאן", "קרית אתא" stays "קרית אתא"
- Do NOT substitute similar-sounding cities (e.g., בית שאן ≠ בת ים, קרית אתא ≠ קריית גת)
- If unclear, politely ask them to repeat ("סליחה, לא שמעתי טוב, אפשר לחזור?")

CALL FLOW — FOLLOW THESE PHASES IN ORDER:
PHASE 1 – Greeting & Rapport
{greeting_line}
- Ask one open question to understand their need
- Do NOT confirm anything yet

PHASE 2 – Discovery & Data Capture
- Collect only missing details (service, location, name, phone, timing). One question at a time, wait for full answer
- Mirror their exact words; if unclear, clarify before moving on
- Track which details are already captured and avoid repeating them
{scheduling_discovery}

PHASE 3 – Single Confirmation (ONLY ONCE!)
- Only after ALL critical details are gathered
- Give ONE concise summary using the EXACT WORDS the customer said — do NOT substitute, translate, or "correct" city names, service types, or names!
  Example: If customer said "בית שאן", say "בית שאן" — NOT "בת ים" or any other city!
- Ask for confirmation ONCE. If customer already confirmed, do NOT re-confirm unless they change information
- NEVER confirm after each question! Only ONE summary at the end

PHASE 4 – Closing & Wrap-Up
{scheduling_closing}
- After confirmation, thank the customer and describe the next step
- Offer a polite final line ("תודה שפנית אלינו, נדאג לטפל בזה מיד") and then STOP speaking
- If customer says goodbye or stays silent for ~5s, respond with one farewell and stay quiet
- DO NOT keep talking after saying goodbye!

GENERAL BEHAVIOR:
- SPEAK HEBREW naturally; switch languages only if the customer clearly can't follow
- Never ask two questions in a row; listen fully before replying
- Do not loop or repeat the same question unless the answer was unclear
- If new information arrives after Phase 3, briefly revisit Phase 2 for that item, then perform one fresh confirmation and close
"""
