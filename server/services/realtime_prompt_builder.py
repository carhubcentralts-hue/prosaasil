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
        if db_session:
            business = db_session.query(Business).get(business_id)
            settings = db_session.query(BusinessSettings).filter_by(tenant_id=business_id).first()
        else:
            business = Business.query.get(business_id)
            settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
        
        if not business:
            raise ValueError(f"Business {business_id} not found")
        
        business_name = business.name or "העסק"
        
        # Load business policy (slot size, opening hours, etc.)
        custom_prompt = settings.ai_prompt if settings else None
        policy = get_business_policy(business_id, prompt_text=custom_prompt, db_session=db_session)
        
        logger.info(f"📋 Building Realtime prompt for {business_name} (business_id={business_id})")
        
        # Build opening hours description in Hebrew
        hours_description = _build_hours_description(policy)
        
        # Build slot size description in Hebrew
        slot_description = _build_slot_description(policy.slot_size_min)
        
        # Build min notice description
        min_notice_description = ""
        if policy.min_notice_min > 0:
            min_notice_hours = policy.min_notice_min // 60
            if min_notice_hours > 0:
                min_notice_description = f"- דורשים הזמנה מראש של לפחות {min_notice_hours} שעות.\n"
            else:
                min_notice_description = f"- דורשים הזמנה מראש של לפחות {policy.min_notice_min} דקות.\n"
        
        # Build core instructions
        core_instructions = f"""אתה נציג טלפוני אנושי ומקצועי של העסק "{business_name}".
אתה עונה בעברית, בקול טבעי, במשפטים קצרים וברורים.

🎯 חוקים לקביעת תור - ⚠️ אלה השעות האמיתיות של העסק:
{hours_description}
- {slot_description}
{min_notice_description}- ⚠️ אלה הן שעות הפעילות האמיתיות - אסור לך להמציא שעות אחרות!
- תן שעות פנויות רק מתוך הטווח הזה.
- תמיד תשאל קודם: "לאיזה יום ושעה נוח לך?" ורק אחרי תשובה תבדוק זמינות.
- אסור להקריא רשימת כל השעות הפנויות, רק להציע עד 2 חלופות קרובות.
- אסור לקבוע תור מחוץ לשעות הפעילות.

🚫 אסורים מוחלטים - חוקי אמת:
- אסור לומר "קבעתי", "שריינתי", "התור נקבע" אלא אם השרת באמת ביצע את הפעולה.
- אסור לומר "שלחתי פרטים", "שלחתי ווטסאפ", "תקבל אישור" - זה לא קורה בשיחת טלפון!
- אם אינך בטוח אם נוצר תור - תגיד: "אני רושם את הבקשה, ופרטים מדויקים יישלחו בהמשך."
- השרת סופית שולט - אתה לא. אל תשקר ללקוח.

📞 לגבי מספר טלפון:
- כדי לקבל מספר טלפון תגיד: "תקליד/י את המספר במקלדת ואז הקש/י סולמית (#)."
- אל תנסה לכתוב את המספר בעברית - רק תבקש הקלדה.

🗣️ התנהגות בשיחה - דיוק ובהירות:
- תשובות קצרות ומדויקות - עד 3 משפטים קצרים.
- אם לא הבנת מה הלקוח אמר - אל תענה תשובה אחרת!
- בקש הבהרה במשפט קצר: "לא בטוח ששמעתי טוב, אפשר לחזור על זה?"
- אל תגיד "לא הבנתי" מיד - תן לאדם להרגיש נעים.
- אל תדבר על תהליכים פנימיים ("אני בודק במערכת", "אני שולח הודעה").
- פשוט תגיד מה קורה: "יש מקום ביום שלישי בשעה 3" (אבל רק אם זה אמת!).
- סיים כל משפט לפני שתתחיל חדש - אל תעצור באמצע משפט!

⏱️ זמנים והיום:
- היום הוא {datetime.now(pytz.timezone('Asia/Jerusalem')).strftime('%A, %d/%m/%Y')}.
- השעה עכשיו היא {datetime.now(pytz.timezone('Asia/Jerusalem')).strftime('%H:%M')}.
"""
        
        # Add custom business prompt if exists
        if custom_prompt and custom_prompt.strip():
            core_instructions += f"\n\n📝 מידע נוסף על העסק:\n{custom_prompt.strip()}\n"
        
        logger.info(f"✅ Built prompt: {len(core_instructions)} chars")
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
        return "- פתוח ראשון עד חמישי מ-09:00 עד 22:00."
    
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
