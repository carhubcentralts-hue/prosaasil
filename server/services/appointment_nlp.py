"""
Appointment NLP Parser - Compact & Dynamic
BUILD 182: Optimized for speed with minimal prompt
"""
import os
import json
import logging
from typing import Optional, Dict
from datetime import datetime, timedelta
import pytz
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def _build_compact_prompt(today_str: str, weekday_hebrew: str, tomorrow_str: str) -> str:
    """Build minimal system prompt - no business-specific data leaked"""
    return f"""מנתח שיחות עברית לקביעת תורים. היום: {today_str} ({weekday_hebrew})

החזר JSON:
{{"action":"hours_info|ask|confirm|none","date":"YYYY-MM-DD|null","time":"HH:MM|null","name":"שם|null","confidence":0.0-1.0}}

actions:
- hours_info: שאלה על שעות פעילות (לא תור!)
- ask: בקשת זמינות לתאריך/שעה
- confirm: לקוח אישר (כן/בסדר/מושלם) + יש שם + יש תאריך+שעה
- none: אין בקשה

כללים:
1. חפש תאריך/שעה בכל השיחה (לא רק הודעה אחרונה)
2. "מחר"={tomorrow_str}, שעות: "בשש"=18:00, "בשבע וחצי"=19:30
3. שם כללי (לקוח/אדון/גברת)=null
4. confirm רק אחרי אישור מפורש (כן/בסדר/מושלם/אוקיי/מתאים)"""


async def extract_appointment_request(conversation_history: list, business_id: int) -> Optional[Dict]:
    """
    Extract appointment details from Hebrew conversation using GPT-4o-mini
    
    Returns: {"action", "date", "time", "name", "confidence"}
    """
    try:
        # Format last 8 messages (optimized from 10)
        formatted = []
        for msg in conversation_history[-8:]:
            if 'speaker' in msg and 'text' in msg:
                label = "לקוח" if msg['speaker'] == 'user' else "נציג"
                formatted.append(f"{label}: {msg['text']}")
            elif 'user' in msg:
                formatted.append(f"לקוח: {msg['user']}")
                if msg.get('bot'):
                    formatted.append(f"נציג: {msg['bot']}")
        
        conversation_text = "\n".join(formatted)
        
        # Date context
        tz = pytz.timezone('Asia/Jerusalem')
        today = datetime.now(tz)
        today_str = today.strftime("%Y-%m-%d")
        weekday_names = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]
        weekday_hebrew = weekday_names[today.weekday()]
        tomorrow_str = (today + timedelta(days=1)).strftime("%Y-%m-%d")
        
        # Compact prompt
        system_prompt = _build_compact_prompt(today_str, weekday_hebrew, tomorrow_str)
        
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"שיחה:\n{conversation_text}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=150  # Reduced from 200
        )
        
        result = json.loads(response.choices[0].message.content or "{}")
        
        logger.info(f"[NLP] action={result.get('action')} date={result.get('date')} time={result.get('time')} name={result.get('name')}")
        return result
        
    except Exception as e:
        logger.error(f"[NLP] Error: {e}")
        return {"action": "none", "date": None, "time": None, "name": None, "confidence": 0.0}
