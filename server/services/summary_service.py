"""
Summary Service - AI-powered conversation summarization
שירות סיכום חכם - סיכום שיחות עם GPT
"""
import os
import logging
from typing import Optional

log = logging.getLogger(__name__)

def summarize_conversation(transcription: str, call_sid: Optional[str] = None) -> str:
    """
    סיכום חכם וקצר של שיחה (10-30 מילים)
    
    Args:
        transcription: התמלול המלא של השיחה
        call_sid: מזהה שיחה ללוגים
        
    Returns:
        סיכום קצר בעברית (10-30 מילים)
    """
    if not transcription or len(transcription.strip()) < 10:
        return "שיחה קצרה ללא תוכן"
    
    try:
        from openai import OpenAI
        
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # פרומפט לסיכום קצר וממוקד
        prompt = f"""סכם את השיחה הבאה בעברית בקצרה (10-30 מילים בלבד).
        
התמקד ב:
- מה הלקוח רוצה/חיפש
- פרטים חשובים (אזור, תקציב, סוג נכס)
- האם קבעו פגישה או יש צורך במעקב

תמלול:
{transcription}

סיכום קצר:"""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # מודל מהיר וזול
            messages=[
                {"role": "system", "content": "אתה מומחה לסיכום שיחות נדל\"ן בעברית. תענה תמיד בעברית, בצורה קצרה וממוקדת."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=80,  # מספיק ל-30 מילים בעברית
            temperature=0.3  # יציבות גבוהה
        )
        
        summary = response.choices[0].message.content
        if summary:
            summary = summary.strip()
            log.info(f"✅ Summary generated for {call_sid}: {len(summary)} chars")
            return summary
        else:
            log.warning(f"⚠️ Empty summary for {call_sid}")
            return "לא ניתן לסכם"
            
    except Exception as e:
        log.error(f"❌ Summary generation failed for {call_sid}: {e}")
        # fallback - החזר קטע ראשון מהתמלול
        return _fallback_summary(transcription)

def _fallback_summary(transcription: str) -> str:
    """סיכום fallback פשוט - 30 מילים ראשונות"""
    words = transcription.strip().split()
    if len(words) <= 30:
        return transcription.strip()
    
    summary = " ".join(words[:30]) + "..."
    return summary

def extract_lead_info(transcription: str) -> dict:
    """
    חילוץ מידע חשוב מהשיחה (אזור, סוג נכס, תקציב)
    
    Args:
        transcription: התמלול המלא
        
    Returns:
        dict עם: {area, property_type, budget, intent}
    """
    if not transcription or len(transcription.strip()) < 10:
        return {}
    
    try:
        from openai import OpenAI
        
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        prompt = f"""חלץ מידע מהשיחה הבאה:

תמלול:
{transcription}

החזר JSON בפורמט:
{{
  "area": "אזור מבוקש או null",
  "property_type": "דירה/בית/משרד או null",
  "budget": "תקציב או טווח או null",
  "intent": "מכירה/השכרה או null",
  "meeting_scheduled": true/false
}}
"""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "אתה מומחה לחילוץ מידע מנדל\"ן. החזר רק JSON תקין."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
            temperature=0.1
        )
        
        import json
        result = json.loads(response.choices[0].message.content)
        log.info(f"✅ Lead info extracted: {result}")
        return result
        
    except Exception as e:
        log.error(f"❌ Lead info extraction failed: {e}")
        return {}
