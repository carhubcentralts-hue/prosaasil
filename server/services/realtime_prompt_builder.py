"""
Realtime Prompt Builder
Build dynamic system prompts for OpenAI Realtime API based on business settings
"""
import logging
from typing import Optional
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)


def build_realtime_system_prompt(business_id: int, db_session=None) -> str:
    """
    Build system prompt for OpenAI Realtime API based on business settings
    
    Args:
        business_id: Business ID
        db_session: Optional SQLAlchemy session (for transaction safety)
    
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
            # Fall back to minimal prompt if DB access fails
            return f"""אתה נציג טלפוני של העסק. עונה בעברית, קצר וברור. עזור ללקוח לקבוע תור או לענות על שאלות.
            
🎤 חוקי שיחה:
1. פתיח קצר: רק 1-2 משפטים שמציג מי אתה ומה אתה עושה
2. תיאום פגישות: חובה לאסוף שם מלא + טלפון + תאריך/שעה לפני קביעת תור
3. אל תגיד "קבעתי לך" עד שהשרת אישר"""
        
        if not business:
            raise ValueError(f"Business {business_id} not found")
        
        business_name = business.name or "העסק"
        
        # Load business policy (slot size, opening hours, etc.)
        policy = get_business_policy(business_id, prompt_text=None, db_session=db_session)
        
        logger.info(f"📋 Building Realtime prompt for {business_name} (business_id={business_id})")
        
        # 🔥 NEW: Load custom prompt from DB (just like WhatsApp)
        core_instructions = ""
        if settings and settings.ai_prompt and settings.ai_prompt.strip():
            import json
            try:
                # Try to parse as JSON (new format with calls/whatsapp)
                if settings.ai_prompt.strip().startswith('{'):
                    prompt_obj = json.loads(settings.ai_prompt)
                    # Get 'calls' prompt, fallback to whatsapp if missing
                    if 'calls' in prompt_obj:
                        core_instructions = prompt_obj['calls']
                        logger.info(f"✅ Using 'calls' prompt from DB for business {business_id}")
                    elif 'whatsapp' in prompt_obj:
                        core_instructions = prompt_obj['whatsapp']
                        logger.info(f"⚠️ 'calls' prompt missing - using 'whatsapp' as fallback for business {business_id}")
                    else:
                        # No valid keys - use raw prompt
                        core_instructions = settings.ai_prompt
                        logger.warning(f"⚠️ No valid channel keys - using raw prompt for business {business_id}")
                else:
                    # Legacy text prompt
                    core_instructions = settings.ai_prompt
                    logger.info(f"✅ Using legacy text prompt for business {business_id}")
            except json.JSONDecodeError:
                # Not valid JSON - use as text
                core_instructions = settings.ai_prompt
                logger.info(f"✅ Using non-JSON prompt for business {business_id}")
        
        # If no custom prompt, use minimal default
        if not core_instructions:
            logger.error(f"❌ No 'calls' prompt in DB for business {business_id} - using minimal fallback")
            core_instructions = f"""אתה נציג טלפוני של "{business_name}". עונה בעברית, קצר וברור. עזור ללקוח לקבוע תור או לענות על שאלות."""
        
        # Replace placeholders
        core_instructions = core_instructions.replace("{{business_name}}", business_name)
        core_instructions = core_instructions.replace("{{BUSINESS_NAME}}", business_name)
        
        # 🔥 Get current date for AI context
        from datetime import datetime
        import pytz
        tz = pytz.timezone(policy.tz)
        today = datetime.now(tz)
        today_str = today.strftime("%Y-%m-%d")  # e.g., "2025-11-17"
        today_hebrew = today.strftime("%d/%m/%Y")  # e.g., "17/11/2025"
        # 🔥 FIX: Python weekday() is Mon=0, Tue=1, ..., Sun=6
        # Hebrew: Mon=שני, Tue=שלישי, ..., Sun=ראשון
        weekday_names = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]
        weekday_hebrew = weekday_names[today.weekday()]
        month_hebrew = ["ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני", "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר"][today.month - 1]
        
        # 🎯 Build layered system prompt: CRITICAL RULES → Core Instructions → Policy Info
        critical_rules = _build_critical_rules(business_name, today_hebrew, weekday_hebrew, month_hebrew, today)
        core_instructions = critical_rules + "\n" + core_instructions
        
        # 🔥 ADD DYNAMIC POLICY INFO (hours, slots, min_notice)
        hours_description = _build_hours_description(policy)
        slot_description = _build_slot_description(policy.slot_size_min)
        
        min_notice_description = ""
        if policy.min_notice_min > 0:
            min_notice_hours = policy.min_notice_min // 60
            if min_notice_hours > 0:
                min_notice_description = f"\n- דורשים הזמנה מראש של לפחות {min_notice_hours} שעות."
            else:
                min_notice_description = f"\n- דורשים הזמנה מראש של לפחות {policy.min_notice_min} דקות."
        
        # Append dynamic policy info
        policy_info = f"\n\n📅 הגדרות תורים:\n{hours_description}\n- {slot_description}{min_notice_description}\n"
        core_instructions += policy_info
        
        # Log final prompt length for monitoring
        logger.info(f"✅ REALTIME PROMPT [business_id={business_id}] LEN={len(core_instructions)} chars")
        
        if len(core_instructions) > 4000:
            logger.warning(f"⚠️ Prompt too long ({len(core_instructions)} chars) - may cause transcription failures!")
        
        return core_instructions
        
    except Exception as e:
        logger.error(f"❌ Error building Realtime prompt: {e}")
        import traceback
        traceback.print_exc()
        
        # Fallback prompt
        return """אתה נציג טלפוני מקצועי.
