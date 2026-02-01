"""
Unified Lead Context Service - Single Source of Truth
Consolidates lead context building for both WhatsApp and Calls

This is the SINGLE authoritative source for:
1. Lead identification (phone/WhatsApp JID)
2. Lead context building (CRM data, notes, appointments, summaries, memory)
3. Cross-channel consistency (same data structure for both channels)

Replaces duplications from:
- tools_crm_context.py (partial)
- customer_intelligence.py (find/create logic)
- customer_memory_service.py (memory loading)

Security: All operations are multi-tenant scoped to business_id
"""
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from server.db import db
from server.models_sql import (
    Lead, LeadNote, Appointment, CallLog, WhatsAppMessage, 
    Customer, Business, BusinessSettings
)
from server.agent_tools.phone_utils import normalize_il_phone
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ================================================================================
# UNIFIED LEAD CONTEXT PAYLOAD - SAME FOR WHATSAPP AND CALLS
# ================================================================================

class UnifiedLeadContextPayload(BaseModel):
    """
    Standard lead context payload for AI agents (both WhatsApp and Calls)
    This is the SINGLE schema used across all channels
    """
    # Lead identification
    found: bool = False
    lead_id: Optional[int] = None
    
    # Lead basic info
    lead_name: Optional[str] = None
    lead_first_name: Optional[str] = None
    lead_last_name: Optional[str] = None
    lead_phone: Optional[str] = None
    lead_email: Optional[str] = None
    lead_source: Optional[str] = None
    
    # Status and pipeline
    current_status: Optional[str] = None
    pipeline_stage: Optional[str] = None
    status_history: List[Dict[str, Any]] = []  # Last N status changes
    
    # Appointments
    next_appointment: Optional[Dict[str, Any]] = None
    past_appointments: List[Dict[str, Any]] = []  # Last N
    
    # Summaries and context
    last_call_summary: Optional[str] = None
    last_whatsapp_summary: Optional[str] = None
    customer_memory: Optional[str] = None  # Unified memory across channels
    
    # Notes (AI-visible only: call_summary, system, customer_service_ai)
    recent_notes: List[Dict[str, Any]] = []  # Last 10
    
    # Additional context
    tags: List[str] = []
    service_type: Optional[str] = None
    city: Optional[str] = None
    summary: Optional[str] = None  # Lead summary field
    
    # Metadata
    created_at: Optional[str] = None
    last_contact_at: Optional[str] = None
    recent_calls_count: int = 0
    recent_whatsapp_count: int = 0
    
    # Sales context (if applicable)
    deal_status: Optional[str] = None
    deal_value: Optional[float] = None


# ================================================================================
# UNIFIED LEAD CONTEXT SERVICE
# ================================================================================

