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
            final_greeting = (
                greeting.strip()
                .replace("{{business_name}}", business_name)
                .replace("{{BUSINESS_NAME}}", business_name)
            )
            logger.info(
                f"✅ [GREETING] Loaded from DB for business {business_id}: "
                f"'{final_greeting[:50]}...'"
            )
            return (final_greeting, business_name)
        else:
            logger.warning(
                f"⚠️ No greeting in DB for business {business_id} - AI will greet naturally"
            )
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
    2. Extract first ~600 chars as context summary
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
            return (
                "You are a professional service rep. SPEAK HEBREW to customer by default. "
                "If they clearly do not understand Hebrew, switch to their language. "
                "Be brief and helpful."
            )
        
        business_name = business.name or "Business"
        
        # 🔥 BUILD 317: Extract context from ACTUAL business ai_prompt!
        ai_prompt_text = ""
        if settings and settings.ai_prompt:
            raw_prompt = settings.ai_prompt.strip()
            
            # Handle JSON format (with 'calls' key)
            if raw_prompt.startswith("{"):
                try:
                    prompt_obj = json.loads(raw_prompt)
                    if "calls" in prompt_obj:
                        ai_prompt_text = prompt_obj["calls"]
                    elif "whatsapp" in prompt_obj:
                        ai_prompt_text = prompt_obj["whatsapp"]
                    else:
                        ai_prompt_text = raw_prompt
                except json.JSONDecodeError:
                    ai_prompt_text = raw_prompt
            else:
                ai_prompt_text = raw_prompt
        
        # 🔥 BUILD 317: Summarize the prompt to ~600 chars
        # This keeps the BUSINESS CONTEXT (services, style, constraints, etc.)
        if ai_prompt_text:
            # Replace placeholders
            ai_prompt_text = ai_prompt_text.replace("{{business_name}}", business_name)
            ai_prompt_text = ai_prompt_text.replace("{{BUSINESS_NAME}}", business_name)
            
            if len(ai_prompt_text) > 600:
                # Find good cut point (end of sentence)
                cut_point = 600
                for delimiter in [". ", ".\n", "\n\n", "\n"]:
                    last_pos = ai_prompt_text[:650].rfind(delimiter)
                    if last_pos > 400:
                        cut_point = last_pos + len(delimiter)
                        break
                compact_context = ai_prompt_text[:cut_point].strip()
            else:
                compact_context = ai_prompt_text.strip()
            
            logger.info(
                f"✅ [BUILD 317] Extracted {len(compact_context)} chars "
                f"from business ai_prompt"
            )
        else:
            # 🔥 BUILD 324: English fallback - no ai_prompt
            compact_context = (
                f"You are a professional service rep for {business_name}. "
                "SPEAK HEBREW to customer by default. If they clearly do not "
                "understand Hebrew, switch to their language. Be brief and helpful."
            )
            logger.warning(
                f"⚠️ [BUILD 324] No ai_prompt for business {business_id} - using English fallback"
            )
        
        # 🔥 BUILD 328: Add minimal scheduling info if calendar is enabled
        scheduling_note = ""
        if settings and hasattr(settings, "enable_calendar_scheduling") and settings.enable_calendar_scheduling:
            from server.policy.business_policy import get_business_policy
            policy = get_business_policy(business_id, prompt_text=None)
            if policy:
                scheduling_note = (
                    f"\nAPPOINTMENTS: {policy.slot_size_min}min slots. "
                    "Follow the business prompt for how to book; "
                    "never invent availability."
                )
                logger.info(
                    f"📅 [BUILD 328] Added scheduling info: {policy.slot_size_min}min slots"
                )
        
        # 🔥 BUILD 327: STT AS SOURCE OF TRUTH + patience
        direction = "INBOUND call" if call_direction == "inbound" else "OUTBOUND call"
        
        final_prompt = (
            f"{compact_context}\n\n"
            f"---\n"
            f"{direction} | CRITICAL: Use EXACT words customer says. NEVER invent or guess!\n"
            f"If unclear - ask to repeat.\n"
            f"SPEAK HEBREW by default. If the caller clearly does not understand Hebrew "
            f"(or explicitly says so), switch to their language and continue with the same logic."
            f"{scheduling_note}"
        )

        logger.info(
            f"📦 [BUILD 328] Final compact prompt: {len(final_prompt)} chars"
        )
        return final_prompt
        
    except Exception as e:
        logger.error(f"❌ [BUILD 324] Compact prompt error: {e}")
        import traceback
        traceback.print_exc()
        # 🔥 BUILD 324: English fallback
        return (
            "You are a professional service rep. SPEAK HEBREW to customer by default. "
            "If they clearly do not understand Hebrew, switch to their language. "
            "Be brief and helpful."
        )


