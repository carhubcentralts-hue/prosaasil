"""
Unified Status Update Service - Single Source of Truth for Status Changes

This is the SINGLE authoritative service for:
1. Updating lead status with validation
2. Audit logging (who, when, channel, reason)
3. Status progression logic (prevent downgrades)
4. Confidence scoring
5. Webhook notifications

Replaces duplications from:
- lead_auto_status_service.py (status suggestions)
- customer_intelligence.py (status updates)
- Direct SQL updates in various places

Security: All operations are multi-tenant scoped to business_id
"""
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from server.db import db
from server.models_sql import Lead, LeadStatusHistory, LeadStatus, BusinessSettings
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ================================================================================
# STATUS UPDATE MODELS
# ================================================================================

class StatusUpdateRequest(BaseModel):
    """Request to update lead status"""
    lead_id: int = Field(..., description="Lead ID to update")
    new_status: str = Field(..., description="New status value")
    reason: Optional[str] = Field(None, description="Reason for status change")
    confidence: Optional[float] = Field(None, description="AI confidence score (0.0-1.0)", ge=0.0, le=1.0)
    channel: str = Field("unknown", description="Channel where update originated (whatsapp, call, manual, system)")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class StatusUpdateResult(BaseModel):
    """Result of status update operation"""
    success: bool
    message: str
    old_status: Optional[str] = None
    new_status: Optional[str] = None
    skipped: bool = False  # True if update was skipped (same status/family)
    audit_id: Optional[int] = None  # ID of audit log entry


# ================================================================================
# STATUS FAMILIES (from lead_auto_status_service.py)
# ================================================================================

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

# Status progression scores
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


# ================================================================================
# UNIFIED STATUS SERVICE
# ================================================================================

