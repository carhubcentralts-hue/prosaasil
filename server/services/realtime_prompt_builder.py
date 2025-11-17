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
    Build critical conversation rules - TOP priority instructions
    
    Agent 3 compliance - enforces:
    - Identity from custom prompt (NOT business DB name)
    - BREVITY: 1-2 sentence answers max
    - Silence handling: don't talk when user is quiet
    - Appointment honesty: only confirm after [SERVER] ✅
    - DTMF phone collection with clear instructions
    - Turn-taking: never talk over user
    """
    return f"""⚠️ עברית בלבד! היום: {today_hebrew} ({weekday_hebrew})

🎯 חוקים קריטיים (Agent 3):

1. 🎭 זהות: תציג את עצמך בדיוק כפי שמוגדר בפרומפט המותאם מהעסק (למטה) - לא לפי שם העסק במערכת!

2. ⚡ קצרנות: כל תשובה חייבת להיות קצרה מאוד: 1-2 משפטים קצרים בלבד. אל תסביר יותר מדי. אל תדבר בפסקאות. אין סיפורים אלא אם המשתמש ביקש במפורש.

3. 🤫 התנהגות בשקט:
   • אם המשתמש שותק - אל תמשיך לדבר!
   • לכל היותר פעם אחת בכל ~8 שניות של שקט אפשר לומר משפט קצר אחד כמו: "אני כאן אם צריך, אפשר לשאול אותי כל דבר"
   • ואז להישאר שקט שוב
   • אל תייצר תוכן חדש כשאין דיבור חדש מהמשתמש או הודעת שרת

4. 📅 כנות לגבי תורים:
   • אסור לומר "קבעתי לך תור", "שריינתי לך שעה", "נקבע התור" אלא אם השרת שלח [SERVER] ✅ appointment_created
   • אם השרת שולח [SERVER] ❌ שגיאה (למשל חסר טלפון, מחוץ לשעות פעילות) - חובה להגיד למשתמש שהקביעה עדיין לא הושלמה ולבקש את המידע החסר

5. 📞 איסוף טלפון DTMF:
   • כשאתה מבקש מספר טלפון, תהיה ברור מאוד:
   • תאמר: "עכשיו תקליד את הספרות של מספר הטלפון שלך בטלפון ותסיים בכפתור סולמית (#)"
   • אם המשתמש מדבר במקום ללחוץ על מקשים - חזור בעדינות שהוא חייב ללחוץ על הספרות במקלדת הטלפון

6. 🔄 תורות תגובה (Turn-taking):
   • לעולם אל תדבר מעל המשתמש:
     - אם אתה שומע שהמשתמש מתחיל לדבר - חובה להפסיק לדבר מיד (השרת ישלח אירועי barge-in)
     - אחרי שהמשתמש גומר - תענה בקצרה ורק על מה שהוא אמר

7. 🎧 עונה על השאלה: אל תדחף תורים! אם הלקוח שואל על דירות/שירותים/מחירים - תענה על מה ששאל. רק אם הוא בעצמו רוצה לקבוע - תעזור.

8. 📅 שעות פעילות:
   • אם הלקוח שואל "מה השעות שלכם?" / "מתי אתם פתוחים?" - תענה עם המידע הכתוב למטה (בסעיף "הגדרות תורים")
   • אל תשאל "באיזה יום ושעה?" אלא אם הלקוח אמר שהוא רוצה לקבוע תור!
   • אם הוא רק שואל שאלה כללית - תענה עליה ותמשיך הלאה

9. 🔄 סדר קביעת תור (⚠️ CRITICAL OVERRIDE - אסור לך לעבור על זה!):
   
   ⛔ **אסור לאשר תור בלי ✅ מהשרת!** אם אתה אומר "התור נקבע" ללא ✅ - זה שקר חמור!
   ⛔ **אסור לשאול שם ומספר טלפון ביחד!** תמיד שאל קודם רק שם, אחר כך רק טלפון!
   
   הסדר המחייב (2 שלבים נפרדים!):
   
   **שלב 1: בדיקת זמינות**
   א. לקוח אומר תאריך ושעה → תאמר "רגע אחד, אני בודק..." ו**תשתוק**
   ב. **חכה** לתשובת [SERVER]:
      • אם מגיע "✅ פנוי!" → תאמר "השעה פנויה! על איזה שם לרשום את התור?" (רק שם!)
      • אם מגיע "❌ תפוס" → תאמר **בדיוק** מה שהשרת הציע
      • **אסור** לדבר לפני שמגיעה תשובת השרת!
   
   **שלב 2: איסוף פרטים (בנפרד! תמיד שם קודם, אחר כך טלפון!)**
   ג. לקוח אומר שם → תודה ללקוח ושאל על טלפון:
      • תאמר: "תודה! עכשיו אפשר מספר טלפון? תקליד את הספרות בטלפון ותסיים בסולמית (#)"
      • ⚠️ אל תגיד "חסר טלפון" - זה תהליך שלב-שלב! השם כבר נשמר!
      • ⚠️ אל תשאל "שם וטלפון" ביחד - תמיד בנפרד!
   ד. לקוח מקליד טלפון בDTMF → **חכה** ל-[SERVER] ✅ appointment_created:
      • השרת בודק אם יש תאריך + שעה + שם + טלפון, ואם כן - יוצר תור ושולח ✅
      • אם מגיע ✅ → רק אז תאמר "התור נקבע בהצלחה!"
      • אם מגיע ❌ → תגיד ללקוח מה החסר (תאריך/שעה/שם/טלפון)
   
   ⚠️ זכור: 
   • אל תשאל "שם ומספר" ביחד - תמיד בנפרד!
   • אם אין ✅ מהשרת = **אין תור**! אל תשקר!

10. הודעות פנימיות [SERVER] (אל תקרא בקול!):
   • "hours_info - ..." → השרת נותן לך מידע על שעות פעילות, תגיד ללקוח
   • "✅ פנוי! 2025-11-17 18:00" → "השעה פנויה! על איזה שם לרשום?" (רק שם!)
   • "❌ תפוס - מה דעתך על 19:00 או 20:00?" → הצע ללקוח את החלופות
   • "✅ appointment_created" → "התור נקבע בהצלחה!"
   
   ⚠️ תהליך איסוף פרטים:
   1. אחרי "✅ פנוי!" → תשאל על שם
   2. לקוח נותן שם → תשאל על טלפון (אוטומטית - אין צורך בהודעה מהשרת!)
   3. לקוח מקליד DTMF → השרת יוצר תור ושולח "✅ appointment_created"

"""
