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
    סיכום מקצועי ומפורט של שיחה - כולל כל הפרטים החשובים
    
    Args:
        transcription: התמלול המלא של השיחה
        call_sid: מזהה שיחה ללוגים
        
    Returns:
        סיכום מקצועי בעברית (80-150 מילים) עם כל הפרטים
    """
    if not transcription or len(transcription.strip()) < 10:
        return "שיחה קצרה ללא תוכן"
    
    try:
        from openai import OpenAI
        
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # ✅ פרומפט מקצועי ומפורט - BUILD 106
        prompt = f"""סכם את השיחה הבאה בעברית בצורה **מקצועית ומפורטת** (80-150 מילים).

📋 מבנה הסיכום הנדרש:

1. **סוג הפנייה**: מה הלקוח מחפש? (מכירה/השכרה/ייעוץ)

2. **פרטי הנכס המבוקש**:
   - סוג נכס: (דירה/בית/משרד/קרקע)
   - אזור/עיר: (מה האזור המועדף?)
   - תקציב: (כולל טווח מחירים - חשוב לציין מיליון/אלף!)
   - מספר חדרים: (אם צוין)
   - גודל: (מ"ר אם צוין)
   - דרישות מיוחדות: (חניה, ממ"ד, מעלית וכו')

3. **פרטי קשר**:
   - שם הלקוח: (אם נמסר)
   - טלפון: (אם צוין במפורש)
   - איך ליצור קשר: (מייל, טלפון, WhatsApp)

4. **סטטוס ומעקב**:
   - האם נקבעה פגישה? (אם כן - מתי ובאיזו שעה?)
   - דחיפות: (גבוהה/בינונית/נמוכה)
   - פעולות מעקב נדרשות: (התקשרות חוזרת, שליחת נכסים, וכו')

5. **הערות נוספות**: כל מידע חשוב שצוין בשיחה

תמלול השיחה:
{transcription}

📝 **סיכום מקצועי**:"""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # מודל מהיר וזול
            messages=[
                {"role": "system", "content": "אתה מומחה סיכום שיחות נדל\"ן בעברית. תכתוב סיכומים **מקצועיים, מפורטים ומובנים** שמכילים את כל המידע החשוב מהשיחה. השתמש בפורמט ברור עם כותרות וסעיפים."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,  # ✅ מספיק ל-150 מילים מפורטות בעברית
            temperature=0.2  # יציבות גבוהה - סיכומים עקביים
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