def build_realtime_system_prompt(
    business_id: int,
    db_session=None,
    call_direction: str = "inbound"
) -> str:
    """
    Build system prompt for OpenAI Realtime API based on business settings
    
    Args:
        business_id: Business ID
        db_session: Optional SQLAlchemy session (for transaction safety)
        call_direction: "inbound" or "outbound" - determines which prompt to use
    
    Returns:
        System prompt (system instructions) for the AI assistant
    """
    try:
        from server.models_sql import Business, BusinessSettings
        from server.policy.business_policy import get_business_policy
        
        # Load business and settings
        try:
            if db_session:
                business = db_session.query(Business).get(business_id)
                settings = (
                    db_session.query(BusinessSettings)
                    .filter_by(tenant_id=business_id)
                    .first()
                )
            else:
                business = Business.query.get(business_id)
                settings = BusinessSettings.query.filter_by(
                    tenant_id=business_id
                ).first()
        except Exception as db_error:
            logger.error(
                f"❌ DB error loading business {business_id}: {db_error}"
            )
            return _get_fallback_prompt(business_id)
        
        if not business:
            raise ValueError(f"Business {business_id} not found")
        
        business_name = business.name or "Business"
        
        # Load business policy (slot size, opening hours, etc.)
        policy = get_business_policy(
            business_id,
            prompt_text=None,
            db_session=db_session
        )
        
        logger.info(
            f"📋 Building Realtime prompt for {business_name} "
            f"(business_id={business_id}, direction={call_direction})"
        )
        
        core_instructions = ""
        
        # 🔥 BUILD 186: SEPARATE LOGIC FOR INBOUND vs OUTBOUND
        if call_direction == "outbound":
            # OUTBOUND CALLS: Use the outbound prompt + mandatory language directive
            if settings and settings.outbound_ai_prompt and settings.outbound_ai_prompt.strip():
                core_instructions = settings.outbound_ai_prompt.strip()
                logger.info(
                    f"✅ [OUTBOUND] Using outbound_ai_prompt for business {business_id} "
                    f"({len(core_instructions)} chars)"
                )
            else:
                # English fallback - no outbound_ai_prompt
                core_instructions = (
                    f'You are a professional sales rep for "{business_name}". '
                    f"Be brief and persuasive."
                )
                logger.warning(
                    f"⚠️ [OUTBOUND] No outbound_ai_prompt for business {business_id} "
                    f"- using English fallback"
                )
            
            # Replace placeholders
            core_instructions = core_instructions.replace(
                "{{business_name}}", business_name
            )
            core_instructions = core_instructions.replace(
                "{{BUSINESS_NAME}}", business_name
            )
            
            # Language rule: Hebrew by default, switch if caller explicitly asks
            language_preamble = (
                "CRITICAL: SPEAK HEBREW to the customer.\n"
                "If the caller clearly says they do not understand Hebrew (for example: \"אני לא מבין עברית\", "
                "\"speak English\", \"רוסית בבקשה\"), detect that language and continue the call in it while following "
                "the same business rules."
            )
            core_instructions = f"{language_preamble}\n\n{core_instructions}"
            
            logger.info(
                f"✅ [OUTBOUND] Final prompt length: {len(core_instructions)} chars"
            )
            return core_instructions
        
        # 🔥 INBOUND CALLS: Use ai_prompt + call control settings
        from json import JSONDecodeError
        import json
        
        if settings and settings.ai_prompt and settings.ai_prompt.strip():
            try:
                if settings.ai_prompt.strip().startswith("{"):
                    prompt_obj = json.loads(settings.ai_prompt)
                    if "calls" in prompt_obj:
                        core_instructions = prompt_obj["calls"]
                        logger.info(
                            f"✅ [INBOUND] Using 'calls' prompt from DB for business {business_id}"
                        )
                    elif "whatsapp" in prompt_obj:
                        core_instructions = prompt_obj["whatsapp"]
                        logger.info(
                            f"⚠️ [INBOUND] Using 'whatsapp' as fallback for business {business_id}"
                        )
                    else:
                        core_instructions = settings.ai_prompt
                else:
                    core_instructions = settings.ai_prompt
            except JSONDecodeError:
                core_instructions = settings.ai_prompt
        
        if not core_instructions:
            # English fallback - no ai_prompt in DB
            logger.error(
                f"❌ [INBOUND] No prompt in DB for business {business_id}"
            )
            core_instructions = (
                f'You are a professional service rep for "{business_name}". '
                f"SPEAK HEBREW to customer by default. If they clearly do not "
                f"understand Hebrew, switch to their language. Be brief and helpful."
            )
        
        # Replace placeholders
        core_instructions = core_instructions.replace(
            "{{business_name}}", business_name
        )
        core_instructions = core_instructions.replace(
            "{{BUSINESS_NAME}}", business_name
        )
        
        # English date context
        tz = pytz.timezone(policy.tz)
        today = datetime.now(tz)
        today_date = today.strftime("%d/%m/%Y")
        weekday_names = [
            "Monday", "Tuesday", "Wednesday", "Thursday",
            "Friday", "Saturday", "Sunday"
        ]
        weekday_name = weekday_names[today.weekday()]
        
        # LOAD GREETING FROM DB (may be used for inbound rules)
        greeting_text = business.greeting_message if business else ""
        if not greeting_text:
            greeting_text = ""
        
        # Check calendar scheduling setting
        enable_calendar_scheduling = True  # Default to enabled
        if settings and hasattr(settings, "enable_calendar_scheduling"):
            enable_calendar_scheduling = settings.enable_calendar_scheduling
        logger.info(
            f"📅 [INBOUND] Calendar scheduling: "
            f"{'ENABLED' if enable_calendar_scheduling else 'DISABLED'}"
        )
        
        # Build compact, generic rules (language, flow, STT, etc.)
        critical_rules = _build_critical_rules_compact(
            business_name,
            today_date,
            weekday_name,
            greeting_text,
            call_direction,
            enable_calendar_scheduling,
            policy=policy,
        )
        
        # Business prompt is sandboxed but not truncated
        sandboxed_instructions = (
            "--- BUSINESS PROMPT (follow the FLOW rules above) ---\n"
            f"{core_instructions}\n"
            "--- END BUSINESS PROMPT ---"
        )
        
        # Combine: Rules + Sandboxed business prompt + scheduling meta
        full_prompt = critical_rules + "\n" + sandboxed_instructions
        
        # Additional scheduling meta info (for the model, not spoken)
        if enable_calendar_scheduling:
            hours_description = _build_hours_description(policy)
            
            min_notice = ""
            if getattr(policy, "min_notice_min", 0) > 0:
                min_notice_hours = policy.min_notice_min // 60
                if min_notice_hours > 0:
                    min_notice = f" (advance booking: {min_notice_hours}h)"
            
            full_prompt += (
                f"\n\nSCHEDULING META (NOT SPOKEN): "
                f"{policy.slot_size_min}min slots{min_notice}\n"
                f"{hours_description}"
            )
        else:
            full_prompt += (
                "\n\nNO SCHEDULING META: Do NOT offer appointments from your side. "
                "If customer asks to schedule – follow the business prompt. "
                "If it doesn't say how to schedule, promise a callback only."
            )
        
        # Log final length
        logger.info(
            f"✅ REALTIME PROMPT [business_id={business_id}] LEN={len(full_prompt)} chars"
        )
        print(f"📏 [PROMPT] Final length: {len(full_prompt)} chars")
        
        if len(full_prompt) > 3000:
            logger.warning(
                f"⚠️ Prompt may be too long ({len(full_prompt)} chars)"
            )
        
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
            settings = BusinessSettings.query.filter_by(
                tenant_id=business_id
            ).first()
            
            # Try to get prompt from settings
            if settings and settings.ai_prompt and settings.ai_prompt.strip():
                return settings.ai_prompt
            
            # Try business.system_prompt
            if business and business.system_prompt and business.system_prompt.strip():
                return business.system_prompt
            
            # Fallback with business name
            if business and business.name:
                return (
                    f"You are a rep for {business.name}. "
                    f"SPEAK HEBREW to customer by default. "
                    f"If they clearly do not understand Hebrew, "
                    f"switch to their language. Be brief and helpful."
                )
    except Exception:
        pass
    
    # Absolute minimal fallback
    return (
        "You are a professional service rep. "
        "SPEAK HEBREW to customer by default. "
        "If they clearly do not understand Hebrew, "
        "switch to their language. Be brief and helpful."
    )


