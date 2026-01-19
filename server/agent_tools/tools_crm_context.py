"""
CRM Context-Aware Support Tools for AgentKit
Provides AI with CRM context (lead notes, appointments) and ability to create call summary notes.

Multi-tenant security: ALL queries are scoped to business_id.
Data protection: Sensitive data is redacted before storage.

Tools:
1. find_lead_by_phone(business_id, phone) - Find lead by phone with E164 normalization
2. get_lead_context(business_id, lead_id) - Get lead card, notes, appointments
3. create_lead_note(business_id, lead_id, note_type, content) - Create notes with redaction
4. update_lead_fields(business_id, lead_id, patch) - Update allowed lead fields
"""
from agents import function_tool
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from server.models_sql import db, Lead, LeadNote, Appointment, CallLog
from server.agent_tools.phone_utils import normalize_il_phone
import logging
import re

logger = logging.getLogger(__name__)


# ================================================================================
# SECURITY UTILITIES
# ================================================================================

def redact_sensitive_data(text: str) -> str:
    """
    Redact sensitive data from text before storing in CRM.
    
    Redacts:
    - Credit card numbers (13-19 digits)
    - Common password patterns
    - API tokens/keys
    - Israeli ID numbers (9 digits)
    
    Args:
        text: Original text content
        
    Returns:
        Text with sensitive data replaced with [REDACTED]
    """
    if not text:
        return text
    
    redacted = text
    
    # Credit card numbers (13-19 digit sequences)
    # Matches Visa, Mastercard, Amex, etc.
    redacted = re.sub(r'\b\d{13,19}\b', '[REDACTED_CARD]', redacted)
    
    # CVV patterns (3-4 digits often following card numbers)
    redacted = re.sub(r'\b(?:cvv|cvc|csv)[:\s]*\d{3,4}\b', '[REDACTED]', redacted, flags=re.IGNORECASE)
    
    # Password patterns
    redacted = re.sub(r'(?:password|סיסמה|סיסמא)[:\s]+\S+', '[REDACTED_PASSWORD]', redacted, flags=re.IGNORECASE)
    
    # API tokens/keys (common patterns)
    redacted = re.sub(r'\b(?:sk|pk|api[_-]?key)[_-][a-zA-Z0-9]{20,}\b', '[REDACTED_TOKEN]', redacted, flags=re.IGNORECASE)
    
    # Israeli ID (9 digits standing alone - be careful not to match phone numbers)
    # Only redact if preceded by ID-related words
    redacted = re.sub(r'(?:ת\.?ז\.?|תעודת זהות|ID)[:\s]*\d{9}\b', '[REDACTED_ID]', redacted, flags=re.IGNORECASE)
    
    return redacted


# ================================================================================
# INPUT/OUTPUT SCHEMAS
# ================================================================================

class FindLeadByPhoneInput(BaseModel):
    """Input for finding a lead by phone number"""
    business_id: int = Field(..., description="Business ID (tenant_id) - REQUIRED for multi-tenant security", ge=1)
    phone: str = Field(..., description="Phone number to search (any format, will be normalized to E.164)")


class FindLeadByPhoneOutput(BaseModel):
    """Output for find_lead_by_phone"""
    found: bool
    lead_id: Optional[int] = None
    lead_name: Optional[str] = None
    normalized_phone: Optional[str] = None


class GetLeadContextInput(BaseModel):
    """Input for getting lead context"""
    business_id: int = Field(..., description="Business ID (tenant_id) - REQUIRED for multi-tenant security", ge=1)
    lead_id: int = Field(..., description="Lead ID to get context for", ge=1)


class LeadContextNote(BaseModel):
    """Note in lead context"""
    id: int
    note_type: str
    content: str
    created_at: str
    created_by: Optional[str] = None


class LeadContextAppointment(BaseModel):
    """Appointment in lead context"""
    id: int
    title: Optional[str]
    start_datetime: str
    end_datetime: str
    status: str
    notes: Optional[str] = None


