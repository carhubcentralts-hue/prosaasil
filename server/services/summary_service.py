"""
Summary Service - AI-powered FULLY DYNAMIC conversation summarization
שירות סיכום חכם ודינמי לחלוטין - מזהה כל סוג עסק ושיחה אוטומטית!
BUILD 144 - Universal Dynamic Summaries
"""
import os
import logging
from typing import Optional

log = logging.getLogger(__name__)

# 🔥 CRITICAL: Minimum summary length - only reject if essentially empty
MIN_SUMMARY_LENGTH = 5  # Characters


def summarize_conversation(
    transcription: str, 
    call_sid: Optional[str] = None,
    business_type: Optional[str] = None,
    business_name: Optional[str] = None,
    call_duration: Optional[int] = None,
    business_id: Optional[int] = None
) -> str:
    """
    סיכום דינמי לחלוטין של שיחה - מזהה אוטומטית את סוג השיחה והעסק!
    BUILD 144 - Universal Dynamic Summaries
    BUILD 183 - CRITICAL FIX: Don't hallucinate summaries when no user spoke!
    🆕 BUILD XXX - Smart duration and disconnect reason tracking
    🆕 BUILD XXX - Dynamic business statuses for intelligent recommendations
    
    GPT מזהה בעצמו:
    - סוג העסק (כל תחום - המערכת מזהה אוטומטית!)
    - מטרת השיחה
    - פרטים רלוונטיים
    - פעולות נדרשות
    - משך זמן השיחה וסיבת הסיום (חכם!)
    - המלצה לסטטוס מתוך הסטטוסים הזמינים לעסק
    
    Args:
        transcription: התמלול המלא של השיחה
        call_sid: מזהה שיחה ללוגים
        business_type: רמז על סוג העסק (אופציונלי - GPT יזהה בעצמו)
        business_name: שם העסק (אופציונלי)
        call_duration: משך השיחה בשניות (🆕 חדש!)
        business_id: מזהה עסק לשליפת סטטוסים זמינים (🆕 חדש!)
        
    Returns:
        סיכום מקצועי דינמי בעברית (80-150 מילים) כולל משך וסיבת סיום
        🆕 CRITICAL: ALWAYS returns a summary, even for unanswered calls!
    """
    # 🔥 CRITICAL FIX: Handle 0-second / no-answer calls FIRST!
    # Even if there's NO transcription, if we have duration info showing no-answer, create summary!
    if call_duration is not None and call_duration == 0:
        log.info(f"📊 [SUMMARY] 0-second call detected for {call_sid} - creating no-answer summary")
        return "שיחה לא נענתה (0 שניות) - אין מענה"
    
    # 🔥 BUILD 183: Early exit if no transcription AND no duration info
    if not transcription or len(transcription.strip()) < 10:
        # If we have duration info, still create a summary!
        if call_duration is not None:
            if call_duration < 3:
                log.info(f"📊 [SUMMARY] Very short call ({call_duration}s) with no transcript for {call_sid}")
                return f"שיחה לא נענתה ({call_duration} שניות) - אין מענה"
            else:
                log.info(f"📊 [SUMMARY] Short call ({call_duration}s) with no transcript for {call_sid}")
                return f"שיחה קצרה ({call_duration} שניות) - ללא תמלול"
        
        log.info(f"📊 [SUMMARY] Skipping - no transcription and no duration info for call {call_sid}")
        return ""  # Return empty only if we have NOTHING
    
    # 🆕 For very short calls - still generate summary but focus on disconnect reason!
    # Don't skip - every call gets a summary!
    
    log.info(f"📊 Generating universal dynamic summary for call {call_sid} (transcript: {len(transcription)} chars, duration: {call_duration}s)")
    
    # 🔥 BUILD 183 CRITICAL: Check if USER actually spoke in the conversation
    # But for very short calls, we still want to document WHY (voicemail, hang up, etc.)
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
    
    # 🆕 For short calls without real user speech - still create a summary!
    # Document WHY the call ended (voicemail, hang up, etc.)
    if not user_spoke or user_content_length < 5:
        log.info(f"📊 [SUMMARY] Short call with minimal user speech ({user_content_length} chars) - creating disconnect reason summary")
        
        # Analyze the transcript to understand why call was short
        # Common patterns: voicemail, immediate hangup, number announcement, etc.
        transcript_lower = transcription.lower()
        
        # Build a smart summary based on what actually happened
        if call_duration is not None:
            minutes = call_duration // 60
            seconds = call_duration % 60
            if minutes > 0:
                duration_text = f"{minutes} דקות ו-{seconds} שניות" if seconds > 0 else f"{minutes} דקות"
            else:
                duration_text = f"{seconds} שניות"
            
            # Detect specific disconnect reasons from transcript
            disconnect_reason = ""
            if any(word in transcript_lower for word in ['תא קולי', 'משיבון', 'voicemail', 'mailbox']):
                disconnect_reason = "הגיע לתא קולי/משיבון אוטומטי"
            elif any(word in transcript_lower for word in ['מספר', 'number', 'חייג', 'dial', 'להקריא']):
                disconnect_reason = "התחיל להקריא מספר/הודעה אוטומטית"
            elif call_duration < 3:
                disconnect_reason = "לא נענה/ניתוק מיידי"
            elif call_duration < 10:
                disconnect_reason = "הלקוח ניתק בתחילת השיחה"
            else:
                disconnect_reason = "הלקוח ניתק את השיחה מהר"
            
            # Create concise summary for short calls
            # 🔥 FIX: Don't include transcript snippet in summary - it pollutes the AI Customer Service display
            # The full transcript is available separately in call.notes/call.final_transcript
            summary = f"שיחה של {duration_text} - {disconnect_reason}"
            
            log.info(f"📊 [SUMMARY] Created short call summary: '{disconnect_reason}'")
            return summary
        
        # Fallback if no duration available
        # 🔥 FIX: Don't include transcript snippet - keep summary clean
        return f"שיחה קצרה - לא נוצר דיאלוג מלא"
    
    log.info(f"📊 [SUMMARY] User spoke detected ({user_content_length} chars) - generating full summary")
    
    # 🔥 DYNAMIC STATUSES: Fetch business-specific statuses for intelligent recommendation
    available_statuses = []
    status_context = ""
    
    if business_id:
        try:
            from server.models_sql import LeadStatus
            statuses = LeadStatus.query.filter_by(
                business_id=business_id,
                is_active=True
            ).all()
            
            if statuses:
                # Build list of available statuses with their Hebrew labels ONLY
                status_list = []
                for s in statuses:
                    hebrew_label = s.label  # 🔥 FIX: Use 'label' not 'display_name'
                    status_list.append(f"- {hebrew_label}")
                    available_statuses.append(hebrew_label)  # Store Hebrew labels
                
                status_context = f"""

🎯 **סטטוסים זמינים בעסק זה** (בחר את המתאים ביותר):
{chr(10).join(status_list)}

⚠️ חשוב: 
- המלץ רק על סטטוס מהרשימה הזו! אל תמציא סטטוסים חדשים.
- השתמש בתווית **בעברית בדיוק** כפי שמופיעה ברשימה
- כתוב את השם בעברית בהמלצה - לא קוד באנגלית!
- אם אין סטטוס מדויק - בחר את הקרוב ביותר מבחינת משמעות"""
                
                log.info(f"📊 [SUMMARY] Loaded {len(statuses)} available statuses for business {business_id}")
            else:
                log.warning(f"📊 [SUMMARY] No active statuses found for business {business_id}")
        except Exception as e:
            log.error(f"📊 [SUMMARY] Failed to load statuses for business {business_id}: {e}")
    else:
        log.warning(f"📊 [SUMMARY] No business_id provided - status recommendation will be generic")
    
    try:
        from openai import OpenAI
        
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        business_context = ""
        if business_name:
            business_context = f"\n\nשם העסק: {business_name}"
        if business_type:
            business_context += f"\nתחום העסק (רמז): {business_type}"
        
        # 🆕 Add duration context for smart disconnect detection
        duration_context = ""
        disconnect_hint = ""
        if call_duration is not None:
            minutes = call_duration // 60
            seconds = call_duration % 60
            if minutes > 0:
                duration_text = f"{minutes} דקות ו-{seconds} שניות" if seconds > 0 else f"{minutes} דקות"
            else:
                duration_text = f"{seconds} שניות"
            
            duration_context = f"\n\n⏱️ **משך השיחה**: {duration_text} ({call_duration} שניות)"
            
            # Add smart disconnect detection hints
            if call_duration < 5:
                disconnect_hint = "\n🔍 שיחה קצרה מאוד (< 5 שניות) - זהה: אין מענה, תא קולי, או ניתוק מיידי"
            elif 5 <= call_duration < 20:
                disconnect_hint = "\n🔍 שיחה קצרה (5-20 שניות) - בדוק: האם ענה או ניתק מהר"
            elif 20 <= call_duration < 30:
                disconnect_hint = "\n🔍 שיחה קצרה-בינונית - בדוק אם היה ניתוק מהיר"
            elif 30 <= call_duration <= 60:
                disconnect_hint = "\n🔍 שיחה בינונית - בדוק אם ניתק באמצע שיחה"
            else:
                disconnect_hint = "\n🔍 שיחה ארוכה - ככל הנראה שיחה מלאה"
        
        prompt = f"""סכם את השיחה הבאה בצורה מקצועית ומדויקת בעברית.

תמלול השיחה:
{transcription}
{business_context}{duration_context}{status_context}

🎯 **הנחיות לסיכום - חובה לכלול כל פרט:**

📋 **מבנה הסיכום (4 חלקים):**
1. **נושא** - על מה השיחה (שורה אחת)
2. **מה נדון** - **כל הפרטים שהלקוח סיפק!** לא לדלג על שום מידע!  
   - אם מדובר בהובלה: כתוב קומות, כמות חדרים, תכולה מפורטת, תאריך, מנוף, גישה וכו'
   - אם מדובר בשירות: כתוב כל הדרישות והפרטים הספציפיים
   - אם מדובר בפגישה: כתוב תאריך, שעה, מיקום, נושא הפגישה
   - **רשום את כל המידע שהלקוח נתן - זה קריטי!**
3. **תוצאה** - מה סוכם/מה קרה בסוף (כולל אם ניתק)
4. **המשך** - מה הפעולה הבאה הנדרשת

🔥 **חובה: רשום את כל הפרטים!**
- אם לקוח אמר קומה - רשום איזו קומה
- אם לקוח אמר כמות חדרים - רשום כמה
- אם לקוח אמר תאריך - רשום את התאריך המדויק
- אם לקוח מנה פריטים - רשום את כל הפריטים
- אם לקוח אמר מחיר/תקציב - רשום
- **אל תסכם בכלליות! תן את הפרטים המלאים!**

📌 **דוגמה להובלה** (שים לב לרמת הפירוט):
❌ לא טוב: "לקוח מעוניין בהובלה. יש לו כמה חדרים ורהיטים."
✅ טוב: "נושא: הובלה מתל אביב לרמלה  
מה נדון: קומת איסוף 3, קומת פריקה 2, 5 חדרים, 4 נפשות בדירה, האריזה והפירוק יעשו ע״י הלקוח, צורך במנוף, גישה למשאית קיימת, תאריך 17.02.26, תכולה: ארון בגדים גדול, מערכת ישיבה מעור, 3 שידות, מקרר משפחתי, תנור גדול, 3 מיטות זוגיות.  
תוצאה: הלקוח מתכנן את ההובלה ומעוניין בהצעת מחיר.  
המשך: שליחת הצעת מחיר מדויקת על בסיס התכולה והמרחק."

כללים נוספים:
- אם הלקוח ניתק או לא התעניין - כתוב את זה במפורש
- אם אין מידע על משהו - אל תמציא
- המלצת סטטוס: בחר את הסטטוס **המדויק בעברית** מהרשימה
- פורמט: [המלצה: <סטטוס_בדיוק_מהרשימה>]

כתוב את הסיכום בעברית:"""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": """אתה מערכת מקצועית לסיכום שיחות עסקיות בעברית.

