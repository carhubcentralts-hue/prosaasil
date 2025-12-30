"""
Lead Auto Status Service
Automatically suggests lead status based on call outcome (inbound + outbound)
Dynamic mapping using structured extraction + keyword scoring
"""
import logging
import re
from typing import Optional

log = logging.getLogger(__name__)

# Configuration constants
CALL_HISTORY_LIMIT = 10  # Number of previous calls to check for no-answer progression


class LeadAutoStatusService:
    """
    Service for automatically suggesting lead status after calls
    Works for both inbound and outbound calls
    """
    
    def suggest_status(
        self,
        tenant_id: int,
        lead_id: int,
        call_direction: str,
        call_summary: Optional[str] = None,
        call_transcript: Optional[str] = None,
        structured_extraction: Optional[dict] = None,
        call_duration: Optional[int] = None
    ) -> Optional[str]:
        """
        Suggest a status for a lead based on call outcome using AI
        
        Args:
            tenant_id: Business/tenant ID
            lead_id: Lead ID
            call_direction: 'inbound' or 'outbound'
            call_summary: AI-generated call summary (preferred)
            call_transcript: Full call transcript (fallback)
            structured_extraction: Structured data extracted from call (if available)
            call_duration: Call duration in seconds (for smart no-summary handling)
            
        Returns:
            Status name (lowercase canonical) or None if cannot determine
        """
        from server.models_sql import LeadStatus
        
        # Get valid statuses for this business
        valid_statuses_dict = self._get_valid_statuses_dict(tenant_id)
        if not valid_statuses_dict:
            log.warning(f"No valid statuses found for tenant {tenant_id}")
            return None
        
        # 🆕 SIMPLIFIED SMART LOGIC: Always use summary/transcript (now always available!)
        # The summary now includes duration and disconnect reason for ALL calls,
        # so we don't need complex duration-based logic anymore!
        text_to_analyze = call_summary if call_summary else call_transcript
        
        # Priority 0: Use AI to intelligently determine status (MAIN PATH)
        # This is the SMART method that actually understands the conversation
        # 🆕 Now the summary ALWAYS includes duration and disconnect reason - SUPER SMART!
        if text_to_analyze and len(text_to_analyze) > 10:
            suggested = self._suggest_status_with_ai(
                text_to_analyze, 
                valid_statuses_dict, 
                call_direction
            )
            if suggested:
                log.info(f"[AutoStatus] ✅ AI suggested '{suggested}' for lead {lead_id} (using {'summary with duration info' if call_summary else 'transcript'})")
                return suggested
        
        # Fallback to keyword matching (less intelligent)
        valid_statuses_set = set(valid_statuses_dict.keys())
        
        # Priority 1: Use structured extraction if available
        if structured_extraction:
            suggested = self._map_from_structured_extraction(structured_extraction, valid_statuses_set)
            if suggested:
                log.info(f"[AutoStatus] Suggested '{suggested}' from structured extraction for lead {lead_id}")
                return suggested
        
        # Priority 2: Use keyword scoring on summary (preferred) or transcript
        if text_to_analyze and len(text_to_analyze) > 10:
            suggested = self._map_from_keywords(text_to_analyze, valid_statuses_set)
            if suggested:
                log.info(f"[AutoStatus] Suggested '{suggested}' from keywords for lead {lead_id}")
                return suggested
        
        # Cannot confidently determine status
        log.info(f"[AutoStatus] Cannot determine status for lead {lead_id} (no confident match)")
        return None
    
    def _get_valid_statuses(self, tenant_id: int) -> set:
        """Get set of valid status names for tenant"""
        from server.models_sql import LeadStatus
        
        statuses = LeadStatus.query.filter_by(
            business_id=tenant_id,
            is_active=True
        ).all()
        
        return {s.name for s in statuses}
    
    def _get_valid_statuses_dict(self, tenant_id: int) -> dict:
        """
        Get dictionary of valid statuses for tenant with descriptions
        Returns: {status_name: status_description}
        """
        from server.models_sql import LeadStatus
        
        statuses = LeadStatus.query.filter_by(
            business_id=tenant_id,
            is_active=True
        ).all()
        
        return {s.name: (s.description or s.name) for s in statuses}
    
    def _suggest_status_with_ai(
        self, 
        conversation_text: str, 
        valid_statuses: dict, 
        call_direction: str
    ) -> Optional[str]:
        """
        🆕 INTELLIGENT STATUS SUGGESTION using OpenAI
        
        Uses GPT-4 to analyze the conversation and intelligently match
        to one of the available statuses for this business.
        
        Args:
            conversation_text: Call summary or transcript
            valid_statuses: Dict of {status_name: status_description}
            call_direction: 'inbound' or 'outbound'
            
        Returns:
            Status name or None
        """
        try:
            import os
            from openai import OpenAI
            
            # Get OpenAI API key
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                log.warning("[AutoStatus] No OpenAI API key found - falling back to keyword matching")
                return None
            
            client = OpenAI(api_key=api_key)
            
            # Build status list for prompt
            status_list = "\n".join([f"- {name}: {desc}" for name, desc in valid_statuses.items()])
            
            # Build intelligent prompt
            prompt = f"""אתה מערכת חכמה לניתוח שיחות ועדכון סטטוס לידים.

ניתן לך סיכום/תמלול של שיחה {'נכנסת' if call_direction == 'inbound' else 'יוצאת'} עם לקוח פוטנציאלי.
🆕 הסיכום כולל מידע על משך השיחה וסיבת הסיום - השתמש בזה בצורה חכמה!
המשימה שלך היא לקבוע את הסטטוס המתאים ביותר עבור הליד הזה מתוך רשימת הסטטוסים הזמינים.

**סטטוסים זמינים:**
{status_list}

**סיכום/תמלול השיחה:**
{conversation_text}

**הנחיות מורחבות (חכם מאוד!):**
1. נתח את תוכן השיחה והבן את רמת העניין של הלקוח
2. 🆕 שים לב למשך השיחה וסיבת הסיום (אם מופיע בסיכום):
   - שיחות קצרות מאוד (< 5 שניות) → כנראה "אין מענה"
   - שיחות קצרות (20-30 שניות) עם ניתוק → "נענה אך ניתק" או דומה
   - שיחות בינוניות (30-60 שניות) עם ניתוק → "ניתק באמצע" או דומה
   - שיחות מלאות שהסתיימו בהצלחה → התאם לתוכן השיחה
3. זהה אם נקבע מפגש/פגישה, אם הלקוח מעוניין, לא מעוניין, או צריך מעקב
4. 🆕 שלב את משך השיחה עם התוכן - אם יש סתירה, העדף את התוכן!
5. בחר את הסטטוס המתאים ביותר מתוך הרשימה לעיל
6. אם אף סטטוס לא מתאים באופן ברור, החזר "none"
7. החזר **רק** את שם הסטטוס בדיוק כמו שהוא ברשימה (lowercase)

🎯 **היה חכם**: אם הסיכום אומר "ניתוק באמצע" - חפש סטטוסים מתאימים כמו "disconnected", "ניתק", וכו'

**התשובה שלך (רק שם הסטטוס):**"""

            # Call OpenAI
            response = client.chat.completions.create(
                model="gpt-4o-mini",  # Fast and cheap for this task
                messages=[
                    {
                        "role": "system",
                        "content": """אתה מערכת חכמה לניתוח שיחות. תמיד החזר רק שם סטטוס אחד או 'none'.
                        
🎯 **יכולות מיוחדות שלך:**
- מבין את משך השיחה וסיבת הסיום
- משלב בין תוכן השיחה ומשך הזמן
- מזהה ניתוקים, שיחות לא שלמות, ושיחות מוצלחות
- תמיד מחזיר את הסטטוס המדויק ביותר

⚠️ **כללים:**
1. אם הסיכום מציין משך קצר מאוד (< 5 שניות) → חפש "no_answer" / "אין מענה"
2. אם הסיכום מציין "ניתוק" → חפש סטטוסים עם "disconnect" / "ניתק"
3. אם הסיכום מציין "הצלחה" → התאם לתוכן השיחה
4. תמיד העדף סטטוס שתואם גם למשך וגם לתוכן"""
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # Low temperature for consistent results
                max_tokens=50  # Just need the status name
            )
            
            suggested_status = response.choices[0].message.content.strip().lower()
            
            # Validate the suggested status is in our list
            if suggested_status in valid_statuses:
                log.info(f"[AutoStatus] 🤖 AI suggested status: '{suggested_status}'")
                return suggested_status
            elif suggested_status != "none":
                log.warning(f"[AutoStatus] AI suggested invalid status: '{suggested_status}' - not in valid list")
            
            return None
            
        except Exception as e:
            log.error(f"[AutoStatus] Error in AI status suggestion: {e}")
            return None
    
    def _map_from_structured_extraction(self, extraction: dict, valid_statuses: set) -> Optional[str]:
        """
        Map from structured extraction fields to status
        
        Example fields:
        - call_outcome: 'interested' | 'not_interested' | 'callback' | 'no_answer'
        - lead_interest: 'high' | 'medium' | 'low' | 'none'
        - appointment_set: true | false
        """
        # Check for explicit outcome field
        outcome = extraction.get('call_outcome', '').lower()
        
        # Map outcomes to statuses
        if 'not_interested' in outcome or 'not interested' in outcome or 'לא מעוניין' in outcome:
            if 'not_relevant' in valid_statuses:
                return 'not_relevant'
        
        if 'interested' in outcome or 'מעוניין' in outcome:
            if 'interested' in valid_statuses:
                return 'interested'
        
        if 'callback' in outcome or 'follow' in outcome or 'חזרה' in outcome or 'תחזור' in outcome:
            if 'follow_up' in valid_statuses:
                return 'follow_up'
        
        if 'no_answer' in outcome or 'no answer' in outcome or 'לא ענה' in outcome:
            if 'no_answer' in valid_statuses:
                return 'no_answer'
        
        # Check appointment field
        if extraction.get('appointment_set'):
            if 'qualified' in valid_statuses:
                return 'qualified'
        
        # Check interest level
        interest = extraction.get('lead_interest', '').lower()
        if interest == 'high':
            if 'interested' in valid_statuses:
                return 'interested'
        elif interest == 'none' or interest == 'low':
            if 'not_relevant' in valid_statuses:
                return 'not_relevant'
        
        return None
    
    def _build_status_groups(self, valid_statuses: set) -> dict:
        """
        Build semantic groups from business's available statuses
        Returns dict mapping group names to available status names for that group
        """
        # Define status name/label synonyms for each semantic group
        groups = {
            'APPOINTMENT_SET': ['qualified', 'appointment', 'meeting', 'נקבע', 'פגישה', 'סגירה'],
            'HOT_INTERESTED': ['interested', 'hot', 'מעוניין', 'חם', 'מתעניין', 'המשך טיפול', 'פוטנציאל'],
            'FOLLOW_UP': ['follow_up', 'callback', 'חזרה', 'תזכורת', 'תחזור', 'מאוחר יותר'],
            'NOT_RELEVANT': ['not_relevant', 'not_interested', 'לא רלוונטי', 'לא מעוניין', 'להסיר', 'חסום'],
            'NO_ANSWER': ['no_answer', 'אין מענה', 'לא ענה', 'תא קולי'],
        }
        
        result = {}
        for group_name, synonyms in groups.items():
            # Find which statuses from this business match this group
            matching = []
            for status_name in valid_statuses:
                status_lower = status_name.lower()
                if any(syn.lower() in status_lower or status_lower in syn.lower() for syn in synonyms):
                    matching.append(status_name)
            
            if matching:
                # Prefer exact matches, then use first match
                for preferred in synonyms:
                    if preferred in matching:
                        result[group_name] = preferred
                        break
                else:
                    result[group_name] = matching[0]
        
        return result
    
    def _map_from_keywords(self, text: str, valid_statuses: set) -> Optional[str]:
        """
        Map from text content using keyword scoring with priority-based tie-breaking
        
        Priority order (highest to lowest):
        1. Appointment set
        2. Hot/Interested  
        3. Follow up
        4. Not relevant
        5. No answer
        """
        text_lower = text.lower()
        
        # Build status groups from available statuses
        status_groups = self._build_status_groups(valid_statuses)
        
        # Score each pattern group (higher score = stronger match)
        scores = {}
        
        # Pattern 4: Not interested / Not relevant (CHECK FIRST - contains negations)
        # Must check before interested keywords to catch "לא מעוניין"
        not_relevant_keywords = [
            'לא מעוניין', 'לא רלוונטי', 'להסיר', 'תפסיקו', 'לא מתאים',
            'not interested', 'not relevant', 'remove me', 'stop calling',
            'תמחקו אותי', 'אל תתקשרו', 'לא צריך', 'תורידו אותי', 'להפסיק'
        ]
        not_relevant_score = sum(1 for kw in not_relevant_keywords if kw in text_lower)
        if not_relevant_score > 0 and 'NOT_RELEVANT' in status_groups:
            scores['NOT_RELEVANT'] = (4, not_relevant_score)  # Priority 4
        
        # Pattern 1: Appointment / Meeting scheduled (HIGHEST PRIORITY)
        appointment_keywords = [
            'קבענו פגישה', 'נקבע', 'פגישה', 'meeting', 'appointment', 'scheduled', 'confirmed',
            'בוקר מתאים', 'אחר הצהריים מתאים', 'ביום', 'בשעה'
        ]
        appointment_score = sum(1 for kw in appointment_keywords if kw in text_lower)
        if appointment_score > 0 and 'APPOINTMENT_SET' in status_groups:
            scores['APPOINTMENT_SET'] = (1, appointment_score)  # Priority 1
        
        # Pattern 2: Hot / Interested (SECOND PRIORITY)
        # Only count if NOT_RELEVANT wasn't already scored (to avoid "לא מעוניין" matching "מעוניין")
        if 'NOT_RELEVANT' not in scores:
            interested_keywords = [
                'מעוניין', 'כן רוצה', 'תשלח פרטים', 'תשלחו פרטים', 'דברו איתי', 'מתאים לי',
                'interested', 'yes please', 'send details', 'call me back', 'sounds good', 'sounds interesting',
                'אני רוצה', 'נשמע טוב', 'נשמע מעניין', 'בואו נדבר', 'יכול להיות מעניין',
                'תן הצעה', 'תתקשרו', 'כן', 'נשמע', 'יפה'
            ]
            interested_score = sum(1 for kw in interested_keywords if kw in text_lower)
            if interested_score > 0 and 'HOT_INTERESTED' in status_groups:
                scores['HOT_INTERESTED'] = (2, interested_score)  # Priority 2
        
        # Pattern 3: Follow up / Call back later (THIRD PRIORITY)
        follow_up_keywords = [
            'תחזרו', 'תחזור', 'מאוחר יותר', 'שבוע הבא', 'חודש הבא', 'תתקשרו שוב',
            'call back', 'follow up', 'later', 'next week', 'next month',
            'בעוד כמה ימים', 'אחרי החגים', 'אחרי החג', 'בשבוע הבא', 'תזכיר לי'
        ]
        follow_up_score = sum(1 for kw in follow_up_keywords if kw in text_lower)
        if follow_up_score > 0 and 'FOLLOW_UP' in status_groups:
            scores['FOLLOW_UP'] = (3, follow_up_score)  # Priority 3
        
        # Pattern 5: No answer / Voicemail (LOWEST PRIORITY)
        no_answer_keywords = [
            'לא ענה', 'אין מענה', 'תא קולי', 'לא זמין', 'לא פנוי',
            'no answer', 'voicemail', 'not available', 'unavailable',
            'מכשיר כבוי', 'לא משיב', 'מספר לא זמין'
        ]
        no_answer_score = sum(1 for kw in no_answer_keywords if kw in text_lower)
        if no_answer_score > 0 and 'NO_ANSWER' in status_groups:
            scores['NO_ANSWER'] = (5, no_answer_score)  # Priority 5
        
        # No matches found
        if not scores:
            # Default fallback: If conversation happened, assume contacted
            if len(text) > 50 and 'contacted' in valid_statuses:
                return 'contacted'
            return None
        
        # Select winner based on priority (lower priority number = higher priority)
        # In case of tie on priority, use keyword count
        winner = min(scores.items(), key=lambda x: (x[1][0], -x[1][1]))
        winner_group = winner[0]
        
        log.info(f"[AutoStatus] Keyword scoring: {scores}, winner: {winner_group}")
        
        return status_groups[winner_group]
    
    def _handle_no_answer_with_progression(
        self, 
        tenant_id: int, 
        lead_id: int, 
        valid_statuses_dict: dict
    ) -> Optional[str]:
        """
        🆕 Smart no-answer status progression
        
        Handles intelligent status progression for no-answer calls:
        - First no-answer: → "no_answer" or "no_answer_1" 
        - Second no-answer: → "no_answer_2" (if exists)
        - Third no-answer: → "no_answer_3" (if exists)
        
        Falls back gracefully if only some no-answer statuses exist.
        
        Args:
            tenant_id: Business ID
            lead_id: Lead ID
            valid_statuses_dict: Dictionary of available statuses
            
        Returns:
            Status name or None
        """
        from server.models_sql import CallLog
        
        valid_statuses_set = set(valid_statuses_dict.keys())
        
        # Find available no-answer statuses in this business
        # Check for: no_answer, no_answer_1, no_answer_2, no_answer_3, אין מענה, אין מענה 2, אין מענה 3
        available_no_answer_statuses = []
        
        for status_name in valid_statuses_set:
            status_lower = status_name.lower()
            # Match variations: no_answer, no_answer_1, no_answer_2, אין מענה, אין מענה 2, etc.
            if ('no_answer' in status_lower or 
                'no answer' in status_lower or 
                'אין מענה' in status_lower or
                'לא ענה' in status_lower):
                available_no_answer_statuses.append(status_name)
        
        if not available_no_answer_statuses:
            log.info(f"[AutoStatus] No 'no_answer' status available for business {tenant_id}")
            return None
        
        # Count previous no-answer calls for this lead
        try:
            # Get all previous calls for this lead
            previous_calls = CallLog.query.filter_by(
                business_id=tenant_id,
                lead_id=lead_id
            ).order_by(CallLog.created_at.desc()).limit(CALL_HISTORY_LIMIT).all()
            
            # Get lead's current status to check if it's already a no-answer variant
            from server.models_sql import Lead
            lead = Lead.query.filter_by(id=lead_id).first()
            if lead and lead.status:
                status_lower = lead.status.lower()
                if ('no_answer' in status_lower or 
                    'no answer' in status_lower or 
                    'אין מענה' in status_lower or
                    'לא ענה' in status_lower):
                    # Lead is currently in a no-answer state
                    # Extract number if present (e.g., "no_answer_2" → 2, "אין מענה 3" → 3)
                    numbers = re.findall(r'\d+', lead.status)
                    if numbers:
                        current_attempt = int(numbers[-1])  # Take last number found
                    else:
                        current_attempt = 1  # First no-answer
                    
                    # Determine next attempt
                    next_attempt = current_attempt + 1
                    
                    log.info(f"[AutoStatus] Lead {lead_id} currently at no-answer attempt {current_attempt}, trying for {next_attempt}")
                else:
                    # Not currently no-answer, this is the first
                    next_attempt = 1
            else:
                # No lead found or no status, assume first attempt
                next_attempt = 1
            
            # Now find the appropriate status based on attempt number
            # Sort available statuses to prefer numbered ones
            sorted_statuses = sorted(available_no_answer_statuses)
            
            # Try to find status matching the attempt number
            # Priority: exact match (no_answer_2) > base status (no_answer)
            target_status = None
            
            if next_attempt == 1:
                # First attempt - use base "no_answer" or "no_answer_1"
                for status in sorted_statuses:
                    status_lower = status.lower()
                    # Prefer exact "no_answer" without number, or "no_answer_1"
                    if (status_lower == 'no_answer' or 
                        status_lower == 'no answer' or
                        status_lower == 'אין מענה' or
                        status_lower == 'לא ענה' or
                        '1' in status_lower):
                        target_status = status
                        break
            else:
                # 2nd, 3rd attempt - try to find numbered status
                for status in sorted_statuses:
                    # Check if status contains the target attempt number
                    if str(next_attempt) in status:
                        target_status = status
                        break
            
            # Fallback: if no exact match, use any available no-answer status
            if not target_status and available_no_answer_statuses:
                target_status = available_no_answer_statuses[0]
                log.info(f"[AutoStatus] No exact match for attempt {next_attempt}, using fallback: {target_status}")
            
            if target_status:
                log.info(f"[AutoStatus] Smart progression: attempt {next_attempt} → '{target_status}'")
                return target_status
            
        except Exception as e:
            log.error(f"[AutoStatus] Error in no-answer progression: {e}")
            # Fallback to simple no_answer if progression logic fails
            for status in available_no_answer_statuses:
                if status.lower() in ['no_answer', 'no answer', 'אין מענה', 'לא ענה']:
                    return status
        
        return None
    
    def _handle_mid_length_disconnect(self, valid_statuses_dict: dict, call_duration: int) -> Optional[str]:
        """
        🆕 Handle short-mid calls (20-30 seconds) without summary
        
        These are typically cases where:
        - Customer answered but hung up quickly
        - Brief connection before disconnect
        
        Looks for appropriate statuses like:
        - "answered_but_disconnected" / "נענה אך ניתק"
        - "contacted" / "נוצר קשר" 
        - "attempted" / "ניסיון קשר"
        - Falls back to generic statuses if specific ones don't exist
        
        Args:
            valid_statuses_dict: Dictionary of available statuses
            call_duration: Duration in seconds (for logging)
            
        Returns:
            Status name or None
        """
        valid_statuses_set = set(valid_statuses_dict.keys())
        
        # Priority 1: Look for "answered but disconnected" type statuses
        for status_name in valid_statuses_set:
            status_lower = status_name.lower()
            # Match: answered_but_disconnected, נענה_אך_ניתק, answered_disconnected, etc.
            if (('answer' in status_lower or 'נענה' in status_lower) and 
                ('disconnect' in status_lower or 'ניתק' in status_lower)):
                log.info(f"[AutoStatus] Short-mid disconnect ({call_duration}s) matched 'answered_but_disconnected': {status_name}")
                return status_name
        
        # Priority 2: Look for "contacted" type statuses
        for status_name in valid_statuses_set:
            status_lower = status_name.lower()
            if ('contact' in status_lower or 'נוצר קשר' in status_lower):
                log.info(f"[AutoStatus] Short-mid disconnect ({call_duration}s) matched 'contacted': {status_name}")
                return status_name
        
        # Priority 3: Look for "attempting" or "attempted" type statuses
        for status_name in valid_statuses_set:
            status_lower = status_name.lower()
            if ('attempt' in status_lower or 'ניסיון' in status_lower):
                log.info(f"[AutoStatus] Short-mid disconnect ({call_duration}s) matched 'attempting': {status_name}")
                return status_name
        
        # No specific status found - let it fall through
        log.info(f"[AutoStatus] Short-mid disconnect ({call_duration}s): no specific status found, will use default logic")
        return None
    
    def _handle_longer_disconnect(self, valid_statuses_dict: dict, call_duration: int) -> Optional[str]:
        """
        🆕 Handle longer calls (30-60 seconds) without summary
        
        These are cases where:
        - Conversation started but customer hung up mid-way
        - Connection lasted 30-60 seconds but no meaningful summary
        - Customer disconnected after partial conversation
        
        Looks for appropriate statuses with smart priority:
        - "disconnected_mid_call" / "ניתק באמצע שיחה"
        - "partial_conversation" / "שיחה חלקית"
        - "disconnected_after_X" / "ניתק אחרי X שניות" (where X matches duration range)
        - "contacted" / "נוצר קשר"
        - "attempted_conversation" / "ניסיון שיחה"
        
        Smart matching based on duration:
        - 30-40 seconds: "disconnected after 30 seconds" / "ניתק אחרי חצי דקה"
        - 40-50 seconds: "disconnected after 40 seconds" / "ניתק אחרי 40 שניות"
        - 50-60 seconds: "disconnected after 50 seconds" / "ניתק אחרי דקה"
        
        Args:
            valid_statuses_dict: Dictionary of available statuses
            call_duration: Duration in seconds
            
        Returns:
            Status name or None
        """
        valid_statuses_set = set(valid_statuses_dict.keys())
        
        # Priority 1: Look for duration-specific "disconnected after X" statuses
        # Smart matching: 30-40s → "30", 40-50s → "40", 50-60s → "50"/"60"
        duration_keywords = []
        if 30 <= call_duration < 40:
            duration_keywords = ['30', 'חצי דקה', 'half minute']
        elif 40 <= call_duration < 50:
            duration_keywords = ['40', '40 שניות']
        elif 50 <= call_duration <= 60:
            duration_keywords = ['50', '60', 'דקה', 'minute']
        
        for status_name in valid_statuses_set:
            status_lower = status_name.lower()
            # Check if status mentions disconnection AND contains duration keyword
            if (('disconnect' in status_lower or 'ניתק' in status_lower) and
                any(kw in status_lower for kw in duration_keywords)):
                log.info(f"[AutoStatus] Longer disconnect ({call_duration}s) matched duration-specific: {status_name}")
                return status_name
        
        # Priority 2: Look for "disconnected mid call" type statuses
        for status_name in valid_statuses_set:
            status_lower = status_name.lower()
            # Match: disconnected_mid_call, ניתק_באמצע, mid_call_disconnect, etc.
            if (('disconnect' in status_lower or 'ניתק' in status_lower) and 
                ('mid' in status_lower or 'באמצע' in status_lower or 'אמצע' in status_lower)):
                log.info(f"[AutoStatus] Longer disconnect ({call_duration}s) matched 'disconnected_mid_call': {status_name}")
                return status_name
        
        # Priority 3: Look for "partial conversation" type statuses
        for status_name in valid_statuses_set:
            status_lower = status_name.lower()
            if (('partial' in status_lower or 'חלקית' in status_lower or 'חלקי' in status_lower) and
                ('conversation' in status_lower or 'שיחה' in status_lower)):
                log.info(f"[AutoStatus] Longer disconnect ({call_duration}s) matched 'partial_conversation': {status_name}")
                return status_name
        
        # Priority 4: Generic "answered but disconnected" (less specific than mid-call)
        for status_name in valid_statuses_set:
            status_lower = status_name.lower()
            if (('answer' in status_lower or 'נענה' in status_lower) and 
                ('disconnect' in status_lower or 'ניתק' in status_lower)):
                log.info(f"[AutoStatus] Longer disconnect ({call_duration}s) matched 'answered_but_disconnected': {status_name}")
                return status_name
        
        # Priority 5: Look for "contacted" type statuses
        for status_name in valid_statuses_set:
            status_lower = status_name.lower()
            if ('contact' in status_lower or 'נוצר קשר' in status_lower):
                log.info(f"[AutoStatus] Longer disconnect ({call_duration}s) matched 'contacted': {status_name}")
                return status_name
        
        # Priority 6: Look for "attempted conversation" type statuses
        for status_name in valid_statuses_set:
            status_lower = status_name.lower()
            if (('attempt' in status_lower or 'ניסיון' in status_lower) and
                ('conversation' in status_lower or 'שיחה' in status_lower)):
                log.info(f"[AutoStatus] Longer disconnect ({call_duration}s) matched 'attempted_conversation': {status_name}")
                return status_name
        
        # No specific status found - let it fall through
        log.info(f"[AutoStatus] Longer disconnect ({call_duration}s): no specific status found, will use default logic")
        return None


# Global singleton instance
_auto_status_service = LeadAutoStatusService()


def get_auto_status_service() -> LeadAutoStatusService:
    """Get the singleton auto status service instance"""
    return _auto_status_service


def suggest_lead_status_from_call(
    tenant_id: int,
    lead_id: int,
    call_direction: str,
    call_summary: Optional[str] = None,
    call_transcript: Optional[str] = None,
    structured_extraction: Optional[dict] = None,
    call_duration: Optional[int] = None
) -> Optional[str]:
    """
    Convenience function to suggest status from call
    
    Returns status name or None
    """
    service = get_auto_status_service()
    return service.suggest_status(
        tenant_id=tenant_id,
        lead_id=lead_id,
        call_direction=call_direction,
        call_summary=call_summary,
        call_transcript=call_transcript,
        structured_extraction=structured_extraction,
        call_duration=call_duration
    )