class LeadData(BaseModel):
    """Lead data in context - explicit schema for strict mode compatibility"""
    id: int
    name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    status: Optional[str] = None
    tags: List[str] = []
    source: Optional[str] = None
    service_type: Optional[str] = None
    city: Optional[str] = None
    summary: Optional[str] = None
    created_at: Optional[str] = None
    last_contact_at: Optional[str] = None


class GetLeadContextOutput(BaseModel):
    """Output for get_lead_context with lead details, notes, and appointments"""
    found: bool
    # 🔥 FIX: Use explicit LeadData model instead of dict to avoid additionalProperties schema error
    lead: Optional[LeadData] = None
    notes: List[LeadContextNote] = []
    appointments: List[LeadContextAppointment] = []
    recent_calls_count: int = 0


class CreateLeadNoteInput(BaseModel):
    """Input for creating a lead note"""
    business_id: int = Field(..., description="Business ID (tenant_id) - REQUIRED for multi-tenant security", ge=1)
    lead_id: int = Field(..., description="Lead ID to add note to", ge=1)
    note_type: str = Field("call_summary", description="Type of note: 'manual' (free notes), 'customer_service_ai' (AI context), 'call_summary' (AI call summary), or 'system'")
    content: str = Field(..., description="Note content (sensitive data will be redacted)", max_length=10000)
    call_id: Optional[int] = Field(None, description="Optional call ID to link the note to")
    # 🔥 FIX: Changed from Dict[str, Any] to avoid additionalProperties schema error
    # Now accepts None or a dict as Python object (no strict schema enforcement)
    structured_data: Optional[dict] = Field(
        None, 
        description="Optional structured data: {sentiment, outcome, next_step_date}"
    )


class CreateLeadNoteOutput(BaseModel):
    """Output for create_lead_note"""
    success: bool
    note_id: Optional[int] = None
    message: str


class UpdateLeadFieldsInput(BaseModel):
    """Input for updating lead fields - only allowed fields can be updated"""
    business_id: int = Field(..., description="Business ID (tenant_id) - REQUIRED for multi-tenant security", ge=1)
    lead_id: int = Field(..., description="Lead ID to update", ge=1)
    # 🔥 FIX: Changed from Dict[str, Any] to avoid additionalProperties schema error
    patch: dict = Field(
        ..., 
        description="""Fields to update. Allowed fields:
        - status: Lead status (e.g., 'new', 'contacted', 'qualified')
        - tags: List of tags
        - notes: Additional notes text
        - summary: Brief summary
        - service_type: Type of service needed
        - city: City/location
        """
    )


class UpdateLeadFieldsOutput(BaseModel):
    """Output for update_lead_fields"""
    success: bool
    message: str
    updated_fields: List[str] = []


# ================================================================================
# ALLOWED FIELDS FOR UPDATE (Security whitelist)
# ================================================================================

ALLOWED_UPDATE_FIELDS = {
    'status',
    'tags',
    'notes',
    'summary',
    'service_type',
    'city',
    'first_name',
    'last_name',
    'email',
}

# Fields that should NEVER be updated via this API
BLOCKED_FIELDS = {
    'tenant_id',
    'business_id',
    'owner_user_id',
    'id',
    'phone_e164',
    'created_at',
}


# ================================================================================
# TOOLS IMPLEMENTATION
# ================================================================================

@function_tool
def find_lead_by_phone(input: FindLeadByPhoneInput) -> FindLeadByPhoneOutput:
    """
    Find a lead by phone number with E.164 normalization.
    
    Security: Query is scoped to business_id (multi-tenant safe).
    If multiple leads match, returns the most recently updated one.
    """
    try:
        # Normalize phone to E.164 format
        normalized_phone = normalize_il_phone(input.phone)
        
        if not normalized_phone:
            logger.warning(f"Could not normalize phone: {input.phone}")
            return FindLeadByPhoneOutput(
                found=False,
                normalized_phone=None
            )
        
        # Query lead with business_id scope (CRITICAL for multi-tenant)
        lead = Lead.query.filter_by(
            tenant_id=input.business_id,
            phone_e164=normalized_phone
        ).order_by(Lead.updated_at.desc()).first()
        
        if lead:
            logger.info(f"Found lead #{lead.id} for phone {normalized_phone} in business {input.business_id}")
            return FindLeadByPhoneOutput(
                found=True,
                lead_id=lead.id,
                lead_name=lead.full_name,
                normalized_phone=normalized_phone
            )
        else:
            logger.info(f"No lead found for phone {normalized_phone} in business {input.business_id}")
            return FindLeadByPhoneOutput(
                found=False,
                normalized_phone=normalized_phone
            )
            
    except Exception as e:
        logger.error(f"Error finding lead by phone: {e}")
        return FindLeadByPhoneOutput(found=False)


