"""
Time Parser - ניתוח זמנים ותאריכים מעברית
מנתח ביטויים כמו "מחר ב-10", "יום שלישי בבוקר", "היום אחרי הצהריים"
"""
import re
from datetime import datetime, timedelta
from typing import Optional, Tuple

def parse_hebrew_time(text: str) -> Optional[Tuple[datetime, datetime]]:
    """
    מנתח ביטוי זמן עברי ומחזיר (start_time, end_time)
    
    Args:
        text: טקסט השיחה
        
    Returns:
        Tuple[datetime, datetime] או None אם לא נמצא זמן
    """
    if not text:
        return None
    
    text_lower = text.lower()
    now = datetime.now()
    
    # ✅ DEBUG: הדפס מה אנחנו מנתחים
    print(f"🔍 TIME_PARSER: Analyzing text: '{text[:100]}...'")
    
    # ✅ 🚨 CRITICAL: סינון סירובים - אם המשתמש אמר "לא", אין פגישה!
    rejection_phrases = [
        'לא תודה', 'לא רוצה', 'לא מעוניין', 'לא צריך', 'לא נוח לי',
        'אני לא', 'לא יכול', 'לא מתאים', 'לא בשביל', 'תודה לא',
        'אין צורך', 'לא ברור', 'אני מוותר', 'ביי', 'להתראות',
        'לא נראה לי', 'כרגע לא', 'עדיין לא', 'אולי פעם אחרת'
    ]
    
    # בדוק אם יש סירוב בטקסט
    for rejection in rejection_phrases:
        if rejection in text_lower:
            print(f"🚫 TIME_PARSER: REJECTION detected - '{rejection}' found in text. NO MEETING!")
            return None
    
    # ✅ ניתוח תאריך (יחסי)
    target_date = now
    days_ahead = 1  # Default: מחר
    
    # ✅ FIX: Check more specific patterns first (מחרתיים before מחר)
    
    # מחרתיים / יומיים (check first!)
    if any(word in text_lower for word in ['מחרתיים', 'יומיים']):
        days_ahead = 2
    
    # מחר (only if not מחרתיים)
    elif 'מחר' in text_lower and 'מחרתיים' not in text_lower:
        days_ahead = 1
    
    # היום
    elif any(word in text_lower for word in ['היום', 'עכשיו', 'בעוד שעה']):
        days_ahead = 0
        target_date = now
    
    # ימים ספציפיים
    elif 'שלושה ימים' in text_lower or '3 ימים' in text_lower:
        days_ahead = 3
    elif 'ארבעה ימים' in text_lower or '4 ימים' in text_lower:
        days_ahead = 4
    
    # ימים בשבוע (ראשון = 6, שני = 0, ...)
    weekday_map = {
        'ראשון': 6,
        'שני': 0,
        'שלישי': 1,
        'רביעי': 2,
        'חמישי': 3,
        'שישי': 4,
        'שבת': 5
    }
    
    for day_name, target_weekday in weekday_map.items():
        if f'יום {day_name}' in text_lower or f'ב{day_name}' in text_lower:
            # חשב כמה ימים עד היום המבוקש
            current_weekday = now.weekday()
            days_until = (target_weekday - current_weekday) % 7
            if days_until == 0:
                days_until = 7  # אם זה היום, קפוץ לשבוע הבא
            days_ahead = days_until
            break
    
    # חשב את התאריך הסופי
    target_date = now + timedelta(days=days_ahead)
    
    # דלג על שבת (אלא אם זה מפורש)
    if target_date.weekday() == 5 and 'שבת' not in text_lower:
        target_date = target_date + timedelta(days=1)  # דחוף ליום ראשון
    
    # ✅ ניתוח שעה
    hour = None
    minute = 0
    
    # דפוסי שעה ספציפיים: "10:00", "10:30", "ב-10", "בשעה 14"
    time_patterns = [
        (r'(?:בשעה\s+|ב-?)(\d{1,2}):(\d{2})', lambda m: (int(m.group(1)), int(m.group(2)))),
        (r'(?:בשעה\s+|ב-?)(\d{1,2})(?:\s+בדיוק|\s+ב)', lambda m: (int(m.group(1)), 0)),
        (r'(\d{1,2}):(\d{2})', lambda m: (int(m.group(1)), int(m.group(2)))),
        (r'ב-?(\d{1,2})(?:\s|$)', lambda m: (int(m.group(1)), 0)),
    ]
    
    for pattern, extractor in time_patterns:
        match = re.search(pattern, text_lower)
        if match:
            hour, minute = extractor(match)
            break
    
    # אם לא נמצאה שעה ספציפית, השתמש בביטויים כלליים
    if hour is None:
        if any(word in text_lower for word in ['בוקר', 'בבוקר', 'ב10', 'ב9', 'ב8']):
            hour = 10  # ברירת מחדל לבוקר
        elif any(word in text_lower for word in ['צהריים', 'בצהריים', '12', 'ב12']):
            hour = 12
        elif any(word in text_lower for word in ['אחר הצהריים', 'אחה"צ', '14', '15', 'ב2', 'ב3']):
            hour = 14
        elif any(word in text_lower for word in ['ערב', 'בערב', '18', '19', 'ב6', 'ב7']):
            hour = 18
        else:
            # Default: אם לא צוין, תלוי בשעה עכשיו
            if now.hour < 12:
                hour = 10  # בוקר
            elif now.hour < 17:
                hour = 14  # אחה"צ
            else:
                hour = 10  # מחר בבוקר
                days_ahead += 1
                target_date = now + timedelta(days=days_ahead)
    
    # ✅ וודא שעה חוקית (9-20)
    if hour < 9:
        hour = 9
    elif hour > 20:
        hour = 20
    
    # ✅ בנה את הזמן הסופי
    meeting_time = target_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
    
    # אם הזמן עבר (אם זה היום והשעה כבר עברה), דחוף למחר
    if meeting_time < now:
        meeting_time = meeting_time + timedelta(days=1)
        # דלג על שבת שוב
        if meeting_time.weekday() == 5:
            meeting_time = meeting_time + timedelta(days=1)
    
    end_time = meeting_time + timedelta(hours=1)  # פגישה של שעה
    
    # ✅ DEBUG: הדפס מה מצאנו
    print(f"✅ TIME_PARSER: Parsed meeting time: {meeting_time.strftime('%Y-%m-%d %H:%M')} (end: {end_time.strftime('%H:%M')})")
    
    return (meeting_time, end_time)


