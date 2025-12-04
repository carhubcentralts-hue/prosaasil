"""
Appointment NLP Parser using GPT-4o-mini
Extracts appointment details from Hebrew conversation
"""
import os
import logging
from typing import Optional, Dict
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


async def extract_appointment_request(conversation_history: list, business_id: int) -> Optional[Dict]:
    """
    Extract appointment details from conversation using GPT-4o-mini
    
    Args:
        conversation_history: List of {"speaker": "ai"|"user", "text": str}
        business_id: Business ID for context
    
    Returns:
        {
            "action": "hours_info" | "ask" | "confirm" | "none",
            "date": ISO string or null,
            "time": "HH:MM" or null,
            "name": str or null,
            "confidence": 0.0-1.0
        }
        
    Action types:
        - "hours_info": User asking for business hours/general info (NOT appointment)
        - "ask": User asking for specific date/time availability
        - "confirm": User confirming an appointment
        - "none": No appointment-related action
    """
    print(f"🔍 [NLP ENTRY] extract_appointment_request called")
    print(f"🔍 [NLP ENTRY] business_id={business_id}, history_length={len(conversation_history)}")
    try:
        # Build conversation text - support both old and new formats
        formatted_messages = []
        for msg in conversation_history[-10:]:  # Last 10 messages
            # Handle new format: {"speaker": "user/ai", "text": "..."}
            if 'speaker' in msg and 'text' in msg:
                speaker_label = "לקוח" if msg['speaker'] == 'user' else "נציג"
                formatted_messages.append(f"{speaker_label}: {msg['text']}")
            # Handle old format: {"user": "...", "bot": "..."}
            elif 'user' in msg and 'bot' in msg:
                formatted_messages.append(f"לקוח: {msg['user']}\nנציג: {msg['bot']}")
            # Handle partial old format (just user or just bot)
            elif 'user' in msg:
                formatted_messages.append(f"לקוח: {msg['user']}")
            elif 'bot' in msg:
                formatted_messages.append(f"נציג: {msg['bot']}")
        
        conversation_text = "\n".join(formatted_messages)
        print(f"🔍 [NLP] Formatted {len(formatted_messages)} messages for GPT-4o-mini")
        print(f"🔍 [NLP] Conversation text: {conversation_text[:200]}...")
        
        # Get current date for context
        from datetime import datetime, timedelta
        import pytz
        tz = pytz.timezone('Asia/Jerusalem')
        today = datetime.now(tz)
        today_str = today.strftime("%Y-%m-%d")  # e.g., "2025-11-17"
        # Python weekday: Mon=0, Tue=1, Wed=2, Thu=3, Fri=4, Sat=5, Sun=6
        # Hebrew: ראשון=Sun, שני=Mon, שלישי=Tue, רביעי=Wed, חמישי=Thu, שישי=Fri, שבת=Sat
        weekday_hebrew = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"][today.weekday()]
        tomorrow_str = (today + timedelta(days=1)).strftime("%Y-%m-%d")
        
        # Calculate next Sunday for examples
        days_until_sunday = (6 - today.weekday()) % 7  # Days until next Sunday
        if days_until_sunday == 0:
            days_until_sunday = 7  # If today is Sunday, get next Sunday
        next_sunday = (today + timedelta(days=days_until_sunday)).strftime("%Y-%m-%d")
        
        # Call GPT-4o-mini for extraction
        print(f"🔍 [NLP] Calling GPT-4o-mini with model=gpt-4o-mini, temperature=0.1")
        logger.info(f"🔍 [NLP VERIFICATION] Using model=gpt-4o-mini, temperature=0.1 for appointment parsing")
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": f"""אתה מנתח שיחות בעברית ומחלץ בקשות לקביעת פגישה.
התאריך היום: {today_str} (יום {weekday_hebrew})

🔥 זרימת קביעת תור (שלב אחר שלב):
1. לקוח מבקש תאריך/שעה → action="ask"
2. נציג מאשר "פנוי!" → לקוח ממשיך
3. נציג שואל "על איזה שם?" → לקוח עונה שם
4. נציג שואל לאשר (זה בסדר? / מתאים?) → לקוח אומר "כן"/"בסדר"/"מושלם" → action="confirm"
5. אם נציג ביקש טלפון/DTMF - גם זה מפעיל action="confirm"

⚠️ CRITICAL: action="confirm" אם:
- יש תאריך/שעה בשיחה (חפש בכל ההיסטוריה - לא רק בהודעה האחרונה!)
- יש שם לקוח (לא כללי!)
- AND אחד מהבאים:
  * לקוח אישר במילה כמו: "כן", "בסדר", "מושלם", "מעולה", "בדיוק", "אחלה", "טוב", "אוקיי"
  * או נציג ביקש טלפון ויש DTMF

🔥 IMPORTANT: חפש תאריך ושעה בכל השיחה, לא רק בהודעה האחרונה!
אם הלקוח אמר "מחר בשש" בהודעה קודמת ועכשיו מאשר - עדיין החזר את התאריך והשעה!