@function_tool
def get_lead_context(input: GetLeadContextInput) -> GetLeadContextOutput:
    """
    Get full lead context: lead details, recent notes (last 10), and upcoming/past appointments.
    
    Security: Query is scoped to business_id (multi-tenant safe).
    This is the main context provider for AI customer service.
    """
    try:
        # Get lead with business_id scope (CRITICAL for multi-tenant)
        lead = Lead.query.filter_by(
            id=input.lead_id,
            tenant_id=input.business_id
        ).first()
        
        if not lead:
            logger.warning(f"Lead {input.lead_id} not found in business {input.business_id}")
            return GetLeadContextOutput(found=False)
        
        # Build lead context dict
        lead_data = {
            'id': lead.id,
            'name': lead.full_name,
            'first_name': lead.first_name,
            'last_name': lead.last_name,
            'phone': lead.phone_e164,
            'email': lead.email,
            'status': lead.status,
            'tags': lead.tags or [],
            'source': lead.source,
            'service_type': lead.service_type,
            'city': lead.city,
            'summary': lead.summary,
            'created_at': lead.created_at.isoformat() if lead.created_at else None,
            'last_contact_at': lead.last_contact_at.isoformat() if lead.last_contact_at else None,
        }
        
        # Get last 10 notes (most recent first) - sufficient context without overflow
        # 🎧 CRM Context-Aware Support: 10 notes with FULL content (no truncation)
        # 🔥 CRITICAL FIX: Removed 300-char truncation - AI needs ALL context to serve customers properly!
        # 🔥 FILTER: Only get AI Customer Service notes (call_summary, system, and customer_service_ai)
        # Migration 75: Added 'customer_service_ai' type for notes visible to AI
        # Exclude Free Notes (manual notes) to avoid context pollution
        # 🆕 CRITICAL: Notes are ordered by created_at DESC - FIRST note is the LATEST/MOST ACCURATE
        # Per requirements: Always treat the last note recorded as the most accurate "piece of truth"
        notes_query = LeadNote.query.filter(
            LeadNote.lead_id == input.lead_id,
            LeadNote.tenant_id == input.business_id,
            db.or_(
                LeadNote.note_type == 'call_summary',  # AI-generated call summaries
                LeadNote.note_type == 'system',  # System notes
                LeadNote.note_type == 'customer_service_ai'  # Manual notes for AI customer service (visible to AI)
            )
        ).order_by(LeadNote.created_at.desc()).limit(10)
        
        notes_list = []
        for idx, note in enumerate(notes_query):
            # 🆕 Mark if this is the latest note (first in the list)
            is_latest = (idx == 0)
            note_content = note.content if note.content else ""
            
            # 🆕 Add context marker for the latest note to help AI prioritize it
            if is_latest and note_content:
                note_content = f"[הערה עדכנית ביותר - מידע מדויק] {note_content}"
            
            notes_list.append(LeadContextNote(
                id=note.id,
                note_type=getattr(note, 'note_type', 'manual') or 'manual',
                content=note_content,  # 🔥 FIX: Use full content, no truncation!
                created_at=note.created_at.isoformat() if note.created_at else "",
                created_by='ai' if note.created_by is None else str(note.created_by)
            ))
        
        # Get appointments (3 upcoming + 3 past)
        now = datetime.utcnow()
        appointments_list = []
        
        # Upcoming appointments
        upcoming = Appointment.query.filter(
            Appointment.lead_id == input.lead_id,
            Appointment.business_id == input.business_id,
            Appointment.start_datetime >= now
        ).order_by(Appointment.start_datetime.asc()).limit(3).all()
        
        for apt in upcoming:
            appointments_list.append(LeadContextAppointment(
                id=apt.id,
                title=apt.treatment_type or apt.title,
                start_datetime=apt.start_datetime.isoformat() if apt.start_datetime else "",
                end_datetime=apt.end_datetime.isoformat() if apt.end_datetime else "",
                status=apt.status or 'scheduled',
                notes=apt.notes[:200] if apt.notes else None
            ))
        
        # Past appointments (last 3)
        past = Appointment.query.filter(
            Appointment.lead_id == input.lead_id,
            Appointment.business_id == input.business_id,
            Appointment.start_datetime < now
        ).order_by(Appointment.start_datetime.desc()).limit(3).all()
        
        for apt in past:
            appointments_list.append(LeadContextAppointment(
                id=apt.id,
                title=apt.treatment_type or apt.title,
                start_datetime=apt.start_datetime.isoformat() if apt.start_datetime else "",
                end_datetime=apt.end_datetime.isoformat() if apt.end_datetime else "",
                status=apt.status or 'completed',
                notes=apt.notes[:200] if apt.notes else None
            ))
        
        # Count recent calls (for context awareness)
        recent_calls = CallLog.query.filter(
            CallLog.lead_id == input.lead_id,
            CallLog.business_id == input.business_id
        ).count()
        
        logger.info(f"Got context for lead {input.lead_id}: {len(notes_list)} notes, {len(appointments_list)} appointments")
        
        # Convert lead_data dict to LeadData model for strict schema compliance
        lead_obj = LeadData(**lead_data)
        
        return GetLeadContextOutput(
            found=True,
            lead=lead_obj,
            notes=notes_list,
            appointments=appointments_list,
            recent_calls_count=recent_calls
        )
        
    except Exception as e:
        logger.error(f"Error getting lead context: {e}")
        return GetLeadContextOutput(found=False)