class UnifiedLeadContextService:
    """
    Single source of truth for lead context building
    Works for both WhatsApp and Calls with identical output
    """
    
    def __init__(self, business_id: int):
        """
        Initialize service for a specific business
        
        Args:
            business_id: Business/tenant ID for multi-tenant scoping
        """
        self.business_id = business_id
        self.business = Business.query.get(business_id)
        if not self.business:
            logger.error(f"Business {business_id} not found")
    
    def is_customer_service_enabled(self) -> bool:
        """
        Check if customer service AI is enabled for this business
        This is the feature flag that controls context injection and tools
        
        Returns:
            bool: True if customer service is enabled
        """
        try:
            settings = BusinessSettings.query.filter_by(tenant_id=self.business_id).first()
            enabled = getattr(settings, 'enable_customer_service', False) if settings else False
            logger.info(f"[UnifiedContext] Customer service enabled={enabled} for business {self.business_id}")
            return enabled
        except Exception as e:
            logger.error(f"[UnifiedContext] Error checking customer service flag: {e}")
            return False
    
    def find_lead_by_phone(self, phone: str) -> Optional[Lead]:
        """
        Find lead by phone number with E.164 normalization
        
        Args:
            phone: Phone number in any format
            
        Returns:
            Lead object or None
        """
        try:
            # Normalize to E.164
            phone_e164 = normalize_il_phone(phone)
            if not phone_e164:
                logger.warning(f"[UnifiedContext] Could not normalize phone: {phone}")
                return None
            
            # Query with business scope
            lead = Lead.query.filter_by(
                tenant_id=self.business_id,
                phone_e164=phone_e164
            ).order_by(Lead.updated_at.desc()).first()
            
            if lead:
                logger.info(f"[UnifiedContext] Found lead #{lead.id} for phone {phone_e164}")
            else:
                logger.info(f"[UnifiedContext] No lead found for phone {phone_e164}")
            
            return lead
            
        except Exception as e:
            logger.error(f"[UnifiedContext] Error finding lead by phone: {e}")
            return None
    
    def find_lead_by_whatsapp_jid(self, jid: str) -> Optional[Lead]:
        """
        Find lead by WhatsApp JID (remoteJid)
        
        Args:
            jid: WhatsApp JID (e.g., "972525951893@s.whatsapp.net")
            
        Returns:
            Lead object or None
        """
        try:
            # Try reply_jid first (most reliable)
            lead = Lead.query.filter_by(
                tenant_id=self.business_id,
                reply_jid=jid
            ).order_by(Lead.updated_at.desc()).first()
            
            if lead:
                logger.info(f"[UnifiedContext] Found lead #{lead.id} by reply_jid: {jid}")
                return lead
            
            # Fallback to whatsapp_jid
            lead = Lead.query.filter_by(
                tenant_id=self.business_id,
                whatsapp_jid=jid
            ).order_by(Lead.updated_at.desc()).first()
            
            if lead:
                logger.info(f"[UnifiedContext] Found lead #{lead.id} by whatsapp_jid: {jid}")
            else:
                logger.info(f"[UnifiedContext] No lead found for JID: {jid}")
            
            return lead
            
        except Exception as e:
            logger.error(f"[UnifiedContext] Error finding lead by JID: {e}")
            return None
    
    def build_lead_context(self, lead: Lead, channel: str = "unknown") -> UnifiedLeadContextPayload:
        """
        Build complete lead context for AI agents
        THIS IS THE SINGLE SOURCE OF TRUTH for lead context
        
        Args:
            lead: Lead object
            channel: "whatsapp", "call", or "unknown"
            
        Returns:
            UnifiedLeadContextPayload with all context data
        """
        if not lead:
            logger.warning(f"[UnifiedContext] build_lead_context called with None lead")
            return UnifiedLeadContextPayload(found=False)
        
        try:
            logger.info(f"[UnifiedContext] Building context for lead #{lead.id} via {channel}")
            
            # Basic lead info
            payload = UnifiedLeadContextPayload(
                found=True,
                lead_id=lead.id,
                lead_name=lead.full_name,
                lead_first_name=lead.first_name,
                lead_last_name=lead.last_name,
                lead_phone=lead.phone_e164,
                lead_email=lead.email,
                lead_source=lead.source,
                current_status=lead.status,
                pipeline_stage=lead.pipeline_stage if hasattr(lead, 'pipeline_stage') else None,
                tags=lead.tags or [],
                service_type=lead.service_type,
                city=lead.city,
                summary=lead.summary,
                created_at=lead.created_at.isoformat() if lead.created_at else None,
                last_contact_at=lead.last_contact_at.isoformat() if lead.last_contact_at else None
            )
            
            # Load notes (AI-visible only: call_summary, system, customer_service_ai)
            # FIRST note is the LATEST/MOST ACCURATE (ordered by created_at DESC)
            notes_query = LeadNote.query.filter(
                LeadNote.lead_id == lead.id,
                LeadNote.tenant_id == self.business_id,
                db.or_(
                    LeadNote.note_type == 'call_summary',
                    LeadNote.note_type == 'system',
                    LeadNote.note_type == 'customer_service_ai'
                )
            ).order_by(LeadNote.created_at.desc()).limit(10)
            
            payload.recent_notes = []
            for idx, note in enumerate(notes_query):
                is_latest = (idx == 0)
                note_content = note.content if note.content else ""
                
                # Mark latest note for AI prioritization
                if is_latest and note_content:
                    note_content = f"[הערה עדכנית ביותר - מידע מדויק] {note_content}"
                
                payload.recent_notes.append({
                    'id': note.id,
                    'type': getattr(note, 'note_type', 'manual') or 'manual',
                    'content': note_content,
                    'created_at': note.created_at.isoformat() if note.created_at else "",
                    'created_by': 'ai' if note.created_by is None else str(note.created_by)
                })
            
            # Load appointments
            now = datetime.utcnow()
            
            # Next upcoming appointment
            next_apt = Appointment.query.filter(
                Appointment.lead_id == lead.id,
                Appointment.business_id == self.business_id,
                Appointment.start_datetime >= now
            ).order_by(Appointment.start_datetime.asc()).first()
            
            if next_apt:
                payload.next_appointment = {
                    'id': next_apt.id,
                    'title': next_apt.treatment_type or next_apt.title,
                    'start': next_apt.start_datetime.isoformat() if next_apt.start_datetime else "",
                    'end': next_apt.end_datetime.isoformat() if next_apt.end_datetime else "",
                    'status': next_apt.status or 'scheduled',
                    'notes': next_apt.notes[:200] if next_apt.notes else None
                }
            
            # Past appointments (last 3)
            past_apts = Appointment.query.filter(
                Appointment.lead_id == lead.id,
                Appointment.business_id == self.business_id,
                Appointment.start_datetime < now
            ).order_by(Appointment.start_datetime.desc()).limit(3).all()
            
            payload.past_appointments = []
            for apt in past_apts:
                payload.past_appointments.append({
                    'id': apt.id,
                    'title': apt.treatment_type or apt.title,
                    'start': apt.start_datetime.isoformat() if apt.start_datetime else "",
                    'end': apt.end_datetime.isoformat() if apt.end_datetime else "",
                    'status': apt.status or 'completed',
                    'notes': apt.notes[:200] if apt.notes else None
                })
            
            # Load last call summary
            last_call = CallLog.query.filter(
                CallLog.lead_id == lead.id,
                CallLog.business_id == self.business_id,
                CallLog.summary.isnot(None)
            ).order_by(CallLog.created_at.desc()).first()
            
            if last_call and last_call.summary:
                payload.last_call_summary = last_call.summary[:500]  # Limit size
            
            # Load last WhatsApp summary (if exists in notes)
            # TODO: Implement WhatsApp summary extraction from notes or separate field
            
            # Count recent interactions
            payload.recent_calls_count = CallLog.query.filter(
                CallLog.lead_id == lead.id,
                CallLog.business_id == self.business_id
            ).count()
            
            payload.recent_whatsapp_count = WhatsAppMessage.query.filter(
                WhatsAppMessage.lead_id == lead.id,
                WhatsAppMessage.business_id == self.business_id
            ).count()
            
            # Load customer memory (unified across channels)
            payload.customer_memory = self._load_customer_memory(lead)
            
            # Status history (last 5 changes)
            # TODO: Implement status history if LeadStatusHistory table exists
            
            logger.info(f"[UnifiedContext] Built context for lead #{lead.id}: "
                       f"{len(payload.recent_notes)} notes, "
                       f"{len(payload.past_appointments)} past appointments, "
                       f"next_apt={'Yes' if payload.next_appointment else 'No'}")
            
            return payload
            
        except Exception as e:
            logger.error(f"[UnifiedContext] Error building lead context: {e}", exc_info=True)
            return UnifiedLeadContextPayload(found=False)
    
    def _load_customer_memory(self, lead: Lead) -> Optional[str]:
        """
        Load unified customer memory across channels
        
        Args:
            lead: Lead object
            
        Returns:
            Memory string or None
        """
        try:
            # Check if customer service is enabled
            if not self.is_customer_service_enabled():
                return None
            
            # Load from customer_memory field if exists
            if hasattr(lead, 'customer_memory') and lead.customer_memory:
                memory_data = lead.customer_memory
                if isinstance(memory_data, dict):
                    # Extract summary from memory JSON
                    summary = memory_data.get('summary', '')
                    profile = memory_data.get('profile', {})
                    
                    memory_parts = []
                    if summary:
                        memory_parts.append(f"סיכום: {summary}")
                    if profile:
                        if profile.get('preferences'):
                            memory_parts.append(f"העדפות: {profile['preferences']}")
                        if profile.get('notes'):
                            memory_parts.append(f"הערות: {profile['notes']}")
                    
                    return " | ".join(memory_parts) if memory_parts else None
                elif isinstance(memory_data, str):
                    return memory_data
            
            return None
            
        except Exception as e:
            logger.error(f"[UnifiedContext] Error loading customer memory: {e}")
            return None
    
    def format_context_for_prompt(self, context: UnifiedLeadContextPayload) -> str:
        """
        Format lead context as text for AI prompt injection
        
        Args:
            context: UnifiedLeadContextPayload
            
        Returns:
            Formatted context string for prompt
        """
        if not context.found:
            return ""
        
        parts = []
        
        # Lead basic info
        parts.append(f"📋 לקוח: {context.lead_name} ({context.lead_phone})")
        if context.lead_email:
            parts.append(f"📧 אימייל: {context.lead_email}")
        
        # Status
        if context.current_status:
            parts.append(f"📊 סטטוס: {context.current_status}")
        
        # Service type and location
        if context.service_type:
            parts.append(f"🔧 סוג שירות: {context.service_type}")
        if context.city:
            parts.append(f"📍 עיר: {context.city}")
        
        # Tags
        if context.tags:
            parts.append(f"🏷️ תגיות: {', '.join(context.tags)}")
        
        # Next appointment
        if context.next_appointment:
            apt = context.next_appointment
            parts.append(f"📅 פגישה הבאה: {apt['title']} ב-{apt['start']}")
        
        # Memory
        if context.customer_memory:
            parts.append(f"🧠 זיכרון לקוח: {context.customer_memory}")
        
        # Recent notes (most recent first)
        if context.recent_notes:
            parts.append(f"\n📝 הערות אחרונות ({len(context.recent_notes)}):")
            for note in context.recent_notes[:3]:  # Show top 3
                note_date = note['created_at'][:10] if note.get('created_at') else ''
                parts.append(f"  - [{note_date}] {note['content'][:150]}...")
        
        # Summary
        if context.summary:
            parts.append(f"\n💬 סיכום: {context.summary}")
        
        return "\n".join(parts)


