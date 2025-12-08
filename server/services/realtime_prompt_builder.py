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
        
        # 🔥 BUILD 335: NO TRUNCATION OF BUSINESS PROMPTS - Keep full business context!
        # Only system rules are compact, business prompts stay as-is
        
        # Compact sandbox wrapper - business prompt is NOT truncated
        sandboxed_instructions = f"""--- BUSINESS INFO (follow FLOW above) ---
{core_instructions}
---"""
        
        # Combine: Rules + Sandboxed custom prompt + Policy
        service_city_prompt = _build_service_city_prompt()
        full_prompt = "\n".join([critical_rules, service_city_prompt, sandboxed_instructions])
        
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
    
    # 🔥 BUILD 336: COMPACT + CLEAR SYSTEM RULES with SPEAK_EXACT support
    return f"""AI Rep for "{business_name}" | {direction_context} call | {weekday_name} {today_date}

LANGUAGE: All instructions are in English. SPEAK HEBREW to customer.

STT IS TRUTH: Trust transcription 100%. NEVER change, substitute, or "correct" any word.

CALL FLOW:
1. GREET: {greeting_line} Ask ONE open question about their need.
2. COLLECT: One question at a time. Mirror their EXACT words.
3. CONFIRM (ONCE!): After ALL details → say the SERVER confirmation (see SPEAK_EXACT below).
4. CLOSE: Thank customer, describe next step, say goodbye. After goodbye → STOP talking.
{scheduling_section}

STRICT RULES:
- Hebrew speech only
- BE PATIENT: Wait for customer to respond. Don't rush or repeat questions too quickly.
- No loops, no repeating questions unless answer was unclear
- No mid-call confirmations - only ONE summary at the end
- After customer says goodbye → one farewell and stay quiet
- Don't ask for multiple pieces of information at once - ONE question at a time!

[SPEAK_EXACT] INSTRUCTION:
When you receive a message starting with "[SPEAK_EXACT]", you MUST say the exact Hebrew text quoted inside - NO changes, NO paraphrasing, NO "improvements". The server provides the CORRECT values from the customer's actual words. Just say it exactly!
"""


def _build_service_city_prompt() -> str:
    return """אתה נציג טלפוני גברי, חם ואדיב. אתה מדבר רק עברית, תמיד קצר וברור.
מטרתך היחידה: להבין מהו השירות שהלקוח צריך ובאיזו עיר הוא נמצא — ולא מעבר לזה.

הזרימה:
1. הברכה כבר שואלת את הלקוח מה השירות שהוא צריך.
2. אם כבר ברור מה השירות (service_type קיים ב-context) → אל תשאל שוב על השירות. תתמקד רק בעיר.
3. אם השירות לא ברור → תשאל שאלה אחת קצרה: “איזה סוג שירות אתה צריך?”
4. אחרי שיש שירות אבל אין עיר → תשאל רק על העיר: “ובאיזה עיר אתה צריך את השירות?”
5. לעולם אל תמציא עיר שלא נאמרה. אם לא שמעת עיר בבירור, תגיד: “לא שמעתי טוב את העיר, תגיד אותה שוב בבקשה.”
6. אחרי שיש גם שירות וגם עיר → תאמר משפט אישור אחד בלבד, למשל:
“רק מוודא — אתה צריך {{service}} בעיר {{city}}, נכון?”
7. אם הלקוח אומר “לא” או מתקן את העיר/שירות, תעדכן לפי מה שהוא אמר, ותשאל שוב פעם אחת אם צריך.
8. אל תאסוף שום פרט אחר (לא שם, לא טלפון, לא מייל).
9. אל תבטיח שום דבר שלא נאמר ב-context. אם אין מידע על תורים, תסיים ב:
“מצוין, קיבלתי. בעל מקצוע מתאים יחזור אליך בהקדם.”
"""
