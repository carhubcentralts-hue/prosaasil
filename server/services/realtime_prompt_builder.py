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
    🔥 BUILD INBOUND SYSTEM PROMPT - Complete separation from outbound
    
    This prompt is used ONLY for inbound calls and includes:
    - Business's inbound ai_prompt
    - Call control settings (שליטת שיחה)
    - Appointment scheduling logic (if enabled)
    - No mid-call tools
    
    Args:
        business_settings: Dict with business info (id, name, ai_prompt, greeting_message)
        call_control_settings: Dict with call control (enable_calendar_scheduling, etc.)
        db_session: Optional SQLAlchemy session
    
    Returns:
        Complete system prompt for inbound calls (English instructions, Hebrew speech)
    """
    try:
        business_id = business_settings.get("id")
        business_name = business_settings.get("name", "Business")
        ai_prompt_raw = business_settings.get("ai_prompt", "")
        greeting_text = business_settings.get("greeting_message", "")
        
        # Extract call control settings
        enable_calendar_scheduling = call_control_settings.get("enable_calendar_scheduling", True)
        
        logger.info(f"📋 [INBOUND] Building prompt for {business_name} (id={business_id}, scheduling={enable_calendar_scheduling})")
        
        # 🔥 PARSE AI PROMPT (handle JSON format with 'calls' key)
        core_instructions = ""
        if ai_prompt_raw and ai_prompt_raw.strip():
            try:
                if ai_prompt_raw.strip().startswith('{'):
                    prompt_obj = json.loads(ai_prompt_raw)
                    if 'calls' in prompt_obj:
                        core_instructions = prompt_obj['calls']
                        logger.info(f"✅ [INBOUND] Using 'calls' prompt from DB")
                    elif 'whatsapp' in prompt_obj:
                        core_instructions = prompt_obj['whatsapp']
                        logger.info(f"⚠️ [INBOUND] Using 'whatsapp' as fallback")
                    else:
                        core_instructions = ai_prompt_raw
                else:
                    core_instructions = ai_prompt_raw
            except json.JSONDecodeError:
                core_instructions = ai_prompt_raw
        
        # Replace placeholders
        if core_instructions:
            core_instructions = core_instructions.replace("{{business_name}}", business_name)
            core_instructions = core_instructions.replace("{{BUSINESS_NAME}}", business_name)
        
        # 🔥 BEHAVIORAL RULES (English instructions, AI speaks Hebrew)
        behavioral_rules = f"""You are a male virtual call agent for an Israeli business: "{business_name}".

LANGUAGE RULES:
- You ALWAYS speak Hebrew unless the caller explicitly says they do not understand Hebrew.
- If the caller says "I don't understand Hebrew" or speaks another language and requests it, switch to that language and continue the conversation there.

TRANSCRIPTION IS TRUTH:
- You NEVER invent facts. The user's transcript is the single source of truth.
- If the user says any information (city, service, name, phone number, or details) — you repeat EXACTLY what they said.
- If something is unclear, ask politely for clarification.
- NEVER correct or modify the caller's words.

HANDLING REJECTIONS:
- When the user says "לא" (no) or rejects your understanding:
  * Apologize briefly
  * Ask them to repeat ALL important details in one short sentence
  * Follow the business instructions to understand what information is needed
- When the user provides only PARTIAL information:
  * Identify what pieces are missing according to the business instructions
  * Ask ONLY about the missing parts
  * Do not restart the entire conversation unless they explicitly reject everything

TONE & STYLE:
- Warm, helpful, patient, concise, masculine, and natural.
- Ask ONE question at a time.

"""
        
        # 🔥 APPOINTMENT SCHEDULING LOGIC
        if enable_calendar_scheduling:
            # Load policy for scheduling info
            from server.policy.business_policy import get_business_policy
            policy = get_business_policy(business_id, prompt_text=None, db_session=db_session)
            
            # Get date context
            tz = pytz.timezone(policy.tz)
            today = datetime.now(tz)
            today_date = today.strftime("%d/%m/%Y")
            weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            weekday_name = weekday_names[today.weekday()]
            
            # Build hours description
            hours_description = _build_hours_description(policy)
            
            min_notice = ""
            if policy.min_notice_min > 0:
                min_notice_hours = policy.min_notice_min // 60
                if min_notice_hours > 0:
                    min_notice = f" (minimum {min_notice_hours}h advance booking required)"
            
            scheduling_rules = f"""
APPOINTMENT SCHEDULING:
Today is {weekday_name}, {today_date}