החזר JSON בלבד עם השדות:
- action: 
  * "hours_info" - לקוח שואל על שעות פעילות/מידע כללי (לא רוצה לקבוע תור!)
  * "ask" - לקוח שואל על זמינות לתאריך/שעה ספציפיים
  * "confirm" - לקוח אישר + יש שם + יש טלפון/DTMF (שלב אחרון!)
  * "none" - אין בקשה
- date: תאריך בפורמט ISO (YYYY-MM-DD) או null. חשב לפי התאריך הנוכחי ({today_str}).
  דוגמאות: "מחר" = {tomorrow_str}, "יום חמישי הקרוב" = חשב מ-{today_str}.
- time: שעה בפורמט HH:MM (24 שעות) או null. "בשש" = 18:00, "בשבע וחצי" = 19:30, "ב-4" = 16:00.
- name: שם הלקוח או null. אם השם הוא "לקוח", "אדון", "גברת" או כללי - החזר null!
- confidence: רמת ודאות (0.0-1.0)

🔥 CRITICAL: הבחן בין שאלות מידע לבקשות תור:
- "מה השעות שלכם?" / "מתי אתם פתוחים?" / "תעבדו מחר?" → "hours_info" (לא רוצה תור!)
- "יש פנוי ביום ראשון בשש?" / "אפשר לקבוע?" → "ask" (רוצה לבדוק זמינות)

🔥 חישוב תאריכים (היום: {today_str}, {weekday_hebrew}):
- "מחר" = {tomorrow_str}
- "יום ראשון" / "ביום ראשון" = {next_sunday} (ראשון הקרוב!)
- "השבוע" = תאריך השבוע הנוכחי
- "שבוע הבא" = תאריך שבוע הבא

דוגמאות:
לקוח: "מה השעות פעילות שלכם?"
→ {{"action":"hours_info","date":null,"time":null,"name":null,"confidence":1.0}}

לקוח: "אפשר ליום ראשון בשבע?"
→ {{"action":"ask","date":"{next_sunday}","time":"19:00","name":null,"confidence":0.9}}

נציג: "על איזה שם?"
לקוח: "שמי דוד"
→ {{"action":"none","date":"{next_sunday}","time":"19:00","name":"דוד","confidence":1.0}}

נציג: "אז יש לנו תור ליום ראשון בשבע על שם דוד. זה בסדר?"
לקוח: "כן"
→ {{"action":"confirm","date":"{next_sunday}","time":"19:00","name":"דוד","confidence":1.0}}

שיחה מלאה עם אישור:
לקוח: "רוצה לקבוע תור למחר בשש"
נציג: "מעולה! הזמן פנוי. על איזה שם?"
לקוח: "על שם שרה"
נציג: "מצוין שרה, אז יש לנו תור למחר בשש. זה בסדר?"
לקוח: "כן, מושלם"
→ {{"action":"confirm","date":"{tomorrow_str}","time":"18:00","name":"שרה","confidence":1.0}}

שיחה עם DTMF:
נציג: "אפשר מספר טלפון?"
לקוח: "[DTMF keys pressed: +972504294724]"
→ {{"action":"confirm","date":"{tomorrow_str}","time":"18:00","name":"שרה","confidence":1.0}}"""
                },
                {
                    "role": "user",
                    "content": f"שיחה:\n{conversation_text}\n\nמה הבקשה האחרונה של הלקוח?"
                }
            ],
            response_format={"type": "json_object"},
            temperature=0.1,  # Agent 3 spec: 0.1-0.2 for deterministic extraction
            max_tokens=200
        )
        
        # Parse response
        result_text = response.choices[0].message.content
        print(f"")
        print(f"=" * 60)
        print(f"🔍 [NLP RESULT] GPT-4o-mini extraction complete")
        print(f"=" * 60)
        print(f"📄 [NLP RESULT] Raw response: {result_text}")
        import json
        result = json.loads(result_text or "{}")
        
        print(f"📊 [NLP RESULT] Parsed values:")
        print(f"📊 [NLP RESULT]   - action: {result.get('action', 'N/A')}")
        print(f"📊 [NLP RESULT]   - date: {result.get('date', 'N/A')}")
        print(f"📊 [NLP RESULT]   - time: {result.get('time', 'N/A')}")
        print(f"📊 [NLP RESULT]   - name: {result.get('name', 'N/A')}")
        print(f"📊 [NLP RESULT]   - confidence: {result.get('confidence', 'N/A')}")
        print(f"=" * 60)
        print(f"")
        logger.info(f"📝 [NLP] Extracted: {result}")
        return result
        
    except Exception as e:
        print(f"❌ [NLP] Extraction failed: {e}")
        logger.error(f"❌ [NLP] Extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return {"action": "none", "date": None, "time": None, "name": None, "confidence": 0.0}