def _build_hours_description(policy) -> str:
    """Build opening hours description in English"""
    if getattr(policy, "allow_24_7", False):
        return "Hours: Open 24/7"
    
    hours = getattr(policy, "opening_hours", None)
    if not hours:
        return "Hours: not defined"
    
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
    
    return "Hours: " + " | ".join(parts) if parts else "Hours: not set"


def _build_slot_description(slot_size_min: int) -> str:
    """Build slot size description in English"""
    return f"Every {slot_size_min}min"


def _build_critical_rules_compact(
    business_name: str,
    today_date: str,
    weekday_name: str,
    greeting_text: str = "",
    call_direction: str = "inbound",
    enable_calendar_scheduling: bool = True,
    policy=None,
) -> str:
    """
    Compact system rules that keep the realtime prompt short and generic.
    Concrete business behaviour always comes from the business prompt itself.
    """
    is_inbound = (call_direction == "inbound")
    direction_en = "INBOUND" if is_inbound else "OUTBOUND"
    direction_he = "שיחה נכנסת" if is_inbound else "שיחה יוצאת"
    
    # Greeting guidance
    if greeting_text and greeting_text.strip():
        greeting_line = (
            f'- Use this greeting once if no pre-recorded opening was played: "{greeting_text.strip()}"'
        )
    else:
        greeting_line = "- Greet warmly and introduce yourself as the business representative."
    
    if is_inbound:
        greeting_block = (
            "- The platform may play a pre-recorded greeting before you speak.\n"
            "- If the caller is already responding to something, do NOT repeat the greeting—just continue the conversation.\n"
            f"{greeting_line}"
        )
    else:
        greeting_block = (
            "- Outbound calls may start with a short recorded opening (caller name + business name).\n"
            "- After the opening, continue naturally according to the outbound business prompt.\n"
            f"{greeting_line}"
        )
    
    # Scheduling guidance (high-level only, details in business prompt / server events)
    if enable_calendar_scheduling:
        slot_desc = ""
        if policy and getattr(policy, "slot_size_min", None):
            slot_desc = f"- Appointment slots are {policy.slot_size_min} דקות.\n"
        notice_line = ""
        if policy and getattr(policy, "min_notice_min", 0):
            notice_minutes = policy.min_notice_min
            if notice_minutes >= 60:
                notice_line = f"- Respect the minimum notice window ({notice_minutes // 60} שעות לפני לפחות).\n"
            else:
                notice_line = f"- Respect the minimum notice window ({notice_minutes} דקות לפני לפחות).\n"
        scheduling_section = (
            "SCHEDULING (only when the business prompt/server tells you to book):\n"
            f"{slot_desc}"
            "- Wait for a server confirmation or explicit availability before promising any slot.\n"
            f"{notice_line}"
            "- Ask for the caller's phone number only after a slot is confirmed, unless the business prompt explicitly asks earlier.\n"
            "- If the prompt is unclear or availability never arrives, say that a human rep will call back instead of guessing."
        )
    else:
        scheduling_section = (
            "SCHEDULING:\n"
            "- Do NOT offer to book appointments yourself on this call.\n"
            "- If the caller asks to schedule, follow the business prompt. "
            "If it gives no instructions, promise a callback from a human rep."
        )
    
    return f"""AI Rep for "{business_name}" | {direction_en} call ({direction_he}) | {weekday_name} {today_date}

BUSINESS PROMPT = SOURCE OF TRUTH:
- The business prompt below defines the goal of the call (lead capture, appointment, order, support, etc.) and which details to collect.
- Never invent additional required fields. Follow the order, tone, and constraints described there.
- Once all required info is gathered, give ONE concise confirmation/summary and move to closing.

LANGUAGE:
- These instructions are for you only; the caller never hears them.
- Speak with the caller in HEBREW by default—short, clear, and warm.
- If the caller clearly says they do not understand Hebrew (e.g. "אני לא מבין עברית", "speak English", "פשוט רוסית"), immediately switch to that language and continue with the same logic.

STT IS TRUTH:
- The transcription you receive is the single source of truth.
- NEVER change, substitute, or "correct" what the caller said.
- If an important detail is unclear, politely ask the caller to repeat it instead of guessing.

GREETING & START:
{greeting_block}
- After the opening, ask ONE short question that matches the business prompt goal, then let the caller speak.

FLOW & QUESTIONS:
- First, understand what the caller wants according to the business prompt.
- Then collect ONLY the details that the business prompt says are important, in the order it prefers.
- Ask ONE question at a time. Never bundle multiple new fields in the same question.
- If an answer starts with "לא" (for example "לא", "לא, אני צריך...", "לא, זה בעיר אחרת") treat it as a correction: update your understanding and ask a focused follow-up question if needed.
- Confirmation happens once: after all required info is collected, recap the details in the caller's language and ask if everything is correct.

CLARITY & SAFETY:
- Be patient. Wait for the caller to finish speaking before you respond.
- Do not repeat the same question unless the answer was unclear or missing.
- Do not add promises, discounts, or facts that the business prompt or server did not provide.
- If the caller says goodbye or clearly tries to end the call, reply with one brief farewell and then stay silent (no restarting the conversation).

{scheduling_section}

SERVER INTEGRATION / SPEAK_EXACT:
- Sometimes the server will send you a text that you must say EXACTLY as-is.
- When you receive a message starting with "[SPEAK_EXACT]", you MUST say the exact Hebrew text inside it—no changes, no paraphrasing, no additions.
- The server text already contains the correct details extracted from the caller. Your role for that turn is only to speak it naturally.
"""
