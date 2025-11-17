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
            "action": "ask" | "confirm" | "none",
            "date": ISO string or null,
            "time": "HH:MM" or null,
            "name": str or null,
            "confidence": 0.0-1.0
        }
    """
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
        
        # Get current date for context
        from datetime import datetime, timedelta
        import pytz
        tz = pytz.timezone('Asia/Jerusalem')
        today = datetime.now(tz)
        today_str = today.strftime("%Y-%m-%d")  # e.g., "2025-11-17"
        weekday_hebrew = ["ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת"][today.weekday()]
        tomorrow_str = (today + timedelta(days=1)).strftime("%Y-%m-%d")
        
        # Call GPT-4o-mini for extraction
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": f"""אתה מנתח שיחות בעברית ומחלץ בקשות לקביעת פגישה.
התאריך היום: {today_str} (יום {weekday_hebrew})

החזר JSON בלבד עם השדות:
- action: "ask" (לקוח שואל על זמינות), "confirm" (לקוח מאשר שעה), או "none" (אין בקשה)
- date: תאריך בפורמט ISO (YYYY-MM-DD) או null. חשב לפי התאריך הנוכחי ({today_str}).
  דוגמאות: "מחר" = {tomorrow_str}, "יום חמישי הקרוב" = חשב מ-{today_str}.
- time: שעה בפורמט HH:MM (24 שעות) או null. "בשש" = 18:00, "בשבע וחצי" = 19:30, "ב-4" = 16:00.
- name: שם הלקוח או null. אם השם הוא "לקוח", "אדון", "גברת" או כללי - החזר null!
- confidence: רמת ודאות (0.0-1.0)

דוגמאות:
לקוח: "אפשר ליום שלישי בשש?"
→ {{"action":"ask","date":"2025-11-19","time":"18:00","name":null,"confidence":0.9}}

נציג: "מעולה, אז ליום שלישי בשש?"
לקוח: "כן, מושלם"
→ {{"action":"confirm","date":"2025-11-19","time":"18:00","name":null,"confidence":0.95}}

לקוח: "שמי דוד"
→ {{"action":"none","date":null,"time":null,"name":"דוד","confidence":1.0}}"""
                },
                {
                    "role": "user",
                    "content": f"שיחה:\n{conversation_text}\n\nמה הבקשה האחרונה של הלקוח?"
                }
            ],
            response_format={"type": "json_object"},
            temperature=0.0,  # Deterministic
            max_tokens=200
        )
        
        # Parse response
        result_text = response.choices[0].message.content
        import json
        result = json.loads(result_text or "{}")
        
        logger.info(f"📝 [NLP] Extracted: {result}")
        return result
        
    except Exception as e:
        logger.error(f"❌ [NLP] Extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return None
