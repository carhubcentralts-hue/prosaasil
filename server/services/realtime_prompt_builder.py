"""
Realtime Prompt Builder
Build dynamic system prompts for OpenAI Realtime API based on business settings

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
    🔥 ROUTER: Routes to correct prompt builder based on call direction
    
    This function is the main entry point and routes to:
    - build_inbound_system_prompt() for inbound calls
    - build_outbound_system_prompt() for outbound calls
    
    Args:
        business_id: Business ID
        db_session: Optional SQLAlchemy session (for transaction safety)
        call_direction: "inbound" or "outbound" - determines which prompt to use
    
    Returns:
        Complete system prompt for the AI assistant
    """
    try:
        from server.models_sql import Business, BusinessSettings
        
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
        
        logger.info(f"📋 [ROUTER] Building prompt for {business_name} (business_id={business_id}, direction={call_direction})")
        
        # 🔥 PREPARE BUSINESS SETTINGS DICT
        business_settings_dict = {
            "id": business_id,
            "name": business_name,
            "ai_prompt": settings.ai_prompt if settings else "",
            "outbound_ai_prompt": settings.outbound_ai_prompt if settings else "",
            "greeting_message": business.greeting_message or ""
        }
        
        # 🔥 ROUTE TO CORRECT BUILDER
        if call_direction == "outbound":
            # 🔥 OUTBOUND: Use pure prompt mode (no call control settings)
            return build_outbound_system_prompt(
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
            
            return build_inbound_system_prompt(
                business_settings=business_settings_dict,
                call_control_settings=call_control_settings_dict,
                db_session=db_session
            )
        
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
    🔥 DEPRECATED: This function is no longer used. Keeping for backwards compatibility.
    🔥 All behavior now comes from System Prompts (INBOUND/OUTBOUND) + Business Prompt
    """
    # This function should not be called anymore
    logger.warning("⚠️ [DEPRECATED] _build_critical_rules_compact called - should use new prompt builders")
    return ""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔥 NEW: PERFECT INBOUND & OUTBOUND SEPARATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def build_inbound_system_prompt(
    business_settings: Dict[str, Any],
    call_control_settings: Dict[str, Any],
    db_session=None
) -> str:
    """
    🔥 REBUILT: Perfect Inbound System Prompt (100% Prompt-Driven)
    
    - Bilingual adaptive (auto-detect & switch)
    - Zero hardcoded conversational logic
    - Dynamic appointment flow based on settings
    - Strict anti-hallucination
    - Optimized for GPT-4o Realtime
    
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
        
        # 🔥 PARSE BUSINESS PROMPT (handle JSON format)
        core_instructions = ""
        if ai_prompt_raw and ai_prompt_raw.strip():
            try:
                if ai_prompt_raw.strip().startswith('{'):
                    prompt_obj = json.loads(ai_prompt_raw)
                    core_instructions = prompt_obj.get('calls') or prompt_obj.get('whatsapp') or ai_prompt_raw
                else:
                    core_instructions = ai_prompt_raw
            except json.JSONDecodeError:
                core_instructions = ai_prompt_raw
        
        # Replace placeholders
        if core_instructions:
            core_instructions = core_instructions.replace("{{business_name}}", business_name)
            core_instructions = core_instructions.replace("{{BUSINESS_NAME}}", business_name)
        
        # 🔥 A. LANGUAGE & TRANSCRIPTION RULES
        language_rules = f"""You are a virtual assistant for "{business_name}".

LANGUAGE (AUTO-ADAPTIVE):
Default = Hebrew. If caller speaks another language (English/Arabic/Russian/etc) → seamlessly switch to that language for the entire call. Never mix languages unless requested.

TRANSCRIPTION IS TRUTH:
The realtime transcription is the single source of truth. Never invent facts. Never assume. If unclear, ask politely for clarification. Use EXACTLY what the caller says."""

        # 🔥 B. BEHAVIOR HIERARCHY
        hierarchy = """
BEHAVIOR HIERARCHY:
Business Prompt > System Rules > Model Defaults
If any conflict → ALWAYS follow Business Prompt."""

        # 🔥 C. CONVERSATION RULES
        conversation = """
CONVERSATION:
- Stay natural, warm, human
- ONE question at a time
- NEVER rush the customer
- NEVER repeat same question more than twice
- If customer unsure → offer alternatives calmly
- Never improvise facts or services
- Never ask for phone number (already available from call metadata)"""

        # 🔥 D. APPOINTMENT LOGIC (dynamic)
        if call_goal == 'appointment' and enable_calendar_scheduling:
            from server.policy.business_policy import get_business_policy
            policy = get_business_policy(business_id, prompt_text=None, db_session=db_session)
            
            tz = pytz.timezone(policy.tz)
            today = datetime.now(tz)
            today_date = today.strftime("%d/%m/%Y")
            weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            weekday_name = weekday_names[today.weekday()]
            
            appointment_logic = f"""
APPOINTMENT SCHEDULING:
Today: {weekday_name}, {today_date}

Required info to collect:
1) Customer name
2) Date and time (natural language → convert to YYYY-MM-DD HH:MM format)

Tool usage:
- Call schedule_appointment ONLY ONCE after you have all required info
- NEVER ask for phone (use call metadata)
- If server returns success=false → ask for different time
- If success=true → confirm appointment is successfully scheduled
- Slot size: {policy.slot_size_min} minutes

CRITICAL: Never say "I scheduled" unless server tool returns success=true."""
        elif call_goal == 'lead_only' or not enable_calendar_scheduling:
            appointment_logic = """
APPOINTMENT SCHEDULING: DISABLED
NEVER attempt to schedule or suggest an appointment. Respond conversationally only. If customer asks about appointments, follow Business Prompt instructions."""
        else:
            appointment_logic = """APPOINTMENT SCHEDULING: DISABLED"""

        # 🔥 E. ERROR RECOVERY
        error_recovery = """
ERROR RECOVERY:
- Unclear audio → ask to repeat politely
- Misunderstood → apologize briefly and correct"""

        # 🔥 F. ANTI-HALLUCINATION
        anti_hallucination = """
ANTI-HALLUCINATION (CRITICAL):
- Never create or assume details
- Never say "I scheduled" unless server returns success=true
- Never say "representative will contact you" unless Business Prompt instructs it"""

        # 🔥 G. HANGUP LOGIC
        if call_goal == 'lead_only':
            hangup = """
CALL END:
If all required info collected → politely end conversation. Follow Business Prompt for goodbye."""
        elif call_goal == 'appointment' and enable_calendar_scheduling:
            hangup = """
CALL END:
If appointment successfully scheduled → politely end conversation. Follow Business Prompt for goodbye."""
        else:
            hangup = """CALL END: Follow Business Prompt."""

        # 🔥 COMBINE ALL
        full_prompt = f"""{language_rules}

{hierarchy}

{conversation}

{appointment_logic}

{error_recovery}

{anti_hallucination}

{hangup}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BUSINESS PROMPT (SOURCE OF TRUTH):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{core_instructions if core_instructions else f"Professional service representative for {business_name}. Be helpful and collect customer information."}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""
        
        logger.info(f"✅ [INBOUND] Prompt built: {len(full_prompt)} chars")
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
    🔥 REBUILT: Perfect Outbound System Prompt (100% Prompt-Driven)
    
    - Bilingual adaptive (auto-detect & switch)
    - Direct, purpose-driven outbound behavior
    - Identity verification reminder
    - Same anti-hallucination rules as inbound
    - Optimized for GPT-4o Realtime
    
    Args:
        business_settings: Dict with business info (id, name, outbound_ai_prompt)
        db_session: Optional SQLAlchemy session
    
    Returns:
        Complete system prompt for outbound calls (2000-3500 chars)
    """
    try:
        business_id = business_settings.get("id")
        business_name = business_settings.get("name", "Business")
        outbound_prompt = business_settings.get("outbound_ai_prompt", "")
        
        logger.info(f"📋 [OUTBOUND] Building prompt: {business_name} (id={business_id})")
        
        # 🔥 USE OUTBOUND PROMPT
        core_instructions = ""
        if outbound_prompt and outbound_prompt.strip():
            core_instructions = outbound_prompt.strip()
            logger.info(f"✅ [OUTBOUND] Using outbound_ai_prompt ({len(core_instructions)} chars)")
        else:
            core_instructions = f"You are a professional representative for {business_name}. Be brief and helpful."
            logger.warning(f"⚠️ [OUTBOUND] No outbound_ai_prompt - using fallback")
        
        # Replace placeholders
        core_instructions = core_instructions.replace("{{business_name}}", business_name)
        core_instructions = core_instructions.replace("{{BUSINESS_NAME}}", business_name)
        
        # 🔥 A. LANGUAGE & TRANSCRIPTION
        language_rules = f"""You are a virtual outbound assistant for "{business_name}".

LANGUAGE (AUTO-ADAPTIVE):
Default = Hebrew. If customer speaks another language (English/Arabic/Russian/etc) → seamlessly switch to that language for the entire call. Never mix languages unless requested.

TRANSCRIPTION IS TRUTH:
The realtime transcription is the single source of truth. Never invent facts. Never assume. If unclear, ask politely. Use EXACTLY what the caller says."""

        # 🔥 B. IDENTITY VERIFICATION
        identity = f"""
IDENTITY VERIFICATION:
If customer sounds unsure who you are, remind them gently:
"שלום, אני העוזרת הדיגיטלית של {business_name}." (or in their language)"""

        # 🔥 C. OUTBOUND BEHAVIOR
        outbound_behavior = """
OUTBOUND BEHAVIOR:
- Be more direct than inbound calls
- State purpose early: "I'm calling from [business] regarding..." (follow Outbound Prompt)
- Push gently toward appointment/lead goal if specified
- ONE question at a time
- NEVER rush the customer
- NEVER repeat same question more than twice
- If customer unsure → offer alternatives calmly
- If customer objects → acknowledge and follow Outbound Prompt instructions
- Never improvise facts or offers
- Never ask for phone (already available from call metadata)

CONVERSATION FLOW:
1. Greet and identify yourself (follow Outbound Prompt)
2. State purpose clearly
3. Engage with customer needs
4. Collect required information
5. Close appropriately (follow Outbound Prompt)"""

        # 🔥 D. ANTI-HALLUCINATION (same as inbound)
        anti_hallucination = """
ANTI-HALLUCINATION (CRITICAL):
- Never create or assume details about products, services, or pricing
- Never promise anything not explicitly stated in Outbound Prompt
- Never say "I scheduled" unless server tool returns success=true
- Never say "representative will contact you" unless Outbound Prompt instructs it
- If customer asks something not covered in Outbound Prompt → politely defer or ask for clarification"""

        # 🔥 E. ERROR RECOVERY
        error_recovery = """
ERROR RECOVERY:
- If unclear audio → ask customer to repeat politely
- If misunderstood → apologize briefly and correct
- If technical issue → acknowledge calmly and continue"""

        # 🔥 F. CALL END
        call_end = """
CALL END:
Follow Outbound Prompt for goodbye. Be warm but professional. Stay quiet after saying goodbye."""

        # 🔥 F. HIERARCHY
        hierarchy = """
BEHAVIOR HIERARCHY:
Outbound Prompt > System Rules > Model Defaults
If conflict → ALWAYS follow Outbound Prompt."""

        # 🔥 COMBINE ALL
        full_prompt = f"""{language_rules}

{identity}

{hierarchy}

{outbound_behavior}

{anti_hallucination}

{error_recovery}

{call_end}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTBOUND PROMPT (SOURCE OF TRUTH):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{core_instructions}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""
        
        logger.info(f"✅ [OUTBOUND] Prompt built: {len(full_prompt)} chars")
        return full_prompt
        
    except Exception as e:
        logger.error(f"❌ [OUTBOUND] Error: {e}")
        import traceback
        traceback.print_exc()
        return f"You are a professional representative for {business_settings.get('name', 'the business')}. Speak Hebrew. Be helpful."
