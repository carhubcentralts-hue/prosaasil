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
            logger.warning(f"⚠️ [BUILD 317] Business {business_id} not found")
            return "נציג AI. עברית בלבד. שאל במה אוכל לעזור."
        
        business_name = business.name or "העסק"
        
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
            # No ai_prompt - use minimal fallback
            compact_context = f"אתה נציג של {business_name}. דבר בעברית, היה קצר וברור."
            logger.warning(f"⚠️ [BUILD 317] No ai_prompt for business {business_id} - using minimal")
        
        # 🔥 BUILD 317: Add essential rules (very short)
        direction = "שיחה נכנסת" if call_direction == "inbound" else "שיחה יוצאת"
        
        final_prompt = f"""{compact_context}

---
{direction} | אם לא שמעת ברור - בקש לחזור. אל תמציא."""

        logger.info(f"📦 [BUILD 317] Final compact prompt: {len(final_prompt)} chars")
        return final_prompt
        
    except Exception as e:
        logger.error(f"❌ [BUILD 317] Compact prompt error: {e}")
        import traceback
        traceback.print_exc()
        # 🔥 BUILD 317: Better fallback with clear instruction
        return """אתה נציג טלפוני מקצועי. דבר בעברית, היה אדיב וקצר.
שאל את הלקוח במה תוכל לעזור ואסוף את הפרטים הנדרשים: שם, טלפון, עיר, סוג שירות.
אם לא שמעת ברור - בקש לחזור. אל תמציא מידע."""


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
        
        business_name = business.name or "העסק"
        
        # Load business policy (slot size, opening hours, etc.)
        policy = get_business_policy(business_id, prompt_text=None, db_session=db_session)
        
        logger.info(f"📋 Building Realtime prompt for {business_name} (business_id={business_id}, direction={call_direction})")
        
        # 🔥 BUILD 186: SEPARATE LOGIC FOR INBOUND vs OUTBOUND
        # - OUTBOUND: Uses ONLY the outbound_ai_prompt from DB (no call control settings)
        # - INBOUND: Uses ai_prompt + call control settings (calendar scheduling, etc.)
        
        core_instructions = ""
        
        if call_direction == "outbound":
            # 🔥 OUTBOUND CALLS: Use ONLY the outbound prompt, nothing else!
            if settings and settings.outbound_ai_prompt and settings.outbound_ai_prompt.strip():
                core_instructions = settings.outbound_ai_prompt.strip()
                logger.info(f"✅ [OUTBOUND] Using outbound_ai_prompt ONLY for business {business_id} ({len(core_instructions)} chars)")
            else:
                # 🔥 BUILD 200: Minimal generic fallback - no business-specific assumptions
                core_instructions = f"""אתה נציג של "{business_name}". דבר בעברית, היה אדיב וקצר."""
                logger.warning(f"⚠️ [OUTBOUND] No outbound_ai_prompt for business {business_id} - using minimal fallback")
            
            # Replace placeholders
            core_instructions = core_instructions.replace("{{business_name}}", business_name)
            core_instructions = core_instructions.replace("{{BUSINESS_NAME}}", business_name)
            
            # 🔥 OUTBOUND: Return the prompt as-is, NO call control settings added!
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
            # 🔥 BUILD 200: Minimal generic fallback - no business-specific assumptions
            logger.error(f"❌ [INBOUND] No prompt in DB for business {business_id}")
            core_instructions = f"""אתה נציג של "{business_name}". עונה בעברית, קצר וברור."""
        
        # Replace placeholders
        core_instructions = core_instructions.replace("{{business_name}}", business_name)
        core_instructions = core_instructions.replace("{{BUSINESS_NAME}}", business_name)
        
        # 🔥 Get current date for AI context
        tz = pytz.timezone(policy.tz)
        today = datetime.now(tz)
        today_hebrew = today.strftime("%d/%m/%Y")
        weekday_names = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]
        weekday_hebrew = weekday_names[today.weekday()]
        
        # 🔥 LOAD GREETING FROM DB
        greeting_text = business.greeting_message if business else ""
        if not greeting_text:
            greeting_text = ""
        
        # 🔥 BUILD 168: Load required_lead_fields for dynamic verification prompt
        required_lead_fields = ['name', 'phone']  # Default
        if settings and hasattr(settings, 'required_lead_fields') and settings.required_lead_fields:
            required_lead_fields = settings.required_lead_fields
            logger.info(f"✅ Using custom required_lead_fields: {required_lead_fields}")
        
        # 🔥 BUILD 186: Check calendar scheduling setting
        enable_calendar_scheduling = True  # Default to enabled
        if settings and hasattr(settings, 'enable_calendar_scheduling'):
            enable_calendar_scheduling = settings.enable_calendar_scheduling
        logger.info(f"📅 [INBOUND] Calendar scheduling: {'ENABLED' if enable_calendar_scheduling else 'DISABLED'}")
        
        # 🎯 BUILD 177: COMPACT system prompt with call control settings
        critical_rules = _build_critical_rules_compact(
            business_name, today_hebrew, weekday_hebrew, greeting_text, 
            required_lead_fields, call_direction, enable_calendar_scheduling
        )
        
        # Combine: Rules + Custom prompt + Policy
        full_prompt = critical_rules + "\n\n" + core_instructions
        
        # 🔥 BUILD 186: Only add scheduling info if calendar scheduling is ENABLED
        if enable_calendar_scheduling:
            hours_description = _build_hours_description(policy)
            slot_description = _build_slot_description(policy.slot_size_min)
            
            min_notice = ""
            if policy.min_notice_min > 0:
                min_notice_hours = policy.min_notice_min // 60
                if min_notice_hours > 0:
                    min_notice = f" (advance booking: {min_notice_hours}h)"
            
            full_prompt += f"\n\nSCHEDULING: Slots every {policy.slot_size_min} min{min_notice}\n{hours_description}"
        else:
            # Explicitly tell AI not to schedule appointments
            full_prompt += "\n\n⚠️ NO SCHEDULING: Do NOT offer to schedule appointments or meetings. Focus only on providing information and collecting lead details."
        
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