🎯 **המשימה שלך: סיכום מפורט עם כל הפרטים שהלקוח סיפק**

הסיכום שלך חייב להיות:
1. ✅ **מדויק** - רק מה שנאמר בפועל, ללא המצאות
2. ✅ **מפורט** - כל מספר, כל תאריך, כל פריט שהוזכר - חובה לרשום!
3. ✅ **שימושי** - מידע שעוזר להבין בדיוק מה הלקוח רוצה
4. ✅ **כן** - אם הלקוח לא התעניין או ניתק, תכתוב את זה במפורש

🔥 **CRITICAL: אל תדלג על פרטים!**
- אם הלקוח אמר "קומה 3" - רשום "קומה 3", לא "קומה גבוהה"
- אם הלקוח מנה 5 פריטים - רשום את כל 5 הפריטים, לא "כמה פריטים"
- אם הלקוח אמר תאריך מדויק - רשום את התאריך המדויק
- אם הלקוח אמר מספר נפשות - רשום את המספר

📋 **מבנה הסיכום:**
- **נושא**: על מה השיחה (שורה אחת, ספציפי)
- **מה נדון**: כל הפרטים שהלקוח סיפק (ללא דילוג!)
- **תוצאה**: מה סוכם או מה קרה בסוף
- **המשך**: הפעולה הבאה הנדרשת
- **[המלצה: <סטטוס>]**: סטטוס מדויק מהרשימה שקיבלת

