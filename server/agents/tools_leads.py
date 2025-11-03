"""
Lead Management Tools for AgentKit - Create and update leads
Integrates with existing Lead model and CRM system
"""
from agents.tool import function_tool
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from server.models_sql import db, Lead, LeadActivity
import logging

logger = logging.getLogger(__name__)

# ================================================================================
# INPUT/OUTPUT SCHEMAS
# ================================================================================

class UpsertLeadInput(BaseModel):
    """Input for creating or updating a lead"""
    business_id: int = Field(..., description="Business ID (tenant_id)", ge=1)
    phone: str = Field(..., description="Customer phone number in E.164 format (+972...)")
    first_name: Optional[str] = Field(None, description="First name")
    last_name: Optional[str] = Field(None, description="Last name")
    email: Optional[str] = Field(None, description="Email address")
    source: str = Field("ai_agent", description="Lead source (call/whatsapp/ai_agent)")
    status: str = Field("new", description="Lead status (new/contacted/qualified/won/lost)")
    tags: Optional[List[str]] = Field(None, description="Tags for categorization")
    notes: Optional[str] = Field(None, description="Notes about the lead")
    summary: Optional[str] = Field(None, description="Brief summary of conversation (10-30 words)")

class UpsertLeadOutput(BaseModel):
    """Lead creation/update result"""
    lead_id: int
    action: str  # created or updated
    phone: str
    full_name: str

class SearchLeadInput(BaseModel):
    """Input for searching leads"""
    business_id: int = Field(..., description="Business ID", ge=1)
    phone: Optional[str] = Field(None, description="Phone number to search")
    email: Optional[str] = Field(None, description="Email to search")
    status: Optional[str] = Field(None, description="Filter by status")

class LeadInfo(BaseModel):
    """Lead information"""
    lead_id: int
    full_name: str
    phone: str
    email: Optional[str]
    status: str
    summary: Optional[str]
    last_contact: Optional[str]

class SearchLeadOutput(BaseModel):
    """Search results"""
    leads: List[LeadInfo]
    count: int

# ================================================================================
# TOOLS
# ================================================================================

@function_tool
def leads_upsert(input: UpsertLeadInput) -> UpsertLeadOutput:
    """
    Create or update a lead
    
    Business logic:
    - Search for existing lead by phone
    - If found: update information
    - If not: create new lead
    - Always updates last_contact_at
    - Logs activity
    """
    try:
        # Normalize phone to E.164 format
        phone = input.phone.strip()
        if not phone.startswith('+'):
            if phone.startswith('0'):
                phone = '+972' + phone[1:]
            else:
                phone = '+972' + phone
        
        # Search for existing lead
        existing_lead = Lead.query.filter_by(
            tenant_id=input.business_id,
            phone_e164=phone
        ).first()
        
        now = datetime.utcnow()
        
        if existing_lead:
            # Update existing lead
            action = "updated"
            lead = existing_lead
            
            # Update fields if provided
            if input.first_name:
                lead.first_name = input.first_name
            if input.last_name:
                lead.last_name = input.last_name
            if input.email:
                lead.email = input.email
            if input.status:
                # Log status change
                if lead.status != input.status:
                    old_status = lead.status
                    lead.status = input.status
                    activity = LeadActivity(
                        lead_id=lead.id,
                        type='status_change',
                        payload={'from': old_status, 'to': input.status, 'by': 'ai_agent'},
                        at=now
                    )
                    db.session.add(activity)
            
            # Append notes if provided
            if input.notes:
                existing_notes = lead.notes or ""
                timestamp = now.strftime("%Y-%m-%d %H:%M")
                lead.notes = f"{existing_notes}\n\n[{timestamp}] {input.notes}".strip()
            
            # Update summary
            if input.summary:
                lead.summary = input.summary
            
            # Merge tags
            if input.tags:
                existing_tags = lead.tags or []
                new_tags = list(set(existing_tags + input.tags))
                lead.tags = new_tags
            
            lead.last_contact_at = now
            lead.updated_at = now
            
            logger.info(f"Updated existing lead #{lead.id} for phone {phone}")
            
        else:
            # Create new lead
            action = "created"
            lead = Lead(
                tenant_id=input.business_id,
                phone_e164=phone,
                first_name=input.first_name,
                last_name=input.last_name,
                email=input.email,
                source=input.source,
                status=input.status,
                tags=input.tags or [],
                notes=input.notes,
                summary=input.summary,
                created_at=now,
                updated_at=now,
                last_contact_at=now
            )
            db.session.add(lead)
            db.session.flush()  # Get the ID
            
            # Log creation activity
            activity = LeadActivity(
                lead_id=lead.id,
                type='created',
                payload={'source': input.source, 'by': 'ai_agent'},
                at=now
            )
            db.session.add(activity)
            
            logger.info(f"Created new lead #{lead.id} for phone {phone}")
        
        db.session.commit()
        
        return UpsertLeadOutput(
            lead_id=lead.id,
            action=action,
            phone=lead.phone_e164,
            full_name=lead.full_name
        )
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error upserting lead: {e}")
        raise ValueError(f"Failed to save lead: {str(e)}")


@function_tool
def leads_search(input: SearchLeadInput) -> SearchLeadOutput:
    """
    Search for leads
    
    Filters:
    - Phone number (E.164 format)
    - Email address
    - Status
    """
    try:
        query = Lead.query.filter_by(tenant_id=input.business_id)
        
        # Apply filters
        if input.phone:
            phone = input.phone.strip()
            if not phone.startswith('+'):
                if phone.startswith('0'):
                    phone = '+972' + phone[1:]
                else:
                    phone = '+972' + phone
            query = query.filter_by(phone_e164=phone)
        
        if input.email:
            query = query.filter_by(email=input.email)
        
        if input.status:
            query = query.filter_by(status=input.status)
        
        # Execute query
        leads = query.order_by(Lead.last_contact_at.desc()).limit(10).all()
        
        # Build results
        result_leads = []
        for lead in leads:
            result_leads.append(LeadInfo(
                lead_id=lead.id,
                full_name=lead.full_name,
                phone=lead.display_phone,
                email=lead.email,
                status=lead.status,
                summary=lead.summary,
                last_contact=lead.last_contact_at.isoformat() if lead.last_contact_at else None
            ))
        
        logger.info(f"Found {len(result_leads)} leads matching search criteria")
        
        return SearchLeadOutput(leads=result_leads, count=len(result_leads))
        
    except Exception as e:
        logger.error(f"Error searching leads: {e}")
        raise ValueError(f"Failed to search leads: {str(e)}")