def _get_fallback_prompt(business_id: int = None) -> str:
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
            
            # Build minimal prompt from business name
            if business and business.name:
                return f"You are a representative of {business.name}. Respond in HEBREW, be brief and helpful."
    except:
        pass
    
    # Absolute minimal - no business info available
    return "Respond in HEBREW, be brief and helpful."


def _build_hours_description(policy) -> str:
    """Build opening hours description in Hebrew"""
    if policy.allow_24_7:
        return "פתוח 24/7"
    
    hours = policy.opening_hours
    if not hours:
        return "שעות פעילות לא הוגדרו"
    
    day_names = {
        "sun": "א", "mon": "ב", "tue": "ג", "wed": "ד",
        "thu": "ה", "fri": "ו", "sat": "ש"
    }
    
    parts = []
    for day_key in ["sun", "mon", "tue", "wed", "thu", "fri", "sat"]:
        windows = hours.get(day_key, [])
        if windows:
            time_ranges = ",".join([f"{w[0]}-{w[1]}" for w in windows])
            parts.append(f"{day_names[day_key]}:{time_ranges}")
    
    return "שעות: " + " | ".join(parts) if parts else "שעות לא הוגדרו"


def _build_slot_description(slot_size_min: int) -> str:
    """Build slot size description in Hebrew - COMPACT"""
    if slot_size_min == 15:
        return "כל 15 דק'"
    elif slot_size_min == 30:
        return "כל חצי שעה"
    elif slot_size_min == 60:
        return "כל שעה"
    elif slot_size_min == 90:
        return "כל 90 דק'"
    elif slot_size_min == 120:
        return "כל שעתיים"
    else:
        return f"כל {slot_size_min} דק'"


def _build_critical_rules_compact(business_name: str, today_hebrew: str, weekday_hebrew: str, greeting_text: str = "", required_fields: Optional[list] = None, call_direction: str = "inbound", enable_calendar_scheduling: bool = True) -> str:
    """
    BUILD 186: FULLY DYNAMIC system prompt - no hardcoded values
    All context comes from business settings, nothing hardcoded
    
    Args:
        enable_calendar_scheduling: If True, AI can schedule appointments. If False, AI should NOT offer scheduling.
    """
    direction_context = "מקבל שיחה" if call_direction == "inbound" else "מתקשר ללקוח"
    
    # 🔥 BUILD 186: Calendar scheduling rules based on setting
    if enable_calendar_scheduling:
        scheduling_rules = """6. תורים: בדוק זמינות לפני אישור!
7. אל תגיד "קבעתי/קבענו" עד שהמערכת מאשרת!
8. רק אם הלקוח ביקש תור במפורש - התחל תהליך קביעה"""
    else:
        scheduling_rules = """6. אל תציע לקבוע פגישות או תורים - רק אסוף פרטים ותן מידע
7. אם הלקוח מבקש פגישה - הסבר שנציג יחזור אליו בהקדם"""
    
    return f"""נציג AI של "{business_name}" | {direction_context}
תאריך: {weekday_hebrew}, {today_hebrew}

כללים:
1. דבר עברית טבעית. אם הלקוח דובר שפה אחרת - עבור לשפתו
2. לא להמציא - רק מה שנאמר או שהמערכת אישרה
3. אישור פרטים: "רק מוודא - אמרת X, נכון?"
4. קצר וברור, בלי חזרות
5. אם לא שמעת ברור: "סליחה, לא שמעתי - תוכל לחזור על זה?"
{scheduling_rules}

⚠️ חובה! בדיקת הקשר:
- אחרי ברכה: המתן לבקשה ברורה מהלקוח. אם התשובה לא קשורה לשאלה (כמו "תודה" אחרי "איך אוכל לעזור?") - שאל: "במה אוכל לעזור?"
- לא לקפוץ למסקנות! אם הלקוח אמר משהו לא ברור - בקש הבהרה
"""
