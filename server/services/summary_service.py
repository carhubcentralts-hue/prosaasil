"""
Summary Service - AI-powered FULLY DYNAMIC conversation summarization
שירות סיכום חכם ודינמי לחלוטין - מזהה כל סוג עסק ושיחה אוטומטית!
BUILD 144 - Universal Dynamic Summaries
"""
import os
import logging
from typing import Optional

log = logging.getLogger(__name__)


def summarize_conversation(
    transcription: str, 
    call_sid: Optional[str] = None,
    business_type: Optional[str] = None,
    business_name: Optional[str] = None
) -> str:
    """
    סיכום דינמי לחלוטין של שיחה - מזהה אוטומטית את סוג השיחה והעסק!
    BUILD 144 - Universal Dynamic Summaries
    BUILD 183 - CRITICAL FIX: Don't hallucinate summaries when no user spoke!
    
    GPT מזהה בעצמו:
    - סוג העסק (כל תחום - המערכת מזהה אוטומטית!)
    - מטרת השיחה
    - פרטים רלוונטיים
    - פעולות נדרשות
    
    Args:
        transcription: התמלול המלא של השיחה
        call_sid: מזהה שיחה ללוגים
        business_type: רמז על סוג העסק (אופציונלי - GPT יזהה בעצמו)
        business_name: שם העסק (אופציונלי)
        
    Returns:
        סיכום מקצועי דינמי בעברית (80-150 מילים)
        Returns EMPTY STRING if no actual user speech occurred!
    """
    # 🔥 BUILD 183: Early exit if no transcription
    if not transcription or len(transcription.strip()) < 10:
        log.info(f"📊 [SUMMARY] Skipping - no/short transcription for call {call_sid}")
        return ""  # Return empty, NOT fake text!
    
    # 🔥 BUILD 183 CRITICAL: Check if USER actually spoke in the conversation
    # If only AI spoke (greeting) but user hung up immediately, don't generate summary!
    user_spoke = False
    user_content_length = 0
    
    # Check if transcript has speaker tags (old format: "לקוח:", "נציג:") or is continuous (new Whisper format)
    has_speaker_tags = any(
        prefix in transcription 
        for prefix in ['לקוח:', 'user:', 'User:', 'Customer:', 'נציג:', 'agent:', 'Agent:']
    )
    
    if has_speaker_tags:
        # OLD FORMAT: Parse by speaker tags
        for line in transcription.split('\n'):
            line = line.strip()
            # Check for user speech markers
            if line.startswith('לקוח:') or line.startswith('user:') or line.startswith('User:') or line.startswith('Customer:'):
                # Extract content after the prefix
                content = line.split(':', 1)[1].strip() if ':' in line else ""
                # Filter out noise/silence markers
                noise_patterns = ['...', '(שקט)', '(silence)', '(noise)', '(רעש)', '(לא שמע)', '(inaudible)']
                if content and len(content) > 2:
                    is_noise = any(noise in content.lower() for noise in noise_patterns)
                    if not is_noise:
                        user_spoke = True
                        user_content_length += len(content)
    else:
        # NEW FORMAT: Continuous transcript without tags (from Whisper)
        # If transcript is long enough, assume real conversation happened
        user_content_length = len(transcription.strip())
        # Consider it a real conversation if > 50 chars (not just greeting)
        if user_content_length > 50:
            user_spoke = True
            log.info(f"📊 [SUMMARY] Continuous transcript detected ({user_content_length} chars), treating as real conversation")
    
    # 🔥 BUILD 183: If no meaningful user speech, return empty (no hallucination!)
    if not user_spoke or user_content_length < 5:
        log.info(f"📊 [SUMMARY] Skipping - NO USER SPEECH detected for call {call_sid} (user_spoke={user_spoke}, content_len={user_content_length})")
        return ""  # CRITICAL: Return empty, don't hallucinate!
    
    log.info(f"📊 Generating universal dynamic summary for call {call_sid} (user_content: {user_content_length} chars)")
    
    try:
        from openai import OpenAI
        
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        business_context = ""
        if business_name:
            business_context = f"\n\nשם העסק: {business_name}"
        if business_type:
            business_context += f"\nתחום העסק (רמז): {business_type}"
        
        prompt = f"""אתה מומחה סיכום שיחות עסקיות בעברית. סכם את השיחה הבאה בצורה **מקצועית, מפורטת ודינמית**.

🎯 **הוראות חשובות:**
1. **זהה אוטומטית** את סוג העסק/השירות מתוכן השיחה עצמה
2. **התאם את מבנה הסיכום** לסוג השיחה שזיהית
3. **חלץ את כל הפרטים הרלוונטיים** לתחום הספציפי
4. **כתוב סיכום שימושי לאיש המכירות/השירות**

📋 **מבנה הסיכום הנדרש (80-150 מילים):**

1. **סוג הפנייה והתחום**: (זהה אוטומטית - מה סוג העסק ומה הלקוח מחפש?)

2. **פרטים ספציפיים**: (התאם לתחום שזיהית!)
   - זהה את התחום אוטומטית וחלץ את הפרטים הרלוונטיים
   - עבור שירותים: סוג השירות, מיקום, דחיפות
   - עבור מוצרים: סוג המוצר, כמות, מפרט
   - עבור פגישות: סוג הפגישה, זמן מועדף, נושא
   - פרטים נוספים ספציפיים לתחום
   
3. **פרטי הלקוח**: שם ואמצעי התקשרות (אם נמסרו)

4. **סטטוס ומעקב**:
   - האם נקבעה פגישה/תור/פעולה? (מתי?)
   - דחיפות: גבוהה/בינונית/נמוכה
   - פעולות נדרשות מהעסק

5. **הערות חשובות**: מידע נוסף רלוונטי לתחום
{business_context}

📝 **תמלול השיחה:**
{transcription}

📝 **סיכום מקצועי דינמי:**"""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system", 
                    "content": """אתה מומחה סיכום שיחות עסקיות בעברית. 
                    
היכולות שלך:
- מזהה אוטומטית כל סוג עסק ושירות (כל תחום אפשרי!)
- מתאים את מבנה הסיכום לתחום הספציפי
- חולץ מידע רלוונטי בצורה חכמה
- כותב סיכומים שימושיים ומקצועיים

כללים:
- סיכום 80-150 מילים בעברית
- מבנה ברור עם כותרות
- התמקד במידע שימושי לאיש המכירות/השירות
- אל תמציא מידע שלא נאמר בשיחה"""
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=400,
            temperature=0.3
        )
        
        summary = response.choices[0].message.content
        if summary:
            summary = summary.strip()
            word_count = len(summary.split())
            
            if word_count < 50:
                log.warning(f"⚠️ Summary too short ({word_count} words) for {call_sid} - using fallback")
                return _fallback_summary(transcription)
            elif word_count > 200:
                log.warning(f"⚠️ Summary too long ({word_count} words) for {call_sid} - truncating")
                words = summary.split()
                summary = " ".join(words[:180]) + "..."
            
            log.info(f"✅ Universal dynamic summary generated for {call_sid}: {word_count} words")
            return summary
        else:
            log.warning(f"⚠️ Empty summary for {call_sid}")
            return _fallback_summary(transcription)
            
    except Exception as e:
        log.error(f"❌ Summary generation failed for {call_sid}: {e}")
        return _fallback_summary(transcription)


