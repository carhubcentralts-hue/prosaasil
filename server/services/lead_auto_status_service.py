"""
Lead Auto Status Service
Automatically suggests lead status based on call outcome (inbound + outbound)
Dynamic mapping using structured extraction + keyword scoring
Enhanced with smart status equivalence checking to avoid unnecessary changes
"""
import logging
import re
from typing import Optional, Tuple

log = logging.getLogger(__name__)

# Configuration constants
CALL_HISTORY_LIMIT = 10  # Number of previous calls to check for no-answer progression

# Status family/group definitions for equivalence checking
# Statuses in the same group are semantically similar
STATUS_FAMILIES = {
    'NO_ANSWER': ['no_answer', 'no answer', 'אין מענה', 'לא ענה', 'לא נענה', 'unanswered', 
                  'voicemail', 'תא קולי', 'משיבון', 'busy', 'תפוס', 'קו תפוס', 'failed', 'נכשל'],
    'INTERESTED': ['interested', 'hot', 'warm', 'מעוניין', 'חם', 'מתעניין', 'פוטנציאל'],
    'QUALIFIED': ['qualified', 'appointment', 'meeting', 'נקבע', 'פגישה', 'מוכשר', 'סגירה'],
    'NOT_RELEVANT': ['not_relevant', 'not_interested', 'לא רלוונטי', 'לא מעוניין', 'להסיר', 'חסום', 'lost', 'אובדן'],
    'FOLLOW_UP': ['follow_up', 'callback', 'חזרה', 'תזכורת', 'תחזור', 'מאוחר יותר'],
    'CONTACTED': ['contacted', 'answered', 'נוצר קשר', 'נענה', 'ענה'],
    'ATTEMPTING': ['attempting', 'trying', 'ניסיון', 'בניסיון', 'מנסה'],
    'NEW': ['new', 'חדש', 'fresh', 'lead']
}