אתה עונה בעברית, במשפטים קצרים וברורים.
עזור ללקוח לקבוע תור או לענות על שאלות בנוגע לעסק."""


def _build_hours_description(policy) -> str:
    """Build opening hours description in Hebrew"""
    if policy.allow_24_7:
        return "- פתוח 24/7 - אפשר לקבוע תור בכל יום ושעה."
    
    hours = policy.opening_hours
    if not hours:
        # ⚠️ NO HOURS DATA - Don't invent anything!
        logger.warning("⚠️ No opening_hours data - omitting from prompt (no invented hours)")
        return "- שעות פעילות לא הוגדרו במערכת."
    
    # 🔍 DEBUG: Log the raw hours data
    logger.info(f"📊 [DEBUG] policy.opening_hours = {hours}")
    
    # Hebrew day names
    day_names = {
        "sun": "ראשון",
        "mon": "שני",
        "tue": "שלישי",
        "wed": "רביעי",
        "thu": "חמישי",
        "fri": "שישי",
        "sat": "שבת"
    }
    
    lines = []
    for day_key in ["sun", "mon", "tue", "wed", "thu", "fri", "sat"]:
        windows = hours.get(day_key, [])
        if not windows:
            lines.append(f"  • {day_names[day_key]}: סגור")
        else:
            # Format: "ראשון: 09:00-22:00"
            time_ranges = ", ".join([f"{w[0]}-{w[1]}" for w in windows])
            lines.append(f"  • {day_names[day_key]}: {time_ranges}")
    
    description = "- שעות פעילות:\n" + "\n".join(lines)
    logger.info(f"📊 [DEBUG] hours_description = {description[:200]}")
    return description


def _build_slot_description(slot_size_min: int) -> str:
    """Build slot size description in Hebrew"""
    if slot_size_min == 15:
        return "קובעים תורים כל רבע שעה (15 דקות)"
    elif slot_size_min == 30:
        return "קובעים תורים כל חצי שעה (30 דקות)"
    elif slot_size_min == 45:
        return "קובעים תורים כל 45 דקות"
    elif slot_size_min == 60:
        return "קובעים תורים כל שעה עגולה (60 דקות)"
    elif slot_size_min == 90:
        return "קובעים תורים כל שעה וחצי (90 דקות)"
    elif slot_size_min == 120:
        return "קובעים תורים כל שעתיים (120 דקות)"
    else:
        return f"קובעים תורים כל {slot_size_min} דקות"


def _build_critical_rules(business_name: str, today_hebrew: str, weekday_hebrew: str, month_hebrew: str, today) -> str:
    """
    Build critical conversation rules - TOP priority instructions (~600 chars)
    
    Enforces:
    - Hebrew only + current date context
    - Brief greeting (1 sentence)
    - Appointment flow with server validation
    - Server event handling
    - Silence handling (no unnecessary talk)
    """
    return f"""⚠️ עברית בלבד! היום: {today_hebrew} ({weekday_hebrew})

🎯 חוקים קריטיים:

1. פתיח: משפט אחד בלבד! "שלום מ-{business_name}, איך אפשר לעזור?"

2. תורים - סדר חובה:
   • שאל שם מלא
   • בקש טלפון: "הקש בכפתורי הסולמית (#)"
   • הצע תאריך/שעה
   • המתן לאישור השרת - אל תאשר בעצמך!

3. הודעות [SERVER]:
   המערכת שולחת לך הודעות [SERVER] - חובה לציית!
   • "פנוי" → תגיד "פנוי, מתאים?"
   • "תפוס" → הצע זמן אחר
   • "✅ נקבע" → תגיד "התור נקבע!"
   • "חסר שם/טלפון" → שאל שוב
   
4. שקט: אם אין קול >5 שניות, אל תדבר! רק אם >15 שניות: "אתה שם?"

"""