def _fallback_summary(transcription: str) -> str:
    """
    סיכום fallback דינמי (במקרה של כשל ב-AI)
    """
    words = transcription.strip().split()
    
    summary_parts = []
    summary_parts.append("**סוג הפנייה**: פנייה עסקית")
    
    if len(words) >= 80:
        content = " ".join(words[:70])
        summary_parts.append(f"\n\n**תוכן השיחה**: {content}...")
    elif len(words) >= 40:
        summary_parts.append(f"\n\n**תוכן השיחה**: {transcription.strip()}")
        summary_parts.append("\n\n**פרטים**: לא צוינו פרטים מלאים בשיחה")
    else:
        summary_parts.append(f"\n\n**תוכן השיחה**: {transcription.strip()}")
        summary_parts.append("\n\n**פרטים**: המידע בשיחה היה מוגבל, יש צורך במעקב נוסף")
        summary_parts.append("\n\n**פרטי קשר**: לא נמסרו פרטי קשר מפורשים")
    
    summary_parts.append("\n\n**סטטוס ומעקב**: לא נקבעה פגישה. מומלץ לחזור ללקוח ולקבל פרטים נוספים.")
    summary_parts.append("\n\n**הערה**: סיכום אוטומטי (מערכת AI זמנית לא זמינה)")
    
    fallback = "\n".join(summary_parts)
    word_count = len(fallback.split())
    log.info(f"📋 Fallback summary created: {word_count} words")
    return fallback


def extract_lead_info(transcription: str, business_type: Optional[str] = None) -> dict:
    """
    חילוץ מידע חשוב מהשיחה - דינמי לחלוטין
    
    Args:
        transcription: התמלול המלא
        business_type: רמז על סוג העסק (אופציונלי)
        
    Returns:
        dict עם מידע רלוונטי
    """
    if not transcription or len(transcription.strip()) < 10:
        return {}
    
    try:
        from openai import OpenAI
        
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        prompt = f"""חלץ מידע מהשיחה הבאה.

תמלול:
{transcription}

זהה אוטומטית את סוג העסק/השירות והחזר JSON עם מידע רלוונטי.

החזר JSON בפורמט:
{{
  "detected_business_type": "סוג העסק שזיהית",
  "request_type": "סוג הבקשה/פנייה",
  "key_details": "פרטים עיקריים רלוונטיים לתחום",
  "customer_name": "שם הלקוח או null",
  "urgency": "גבוהה/בינונית/נמוכה",
  "meeting_scheduled": true/false,
  "next_action": "פעולה מומלצת"
}}
"""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "אתה מומחה לחילוץ מידע משיחות עסקיות. זהה אוטומטית את סוג העסק והחזר רק JSON תקין."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            temperature=0.1
        )
        
        import json
        result = json.loads(response.choices[0].message.content)
        log.info(f"✅ Lead info extracted dynamically: {result}")
        return result
        
    except Exception as e:
        log.error(f"❌ Lead info extraction failed: {e}")
        return {}
