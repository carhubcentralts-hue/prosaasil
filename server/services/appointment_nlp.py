"""
Appointment NLP Parser - EXTRACTION ONLY
=========================================

🎯 PURPOSE: Extract appointment data from conversation history
✅ Contains: Entity extraction rules only
❌ Does NOT contain: Conversation behavior, greetings, flow logic

BUILD 182: Optimized for speed with minimal prompt + phone extraction
"""
import os
import json
import logging
import re
from typing import Optional, Dict
from datetime import datetime, timedelta
import pytz
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

_openai_client: Optional[AsyncOpenAI] = None


def _get_openai_client() -> AsyncOpenAI:
    """
    Lazily construct the OpenAI client.

    IMPORTANT: Never instantiate clients at import-time because it breaks pre-deploy
    import smoke tests and can crash the server if env vars aren't set yet.
    """
    global _openai_client
    if _openai_client is not None:
        return _openai_client

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    _openai_client = AsyncOpenAI(api_key=api_key)
    return _openai_client


def _extract_phone_from_text(text: str) -> Optional[str]:
    """
    Extract Israeli phone number from text using regex
    Fast path - no LLM call needed for phone extraction
    """
    if not text:
        return None
    
    # Israeli phone patterns
    patterns = [
        r'05[0-9]-?[0-9]{3}-?[0-9]{4}',  # 05X-XXX-XXXX or 05XXXXXXXX
        r'\+972-?5[0-9]-?[0-9]{3}-?[0-9]{4}',  # +972-5X-XXX-XXXX
        r'972-?5[0-9]-?[0-9]{3}-?[0-9]{4}',  # 972-5X-XXX-XXXX
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text.replace(' ', ''))
        if match:
            phone = match.group().replace('-', '').replace(' ', '')
            # Normalize to E.164
            if phone.startswith('05'):
                phone = '+972' + phone[1:]
            elif phone.startswith('972'):
                phone = '+' + phone
            logger.info(f"📞 [NLP] Extracted phone from text: {phone}")
            return phone
    
    return None


def _build_compact_prompt(today_str: str, weekday_hebrew: str, tomorrow_str: str) -> str:
    """
    Appointment extraction prompt - extraction rules only.
    
    English instructions, no conversation guidance.
    """
    return f"""Extract appointment data from Hebrew conversation.
Today: {today_str} ({weekday_hebrew})

Return JSON:
{{"action":"hours_info|ask|confirm|none","date":"YYYY-MM-DD|null","time":"HH:MM|null","name":"name|null","phone":"05X...|null","confidence":0.0-1.0}}

Action:
- hours_info: asking about hours (not booking)
- ask: requesting availability
- confirm: confirmed (and has name + date + time)
- none: no appointment action

Entity rules:
1. Search conversation for: date, time, name, phone
2. Date: "today"={today_str}, "tomorrow"={tomorrow_str}
3. Weekday: nearest upcoming date for that weekday
4. Time: "six"=18:00, "seven thirty"=19:30
5. Name: Generic = null (wait for actual name)
6. Phone: Extract Israeli format (05X... or +972-5X...)
7. Confidence: >80% if all required fields present

CRITICAL: This is pure extraction. Never guess if confidence <80%."""


async def extract_appointment_request(conversation_history: list, business_id: int) -> Optional[Dict]:
    """
    Extract appointment details from Hebrew conversation using GPT-4o-mini
    
    Returns: {"action", "date", "time", "name", "phone", "confidence"}
    """
    try:
        # Format last 8 messages (optimized from 10)
        formatted = []
        full_text = ""  # For regex phone extraction
        for msg in conversation_history[-8:]:
            if 'speaker' in msg and 'text' in msg:
                label = "לקוח" if msg['speaker'] == 'user' else "נציג"
                formatted.append(f"{label}: {msg['text']}")
                if msg['speaker'] == 'user':
                    full_text += " " + msg['text']
            elif 'user' in msg:
                formatted.append(f"לקוח: {msg['user']}")
                full_text += " " + msg['user']
                if msg.get('bot'):
                    formatted.append(f"נציג: {msg['bot']}")
        
        conversation_text = "\n".join(formatted)
        
        # 🔥 BUILD 182: Fast regex phone extraction (no LLM needed for this)
        regex_phone = _extract_phone_from_text(full_text)
        
        # Date context
        tz = pytz.timezone('Asia/Jerusalem')
        today = datetime.now(tz)
        today_str = today.strftime("%Y-%m-%d")
        weekday_names = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]
        weekday_hebrew = weekday_names[today.weekday()]
        tomorrow_str = (today + timedelta(days=1)).strftime("%Y-%m-%d")
        
        # Compact prompt
        system_prompt = _build_compact_prompt(today_str, weekday_hebrew, tomorrow_str)
        
        client = _get_openai_client()
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
        
        # 🔥 BUILD 182: Use regex phone if LLM didn't find one
        if not result.get('phone') and regex_phone:
            result['phone'] = regex_phone
            logger.info(f"📞 [NLP] Using regex-extracted phone: {regex_phone}")
        
        logger.info(f"[NLP] ✅ action={result.get('action')} date={result.get('date')} time={result.get('time')} name={result.get('name')} phone={result.get('phone')}")
        return result
        
    except Exception as e:
        logger.error(f"[NLP] Error: {e}")
        return {"action": "none", "date": None, "time": None, "name": None, "phone": None, "confidence": 0.0}