# ================================================================================
# CONVENIENCE FUNCTIONS (for backwards compatibility)
# ================================================================================

def get_unified_context_for_phone(business_id: int, phone: str, channel: str = "call") -> UnifiedLeadContextPayload:
    """
    Get unified lead context by phone number
    
    Args:
        business_id: Business ID
        phone: Phone number
        channel: Channel name ("call", "whatsapp", etc.)
        
    Returns:
        UnifiedLeadContextPayload
    """
    service = UnifiedLeadContextService(business_id)
    
    # Check if customer service is enabled
    if not service.is_customer_service_enabled():
        logger.info(f"[UnifiedContext] Customer service disabled for business {business_id}, returning empty context")
        return UnifiedLeadContextPayload(found=False)
    
    lead = service.find_lead_by_phone(phone)
    if not lead:
        return UnifiedLeadContextPayload(found=False)
    
    return service.build_lead_context(lead, channel=channel)


def get_unified_context_for_whatsapp_jid(business_id: int, jid: str) -> UnifiedLeadContextPayload:
    """
    Get unified lead context by WhatsApp JID
    
    Args:
        business_id: Business ID
        jid: WhatsApp JID
        
    Returns:
        UnifiedLeadContextPayload
    """
    service = UnifiedLeadContextService(business_id)
    
    # Check if customer service is enabled
    if not service.is_customer_service_enabled():
        logger.info(f"[UnifiedContext] Customer service disabled for business {business_id}, returning empty context")
        return UnifiedLeadContextPayload(found=False)
    
    lead = service.find_lead_by_whatsapp_jid(jid)
    if not lead:
        return UnifiedLeadContextPayload(found=False)
    
    return service.build_lead_context(lead, channel="whatsapp")


def get_unified_context_for_lead(business_id: int, lead_id: int, channel: str = "unknown") -> UnifiedLeadContextPayload:
    """
    Get unified lead context by lead ID
    
    Args:
        business_id: Business ID
        lead_id: Lead ID
        channel: Channel name
        
    Returns:
        UnifiedLeadContextPayload
    """
    service = UnifiedLeadContextService(business_id)
    
    # Check if customer service is enabled
    if not service.is_customer_service_enabled():
        logger.info(f"[UnifiedContext] Customer service disabled for business {business_id}, returning empty context")
        return UnifiedLeadContextPayload(found=False)
    
    try:
        lead = Lead.query.filter_by(
            id=lead_id,
            tenant_id=business_id
        ).first()
        
        if not lead:
            logger.warning(f"[UnifiedContext] Lead {lead_id} not found in business {business_id}")
            return UnifiedLeadContextPayload(found=False)
        
        return service.build_lead_context(lead, channel=channel)
        
    except Exception as e:
        logger.error(f"[UnifiedContext] Error getting context for lead {lead_id}: {e}")
        return UnifiedLeadContextPayload(found=False)
