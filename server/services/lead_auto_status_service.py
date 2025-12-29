"""
Lead Auto Status Service
Automatically suggests lead status based on call outcome (inbound + outbound)
Dynamic mapping using structured extraction + keyword scoring
"""
import logging
from typing import Optional

log = logging.getLogger(__name__)


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
        structured_extraction: Optional[dict] = None
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
            
        Returns:
            Status name (lowercase canonical) or None if cannot determine
        """
        from server.models_sql import LeadStatus
        
        # Get valid statuses for this business
        valid_statuses_dict = self._get_valid_statuses_dict(tenant_id)
        if not valid_statuses_dict:
            log.warning(f"No valid statuses found for tenant {tenant_id}")
            return None
        
        # 🆕 Priority 0: Use AI to intelligently determine status
        # This is the SMART method that actually understands the conversation
        text_to_analyze = call_summary if call_summary else call_transcript
        if text_to_analyze and len(text_to_analyze) > 10:
            suggested = self._suggest_status_with_ai(
                text_to_analyze, 
                valid_statuses_dict, 
                call_direction
            )
            if suggested:
                log.info(f"[AutoStatus] ✅ AI suggested '{suggested}' for lead {lead_id}")
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
המשימה שלך היא לקבוע את הסטטוס המתאים ביותר עבור הליד הזה מתוך רשימת הסטטוסים הזמינים.

**סטטוסים זמינים:**
{status_list}

**סיכום/תמלול השיחה:**
{conversation_text}

**הנחיות:**
1. נתח את תוכן השיחה והבן את רמת העניין של הלקוח
2. זהה אם נקבע מפגש/פגישה, אם הלקוח מעוניין, לא מעוניין, או צריך מעקב
3. בחר את הסטטוס המתאים ביותר מתוך הרשימה לעיל
4. אם אף סטטוס לא מתאים באופן ברור, החזר "none"
5. החזר **רק** את שם הסטטוס בדיוק כמו שהוא ברשימה (lowercase)

**התשובה שלך (רק שם הסטטוס):**"""

            # Call OpenAI
            response = client.chat.completions.create(
                model="gpt-4o-mini",  # Fast and cheap for this task
                messages=[
                    {
                        "role": "system",
                        "content": "אתה מערכת חכמה לניתוח שיחות. תמיד החזר רק שם סטטוס אחד או 'none'."
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
    structured_extraction: Optional[dict] = None
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
        structured_extraction=structured_extraction
    )