def get_meeting_time_from_conversation(conversation_history: list) -> Optional[Tuple[datetime, datetime]]:
    """
    מנתח את כל השיחה ומחפש זמן פגישה מוסכם
    
    Args:
        conversation_history: רשימת תורות שיחה [{'user': '...', 'bot': '...'}]
        
    Returns:
        (start_time, end_time) או None
    """
    if not conversation_history:
        return None
    
    # 🚨 CRITICAL: בדוק תחילה אם התור האחרון הוא סירוב!
    if conversation_history:
        last_turn = conversation_history[-1]
        last_user_text = last_turn.get('user', '').lower()
        
        # סירובים חזקים שמבטלים את כל הפגישה
        strong_rejections = [
            'לא תודה', 'לא רוצה', 'לא מעוניין', 'תודה לא', 
            'ביי', 'להתראות', 'שלום', 'אני לא'
        ]
        
        for rejection in strong_rejections:
            if rejection in last_user_text:
                print(f"🚫 CONVERSATION: Last turn is REJECTION - '{rejection}'. NO MEETING!")
                return None
    
    # בדוק את התורות האחרונים (5 תורות אחרונים) - שם בדרך כלל נקבע זמן
    recent_turns = conversation_history[-5:]
    
    for turn in reversed(recent_turns):
        user_text = turn.get('user', '')
        bot_text = turn.get('bot', '')
        
        # ✅ BUILD 110: הרחבת ביטויי אישור - כיסוי כל האפשרויות!
        confirmation_phrases = [
            'נקבע ל', 'נקבע לך פגישה ל', 'אראה אותך ב', 'אקבע ל', 
            'מצוין! ל', 'מצוין! נקבע', 'נפגש ב', 'פגישה ב', 
            'אשמח לראות אותך ב', 'קבעתי לך פגישה ל', 'קבענו ל',
            'בוא ב', 'מחכה לך ב', 'אני מזמין אותך ל'
        ]
        
        # חפש אישור זמן מהבוט (זה אומר שהזמן הוסכם)
        bot_confirmed = any(phrase in bot_text for phrase in confirmation_phrases)
        
        # ✅ FIX: נסה תמיד את תשובת המשתמש תחילה - היא הכי אמינה!
        if user_text:
            result = parse_hebrew_time(user_text)
            if result:
                print(f"✅ Found meeting time in USER text: {result[0]}")
                return result
        
        # אם יש אישור מהבוט, נסה לנתח את תגובת הבוט
        if bot_confirmed:
            result = parse_hebrew_time(bot_text)
            if result:
                print(f"✅ Found meeting time in BOT confirmation: {result[0]}")
                return result
    
    # אם לא נמצא זמן מוסכם, נסה בכל השיחה
    full_conversation = ' '.join([turn.get('user', '') + ' ' + turn.get('bot', '') for turn in conversation_history])
    return parse_hebrew_time(full_conversation)


def format_meeting_time_hebrew(meeting_time: datetime) -> str:
    """
    מעצב זמן פגישה לעברית בצורה קריאה
    
    Args:
        meeting_time: זמן הפגישה
        
    Returns:
        מחרוזת כמו "מחר בשעה 10:00" או "יום רביעי ב-14:30"
    """
    now = datetime.now()
    days_diff = (meeting_time.date() - now.date()).days
    
    # קביעת "מתי"
    if days_diff == 0:
        day_part = "היום"
    elif days_diff == 1:
        day_part = "מחר"
    elif days_diff == 2:
        day_part = "מחרתיים"
    else:
        # שם היום בשבוע
        weekday_names = ['שני', 'שלישי', 'רביעי', 'חמישי', 'שישי', 'שבת', 'ראשון']
        day_name = weekday_names[meeting_time.weekday()]
        day_part = f"יום {day_name}"
    
    # שעה
    time_str = meeting_time.strftime("%H:%M")
    
    return f"{day_part} בשעה {time_str}"