@function_tool
def create_lead_note(input: CreateLeadNoteInput) -> CreateLeadNoteOutput:
    """
    Create a note for a lead with automatic sensitive data redaction.
    
    Security: 
    - Query is scoped to business_id (multi-tenant safe)
    - Sensitive data (credit cards, passwords, tokens) is redacted before storage
    
    Use note_type='call_summary' for AI-generated call summaries.
    """
    try:
        # Verify lead belongs to this business (CRITICAL for multi-tenant)
        lead = Lead.query.filter_by(
            id=input.lead_id,
            tenant_id=input.business_id
        ).first()
        
        if not lead:
            logger.warning(f"Lead {input.lead_id} not found in business {input.business_id}")
            return CreateLeadNoteOutput(
                success=False,
                message="לא נמצא ליד - Lead not found"
            )
        
        # Validate note_type
        # Migration 75: Added 'customer_service_ai' for AI customer service context notes
        valid_note_types = {'manual', 'call_summary', 'system', 'customer_service_ai'}
        note_type = input.note_type if input.note_type in valid_note_types else 'manual'
        
        # Redact sensitive data from content
        redacted_content = redact_sensitive_data(input.content)
        
        # Log if redaction occurred
        if redacted_content != input.content:
            logger.info(f"Redacted sensitive data from note for lead {input.lead_id}")
        
        # Create note
        note = LeadNote(
            lead_id=input.lead_id,
            tenant_id=input.business_id,
            note_type=note_type,
            content=redacted_content,
            call_id=input.call_id,
            structured_data=input.structured_data,
            created_at=datetime.utcnow(),
            created_by=None  # AI-created notes have no user
        )
        
        db.session.add(note)
        db.session.commit()
        
        logger.info(f"Created {note_type} note #{note.id} for lead {input.lead_id}")
        
        return CreateLeadNoteOutput(
            success=True,
            note_id=note.id,
            message=f"הערה נוצרה בהצלחה - Note created successfully"
        )
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating lead note: {e}")
        return CreateLeadNoteOutput(
            success=False,
            message=f"שגיאה ביצירת הערה - Error creating note: {str(e)}"
        )


