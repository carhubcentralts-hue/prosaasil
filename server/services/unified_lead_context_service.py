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
    Customer, Business, BusinessSettings, Deal, CRMTask,
    Invoice, Payment, Contract, BusinessCalendar, User
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
    
    # Status and pipeline (with Hebrew labels)
    current_status: Optional[str] = None  # Status code (e.g., "active")
    current_status_id: Optional[int] = None  # Status ID
    current_status_label_he: Optional[str] = None  # Hebrew label (e.g., "פעיל")
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
    deal_amount: Optional[float] = None  # Same as deal_value for compatibility
    loss_reason: Optional[str] = None  # Why deal was lost
    quote_sent: Optional[str] = None  # Quote/proposal status
    
    # Owner/Agent info
    owner_name: Optional[str] = None
    owner_user_id: Optional[int] = None
    
    # Tasks
    open_tasks: List[Dict[str, Any]] = []  # Open tasks for this lead
    
    # Documents and payments
    invoices: List[Dict[str, Any]] = []  # Recent invoices
    payments: List[Dict[str, Any]] = []  # Recent payments
    contracts: List[Dict[str, Any]] = []  # Contracts
    
    # Communication history
    recent_calls: List[Dict[str, Any]] = []  # Recent call logs with details
    recent_whatsapp_messages: List[Dict[str, Any]] = []  # Last 20 WhatsApp messages
    
    # Calendars available for scheduling
    available_calendars: List[Dict[str, Any]] = []  # All calendars with Hebrew names


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
            
            # 🔥 NEW: Get Hebrew label service
            from server.services.hebrew_label_service import get_hebrew_label_service
            hebrew_label_service = get_hebrew_label_service(self.business_id)
            
            # 🔥 NEW: Get Hebrew label for lead status
            status_info = hebrew_label_service.get_lead_status_label(lead.status)
            
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
                current_status_id=status_info.get('status_id'),
                current_status_label_he=status_info.get('status_label_he'),
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
                LeadNote.note_type.in_(['call_summary', 'system', 'customer_service_ai'])
            ).order_by(LeadNote.created_at.desc()).limit(10)
            
            payload.recent_notes = []
            for idx, note in enumerate(notes_query):
                is_latest = (idx == 0)
                note_content = note.content if note.content else ""
                
                # Create note dict with metadata
                note_dict = {
                    'id': note.id,
                    'type': getattr(note, 'note_type', 'manual') or 'manual',
                    'content': note_content,
                    'created_at': note.created_at.isoformat() if note.created_at else "",
                    'created_by': 'ai' if note.created_by is None else str(note.created_by),
                    'is_latest': is_latest  # Metadata instead of modifying content
                }
                
                payload.recent_notes.append(note_dict)
            
            # Load appointments
            now = datetime.utcnow()
            
            # Next upcoming appointment
            next_apt = Appointment.query.filter(
                Appointment.lead_id == lead.id,
                Appointment.business_id == self.business_id,
                Appointment.start_datetime >= now
            ).order_by(Appointment.start_datetime.asc()).first()
            
            if next_apt:
                # 🔥 NEW: Get Hebrew label for appointment status
                apt_status_info = hebrew_label_service.get_appointment_status_label(next_apt.status or 'scheduled')
                
                # 🔥 NEW: Include custom fields with Hebrew labels
                custom_fields_formatted = []
                if next_apt.custom_fields:
                    custom_fields_formatted = hebrew_label_service.format_custom_fields(next_apt.custom_fields)
                
                payload.next_appointment = {
                    'id': next_apt.id,
                    'title': next_apt.treatment_type or next_apt.title,
                    'start': next_apt.start_datetime.isoformat() if next_apt.start_datetime else "",
                    'end': next_apt.end_datetime.isoformat() if next_apt.end_datetime else "",
                    'status': next_apt.status or 'scheduled',
                    'calendar_status_id': apt_status_info.get('calendar_status_id'),
                    'calendar_status_label_he': apt_status_info.get('calendar_status_label_he'),
                    'notes': next_apt.notes[:200] if next_apt.notes else None,
                    'custom_fields': custom_fields_formatted
                }
            
            # Past appointments (last 3)
            past_apts = Appointment.query.filter(
                Appointment.lead_id == lead.id,
                Appointment.business_id == self.business_id,
                Appointment.start_datetime < now
            ).order_by(Appointment.start_datetime.desc()).limit(3).all()
            
            payload.past_appointments = []
            for apt in past_apts:
                # 🔥 NEW: Get Hebrew label for appointment status
                apt_status_info = hebrew_label_service.get_appointment_status_label(apt.status or 'completed')
                
                # 🔥 NEW: Include custom fields with Hebrew labels
                custom_fields_formatted = []
                if apt.custom_fields:
                    custom_fields_formatted = hebrew_label_service.format_custom_fields(apt.custom_fields)
                
                payload.past_appointments.append({
                    'id': apt.id,
                    'title': apt.treatment_type or apt.title,
                    'start': apt.start_datetime.isoformat() if apt.start_datetime else "",
                    'end': apt.end_datetime.isoformat() if apt.end_datetime else "",
                    'status': apt.status or 'completed',
                    'calendar_status_id': apt_status_info.get('calendar_status_id'),
                    'calendar_status_label_he': apt_status_info.get('calendar_status_label_he'),
                    'notes': apt.notes[:200] if apt.notes else None,
                    'custom_fields': custom_fields_formatted
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
            
            # Load owner/agent information
            if lead.owner_user_id:
                owner = User.query.get(lead.owner_user_id)
                if owner:
                    payload.owner_user_id = owner.id
                    payload.owner_name = owner.name or owner.email
            
            # Load open tasks
            payload.open_tasks = self._load_open_tasks(lead)
            
            # Load deal information (read-only)
            payload = self._load_deal_info(lead, payload)
            
            # Load invoices and payments (read-only)
            payload.invoices = self._load_invoices(lead)
            payload.payments = self._load_payments(lead)
            
            # Load contracts
            payload.contracts = self._load_contracts(lead)
            
            # Load recent call logs with details
            payload.recent_calls = self._load_recent_calls(lead)
            
            # Load recent WhatsApp messages (last 20)
            payload.recent_whatsapp_messages = self._load_recent_whatsapp(lead)
            
            # Load WhatsApp summary from lead field
            if hasattr(lead, 'whatsapp_last_summary') and lead.whatsapp_last_summary:
                payload.last_whatsapp_summary = lead.whatsapp_last_summary[:500]
            
            # Load available calendars for scheduling
            payload.available_calendars = self._load_available_calendars()
            
            # Load status history
            payload.status_history = self._load_status_history(lead)
            
            logger.info(f"[UnifiedContext] Built context for lead #{lead.id}: "
                       f"{len(payload.recent_notes)} notes, "
                       f"{len(payload.past_appointments)} past appointments, "
                       f"next_apt={'Yes' if payload.next_appointment else 'No'}, "
                       f"{len(payload.open_tasks)} open tasks, "
                       f"{len(payload.available_calendars)} calendars")
            
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
    
    def _load_open_tasks(self, lead: Lead) -> List[Dict[str, Any]]:
        """
        Load open tasks for this lead
        
        Args:
            lead: Lead object
            
        Returns:
            List of open task dictionaries
        """
        try:
            tasks = CRMTask.query.filter(
                CRMTask.lead_id == lead.id,
                CRMTask.tenant_id == self.business_id,
                CRMTask.status.in_(['open', 'pending', 'in_progress'])
            ).order_by(CRMTask.due_date.asc()).limit(10).all()
            
            task_list = []
            for task in tasks:
                task_list.append({
                    'id': task.id,
                    'title': task.title or task.description[:50],
                    'description': task.description[:200] if task.description else None,
                    'status': task.status,
                    'priority': getattr(task, 'priority', 'medium'),
                    'due_date': task.due_date.isoformat() if task.due_date else None,
                    'assigned_to': getattr(task, 'assigned_to', None)
                })
            
            return task_list
            
        except Exception as e:
            logger.error(f"[UnifiedContext] Error loading tasks: {e}")
            return []
    
    def _load_deal_info(self, lead: Lead, payload: UnifiedLeadContextPayload) -> UnifiedLeadContextPayload:
        """
        Load deal/sales information (read-only)
        
        Args:
            lead: Lead object
            payload: Current payload to update
            
        Returns:
            Updated payload with deal info
        """
        try:
            # Find customer associated with this lead
            customer = None
            if lead.phone_e164:
                customer = Customer.query.filter_by(
                    business_id=self.business_id,
                    phone=lead.phone_e164
                ).first()
            
            if customer:
                # Find most recent deal for this customer
                deal = Deal.query.filter_by(
                    customer_id=customer.id
                ).order_by(Deal.created_at.desc()).first()
                
                if deal:
                    payload.deal_status = deal.stage
                    payload.deal_value = float(deal.amount) if deal.amount else None
                    payload.deal_amount = payload.deal_value
                    
                    # Check for loss reason in deal (if field exists)
                    if hasattr(deal, 'loss_reason') and deal.loss_reason:
                        payload.loss_reason = deal.loss_reason
            
            return payload
            
        except Exception as e:
            logger.error(f"[UnifiedContext] Error loading deal info: {e}")
            return payload
    
    def _load_invoices(self, lead: Lead) -> List[Dict[str, Any]]:
        """
        Load recent invoices (read-only)
        
        Args:
            lead: Lead object
            
        Returns:
            List of invoice dictionaries
        """
        try:
            invoices = Invoice.query.filter(
                Invoice.business_id == self.business_id,
                Invoice.customer_phone == lead.phone_e164
            ).order_by(Invoice.created_at.desc()).limit(5).all()
            
            invoice_list = []
            for inv in invoices:
                invoice_list.append({
                    'id': inv.id,
                    'invoice_number': inv.invoice_number,
                    'total': float(inv.total) if inv.total else 0,
                    'status': inv.status,
                    'issued_at': inv.issued_at.isoformat() if inv.issued_at else None
                })
            
            return invoice_list
            
        except Exception as e:
            logger.error(f"[UnifiedContext] Error loading invoices: {e}")
            return []
    
    def _load_payments(self, lead: Lead) -> List[Dict[str, Any]]:
        """
        Load recent payments (read-only)
        
        Args:
            lead: Lead object
            
        Returns:
            List of payment dictionaries
        """
        try:
            # Find customer to get payments
            customer = None
            if lead.phone_e164:
                customer = Customer.query.filter_by(
                    business_id=self.business_id,
                    phone=lead.phone_e164
                ).first()
            
            if not customer:
                return []
            
            # Find deals for this customer
            deals = Deal.query.filter_by(customer_id=customer.id).all()
            deal_ids = [d.id for d in deals]
            
            if not deal_ids:
                return []
            
            payments = Payment.query.filter(
                Payment.business_id == self.business_id,
                Payment.deal_id.in_(deal_ids)
            ).order_by(Payment.created_at.desc()).limit(5).all()
            
            payment_list = []
            for payment in payments:
                payment_list.append({
                    'id': payment.id,
                    'amount': payment.amount / 100 if payment.amount else 0,  # Convert from agorot
                    'currency': payment.currency or 'ILS',
                    'status': payment.status,
                    'paid_at': payment.paid_at.isoformat() if payment.paid_at else None
                })
            
            return payment_list
            
        except Exception as e:
            logger.error(f"[UnifiedContext] Error loading payments: {e}")
            return []
    
    def _load_contracts(self, lead: Lead) -> List[Dict[str, Any]]:
        """
        Load contracts for this lead
        
        Args:
            lead: Lead object
            
        Returns:
            List of contract dictionaries
        """
        try:
            contracts = Contract.query.filter(
                Contract.business_id == self.business_id,
                Contract.lead_id == lead.id
            ).order_by(Contract.created_at.desc()).limit(5).all()
            
            contract_list = []
            for contract in contracts:
                contract_list.append({
                    'id': contract.id,
                    'title': contract.title,
                    'status': contract.status,
                    'signer_name': contract.signer_name,
                    'created_at': contract.created_at.isoformat() if contract.created_at else None
                })
            
            return contract_list
            
        except Exception as e:
            logger.error(f"[UnifiedContext] Error loading contracts: {e}")
            return []
    
    def _load_recent_calls(self, lead: Lead) -> List[Dict[str, Any]]:
        """
        Load recent call logs with details
        
        Args:
            lead: Lead object
            
        Returns:
            List of call log dictionaries
        """
        try:
            calls = CallLog.query.filter(
                CallLog.lead_id == lead.id,
                CallLog.business_id == self.business_id
            ).order_by(CallLog.created_at.desc()).limit(10).all()
            
            call_list = []
            for call in calls:
                call_dict = {
                    'id': call.id,
                    'direction': call.direction,
                    'duration': call.duration_sec if hasattr(call, 'duration_sec') else None,
                    'status': call.status if hasattr(call, 'status') else None,
                    'created_at': call.created_at.isoformat() if call.created_at else None
                }
                
                # Add summary if exists (already limited in earlier query)
                if call.summary:
                    call_dict['summary'] = call.summary[:200]
                
                call_list.append(call_dict)
            
            return call_list
            
        except Exception as e:
            logger.error(f"[UnifiedContext] Error loading recent calls: {e}")
            return []
    
    def _load_recent_whatsapp(self, lead: Lead) -> List[Dict[str, Any]]:
        """
        Load recent WhatsApp messages (last 20)
        
        🔥 FIX: Load by (lead_id OR phone) to include outgoing messages
        that might not have lead_id populated yet.
        
        Args:
            lead: Lead object
            
        Returns:
            List of WhatsApp message dictionaries
        """
        try:
            from sqlalchemy import or_
            
            # Build filters: lead_id OR phone match
            filters = [WhatsAppMessage.business_id == self.business_id]
            
            # Add lead_id filter
            if lead.id:
                filters.append(WhatsAppMessage.lead_id == lead.id)
            
            # Add phone filter (normalized)
            if lead.phone_e164:
                phone_clean = lead.phone_e164.replace('+', '').strip()
                filters.append(WhatsAppMessage.to_number.like(f'%{phone_clean}%'))
            
            messages = WhatsAppMessage.query.filter(
                or_(*filters)
            ).order_by(WhatsAppMessage.timestamp.desc()).limit(20).all()
            
            message_list = []
            for msg in messages:
                message_list.append({
                    'id': msg.id,
                    'direction': msg.direction if hasattr(msg, 'direction') else 'unknown',
                    'message_text': msg.message_text[:200] if msg.message_text else None,
                    'timestamp': msg.timestamp.isoformat() if msg.timestamp else None,
                    'is_from_customer': msg.direction == 'in' if hasattr(msg, 'direction') else True
                })
            
            return message_list
            
        except Exception as e:
            logger.error(f"[UnifiedContext] Error loading WhatsApp messages: {e}")
            return []
    
    def _load_available_calendars(self) -> List[Dict[str, Any]]:
        """
        Load all available calendars for this business
        
        Returns:
            List of calendar dictionaries with Hebrew names
        """
        try:
            calendars = BusinessCalendar.query.filter(
                BusinessCalendar.business_id == self.business_id,
                BusinessCalendar.is_active.is_(True)
            ).order_by(BusinessCalendar.priority.desc()).all()
            
            calendar_list = []
            for cal in calendars:
                calendar_list.append({
                    'id': cal.id,
                    'name': cal.name,  # Hebrew name
                    'type_key': cal.type_key,
                    'priority': cal.priority,
                    'default_duration_minutes': cal.default_duration_minutes,
                    'allowed_tags': cal.allowed_tags or []
                })
            
            return calendar_list
            
        except Exception as e:
            logger.error(f"[UnifiedContext] Error loading calendars: {e}")
            return []
    
    def _load_status_history(self, lead: Lead) -> List[Dict[str, Any]]:
        """
        Load status change history
        
        Args:
            lead: Lead object
            
        Returns:
            List of status history dictionaries
        """
        try:
            # Try to find LeadStatusAudit or similar table
            # If it doesn't exist, return empty list
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            # Check for status audit table
            if 'lead_status_audit' in tables:
                # Import dynamically to avoid errors if table doesn't exist
                from server.models_sql import db
                
                # Query status history
                history_query = db.session.execute(
                    db.text("""
                        SELECT old_status, new_status, change_reason, changed_at, channel
                        FROM lead_status_audit
                        WHERE lead_id = :lead_id AND tenant_id = :tenant_id
                        ORDER BY changed_at DESC
                        LIMIT 10
                    """),
                    {'lead_id': lead.id, 'tenant_id': self.business_id}
                )
                
                history_list = []
                for row in history_query:
                    history_list.append({
                        'old_status': row[0],
                        'new_status': row[1],
                        'reason': row[2],
                        'changed_at': row[3].isoformat() if row[3] else None,
                        'channel': row[4]
                    })
                
                return history_list
            
            return []
            
        except Exception as e:
            logger.debug(f"[UnifiedContext] Status history not available or error: {e}")
            return []
    
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
        
        # Owner/Agent
        if context.owner_name:
            parts.append(f"👤 מטפל: {context.owner_name}")
        
        # 🔥 NEW: Status with Hebrew label
        if context.current_status or context.current_status_label_he:
            # Use Hebrew label if available, otherwise fallback to status code, or "לא ידוע" if neither exists
            status_display = context.current_status_label_he or context.current_status or "לא ידוע"
            parts.append(f"📊 סטטוס ליד: {status_display}")
        
        # Service type and location
        if context.service_type:
            parts.append(f"🔧 סוג שירות: {context.service_type}")
        if context.city:
            parts.append(f"📍 עיר: {context.city}")
        
        # Tags
        if context.tags:
            parts.append(f"🏷️ תגיות: {', '.join(context.tags)}")
        
        # Available calendars (CRITICAL for multi-calendar scheduling)
        if context.available_calendars:
            parts.append(f"\n📆 לוחות שנה זמינים לתיאום ({len(context.available_calendars)}):")
            for cal in context.available_calendars:
                cal_info = f"  - {cal['name']}"
                if cal.get('allowed_tags'):
                    cal_info += f" (מתאים ל: {', '.join(cal['allowed_tags'])})"
                parts.append(cal_info)
            if len(context.available_calendars) > 1:
                parts.append("  ⚠️ יש מספר לוחות שנה - ודא בחירת הלוח הנכון לפי סוג הפגישה!")
        
        # 🔥 NEW: Next appointment with Hebrew status label and custom fields
        if context.next_appointment:
            apt = context.next_appointment
            parts.append(f"\n📅 פגישה הבאה: {apt['title']} ב-{apt['start']}")
            
            # Use Hebrew label for appointment status if available
            if apt.get('calendar_status_label_he'):
                parts.append(f"  סטטוס פגישה: {apt['calendar_status_label_he']}")
            elif apt.get('status') and apt['status'] != 'scheduled':
                parts.append(f"  סטטוס: {apt['status']}")
            
            # 🔥 NEW: Include custom fields if present
            if apt.get('custom_fields'):
                parts.append(f"  שדות נוספים:")
                for field in apt['custom_fields']:
                    parts.append(f"    - {field['field_label_he']}: {field['value']}")
        
        # 🔥 NEW: Past appointments with Hebrew status labels and custom fields
        if context.past_appointments:
            parts.append(f"\n📅 פגישות קודמות ({len(context.past_appointments)}):")
            for apt in context.past_appointments[:3]:
                apt_date = apt['start'][:10] if apt.get('start') else ''
                # Use Hebrew label for status if available
                status_display = apt.get('calendar_status_label_he') or apt.get('status', 'completed')
                parts.append(f"  - [{apt_date}] {apt['title']} - {status_display}")
                
                # Include custom fields if present
                if apt.get('custom_fields'):
                    for field in apt['custom_fields'][:2]:  # Show max 2 custom fields per appointment
                        parts.append(f"      {field['field_label_he']}: {field['value']}")
        
        # Open tasks
        if context.open_tasks:
            parts.append(f"\n✅ משימות פתוחות ({len(context.open_tasks)}):")
            for task in context.open_tasks[:3]:
                task_info = f"  - {task['title']}"
                if task.get('due_date'):
                    task_info += f" (יעד: {task['due_date'][:10]})"
                parts.append(task_info)
        
        # Deal information (read-only)
        if context.deal_status or context.deal_value:
            deal_parts = []
            if context.deal_status:
                deal_parts.append(f"סטטוס: {context.deal_status}")
            if context.deal_value:
                deal_parts.append(f"סכום: ₪{context.deal_value:,.0f}")
            if context.loss_reason:
                deal_parts.append(f"סיבת הפסד: {context.loss_reason}")
            parts.append(f"\n💰 עסקה: {' | '.join(deal_parts)}")
        
        # Invoices and payments (read-only)
        if context.invoices:
            parts.append(f"\n🧾 חשבוניות אחרונות ({len(context.invoices)}):")
            for inv in context.invoices[:3]:
                inv_info = f"  - {inv['invoice_number']}: ₪{inv['total']:,.0f} ({inv['status']})"
                parts.append(inv_info)
        
        if context.payments:
            parts.append(f"\n💳 תשלומים אחרונים ({len(context.payments)}):")
            for payment in context.payments[:3]:
                payment_info = f"  - ₪{payment['amount']:,.0f} ({payment['status']})"
                parts.append(payment_info)
        
        # Contracts
        if context.contracts:
            parts.append(f"\n📄 חוזים ({len(context.contracts)}):")
            for contract in context.contracts[:3]:
                contract_info = f"  - {contract['title']}: {contract['status']}"
                parts.append(contract_info)
        
        # Memory
        if context.customer_memory:
            parts.append(f"\n🧠 זיכרון לקוח: {context.customer_memory}")
        
        # Recent notes (most recent first)
        if context.recent_notes:
            parts.append(f"\n📝 הערות אחרונות ({len(context.recent_notes)}):")
            for note in context.recent_notes[:3]:  # Show top 3
                note_date = note['created_at'][:10] if note.get('created_at') else ''
                content = note['content'][:150]
                # Add marker for latest note
                if note.get('is_latest'):
                    content = f"[עדכני ביותר] {content}"
                parts.append(f"  - [{note_date}] {content}...")
        
        # Summary
        if context.summary:
            parts.append(f"\n💬 סיכום: {context.summary}")
        
        # Status history
        if context.status_history:
            parts.append(f"\n📊 היסטוריית סטטוסים ({len(context.status_history)}):")
            for hist in context.status_history[:3]:
                hist_date = hist['changed_at'][:10] if hist.get('changed_at') else ''
                parts.append(f"  - [{hist_date}] {hist['old_status']} → {hist['new_status']}")
        
        # Communication summary
        if context.recent_calls or context.recent_whatsapp_messages:
            comm_parts = []
            if context.recent_calls:
                comm_parts.append(f"{len(context.recent_calls)} שיחות")
            if context.recent_whatsapp_messages:
                comm_parts.append(f"{len(context.recent_whatsapp_messages)} הודעות WhatsApp")
            parts.append(f"\n💬 תקשורת אחרונה: {', '.join(comm_parts)}")
        
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