# Status progression order - higher number = more advanced in sales funnel
# Statuses with same score are considered equivalent
STATUS_PROGRESSION_SCORE = {
    'NO_ANSWER': 1,
    'ATTEMPTING': 2,
    'CONTACTED': 3,
    'NOT_RELEVANT': 3,  # Negative outcome, but contacted
    'FOLLOW_UP': 4,
    'INTERESTED': 5,
    'QUALIFIED': 6,
    'NEW': 0  # Starting point
}


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
        
        # 🆕 CRITICAL FIX: Handle no-answer calls with smart progression!
        # Check BOTH duration and summary content to catch all no-answer cases
        text_to_analyze = call_summary if call_summary else call_transcript
        
        # Method 1: Check for 0-3 second duration (very short = likely no answer)
        is_very_short_call = call_duration is not None and call_duration < 3
        
        # Method 2: Check for explicit no-answer indicators in summary/transcript
        no_answer_indicators = [
            'לא נענה', 'לא ענה', 'אין מענה', 'no answer', 'unanswered', 
            'didn\'t answer', 'did not answer', 'לא השיב', 'לא הגיב',
            'ניתוק מיידי', 'immediate disconnect', '0 שניות', '1 שנייה', '2 שניות',
            'שיחה לא נענתה',  # Direct match for our summary service output
            'קו תפוס', 'line busy', 'busy', 'תפוס',  # 🆕 CRITICAL FIX: Include busy signals!
            'שיחה נכשלה', 'call failed', 'failed', 'נכשל'  # 🆕 Include failed calls
        ]
        has_no_answer_indicator = False
        matched_indicator = None
        if text_to_analyze:
            text_lower = text_to_analyze.lower()
            for indicator in no_answer_indicators:
                if indicator in text_lower:
                    has_no_answer_indicator = True
                    matched_indicator = indicator
                    break
        
        # If EITHER condition is true → handle as no-answer with smart progression
        if is_very_short_call or has_no_answer_indicator:
            reason = f"duration < 3s" if is_very_short_call else f"matched indicator: '{matched_indicator}' in text"
            log.info(f"[AutoStatus] 🔍 Detected no-answer call for lead {lead_id} ({reason})")
            log.info(f"[AutoStatus] 📋 Summary/Transcript text: '{text_to_analyze[:100]}...'")
            suggested = self._handle_no_answer_with_progression(tenant_id, lead_id, valid_statuses_dict)
            if suggested:
                log.info(f"[AutoStatus] ✅ No-answer progression suggested '{suggested}' for lead {lead_id}")
                return suggested
            else:
                log.warning(f"[AutoStatus] ⚠️ No-answer detected but no status suggested for lead {lead_id} - check available statuses!")
        
        # 🆕 SIMPLIFIED SMART LOGIC: Always use summary/transcript (now always available!)
        # The summary now includes duration and disconnect reason for ALL calls,
        # so we don't need complex duration-based logic anymore!
        
        # Priority 0: Use AI to intelligently determine status (MAIN PATH)
        # This is the SMART method that actually understands the conversation
        # 🆕 Now the summary ALWAYS includes duration and disconnect reason - SUPER SMART!
        if text_to_analyze and len(text_to_analyze) > 10:
            suggested = self._suggest_status_with_ai(
                text_to_analyze, 
                valid_statuses_dict, 
                call_direction,
                tenant_id=tenant_id,  # 🆕 Pass for smart progression
                lead_id=lead_id  # 🆕 Pass for smart progression
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
            suggested = self._map_from_keywords(text_to_analyze, valid_statuses_set, tenant_id)
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
    
    def _get_valid_statuses_full(self, tenant_id: int) -> list:
        """
        Get full status objects for tenant (including name, label, description)
        Used for smart matching against Hebrew/multilingual labels
        
        Returns: List of LeadStatus objects
        """
        from server.models_sql import LeadStatus
        
        statuses = LeadStatus.query.filter_by(
            business_id=tenant_id,
            is_active=True
        ).all()
        
        return statuses
    
    def _suggest_status_with_ai(
        self, 
        conversation_text: str, 
        valid_statuses: dict, 
        call_direction: str,
        tenant_id: int = None,
        lead_id: int = None
    ) -> Optional[str]:
        """
        🆕 INTELLIGENT STATUS SUGGESTION using OpenAI - Dynamic Hebrew Label Selection
        
        Uses GPT-4 to analyze the conversation and intelligently match
        to one of the available statuses for this business.
        
        🔥 NEW APPROACH (per requirement):
        1. Send AI the Hebrew labels (for understanding context)
        2. AI returns JSON with selected_label_he (Hebrew label it chose)
        3. Backend maps label back to status_id
        
        This ensures:
        - AI understands context through Hebrew labels
        - Exact label matching prevents "inventing" statuses
        - Works dynamically for any business's custom status names
        
        Args:
            conversation_text: Call summary or transcript
            valid_statuses: Dict of {status_name: status_description}
            call_direction: 'inbound' or 'outbound'
            tenant_id: Business ID (for checking lead history)
            lead_id: Lead ID (for checking previous status)
            
        Returns:
            Status name (status_id) or None
        """
        try:
            import os
            import json
            from openai import OpenAI
            
            # Get OpenAI API key
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                log.warning("[AutoStatus] No OpenAI API key found - falling back to keyword matching")
                return None
            
            client = OpenAI(api_key=api_key)
            
            # ═══════════════════════════════════════════════════════════════════════
            # 🔥 DYNAMIC STATUS LIST: Build clean list with Hebrew labels for AI
            # Format: Each line shows the Hebrew label (what AI understands)
            # AI will select from these exact Hebrew labels only
            # ═══════════════════════════════════════════════════════════════════════
            full_statuses = self._get_valid_statuses_full(tenant_id) if tenant_id else []
            
            if not full_statuses:
                log.warning(f"[AutoStatus] No statuses found for tenant {tenant_id}")
                return None
            
            # Build mapping: Hebrew label -> status_id (for reverse lookup)
            label_to_status_id = {}
            hebrew_labels_list = []
            
            for status in full_statuses:
                status_id = status.name  # The actual ID to return
                label_he = status.label or status.name  # Hebrew display name
                
                # Store mapping for reverse lookup
                label_to_status_id[label_he.strip()] = status_id
                hebrew_labels_list.append(label_he.strip())
            
            # Create clean list of Hebrew labels for the AI prompt
            status_labels_formatted = "\n".join([f"- {label}" for label in hebrew_labels_list])
            
            # ═══════════════════════════════════════════════════════════════════════
            # 🔥 CLEAN PROMPT: Two blocks only - summary + status list
            # AI must return JSON with selected_label_he (exact Hebrew match)
            # ═══════════════════════════════════════════════════════════════════════
            prompt = f"""סיכום השיחה:
{conversation_text}

רשימת הסטטוסים האפשריים (בחר אחד בדיוק מהרשימה):
{status_labels_formatted}

בחר בדיוק אחד מהסטטוסים מהרשימה. אסור להמציא. הפלט חייב להיות JSON בלבד."""

            # Call OpenAI with temperature=0 for deterministic output
            response = client.chat.completions.create(
                model="gpt-4o-mini",  # Fast and cheap for this task
                messages=[
                    {
                        "role": "system",
                        "content": """אתה מערכת לבחירת סטטוס ליד על פי סיכום שיחה.

כללים מחייבים:
1. קרא את סיכום השיחה
2. בחר סטטוס אחד בדיוק מתוך הרשימה שקיבלת
3. אסור להמציא סטטוס - רק מה שברשימה!
4. אם לא בטוח, החזר ערך ריק

פורמט הפלט (JSON בלבד):
{"selected_label_he":"<הסטטוס בדיוק כפי שמופיע ברשימה>"}

אם אין התאמה ברורה:
{"selected_label_he":""}"""
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0,  # 🔥 temperature=0 for deterministic output (per requirement)
                max_tokens=50
            )
            
            ai_response = response.choices[0].message.content.strip()
            log.debug(f"[AutoStatus] 🤖 AI raw response: '{ai_response}'")
            
            # ═══════════════════════════════════════════════════════════════════════
            # 🔥 PARSE JSON RESPONSE: Extract selected_label_he
            # ═══════════════════════════════════════════════════════════════════════
            selected_label = ""
            try:
                # Try to parse as JSON
                # Handle potential markdown code blocks
                if ai_response.startswith('```'):
                    ai_response = ai_response.split('```')[1]
                    if ai_response.startswith('json'):
                        ai_response = ai_response[4:]
                    ai_response = ai_response.strip()
                
                parsed = json.loads(ai_response)
                selected_label = parsed.get("selected_label_he", "").strip()
            except json.JSONDecodeError:
                # If JSON parsing fails, try to extract the label directly
                log.warning(f"[AutoStatus] JSON parsing failed, trying direct extraction")
                # Try to find the label in the response
                for label in hebrew_labels_list:
                    if label in ai_response:
                        selected_label = label
                        break
            
            log.info(f"[AutoStatus] 📋 AI selected label: '{selected_label}'")
            
            # ═══════════════════════════════════════════════════════════════════════
            # 🔥 MAP LABEL BACK TO STATUS_ID: EXACT MATCH ONLY
            # Per requirement: No exact match → don't change status at all
            # This prevents incorrect status changes from fuzzy/partial matches
            # ═══════════════════════════════════════════════════════════════════════
            if not selected_label:
                log.info(f"[AutoStatus] ⚪ AI returned empty selection - no status change")
                return None
            
            # Exact match lookup (strict - no partial/fuzzy matching)
            if selected_label in label_to_status_id:
                status_id = label_to_status_id[selected_label]
                log.info(f"[AutoStatus] ✅ Exact match: '{selected_label}' → status_id '{status_id}'")
                return status_id
            
            # Try case-insensitive exact match as only fallback
            for label, sid in label_to_status_id.items():
                if label.lower().strip() == selected_label.lower().strip():
                    log.info(f"[AutoStatus] ✅ Case-insensitive exact match: '{selected_label}' → '{sid}'")
                    return sid
            
            # 🔥 NO PARTIAL MATCHING: If no exact match, don't change status
            # This prevents incorrect status changes from "inventing" matches
            log.warning(f"[AutoStatus] ❌ No exact match for '{selected_label}' - NOT changing status")
            log.debug(f"[AutoStatus] Available labels were: {list(label_to_status_id.keys())}")
            return None
            
        except Exception as e:
            log.error(f"[AutoStatus] Error in AI status suggestion: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _map_label_to_status_id(self, label_or_variant: str, tenant_id: int) -> Optional[str]:
        """
        🔥 FIX: Map AI response (label/variant) to valid status_id
        
        This handles cases where AI returns:
        - Hebrew label (e.g., "אין מענה 2")
        - English variant (e.g., "no_answer_2", "no answer 2")
        - Mixed (e.g., "no_answer_2" when status_id is "custom_xyz123")
        
        Args:
            label_or_variant: The AI's suggested status (may be label, not ID)
            tenant_id: Business ID
            
        Returns:
            Valid status_id (name) or None if no match found
        """
        if not label_or_variant:
            return None
            
        # Get full status objects with labels
        full_statuses = self._get_valid_statuses_full(tenant_id)
        if not full_statuses:
            return None
        
        label_lower = label_or_variant.lower().strip()
        
        # Strategy 1: Exact match on name (already checked, but for completeness)
        for status in full_statuses:
            if status.name.lower() == label_lower:
                return status.name
        
        # Strategy 2: Exact match on label (Hebrew display name)
        for status in full_statuses:
            if status.label and status.label.lower() == label_lower:
                log.info(f"[AutoStatus] Label match: '{label_lower}' → '{status.name}' (label='{status.label}')")
                return status.name
        
        # Strategy 3: Partial/fuzzy match on label
        # Handle cases like "אין מענה 2" matching status with label "אין מענה 2"
        for status in full_statuses:
            if status.label:
                status_label_lower = status.label.lower()
                # Check if labels are semantically similar
                if (label_lower in status_label_lower or 
                    status_label_lower in label_lower):
                    log.info(f"[AutoStatus] Partial label match: '{label_lower}' → '{status.name}' (label='{status.label}')")
                    return status.name
        
        # Strategy 4: Pattern-based mapping for common cases
        # Handle "no_answer_2" style variants
        no_answer_patterns = ['no_answer', 'no answer', 'אין מענה', 'לא ענה', 'לא נענה']
        is_no_answer_variant = any(p in label_lower for p in no_answer_patterns)
        
        if is_no_answer_variant:
            # Extract number if present (e.g., "no_answer_2" → 2)
            import re
            numbers = re.findall(r'\d+', label_lower)
            target_number = int(numbers[-1]) if numbers else None
            
            if target_number:
                # Look for status with that number in name or label
                for status in full_statuses:
                    status_name_lower = status.name.lower()
                    status_label_lower = (status.label or "").lower()
                    
                    # Check if this status has the same number
                    name_numbers = re.findall(r'\d+', status_name_lower)
                    label_numbers = re.findall(r'\d+', status_label_lower)
                    
                    if ((name_numbers and int(name_numbers[-1]) == target_number) or
                        (label_numbers and int(label_numbers[-1]) == target_number)):
                        # Verify it's a no-answer type status
                        if any(p in status_name_lower or p in status_label_lower for p in no_answer_patterns):
                            log.info(f"[AutoStatus] Number pattern match: '{label_lower}' → '{status.name}' (target_num={target_number})")
                            return status.name
            
            # Fallback: return base no_answer status if exists
            for status in full_statuses:
                if status.name.lower() in ['no_answer', 'אין מענה']:
                    log.info(f"[AutoStatus] Fallback to base no_answer: '{label_lower}' → '{status.name}'")
                    return status.name
        
        # Strategy 5: Synonym-based matching
        synonym_groups = {
            'voicemail': ['voicemail', 'תא קולי', 'משיבון'],
            'busy': ['busy', 'תפוס', 'קו תפוס'],
            'interested': ['interested', 'מעוניין', 'מתעניין', 'hot', 'חם'],
            'not_interested': ['not_interested', 'לא מעוניין', 'not_relevant', 'לא רלוונטי'],
            'follow_up': ['follow_up', 'callback', 'חזרה', 'לחזור'],
        }
        
        for base_status, synonyms in synonym_groups.items():
            if any(syn in label_lower for syn in synonyms):
                # Find matching status
                for status in full_statuses:
                    if any(syn in status.name.lower() or syn in (status.label or "").lower() 
                           for syn in synonyms):
                        log.info(f"[AutoStatus] Synonym match: '{label_lower}' → '{status.name}'")
                        return status.name
        
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
    
    def _build_status_groups(self, valid_statuses: set, tenant_id: int) -> dict:
        """
        🆕 SMART: Build semantic groups using HEBREW LABELS from database!
        
        Instead of just checking English status names, this now:
        1. Gets full status objects with Hebrew labels
        2. Checks BOTH name AND label fields
        3. Uses label (user-visible Hebrew text) for better matching
        
        Args:
            valid_statuses: Set of valid status names
            tenant_id: Business ID to fetch Hebrew labels
            
        Returns:
            dict mapping group names to available status names for that group
        """
        # Get full status objects with labels
        full_statuses = self._get_valid_statuses_full(tenant_id)
        
        # Define status synonyms for each semantic group (Hebrew + English)
        groups = {
            'APPOINTMENT_SET': ['qualified', 'appointment', 'meeting', 'נקבע', 'פגישה', 'סגירה', 'פגישה קבועה', 'נקבעה פגישה'],
            'HOT_INTERESTED': ['interested', 'hot', 'מעוניין', 'חם', 'מתעניין', 'המשך טיפול', 'פוטנציאל', 'warm', 'רותח'],
            'FOLLOW_UP': ['follow_up', 'callback', 'חזרה', 'תזכורת', 'תחזור', 'מאוחר יותר', 'לחזור', 'תזמון מחדש'],
            'NOT_RELEVANT': ['not_relevant', 'not_interested', 'לא רלוונטי', 'לא מעוניין', 'להסיר', 'חסום', 'דחייה', 'סירוב'],
            'NO_ANSWER': ['no_answer', 'אין מענה', 'לא ענה', 'לא נענה', 'תא קולי', 'busy', 'תפוס', 'failed', 'נכשל', 'קו תפוס', 'משיבון'],
        }
        
        result = {}
        for group_name, synonyms in groups.items():
            # Find which statuses from this business match this group
            # 🆕 CRITICAL: Check BOTH name AND label (label is in Hebrew!)
            matching = []
            for status_obj in full_statuses:
                # Combine name + label for searching
                searchable_text = status_obj.name.lower() if status_obj.name else ""
                if status_obj.label:
                    searchable_text += " " + status_obj.label.lower()
                
                # Check if any synonym matches
                for syn in synonyms:
                    if syn.lower() in searchable_text or searchable_text in syn.lower():
                        matching.append(status_obj.name)
                        break
            
            if matching:
                # Prefer exact matches, then use first match
                for preferred in synonyms:
                    if preferred in matching:
                        result[group_name] = preferred
                        break
                else:
                    result[group_name] = matching[0]
        
        return result
    
    def _map_from_keywords(self, text: str, valid_statuses: set, tenant_id: int) -> Optional[str]:
        """
        🆕 SUPER SMART: Map from text content using HEBREW LABELS from database!
        
        Now checks status labels (Hebrew user-facing text) not just English names!
        This makes keyword matching MUCH better for Hebrew businesses.
        
        Priority order (highest to lowest):
        1. Appointment set
        2. Hot/Interested  
        3. Follow up
        4. Not relevant
        5. No answer
        
        Args:
            text: Call summary or transcript text
            valid_statuses: Set of valid status names
            tenant_id: Business ID to fetch Hebrew labels
            
        Returns:
            Status name or None
        """
        text_lower = text.lower()
        
        # Build status groups from available statuses WITH HEBREW LABELS
        status_groups = self._build_status_groups(valid_statuses, tenant_id)
        
        # Score each pattern group (higher score = stronger match)
        scores = {}
        
        # Pattern 4: Not interested / Not relevant (CHECK FIRST - contains negations)
        # Must check before interested keywords to catch "לא מעוניין"
        not_relevant_keywords = [
            'לא מעוניין', 'לא רלוונטי', 'להסיר', 'תפסיקו', 'לא מתאים',
            'not interested', 'not relevant', 'remove me', 'stop calling',
            'תמחקו אותי', 'אל תתקשרו', 'לא צריך', 'תורידו אותי', 'להפסיק',
            'לא מתאים לי', 'זה לא בשבילי', 'אני לא צריך', 'אין לי עניין'
        ]
        not_relevant_score = sum(1 for kw in not_relevant_keywords if kw in text_lower)
        if not_relevant_score > 0 and 'NOT_RELEVANT' in status_groups:
            scores['NOT_RELEVANT'] = (4, not_relevant_score)  # Priority 4
        
        # Pattern 1: Appointment / Meeting scheduled (HIGHEST PRIORITY)
        appointment_keywords = [
            'קבענו פגישה', 'נקבע', 'פגישה', 'meeting', 'appointment', 'scheduled', 'confirmed',
            'בוקר מתאים', 'אחר הצהריים מתאים', 'ביום', 'בשעה', 'נפגש',
            'נקבעה פגישה', 'קבעתי פגישה', 'מתאים לי', 'אשמח להיפגש', 'בואו נפגש'
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
                'תן הצעה', 'תתקשרו', 'כן', 'נשמע', 'יפה', 'אשמח לשמוע', 'תספר לי עוד',
                'אני מתעניין', 'אני מתעניינת', 'זה מעניין', 'רוצה לשמוע', 'אשמח למידע'
            ]
            interested_score = sum(1 for kw in interested_keywords if kw in text_lower)
            if interested_score > 0 and 'HOT_INTERESTED' in status_groups:
                scores['HOT_INTERESTED'] = (2, interested_score)  # Priority 2
        
        # Pattern 3: Follow up / Call back later (THIRD PRIORITY)
        follow_up_keywords = [
            'תחזרו', 'תחזור', 'מאוחר יותר', 'שבוע הבא', 'חודש הבא', 'תתקשרו שוב',
            'call back', 'follow up', 'later', 'next week', 'next month',
            'בעוד כמה ימים', 'אחרי החגים', 'אחרי החג', 'בשבוע הבא', 'תזכיר לי',
            'חזור אליי', 'תחזרו מחר', 'בוא נדבר אחר כך', 'לא עכשיו', 'לא זמין עכשיו'
        ]
        follow_up_score = sum(1 for kw in follow_up_keywords if kw in text_lower)
        if follow_up_score > 0 and 'FOLLOW_UP' in status_groups:
            scores['FOLLOW_UP'] = (3, follow_up_score)  # Priority 3
        
        # Pattern 5: No answer / Voicemail / Busy (LOWEST PRIORITY)
        no_answer_keywords = [
            'לא ענה', 'אין מענה', 'תא קולי', 'לא זמין', 'לא פנוי',
            'no answer', 'voicemail', 'not available', 'unavailable',
            'מכשיר כבוי', 'לא משיב', 'מספר לא זמין',
            'קו תפוס', 'busy', 'line busy', 'תפוס',  # 🆕 CRITICAL FIX: Include busy!
            'שיחה נכשלה', 'call failed', 'failed', 'נכשל',  # 🆕 Include failed calls
            'לא נענה', 'לא השיב', 'לא הגיב', 'משיבון'
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
        🆕 Smart no-answer status progression with SMART MULTILINGUAL MATCHING
        
        Handles intelligent status progression for no-answer calls:
        - First no-answer: → "no_answer" or "no_answer_1" 
        - Second no-answer: → "no_answer_2" (if exists)
        - Third no-answer: → "no_answer_3" (if exists)
        
        🆕 ENHANCED: Searches across status name, label, AND description fields
        to find Hebrew/multilingual matches like "אין מענה", "לא נענה", etc.
        
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
        
        # 🆕 CRITICAL FIX: Get full status objects to check ALL fields (name, label, description)
        full_statuses = self._get_valid_statuses_full(tenant_id)
        
        # Find available no-answer statuses in this business
        # Check for: no_answer, no_answer_1, no_answer_2, no_answer_3, אין מענה, אין מענה 2, אין מענה 3
        # 🆕 ALSO include: busy, תפוס, failed, נכשל (they're all types of no-answer!)
        # 🆕 SMART: Check name, label, AND description fields!
        available_no_answer_statuses = []
        status_match_info = {}  # Track which field matched for logging
        
        # Keywords to search for across all fields
        no_answer_keywords = [
            'no_answer', 'no answer', 'אין מענה', 'לא ענה', 'לא נענה',
            'busy', 'תפוס', 'קו תפוס', 'failed', 'נכשל', 'שיחה נכשלה',
            'unanswered', 'not answered', 'didnt answer', "didn't answer"
        ]
        
        for status in full_statuses:
            # Combine all searchable text: name, label, description
            searchable_text = ""
            matched_in = []
            
            # Check name field
            if status.name:
                name_lower = status.name.lower()
                if any(kw in name_lower for kw in no_answer_keywords):
                    matched_in.append("name")
                searchable_text += name_lower + " "
            
            # 🆕 CRITICAL: Check label field (user-visible text, often in Hebrew!)
            if status.label:
                label_lower = status.label.lower()
                if any(kw in label_lower for kw in no_answer_keywords):
                    matched_in.append("label")
                searchable_text += label_lower + " "
            
            # Check description field
            if status.description:
                desc_lower = status.description.lower()
                if any(kw in desc_lower for kw in no_answer_keywords):
                    matched_in.append("description")
                searchable_text += desc_lower
            
            # If any field matched, add this status
            if matched_in:
                available_no_answer_statuses.append(status.name)
                status_match_info[status.name] = {
                    'fields': matched_in,
                    'label': status.label,
                    'name': status.name
                }
                log.info(f"[AutoStatus] 🎯 Found no-answer status: '{status.name}' (label: '{status.label}', matched in: {', '.join(matched_in)})")
        
        if not available_no_answer_statuses:
            log.warning(f"[AutoStatus] ⚠️ No 'no_answer' status available for business {tenant_id}!")
            log.info(f"[AutoStatus] 📋 Available statuses (first 10): {', '.join(list(valid_statuses_set)[:10])}")
            log.info(f"[AutoStatus] 💡 TIP: Create a status with label 'אין מענה' or 'no answer' to enable auto-status for no-answer calls")
            return None
        
        log.info(f"[AutoStatus] 🔍 Found {len(available_no_answer_statuses)} no-answer statuses: {', '.join(available_no_answer_statuses)}")
        
        # 🆕 ENHANCED: Count previous no-answer calls from CALL HISTORY
        # This is SMARTER than just looking at current status!
        try:
            # Get all previous calls for this lead
            previous_calls = CallLog.query.filter_by(
                business_id=tenant_id,
                lead_id=lead_id
            ).order_by(CallLog.created_at.desc()).limit(CALL_HISTORY_LIMIT).all()
            
            # 🆕 Count how many no-answer calls we've already had
            no_answer_call_count = 0
            no_answer_patterns = [
                'לא נענה', 'אין מענה', 'no answer', 'קו תפוס', 'busy', 
                'שיחה נכשלה', 'failed', 'לא ענה', 'תפוס', 'נכשל'
            ]
            
            log.info(f"[AutoStatus] 📋 Checking call history for lead {lead_id}...")
            for call in previous_calls:
                if call.summary:
                    summary_lower = call.summary.lower()
                    is_no_answer = any(pattern in summary_lower for pattern in no_answer_patterns)
                    if is_no_answer:
                        no_answer_call_count += 1
                        log.info(f"[AutoStatus]   - Call {call.call_sid[:20]}... had no-answer: '{call.summary[:60]}...'")
            
            log.info(f"[AutoStatus] 🔢 Found {no_answer_call_count} previous no-answer calls for lead {lead_id}")
            
            # Get lead's current status to check if it's already a no-answer variant
            from server.models_sql import Lead, LeadStatus
            lead = Lead.query.filter_by(id=lead_id).first()
            
            # Determine next attempt based on BOTH history and current status
            next_attempt = 1  # Default
            
            if lead and lead.status:
                # 🆕 CRITICAL: Check if current status is a no-answer status
                # Need to check BOTH the status name AND its label
                current_status_obj = LeadStatus.query.filter_by(
                    business_id=tenant_id,
                    name=lead.status,
                    is_active=True
                ).first()
                
                is_no_answer_status = False
                current_attempt = 1
                
                # Check if status name OR label contains no-answer keywords
                status_name_lower = lead.status.lower()
                status_label_lower = (current_status_obj.label.lower() if current_status_obj and current_status_obj.label else '')
                
                # Combine both for checking
                combined_text = status_name_lower + ' ' + status_label_lower
                
                if ('no_answer' in combined_text or 
                    'no answer' in combined_text or 
                    'אין מענה' in combined_text or
                    'לא ענה' in combined_text or
                    'לא נענה' in combined_text or
                    'busy' in combined_text or
                    'תפוס' in combined_text):
                    is_no_answer_status = True
                    
                    # Extract number from BOTH name and label
                    numbers_in_name = re.findall(r'\d+', lead.status)
                    numbers_in_label = re.findall(r'\d+', status_label_lower)
                    
                    # Prefer label number over name number
                    if numbers_in_label:
                        current_attempt = int(numbers_in_label[-1])
                    elif numbers_in_name:
                        current_attempt = int(numbers_in_name[-1])
                    else:
                        current_attempt = 1  # First no-answer (no number = attempt 1)
                    
                    # Determine next attempt
                    next_attempt = current_attempt + 1
                    
                    log.info(f"[AutoStatus] 👤 Lead {lead_id} currently at no-answer status '{lead.status}' (label: '{status_label_lower}', attempt {current_attempt})")
                    log.info(f"[AutoStatus] ➡️  Next attempt will be: {next_attempt}")
                
                if not is_no_answer_status:
                    # Not currently no-answer, but check history
                    # If we have no-answer calls in history, start from attempt based on count
                    if no_answer_call_count > 0:
                        next_attempt = no_answer_call_count + 1
                        log.info(f"[AutoStatus] 👤 Lead {lead_id} not in no-answer status, but has {no_answer_call_count} no-answer calls in history")
                        log.info(f"[AutoStatus] ➡️  Starting from attempt: {next_attempt}")
                    else:
                        # First time!
                        next_attempt = 1
                        log.info(f"[AutoStatus] 👤 Lead {lead_id} - first no-answer attempt!")
            else:
                # No lead found or no status
                if no_answer_call_count > 0:
                    next_attempt = no_answer_call_count + 1
                else:
                    next_attempt = 1
                log.info(f"[AutoStatus] ⚠️  Lead {lead_id} has no status yet, using attempt: {next_attempt}")
            
            # 🆕 SMART NUMBER EXTRACTION: Extract numbers from both name AND label
            # Build map: {attempt_number: status_name}
            status_by_attempt = {}
            
            for status_name in available_no_answer_statuses:
                # Get the full status object to check label
                status_obj = next((s for s in full_statuses if s.name == status_name), None)
                if not status_obj:
                    continue
                
                # Extract numbers from name AND label
                numbers_in_name = re.findall(r'\d+', status_name)
                numbers_in_label = re.findall(r'\d+', status_obj.label or '')
                
                # Combine all found numbers (prefer label over name)
                all_numbers = numbers_in_label + numbers_in_name
                
                if all_numbers:
                    # Take the first (or last) number found - represents the attempt
                    attempt_num = int(all_numbers[0])
                    status_by_attempt[attempt_num] = status_name
                    log.info(f"[AutoStatus] 🔢 Mapped attempt {attempt_num} → status '{status_name}' (label: '{status_obj.label}')")
                else:
                    # No number in name or label - this is the base status (attempt 1)
                    if 1 not in status_by_attempt:
                        status_by_attempt[1] = status_name
                        log.info(f"[AutoStatus] 🔢 Mapped base status (attempt 1) → '{status_name}' (label: '{status_obj.label}')")
            
            log.info(f"[AutoStatus] 📊 Available attempt mapping: {status_by_attempt}")
            
            # Try to find status matching the attempt number
            target_status = None
            
            # Priority 1: Exact match for attempt number
            if next_attempt in status_by_attempt:
                target_status = status_by_attempt[next_attempt]
                log.info(f"[AutoStatus] ✅ Found exact match for attempt {next_attempt}: '{target_status}'")
            
            # Priority 2: If no exact match, use highest available attempt that's <= next_attempt
            if not target_status:
                available_attempts = sorted([k for k in status_by_attempt.keys() if k <= next_attempt], reverse=True)
                if available_attempts:
                    fallback_attempt = available_attempts[0]
                    target_status = status_by_attempt[fallback_attempt]
                    log.info(f"[AutoStatus] 📌 No exact match for attempt {next_attempt}, using closest: attempt {fallback_attempt} → '{target_status}'")
            
            # Priority 3: If still nothing, just use first available no-answer status
            if not target_status and available_no_answer_statuses:
                target_status = available_no_answer_statuses[0]
                log.info(f"[AutoStatus] 🔄 Fallback: using first available no-answer status: '{target_status}'")
            
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
    
    def _get_status_family(self, status_name: str, tenant_id: Optional[int] = None) -> Optional[str]:
        """
        🆕 ENHANCED: Dynamically determine which family/group a status belongs to
        
        Uses AI-powered semantic understanding to classify ANY status name (Hebrew, English, custom)
        into semantic families, WITHOUT relying on hardcoded keyword lists!
        
        This makes the system truly dynamic and adaptive to any business's custom statuses.
        
        Args:
            status_name: Status name to classify (can be ANY name in ANY language!)
            tenant_id: Optional business ID for context
            
        Returns:
            Family name (e.g., 'NO_ANSWER', 'INTERESTED') or None
        """
        if not status_name:
            return None
        
        status_lower = status_name.lower()
        
        # 🔥 STEP 1: Quick keyword check for common cases (performance optimization)
        # This handles 90% of cases instantly without AI call
        for family_name, patterns in STATUS_FAMILIES.items():
            for pattern in patterns:
                # More precise matching: pattern must be contained in status name
                if pattern in status_lower:
                    return family_name
        
        # 🔥 STEP 2: AI-powered semantic classification for unknown/custom statuses
        # This is the MAGIC that makes it work with ANY status name!
        try:
            import os
            from openai import OpenAI
            
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                log.warning(f"[StatusFamily] No OpenAI API key - cannot classify custom status '{status_name}'")
                return None
            
            # Get full status info (label + description) for better classification
            status_info = None
            if tenant_id:
                status_info = self._get_full_status_info(tenant_id, status_name)
            
            # Build context for AI
            status_text = status_name
            if status_info:
                # Use label (Hebrew user-facing text) if available - much better for classification!
                if status_info.get('label'):
                    status_text = status_info['label']
                # Add description if available
                if status_info.get('description'):
                    status_text += f" ({status_info['description']})"
            
            log.info(f"[StatusFamily] 🤖 Using AI to classify custom status: '{status_text}'")
            
            client = OpenAI(api_key=api_key)
            
            # 🎯 Smart AI prompt for semantic classification
            prompt = f"""סטטוס: "{status_text}"

סווג את הסטטוס לאחת מהקטגוריות הבאות:

1. NO_ANSWER - לא נענה, אין מענה, קו תפוס, תא קולי, נכשל
2. INTERESTED - מעוניין, רוצה, מתעניין, חם, פוטנציאל
3. QUALIFIED - נקבע, פגישה, סגירה, מוכשר, הזדמנות
4. NOT_RELEVANT - לא רלוונטי, לא מעוניין, להסיר, אובדן
5. FOLLOW_UP - חזרה, תזכורת, מאוחר יותר, תחזור
6. CONTACTED - נוצר קשר, נענה, דיבר
7. ATTEMPTING - ניסיון, מנסה, בניסיון קשר
8. NEW - חדש, ליד חדש

החזר רק את שם הקטגוריה (באנגלית) או "UNKNOWN" אם לא ברור."""

            response = client.chat.completions.create(
                model="gpt-4o-mini",  # Fast and cheap
                messages=[
                    {
                        "role": "system",
                        "content": "אתה מומחה לסיווג סטטוסי לידים. סווג את הסטטוס לפי המשמעות הסמנטית שלו."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # Low temperature for consistent classification
                max_tokens=20
            )
            
            family = response.choices[0].message.content.strip().upper()
            
            # Validate response
            valid_families = ['NO_ANSWER', 'INTERESTED', 'QUALIFIED', 'NOT_RELEVANT', 
                            'FOLLOW_UP', 'CONTACTED', 'ATTEMPTING', 'NEW']
            
            if family in valid_families:
                log.info(f"[StatusFamily] ✅ AI classified '{status_text}' → {family}")
                return family
            elif family == 'UNKNOWN':
                log.info(f"[StatusFamily] ⚪ AI couldn't classify '{status_text}' (ambiguous)")
                return None
            else:
                log.warning(f"[StatusFamily] ⚠️ AI returned invalid family: '{family}' for '{status_text}'")
                return None
                
        except Exception as e:
            log.error(f"[StatusFamily] ❌ AI classification failed for '{status_name}': {e}")
            return None
    
    def _get_status_progression_score(self, status_name: str, tenant_id: Optional[int] = None) -> int:
        """
        Get the progression score for a status (how advanced it is in the sales funnel)
        
        Args:
            status_name: Status name
            tenant_id: Optional business ID for AI-powered classification
            
        Returns:
            Score (0-6), higher = more advanced
        """
        family = self._get_status_family(status_name, tenant_id)
        return STATUS_PROGRESSION_SCORE.get(family, 0)
    
    def _is_no_answer_progression(self, current_status: str, suggested_status: str, tenant_id: Optional[int] = None) -> bool:
        """
        Check if this is a valid no-answer progression (no_answer → no_answer_2 → no_answer_3)
        
        Args:
            current_status: Current lead status
            suggested_status: Suggested new status
            tenant_id: Optional business ID for AI-powered classification
            
        Returns:
            True if this is a valid no-answer progression
        """
        # Both must be in NO_ANSWER family
        if self._get_status_family(current_status, tenant_id) != 'NO_ANSWER':
            return False
        if self._get_status_family(suggested_status, tenant_id) != 'NO_ANSWER':
            return False
        
        # Extract numbers from both statuses
        current_numbers = re.findall(r'\d+', current_status)
        suggested_numbers = re.findall(r'\d+', suggested_status)
        
        current_num = int(current_numbers[-1]) if current_numbers else 1
        suggested_num = int(suggested_numbers[-1]) if suggested_numbers else 1
        
        # Valid progression: suggested number should be higher
        return suggested_num > current_num
    
    def should_change_status(
        self, 
        current_status: Optional[str], 
        suggested_status: Optional[str],
        tenant_id: int,
        call_summary: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        🆕 CRITICAL: Decide whether to change status based on SMART analysis
        
        Now uses CALL SUMMARY to understand the TRUE context and make
        the best decision possible!
        
        This is the KEY improvement - we don't just compare status names,
        we understand the CONVERSATION and decide intelligently!
        
        Rules:
        1. If no suggested status, don't change
        2. If no current status (new lead), always change
        3. If statuses are identical, don't change
        4. 🆕 If we have call summary, use AI to decide based on conversation context
        5. If statuses are in same family AND same progression level, don't change
        6. If statuses are in same family AND suggested is progression, change
        7. If suggested status is lower progression than current, don't change (downgrade)
        8. If suggested status is higher progression, change (upgrade)
        9. Default: change (be conservative, allow the change)
        
        Args:
            current_status: Lead's current status
            suggested_status: Newly suggested status
            tenant_id: Business ID
            call_summary: 🆕 Call summary for context-aware decision making
            
        Returns:
            Tuple of (should_change: bool, reason: str)
        """
        # Rule 1: No suggested status
        if not suggested_status:
            return False, "No suggested status"
        
        # Rule 2: No current status (new lead or first status assignment)
        if not current_status:
            return True, "No current status - first assignment"
        
        # Rule 3: Identical statuses
        if current_status.lower() == suggested_status.lower():
            return False, f"Already in status '{current_status}'"
        
        # 🔥 Rule 4: SMART CONTEXT-AWARE DECISION using call summary
        # This is the MAGIC - understand the conversation to make smart decisions!
        if call_summary and len(call_summary) > 20:
            try:
                smart_decision = self._make_smart_status_decision(
                    current_status=current_status,
                    suggested_status=suggested_status,
                    call_summary=call_summary,
                    tenant_id=tenant_id
                )
                
                if smart_decision:
                    should_change, reason = smart_decision
                    log.info(f"[StatusCompare] 🤖 AI-powered decision: should_change={should_change}")
                    return should_change, f"AI decision based on call: {reason}"
                    
            except Exception as e:
                log.error(f"[StatusCompare] ❌ Smart decision failed: {e}")
                # Continue to rule-based logic as fallback
        
        # Get status families and progression scores
        # 🆕 Pass tenant_id for AI-powered classification of custom statuses
        current_family = self._get_status_family(current_status, tenant_id)
        suggested_family = self._get_status_family(suggested_status, tenant_id)
        current_score = self._get_status_progression_score(current_status, tenant_id)
        suggested_score = self._get_status_progression_score(suggested_status, tenant_id)
        
        log.info(f"[StatusCompare] Current: '{current_status}' (family={current_family}, score={current_score})")
        log.info(f"[StatusCompare] Suggested: '{suggested_status}' (family={suggested_family}, score={suggested_score})")
        
        # Rule 5 & 6: Same family - check for progression
        if current_family and current_family == suggested_family:
            # Special case: NO_ANSWER progression (no_answer → no_answer_2)
            if current_family == 'NO_ANSWER':
                if self._is_no_answer_progression(current_status, suggested_status, tenant_id):
                    return True, f"Valid no-answer progression: {current_status} → {suggested_status}"
                else:
                    return False, f"Same no-answer family without valid progression"
            
            # For other families, if scores are same, don't change
            if current_score == suggested_score:
                return False, f"Same family '{current_family}' and progression level ({current_score})"
        
        # Rule 7: Don't downgrade (suggested is lower progression)
        if suggested_score < current_score:
            # Exception: NOT_RELEVANT can override any status (customer explicitly rejected)
            if suggested_family == 'NOT_RELEVANT':
                return True, f"Customer explicitly not interested - override '{current_status}'"
            
            return False, f"Would downgrade from {current_family}(score={current_score}) to {suggested_family}(score={suggested_score})"
        
        # Rule 8: Upgrade (suggested is higher progression)
        if suggested_score > current_score:
            return True, f"Upgrade from {current_family}(score={current_score}) to {suggested_family}(score={suggested_score})"
        
        # Rule 9: Default - allow change if we're not sure
        # This handles edge cases and statuses not in our families
        return True, f"Allowing change (families differ or not classified)"
    
    def _make_smart_status_decision(
        self,
        current_status: str,
        suggested_status: str,
        call_summary: str,
        tenant_id: int
    ) -> Optional[Tuple[bool, str]]:
        """
        🆕 REVOLUTIONARY: Use AI to make CONTEXT-AWARE status change decision
        
        This analyzes the ACTUAL CONVERSATION to decide if status should change!
        Much smarter than just comparing status names.
        
        Args:
            current_status: Current lead status
            suggested_status: Suggested new status  
            call_summary: Summary of the call conversation
            tenant_id: Business ID
            
        Returns:
            Tuple of (should_change: bool, reason: str) or None if cannot decide
        """
        try:
            import os
            from openai import OpenAI
            
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                log.warning("[StatusDecision] No OpenAI API key - cannot make smart decision")
                return None
            
            # Get full status info (labels in Hebrew are much more meaningful!)
            current_info = self._get_full_status_info(tenant_id, current_status)
            suggested_info = self._get_full_status_info(tenant_id, suggested_status)
            
            current_label = current_info.get('label', current_status) if current_info else current_status
            suggested_label = suggested_info.get('label', suggested_status) if suggested_info else suggested_status
            
            log.info(f"[StatusDecision] 🤖 Analyzing: '{current_label}' → '{suggested_label}' based on call summary")
            
            client = OpenAI(api_key=api_key)
            
            # 🎯 SUPER SMART AI PROMPT - analyzes conversation context
            prompt = f"""סיכום השיחה:
{call_summary}

סטטוס נוכחי: "{current_label}"
סטטוס מוצע: "{suggested_label}"

**משימה:** תחליט האם לשנות את הסטטוס על סמך תוכן השיחה.

**כללי החלטה חכמים:**
1. אם הלקוח כבר במצב שמתאים למה שקרה בשיחה → אל תשנה (למשל: כבר "מעוניין" ובשיחה היה מעוניין)
2. אם יש התקדמות משמעותית (מעוניין → נקבעה פגישה) → שנה
3. אם יש הרעה במצב (היה מעוניין עכשיו אומר לא) → שנה
4. אם זה אותו דבר בעצם (לא ענה → עדיין לא ענה) → אל תשנה אלא אם זה ניסיון נוסף
5. אם לא ברור מהשיחה → אל תשנה (שמור סטטוס נוכחי)

החזר JSON בדיוק בפורמט הזה:
{{
  "should_change": true/false,
  "reason": "הסבר קצר בעברית למה כן או לא"
}}"""

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """אתה מומחה לניהול לידים ושיחות מכירה. 
אתה מבין את ההקשר של השיחה ויודע מתי כדאי לשנות סטטוס ומתי לא.
היה חכם - אל תשנה סטטוס סתם, רק כשזה באמת הגיוני!"""
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=100
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Parse JSON response
            import json
            # Remove markdown code blocks if present
            if '```' in result_text:
                result_text = result_text.split('```')[1]
                if result_text.startswith('json'):
                    result_text = result_text[4:]
            
            result = json.loads(result_text)
            
            should_change = result.get('should_change', False)
            reason = result.get('reason', 'AI decision')
            
            log.info(f"[StatusDecision] ✅ AI decision: should_change={should_change}, reason='{reason}'")
            
            return (should_change, reason)
            
        except Exception as e:
            log.error(f"[StatusDecision] ❌ Smart decision failed: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _get_full_status_info(self, tenant_id: int, status_name: str) -> Optional[dict]:
        """
        Get full information about a status (label, description) for better matching
        
        Args:
            tenant_id: Business ID
            status_name: Status name to look up
            
        Returns:
            Dict with status info or None
        """
        from server.models_sql import LeadStatus
        
        status_obj = LeadStatus.query.filter_by(
            business_id=tenant_id,
            name=status_name,
            is_active=True
        ).first()
        
        if status_obj:
            return {
                'name': status_obj.name,
                'label': status_obj.label,
                'description': status_obj.description
            }
        
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