@function_tool
def update_lead_fields(input: UpdateLeadFieldsInput) -> UpdateLeadFieldsOutput:
    """
    Update allowed fields on a lead.
    
    Security:
    - Query is scoped to business_id (multi-tenant safe)
    - Only whitelisted fields can be updated (no tenant_id, owner_id changes)
    - Field values are validated
    """
    try:
        # Verify lead belongs to this business (CRITICAL for multi-tenant)
        lead = Lead.query.filter_by(
            id=input.lead_id,
            tenant_id=input.business_id
        ).first()
        
        if not lead:
            logger.warning(f"Lead {input.lead_id} not found in business {input.business_id}")
            return UpdateLeadFieldsOutput(
                success=False,
                message="לא נמצא ליד - Lead not found"
            )
        
        updated_fields = []
        blocked_attempts = []
        
        for field, value in input.patch.items():
            # Check if field is blocked
            if field in BLOCKED_FIELDS:
                blocked_attempts.append(field)
                logger.warning(f"Blocked attempt to update protected field: {field}")
                continue
            
            # Check if field is allowed
            if field not in ALLOWED_UPDATE_FIELDS:
                logger.warning(f"Skipping unknown field: {field}")
                continue
            
            # Update the field
            if hasattr(lead, field):
                # Special handling for tags (ensure it's a list)
                if field == 'tags':
                    if isinstance(value, list):
                        setattr(lead, field, value)
                        updated_fields.append(field)
                    else:
                        logger.warning(f"Tags must be a list, got: {type(value)}")
                # Special handling for notes (append, don't replace)
                elif field == 'notes':
                    existing_notes = lead.notes or ""
                    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
                    new_notes = f"{existing_notes}\n\n[{timestamp}] {value}".strip()
                    setattr(lead, field, new_notes)
                    updated_fields.append(field)
                else:
                    setattr(lead, field, value)
                    updated_fields.append(field)
        
        if blocked_attempts:
            return UpdateLeadFieldsOutput(
                success=False,
                message=f"אין הרשאה לעדכן שדות: {', '.join(blocked_attempts)}",
                updated_fields=[]
            )
        
        if not updated_fields:
            return UpdateLeadFieldsOutput(
                success=False,
                message="לא נמצאו שדות תקינים לעדכון - No valid fields to update",
                updated_fields=[]
            )
        
        # Update timestamps
        lead.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        logger.info(f"Updated lead {input.lead_id} fields: {updated_fields}")
        
        return UpdateLeadFieldsOutput(
            success=True,
            message=f"ליד עודכן בהצלחה - Lead updated successfully",
            updated_fields=updated_fields
        )
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating lead fields: {e}")
        return UpdateLeadFieldsOutput(
            success=False,
            message=f"שגיאה בעדכון ליד - Error updating lead: {str(e)}",
            updated_fields=[]
        )


# ================================================================================
# STANDALONE FUNCTIONS (for direct Python calls without FunctionTool wrapper)
# ================================================================================

def find_lead_by_phone_impl(business_id: int, phone: str) -> FindLeadByPhoneOutput:
    """Direct implementation without FunctionTool wrapper"""
    return find_lead_by_phone(FindLeadByPhoneInput(business_id=business_id, phone=phone))


def get_lead_context_impl(business_id: int, lead_id: int) -> GetLeadContextOutput:
    """Direct implementation without FunctionTool wrapper"""
    return get_lead_context(GetLeadContextInput(business_id=business_id, lead_id=lead_id))


def create_call_summary_note(
    business_id: int, 
    lead_id: int, 
    content: str, 
    call_id: Optional[int] = None,
    # 🔥 FIX: Changed from Dict[str, Any] to avoid additionalProperties schema error
    structured_data: Optional[dict] = None
) -> CreateLeadNoteOutput:
    """
    Convenience function to create a call summary note.
    Typically called at the end of a call conversation.
    """
    return create_lead_note(CreateLeadNoteInput(
        business_id=business_id,
        lead_id=lead_id,
        note_type='call_summary',
        content=content,
        call_id=call_id,
        structured_data=structured_data
    ))