🎯 **המלצת סטטוס:**
⚠️ חשוב מאוד: אתה תקבל רשימת סטטוסים ספציפית לעסק הזה בפרומפט
⚠️ המלץ רק על סטטוס מהרשימה שקיבלת - אל תמציא סטטוסים חדשים!
⚠️ בחר את הסטטוס המתאים ביותר בהתאם לתוכן השיחה
⚠️ הסטטוס חייב להיות **בדיוק** כפי שמופיע ברשימה (תווית עברית)

📌 **דוגמאות לסיכום מפורט:**
❌ גרוע: "לקוח מעוניין בהובלה."
❌ בינוני: "לקוח רוצה הובלה מתל אביב לרמלה."
✅ מצוין: "נושא: הובלה מתל אביב לרמלה  
מה נדון: איסוף מקומה 3, פריקה בקומה 2, דירת 5 חדרים, 4 נפשות, האריזה והפירוק ע״י הלקוח, צריך מנוף, גישה למשאית קיימת, תאריך: 17.02.26. תכולה: ארון בגדים גדול, מערכת ישיבה מעור, 3 שידות, מקרר משפחתי, תנור גדול, 3 מיטות זוגיות.  
תוצאה: הלקוח מתכנן ומעוניין בהצעת מחיר.  
המשך: שליחת הצעת מחיר מדויקת."