class UnifiedStatusService:
    """
    Single source of truth for lead status updates
    Handles validation, progression logic, audit logging, and webhooks
    """
    
    def __init__(self, business_id: int):
        """
        Initialize service for a specific business
        
        Args:
            business_id: Business/tenant ID for multi-tenant scoping
        """
        self.business_id = business_id
    
    def is_customer_service_enabled(self) -> bool:
        """
        Check if customer service AI (and auto-status updates) is enabled
        
        Returns:
            bool: True if customer service is enabled
        """
        try:
            settings = BusinessSettings.query.filter_by(tenant_id=self.business_id).first()
            enabled = getattr(settings, 'enable_customer_service', False) if settings else False
            return enabled
        except Exception as e:
            logger.error(f"[UnifiedStatus] Error checking customer service flag: {e}")
            return False
    
    def update_lead_status(self, request: StatusUpdateRequest) -> StatusUpdateResult:
        """
        Update lead status with validation, progression logic, and audit logging
        THIS IS THE SINGLE AUTHORITATIVE METHOD for status updates
        
        Args:
            request: StatusUpdateRequest with lead_id, new_status, etc.
            
        Returns:
            StatusUpdateResult with success/failure and details
        """
        try:
            # Check if customer service (auto-status) is enabled
            if request.channel in ['whatsapp', 'call'] and not self.is_customer_service_enabled():
                logger.info(f"[UnifiedStatus] Customer service disabled for business {self.business_id}, "
                           f"skipping auto-status update")
                return StatusUpdateResult(
                    success=False,
                    message="Customer service mode disabled - status updates not allowed",
                    skipped=True
                )
            
            # Verify lead belongs to this business
            lead = Lead.query.filter_by(
                id=request.lead_id,
                tenant_id=self.business_id
            ).first()
            
            if not lead:
                logger.warning(f"[UnifiedStatus] Lead {request.lead_id} not found in business {self.business_id}")
                return StatusUpdateResult(
                    success=False,
                    message=f"Lead {request.lead_id} not found"
                )
            
            old_status = lead.status
            new_status = request.new_status.lower().strip()
            
            # Check if status is actually changing
            if old_status and old_status.lower() == new_status:
                logger.info(f"[UnifiedStatus] Status unchanged for lead {request.lead_id}: {old_status}")
                return StatusUpdateResult(
                    success=True,
                    message="Status unchanged - no update needed",
                    old_status=old_status,
                    new_status=old_status,
                    skipped=True
                )
            
            # Check status family equivalence (avoid unnecessary changes)
            if old_status and self._are_status_equivalent(old_status, new_status):
                logger.info(f"[UnifiedStatus] Status family unchanged for lead {request.lead_id}: "
                           f"{old_status} ≈ {new_status}")
                return StatusUpdateResult(
                    success=True,
                    message=f"Status in same family - keeping {old_status}",
                    old_status=old_status,
                    new_status=old_status,
                    skipped=True
                )
            
            # Check status progression (prevent downgrades unless manual/forced)
            if request.channel in ['whatsapp', 'call']:  # Only for automated updates
                if not self._is_valid_progression(old_status, new_status):
                    logger.warning(f"[UnifiedStatus] Invalid status progression for lead {request.lead_id}: "
                                 f"{old_status} → {new_status}")
                    return StatusUpdateResult(
                        success=False,
                        message=f"Invalid status progression: {old_status} → {new_status}",
                        old_status=old_status,
                        skipped=True
                    )
            
            # Validate status exists for this business
            valid_statuses = self._get_valid_statuses()
            if new_status not in valid_statuses:
                logger.warning(f"[UnifiedStatus] Invalid status '{new_status}' for business {self.business_id}")
                # Try to find closest match
                closest = self._find_closest_status(new_status, valid_statuses)
                if closest:
                    logger.info(f"[UnifiedStatus] Using closest match: {new_status} → {closest}")
                    new_status = closest
                else:
                    return StatusUpdateResult(
                        success=False,
                        message=f"Status '{new_status}' not valid for this business"
                    )
            
            # Update the status
            lead.status = new_status
            lead.updated_at = datetime.utcnow()
            
            # Create audit log entry
            audit_id = self._create_audit_log(
                lead=lead,
                old_status=old_status,
                new_status=new_status,
                reason=request.reason,
                confidence=request.confidence,
                channel=request.channel,
                metadata=request.metadata
            )
            
            # Commit changes
            db.session.commit()
            
            logger.info(f"[UnifiedStatus] ✅ Updated lead {request.lead_id} status: "
                       f"{old_status} → {new_status} (channel={request.channel}, "
                       f"confidence={request.confidence}, audit_id={audit_id})")
            
            # Trigger webhook if configured
            self._trigger_status_webhook(lead, old_status, new_status, request.channel)
            
            return StatusUpdateResult(
                success=True,
                message="Status updated successfully",
                old_status=old_status,
                new_status=new_status,
                audit_id=audit_id
            )
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"[UnifiedStatus] Error updating lead status: {e}", exc_info=True)
            return StatusUpdateResult(
                success=False,
                message=f"Error updating status: {str(e)}"
            )
    
    def _are_status_equivalent(self, status1: str, status2: str) -> bool:
        """
        Check if two statuses are in the same family (semantically equivalent)
        
        Args:
            status1: First status
            status2: Second status
            
        Returns:
            bool: True if statuses are equivalent
        """
        if not status1 or not status2:
            return False
        
        s1_lower = status1.lower().strip()
        s2_lower = status2.lower().strip()
        
        # Find families for each status
        family1 = None
        family2 = None
        
        for family_name, family_values in STATUS_FAMILIES.items():
            if s1_lower in family_values:
                family1 = family_name
            if s2_lower in family_values:
                family2 = family_name
        
        return family1 is not None and family1 == family2
    
    def _is_valid_progression(self, old_status: Optional[str], new_status: str) -> bool:
        """
        Check if status progression is valid (not a downgrade)
        
        Args:
            old_status: Current status
            new_status: Proposed new status
            
        Returns:
            bool: True if progression is valid
        """
        if not old_status:
            return True  # Any status is valid if no previous status
        
        # Get progression scores
        old_family = self._get_status_family(old_status)
        new_family = self._get_status_family(new_status)
        
        old_score = STATUS_PROGRESSION_SCORE.get(old_family, 0)
        new_score = STATUS_PROGRESSION_SCORE.get(new_family, 0)
        
        # Allow progression forward or lateral (same score)
        return new_score >= old_score
    
    def _get_status_family(self, status: str) -> Optional[str]:
        """Get status family name"""
        if not status:
            return None
        
        status_lower = status.lower().strip()
        for family_name, family_values in STATUS_FAMILIES.items():
            if status_lower in family_values:
                return family_name
        
        return None
    
    def _get_valid_statuses(self) -> List[str]:
        """
        Get list of valid status values for this business
        
        Returns:
            List of valid status strings (lowercase)
        """
        try:
            statuses = LeadStatus.query.filter_by(tenant_id=self.business_id).all()
            return [s.status_key.lower() for s in statuses]
        except Exception as e:
            logger.error(f"[UnifiedStatus] Error getting valid statuses: {e}")
            # Fallback to common statuses
            return ['new', 'contacted', 'qualified', 'interested', 'not_relevant', 
                   'follow_up', 'no_answer', 'appointment_scheduled']
    
    def _find_closest_status(self, status: str, valid_statuses: List[str]) -> Optional[str]:
        """
        Find closest matching status from valid statuses
        
        Args:
            status: Proposed status
            valid_statuses: List of valid statuses
            
        Returns:
            Closest matching status or None
        """
        status_lower = status.lower().strip()
        
        # Exact match
        if status_lower in valid_statuses:
            return status_lower
        
        # Check if status is in a family and find valid status in same family
        family = self._get_status_family(status)
        if family:
            for valid in valid_statuses:
                if self._get_status_family(valid) == family:
                    return valid
        
        return None
    
    def _create_audit_log(
        self,
        lead: Lead,
        old_status: Optional[str],
        new_status: str,
        reason: Optional[str],
        confidence: Optional[float],
        channel: str,
        metadata: Optional[Dict[str, Any]]
    ) -> Optional[int]:
        """
        Create audit log entry for status change
        
        Returns:
            Audit log entry ID or None
        """
        try:
            # Check if LeadStatusHistory model exists
            from server.models_sql import LeadStatusHistory
            
            audit = LeadStatusHistory(
                lead_id=lead.id,
                tenant_id=self.business_id,
                old_status=old_status,
                new_status=new_status,
                changed_by=None,  # AI/automated
                change_reason=reason,
                confidence_score=confidence,
                channel=channel,
                metadata_json=metadata,
                created_at=datetime.utcnow()
            )
            
            db.session.add(audit)
            db.session.flush()
            
            logger.info(f"[UnifiedStatus] Created audit log #{audit.id} for lead {lead.id}")
            return audit.id
            
        except ImportError:
            # LeadStatusHistory table doesn't exist yet
            logger.info(f"[UnifiedStatus] AUDIT: lead_id={lead.id}, "
                       f"{old_status} → {new_status}, channel={channel}, "
                       f"reason={reason}, confidence={confidence}")
            return None
        except Exception as e:
            logger.error(f"[UnifiedStatus] Error creating audit log: {e}")
            return None
    
    def _trigger_status_webhook(
        self,
        lead: Lead,
        old_status: Optional[str],
        new_status: str,
        channel: str
    ):
        """
        Trigger status change webhook if configured
        
        Args:
            lead: Lead object
            old_status: Previous status
            new_status: New status
            channel: Channel where change originated
        """
        try:
            settings = BusinessSettings.query.filter_by(tenant_id=self.business_id).first()
            webhook_url = getattr(settings, 'status_webhook_url', None) if settings else None
            
            if not webhook_url:
                return
            
            # TODO: Implement webhook trigger
            # This would be similar to existing webhook implementations
            logger.info(f"[UnifiedStatus] Would trigger webhook: {webhook_url} "
                       f"(lead={lead.id}, {old_status}→{new_status})")
            
        except Exception as e:
            logger.error(f"[UnifiedStatus] Error triggering status webhook: {e}")


# ================================================================================
# CONVENIENCE FUNCTIONS
# ================================================================================

def update_lead_status_unified(
    business_id: int,
    lead_id: int,
    new_status: str,
    reason: Optional[str] = None,
    confidence: Optional[float] = None,
    channel: str = "unknown",
    metadata: Optional[Dict[str, Any]] = None
) -> StatusUpdateResult:
    """
    Update lead status using unified service
    
    Args:
        business_id: Business ID
        lead_id: Lead ID
        new_status: New status value
        reason: Reason for change
        confidence: AI confidence (0.0-1.0)
        channel: Channel (whatsapp, call, manual, system)
        metadata: Additional metadata
        
    Returns:
        StatusUpdateResult
    """
    service = UnifiedStatusService(business_id)
    request = StatusUpdateRequest(
        lead_id=lead_id,
        new_status=new_status,
        reason=reason,
        confidence=confidence,
        channel=channel,
        metadata=metadata
    )
    return service.update_lead_status(request)
