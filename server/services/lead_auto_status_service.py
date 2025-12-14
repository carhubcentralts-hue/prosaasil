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
        Suggest a status for a lead based on call outcome
        
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
        valid_statuses = self._get_valid_statuses(tenant_id)
        if not valid_statuses:
            log.warning(f"No valid statuses found for tenant {tenant_id}")
            return None
        
        # Priority 1: Use structured extraction if available
        if structured_extraction:
            suggested = self._map_from_structured_extraction(structured_extraction, valid_statuses)
            if suggested:
                log.info(f"[AutoStatus] Suggested '{suggested}' from structured extraction for lead {lead_id}")
                return suggested
        
        # Priority 2: Use keyword scoring on summary (preferred) or transcript
        text_to_analyze = call_summary if call_summary else call_transcript
        if text_to_analyze and len(text_to_analyze) > 10:
            suggested = self._map_from_keywords(text_to_analyze, valid_statuses)
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
    
    def _map_from_keywords(self, text: str, valid_statuses: set) -> Optional[str]:
        """
        Map from text content using keyword scoring
        
        Looks for Hebrew and English keywords that indicate call outcome
        """
        text_lower = text.lower()
        
        # Pattern 1: Not interested / Not relevant
        not_relevant_keywords = [
            'לא מעוניין', 'לא רלוונטי', 'להסיר', 'תפסיקו', 'לא מתאים',
            'not interested', 'not relevant', 'remove me', 'stop calling',
            'תמחקו אותי', 'אל תתקשרו', 'לא צריך'
        ]
        
        if any(kw in text_lower for kw in not_relevant_keywords):
            if 'not_relevant' in valid_statuses:
                return 'not_relevant'
            elif 'lost' in valid_statuses:  # Fallback
                return 'lost'
        
        # Pattern 2: Interested / Wants more info
        interested_keywords = [
            'מעוניין', 'כן רוצה', 'תשלח פרטים', 'דברו איתי', 'מתאים לי',
            'interested', 'yes please', 'send details', 'call me back',
            'אני רוצה', 'נשמע טוב', 'בואו נדבר'
        ]
        
        if any(kw in text_lower for kw in interested_keywords):
            if 'interested' in valid_statuses:
                return 'interested'
            elif 'qualified' in valid_statuses:  # Fallback
                return 'qualified'
        
        # Pattern 3: Follow up / Call back later
        follow_up_keywords = [
            'תחזרו', 'מאוחר יותר', 'שבוע הבא', 'חודש הבא', 'תתקשרו שוב',
            'call back', 'follow up', 'later', 'next week', 'next month',
            'בעוד כמה ימים', 'אחרי החגים', 'בשבוע הבא'
        ]
        
        if any(kw in text_lower for kw in follow_up_keywords):
            if 'follow_up' in valid_statuses:
                return 'follow_up'
        
        # Pattern 4: No answer / Voicemail
        no_answer_keywords = [
            'לא ענה', 'אין מענה', 'תא קולי', 'לא זמין', 'לא פנוי',
            'no answer', 'voicemail', 'not available', 'unavailable',
            'מכשיר כבוי', 'לא משיב'
        ]
        
        if any(kw in text_lower for kw in no_answer_keywords):
            if 'no_answer' in valid_statuses:
                return 'no_answer'
            elif 'attempting' in valid_statuses:  # Fallback
                return 'attempting'
        
        # Pattern 5: Appointment / Meeting scheduled
        appointment_keywords = [
            'קבענו פגישה', 'נקבע', 'ביום', 'בשעה', 'יום רביעי', 'יום חמישי',
            'appointment', 'meeting', 'scheduled', 'confirmed',
            'בוקר מתאים', 'אחר הצהריים מתאים'
        ]
        
        if any(kw in text_lower for kw in appointment_keywords):
            if 'qualified' in valid_statuses:
                return 'qualified'
            elif 'interested' in valid_statuses:  # Fallback
                return 'interested'
        
        # Default fallback: If we got here and text is long enough, assume contacted
        if len(text) > 50:  # Meaningful conversation happened
            if 'contacted' in valid_statuses:
                return 'contacted'
        
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