BOOKING FLOW (STRICT ORDER):
1. FIRST: Ask for NAME: "מה השם שלך?" - Get name before anything else
2. THEN: Ask for DATE/TIME: "לאיזה יום ושעה?" - Get preferred date and time
3. WAIT: For system to check availability (don't promise slot is available!)
4. AFTER CONFIRMATION: Ask for PHONE: "מה הטלפון שלך לאישור?" - Phone is collected LAST
5. BOOKING SUCCESS: Only say "התור נקבע" AFTER system confirms booking

CRITICAL RULES:
- Appointment slots: {policy.slot_size_min} minutes{min_notice}
- Business hours: {hours_description}
- Phone is collected LAST, only after appointment time is confirmed
- If slot is taken, offer alternatives (system will provide)
- NEVER ask for phone before confirming date/time availability
"""
        else:
            scheduling_rules = """
NO APPOINTMENT SCHEDULING:
- You do NOT offer appointments.
- If customer asks for an appointment, politely say a representative will call them back to schedule.
- Focus only on collecting lead information.
"""
        
        # 🔥 END OF CALL
        end_of_call = """
END OF CALL:
- Once you have collected service and location info, close the call naturally.
- Say: "מצוין, קיבלתי. בעל מקצוע יחזור אליך בהקדם. תודה ולהתראות."
- After saying goodbye, stay quiet.
- DO NOT repeat or confirm details back to the customer.
"""
        
        # 🔥 COMBINE ALL SECTIONS
        full_prompt = f"""{behavioral_rules}

--- BUSINESS INSTRUCTIONS ---
{core_instructions if core_instructions else f"You are a professional service representative for {business_name}. Be helpful and collect customer information."}
---

{scheduling_rules}

{end_of_call}

CRITICAL: Do not perform any mid-call extraction or internal tools. Only converse naturally.
Never hallucinate cities or services.
Never correct the caller's words.
Use the exact words the customer said.
"""
        
        logger.info(f"✅ [INBOUND] Prompt built: {len(full_prompt)} chars")
        return full_prompt
        
    except Exception as e:
        logger.error(f"❌ [INBOUND] Error building prompt: {e}")
        import traceback
        traceback.print_exc()
        return f"You are a professional service rep for {business_settings.get('name', 'the business')}. SPEAK HEBREW to customer. Be brief and helpful."


def build_outbound_system_prompt(
    business_settings: Dict[str, Any],
    db_session=None
) -> str:
    """
    🔥 BUILD OUTBOUND SYSTEM PROMPT - Pure prompt mode, no call control
    
    This prompt is used ONLY for outbound calls and includes:
    - Business's outbound ai_prompt ONLY
    - NO call control settings
    - NO appointment scheduling logic (unless explicitly in the prompt)
    - NO tools
    
    Args:
        business_settings: Dict with business info (id, name, outbound_ai_prompt)
        db_session: Optional SQLAlchemy session
    
    Returns:
        Complete system prompt for outbound calls (English instructions, Hebrew speech)
    """
    try:
        business_id = business_settings.get("id")
        business_name = business_settings.get("name", "Business")
        outbound_prompt = business_settings.get("outbound_ai_prompt", "")
        
        logger.info(f"📋 [OUTBOUND] Building prompt for {business_name} (id={business_id})")
        
        # 🔥 USE OUTBOUND PROMPT ONLY
        core_instructions = ""
        if outbound_prompt and outbound_prompt.strip():
            core_instructions = outbound_prompt.strip()
            logger.info(f"✅ [OUTBOUND] Using outbound_ai_prompt ({len(core_instructions)} chars)")
        else:
            # Fallback if no outbound prompt
            core_instructions = f"You are a professional sales representative for {business_name}. Be brief and persuasive."
            logger.warning(f"⚠️ [OUTBOUND] No outbound_ai_prompt found - using fallback")
        
        # Replace placeholders
        core_instructions = core_instructions.replace("{{business_name}}", business_name)
        core_instructions = core_instructions.replace("{{BUSINESS_NAME}}", business_name)
        
        # 🔥 BEHAVIORAL RULES FOR OUTBOUND (English instructions, AI speaks Hebrew)
        behavioral_rules = f"""You are a male virtual outbound caller representing the business: "{business_name}".

LANGUAGE RULES:
- You ALWAYS speak Hebrew unless the customer explicitly requests another language.
- If customer says "I don't understand Hebrew" or speaks another language, switch immediately.

OUTBOUND GREETING:
- Start naturally with a short greeting appropriate for outbound calls.
- Example: "שלום, מדבר נציג של {business_name}..."
- Be warm but professional.

TRANSCRIPTION IS TRUTH:
- You NEVER invent any facts.
- Repeat ONLY what is given in the transcript or outbound prompt context.
- If something is unclear, ask politely.

HANDLING REJECTIONS:
- When the customer says "לא" (no) or rejects your understanding:
  * Apologize briefly
  * Ask them to repeat ALL important details in one short sentence
  * Follow the outbound instructions to understand what information is needed
- When the customer provides only PARTIAL information:
  * Identify what pieces are missing according to the outbound instructions
  * Ask ONLY about the missing parts

TONE & STYLE:
- Polite, concise, masculine, and helpful.
- Ask ONE question at a time.

"""
        
        # 🔥 OUTBOUND CLOSING
        outbound_closing = """
END OF CALL:
- At the end of the conversation, politely close the call.
- Thank the customer for their time.
- After saying goodbye, stay quiet.
- DO NOT repeat or confirm details back to the customer.
"""
        
        # 🔥 COMBINE ALL SECTIONS
        full_prompt = f"""{behavioral_rules}

--- OUTBOUND INSTRUCTIONS ---
{core_instructions}
---

{outbound_closing}

CRITICAL: 
- Use ONLY the information provided in the outbound prompt above.
- Do not use inbound call logic.
- NEVER invent facts or details.
- Be polite and professional.
"""
        
        logger.info(f"✅ [OUTBOUND] Prompt built: {len(full_prompt)} chars")
        return full_prompt
        
    except Exception as e:
        logger.error(f"❌ [OUTBOUND] Error building prompt: {e}")
        import traceback
        traceback.print_exc()
        return f"You are a professional sales rep for {business_settings.get('name', 'the business')}. SPEAK HEBREW to customer. Be brief and persuasive."