אורך: 50-150 מילים (תלוי בכמות הפרטים שיש) + המלצת סטטוס.
זכור: פרטים = הכי חשוב! אל תדלג על שום מידע שהלקוח סיפק!"""
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,  # Increased token limit to ensure AI has sufficient space for summaries
            temperature=0.0  # Temperature 0.0 for deterministic summaries
        )
        
        summary = response.choices[0].message.content
        if summary:
            summary = summary.strip()
            word_count = len(summary.split())
            
            # 🔥 FIX: Accept ANY summary from AI - no minimum word count!
            # The AI knows best what summary length is appropriate for each call
            if not summary or len(summary) < MIN_SUMMARY_LENGTH:
                # Only reject if completely empty or less than minimum characters
                log.warning(f"⚠️ Summary essentially empty for {call_sid} - using fallback")
                return _fallback_summary(transcription)
            
            # Truncate if too long
            if word_count > 200:
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
    סיכום fallback פשוט (במקרה של כשל ב-AI)
    FIX: Generate simple summary from transcript directly without mentioning AI issues
    Note: This should RARELY be used - only when AI completely fails
    """
    words = transcription.strip().split()
    
    # For short transcripts, return as-is with header for consistency
    if len(words) <= 50:
        return f"סיכום שיחה:\n\n{transcription.strip()}"
    
    # For longer transcripts, create a brief preview
    # Take first ~40 words as a preview
    preview = " ".join(words[:40]) + "..."
    summary = f"סיכום שיחה:\n\n{preview}"
    
    log.info(f"📋 Fallback summary created from transcript preview")
    return summary


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
            temperature=0.0  # 🔥 FIX: Temperature 0.0 for deterministic classification
        )
        
        import json
        result = json.loads(response.choices[0].message.content)
        log.info(f"✅ Lead info extracted dynamically: {result}")
        return result
        
    except Exception as e:
        log.error(f"❌ Lead info extraction failed: {e}")
        return {}
