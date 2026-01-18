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
    business_name: Optional[str] = None,
    call_duration: Optional[int] = None
) -> str:
    """
    סיכום דינמי לחלוטין של שיחה - מזהה אוטומטית את סוג השיחה והעסק!
    BUILD 144 - Universal Dynamic Summaries
    BUILD 183 - CRITICAL FIX: Don't hallucinate summaries when no user spoke!
    🆕 BUILD XXX - Smart duration and disconnect reason tracking
    
    GPT מזהה בעצמו:
    - סוג העסק (כל תחום - המערכת מזהה אוטומטית!)
    - מטרת השיחה
    - פרטים רלוונטיים
    - פעולות נדרשות
    - משך זמן השיחה וסיבת הסיום (חכם!)
    
    Args:
        transcription: התמלול המלא של השיחה
        call_sid: מזהה שיחה ללוגים
        business_type: רמז על סוג העסק (אופציונלי - GPT יזהה בעצמו)
        business_name: שם העסק (אופציונלי)
        call_duration: משך השיחה בשניות (🆕 חדש!)
        
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
        
        prompt = f"""Summarize the conversation factually.

Write only what was actually said. Do not invent.

Identify business type from conversation content.

Document call duration and disconnect reason.

If customer disconnected - state it.

If reached voicemail - state it.
{business_context}{duration_context}{disconnect_hint}

Conversation transcript:
{transcription}

Summary (80-150 words in Hebrew):
- First line: Call duration and end reason (required).
  Example: "Call 45 seconds - customer disconnected mid-call"
  Example: "Call 3 seconds - reached voicemail"
- Inquiry type and topic
- Details provided
- Real status: interested/not interested/unclear
- Required action"""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system", 
                    "content": """Summarize business calls in Hebrew.

Write only what was actually said.

First line: duration + disconnect reason (required).

If disconnected - state it.

If voicemail - state it.

Do not invent.

Examples:
- "Call 45 seconds - customer disconnected mid-call"
- "Call 3 seconds - reached voicemail"
- "Call 90 seconds - completed successfully"

Summary: 80-150 words, factual only."""
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=400,
            temperature=0.0  # 🔥 FIX: Temperature 0.0 for deterministic summaries
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
    🔥 FIX: Generate concise summary without embedding full transcript
    """
    words = transcription.strip().split()
    
    # Create a clean, concise fallback summary
    summary_parts = []
    summary_parts.append("סיכום אוטומטי: שיחה עסקית התקבלה")
    
    # Add length indication without full content
    if len(words) >= 80:
        summary_parts.append(f"\n\nהשיחה הכילה {len(words)} מילים - שיחה מפורטת")
    elif len(words) >= 40:
        summary_parts.append(f"\n\nהשיחה הכילה {len(words)} מילים - שיחה בינונית")
    else:
        summary_parts.append(f"\n\nהשיחה הכילה {len(words)} מילים - שיחה קצרה")
    
    summary_parts.append("\n\n**הערה**: התמליל המלא זמין בכרטיסייה 'שיחות טלפון'")
    summary_parts.append("\n\n(סיכום זה נוצר אוטומטית - שירות AI זמנית לא זמין)")
    
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
            temperature=0.0  # 🔥 FIX: Temperature 0.0 for deterministic classification
        )
        
        import json
        result = json.loads(response.choices[0].message.content)
        log.info(f"✅ Lead info extracted dynamically: {result}")
        return result
        
    except Exception as e:
        log.error(f"❌ Lead info extraction failed: {e}")
        return {}
