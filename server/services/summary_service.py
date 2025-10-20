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
            word_count = len(summary.split())
            
            # ✅ Validation: verify word count (target 80-150, accept 70-180 with warning)
            if word_count < 70:
                log.warning(f"⚠️ Summary too short ({word_count} words) for {call_sid} - using fallback")
                return _fallback_summary(transcription)
            elif word_count < 80:
                log.warning(f"⚠️ Summary slightly short ({word_count} words) for {call_sid} - acceptable")
            elif word_count > 180:
                log.warning(f"⚠️ Summary too long ({word_count} words) for {call_sid} - truncating to 150")
                words = summary.split()
                summary = " ".join(words[:150]) + "..."
            elif word_count > 150:
                log.warning(f"⚠️ Summary slightly long ({word_count} words) for {call_sid} - acceptable")
            
            log.info(f"✅ Summary generated for {call_sid}: {word_count} words, {len(summary)} chars")
            return summary
        else:
            log.warning(f"⚠️ Empty summary for {call_sid}")
            return _fallback_summary(transcription)
            
    except Exception as e:
        log.error(f"❌ Summary generation failed for {call_sid}: {e}")
        # fallback - סיכום מובנה גם במקרה של שגיאה
        return _fallback_summary(transcription)

def _fallback_summary(transcription: str) -> str:
    """
    ✅ סיכום fallback מובנה (במקרה של כשל ב-AI)
    מנסה לחלץ מידע בסיסי מהתמלול עצמו
    """
    words = transcription.strip().split()
    
    # ✅ Build structured fallback summary (target 80+ words)
    summary_parts = []
    text_lower = transcription.lower()
    
    # 1. סוג פנייה
    if any(word in text_lower for word in ['לקנות', 'קונה', 'מעוניין לרכוש']):
        summary_parts.append("**סוג הפנייה**: הלקוח מעוניין לרכוש נכס")
    elif any(word in text_lower for word in ['לשכור', 'שוכר', 'להשכיר']):
        summary_parts.append("**סוג הפנייה**: הלקוח מעוניין לשכור נכס")
    else:
        summary_parts.append("**סוג הפנייה**: פנייה כללית לנדל\"ן")
    
    # 2. תוכן השיחה (כולל פרטים מהתמלול)
    if len(words) >= 80:
        # תמלול ארוך - 70 מילים מהתחלה
        content = " ".join(words[:70])
        summary_parts.append(f"\n\n**תוכן השיחה**: {content}...")
    elif len(words) >= 40:
        # תמלול בינוני - כל התמלול + padding
        summary_parts.append(f"\n\n**תוכן השיחה**: {transcription.strip()}")
        summary_parts.append("\n\n**פרטי הנכס**: לא צוינו פרטים מלאים בשיחה")
    else:
        # תמלול קצר מאוד - padding נוסף
        summary_parts.append(f"\n\n**תוכן השיחה**: {transcription.strip()}")
        summary_parts.append("\n\n**פרטי הנכס**: המידע בשיחה היה מוגבל, יש צורך במעקב נוסף")
        summary_parts.append("\n\n**פרטי קשר**: לא נמסרו פרטי קשר מפורשים")
    
    # 3. סטטוס ומעקב (padding לקבלת 80+ מילים)
    summary_parts.append("\n\n**סטטוס ומעקב**: לא נקבעה פגישה. מומלץ לחזור ללקוח ולקבל פרטים נוספים על הנכס המבוקש, התקציב, והזמינות לפגישת ייעוץ.")
    
    # 4. הערה
    summary_parts.append("\n\n**הערה**: סיכום אוטומטי (מערכת AI זמנית לא זמינה)")
    
    fallback = "\n".join(summary_parts)
    word_count = len(fallback.split())
    log.info(f"📋 Fallback summary created: {word_count} words")
    return fallback

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
