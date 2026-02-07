"""
Lead Status Update Service - Single Source of Truth (SSOT)

This is the ONLY service allowed to update lead status automatically.
All automated status changes from WhatsApp summaries, call summaries, or other
AI sources MUST go through this service.

Key Features:
- Idempotency: Prevents duplicate updates from retries/webhooks
- Status mapping: Maps Hebrew labels to business-specific status IDs
- Confidence gating: Only applies changes with sufficient confidence
- Audit trail: Records all attempts and applications
- Push notifications: Notifies users of status changes

🔒 IRON RULE: No other code should do `lead.status = ...` for AI-driven changes!
"""
import logging
import re
from typing import Optional, Tuple
from datetime import datetime
from flask import has_app_context

log = logging.getLogger(__name__)

# Confidence threshold for applying status changes
CONFIDENCE_THRESHOLD = 0.65


class LeadStatusUpdateService:
    """
    Single source of truth for automated lead status updates
    
    This service ensures:
    - Idempotency (no duplicate updates)
    - Proper status mapping (Hebrew → status_id)
    - Audit trail
    - Push notifications
    """
    
    def __init__(self, app=None):
        """
        Initialize the service
        
        Args:
            app: Flask app instance (optional, will use app context if available)
        """
        self.app = app
    
    def apply_from_recommendation(
        self,
        business_id: int,
        lead_id: int,
        summary_text: str,
        source: str,
        source_event_id: str,
        confidence: Optional[float] = None
    ) -> Tuple[bool, str]:
        """
        Apply status change from AI recommendation in summary
        
        This is the main entry point for all automated status updates.
        
        Args:
            business_id: Business ID
            lead_id: Lead ID
            summary_text: Summary text containing [המלצה: <status_label>]
            source: Source of recommendation ('whatsapp_summary' | 'call_summary')
            source_event_id: Unique event ID (message_id | call_sid | conversation_id)
            confidence: AI confidence score (0.0-1.0), if available
            
        Returns:
            (success: bool, message: str) - Success flag and descriptive message
        """
        from server.models_sql import LeadStatusEvent, Lead, LeadStatus, LeadStatusHistory
        from server.db import db
        
        log.info(f"[StatusUpdate] Processing recommendation for lead {lead_id} from {source} (event: {source_event_id})")
        
        # Extract recommendation from summary
        recommended_label = self._extract_recommendation(summary_text)
        if not recommended_label:
            log.info(f"[StatusUpdate] No recommendation found in summary for lead {lead_id}")
            return False, "No recommendation found in summary"
        
        log.info(f"[StatusUpdate] Found recommendation: '{recommended_label}'")
        
        # Check idempotency first
        existing_event = LeadStatusEvent.query.filter_by(
            business_id=business_id,
            source=source,
            source_event_id=source_event_id
        ).first()
        
        if existing_event:
            log.info(f"[StatusUpdate] ⚠️ Idempotency hit - event already processed: {source_event_id}")
            if existing_event.applied:
                return True, f"Status already updated (idempotent - previously applied to '{existing_event.recommended_status_id}')"
            else:
                return False, f"Status update already attempted but not applied (reason: {existing_event.reason or 'unknown'})"
        
        # Map Hebrew label to status_id
        matched_status_id = self._map_label_to_status_id(recommended_label, business_id)
        
        if not matched_status_id:
            log.warning(f"[StatusUpdate] ❌ Status label '{recommended_label}' not found in business {business_id} statuses")
            # Record the event as not applied
            event = LeadStatusEvent(
                business_id=business_id,
                lead_id=lead_id,
                source=source,
                source_event_id=source_event_id,
                recommended_status_label=recommended_label,
                recommended_status_id=None,
                confidence=confidence,
                reason="Status label not found in business statuses",
                applied=False,
                created_at=datetime.utcnow()
            )
            db.session.add(event)
            db.session.commit()
            return False, f"Status label '{recommended_label}' not found in available statuses"
        
        log.info(f"[StatusUpdate] Mapped '{recommended_label}' → '{matched_status_id}'")
        
        # Check confidence threshold
        if confidence is not None and confidence < CONFIDENCE_THRESHOLD:
            log.info(f"[StatusUpdate] ⚠️ Confidence too low ({confidence:.2f} < {CONFIDENCE_THRESHOLD}) - skipping update")
            # Record the event as not applied
            event = LeadStatusEvent(
                business_id=business_id,
                lead_id=lead_id,
                source=source,
                source_event_id=source_event_id,
                recommended_status_label=recommended_label,
                recommended_status_id=matched_status_id,
                confidence=confidence,
                reason=f"Low confidence ({confidence:.2f})",
                applied=False,
                created_at=datetime.utcnow()
            )
            db.session.add(event)
            db.session.commit()
            return False, f"Confidence too low ({confidence:.2f} < {CONFIDENCE_THRESHOLD})"
        
        # Get lead and check current status
        lead = Lead.query.get(lead_id)
        if not lead:
            log.error(f"[StatusUpdate] Lead {lead_id} not found")
            return False, "Lead not found"
        
        old_status = lead.status
        
        # Check if status is already the same
        if old_status == matched_status_id:
            log.info(f"[StatusUpdate] ℹ️ Status already set to '{matched_status_id}' - no-op")
            # Record the event as applied (but no change needed)
            event = LeadStatusEvent(
                business_id=business_id,
                lead_id=lead_id,
                source=source,
                source_event_id=source_event_id,
                recommended_status_label=recommended_label,
                recommended_status_id=matched_status_id,
                confidence=confidence,
                reason="No change needed - status already set",
                applied=True,
                applied_at=datetime.utcnow(),
                created_at=datetime.utcnow()
            )
            db.session.add(event)
            db.session.commit()
            return True, f"Status already set to '{matched_status_id}' (no-op)"
        
        # Apply the status change
        log.info(f"[StatusUpdate] ✅ Updating lead {lead_id} status: '{old_status}' → '{matched_status_id}'")
        
        try:
            # Update lead status with optimistic locking
            # Note: In a high-concurrency environment, consider adding version field
            # and checking it before update to prevent race conditions
            lead.status = matched_status_id
            lead.status_sequence_token = Lead.status_sequence_token + 1  # Use column expression for atomic increment
            lead.status_entered_at = datetime.utcnow()
            lead.updated_at = datetime.utcnow()
            
            # Record in status history for audit trail
            history = LeadStatusHistory(
                lead_id=lead_id,
                tenant_id=business_id,
                old_status=old_status,
                new_status=matched_status_id,
                changed_by=None,  # Automated change
                change_reason=f"AI recommendation from {source}: {recommended_label}",
                confidence_score=confidence,
                channel=source.replace('_summary', ''),  # 'whatsapp' or 'call'
                metadata_json={
                    'source': source,
                    'source_event_id': source_event_id,
                    'recommended_label': recommended_label
                },
                created_at=datetime.utcnow()
            )
            db.session.add(history)
            
            # Record the status event as applied
            event = LeadStatusEvent(
                business_id=business_id,
                lead_id=lead_id,
                source=source,
                source_event_id=source_event_id,
                recommended_status_label=recommended_label,
                recommended_status_id=matched_status_id,
                confidence=confidence,
                reason=f"Applied: {old_status} → {matched_status_id}",
                applied=True,
                applied_at=datetime.utcnow(),
                created_at=datetime.utcnow()
            )
            db.session.add(event)
            
            db.session.commit()
            
            log.info(f"[StatusUpdate] ✅ Status update committed to database")
            
            # Send push notification (async, non-blocking)
            self._send_push_notification(
                business_id=business_id,
                lead_id=lead_id,
                old_status=old_status,
                new_status=matched_status_id,
                source=source,
                confidence=confidence
            )
            
            return True, f"Status updated: {old_status} → {matched_status_id}"
            
        except Exception as e:
            log.error(f"[StatusUpdate] ❌ Failed to update status: {e}", exc_info=True)
            db.session.rollback()
            return False, f"Failed to update status: {str(e)}"
    
    def _extract_recommendation(self, text: str) -> Optional[str]:
        """
        Extract recommendation from summary text: [המלצה: <status_label>]
        
        Args:
            text: Summary text
            
        Returns:
            Status label (Hebrew) or None if not found
        """
        if not text:
            return None
        
        # Pattern: [המלצה: <label>]
        pattern = r'\[המלצה:\s*([^\]]+)\]'
        match = re.search(pattern, text)
        
        if match:
            label = match.group(1).strip()
            # Normalize: remove extra spaces, normalize quotes
            label = ' '.join(label.split())
            label = label.replace('"', '"').replace('"', '"').replace("'", "'")
            return label
        
        return None
    
    def _map_label_to_status_id(self, label: str, business_id: int) -> Optional[str]:
        """
        Map Hebrew status label to status_id (name) for the business
        
        Args:
            label: Hebrew label from AI (e.g., "מעוניין")
            business_id: Business ID
            
        Returns:
            Status ID (name) or None if no match found
        """
        from server.models_sql import LeadStatus
        
        # Get all active statuses for the business
        statuses = LeadStatus.query.filter_by(
            business_id=business_id,
            is_active=True
        ).all()
        
        if not statuses:
            log.warning(f"[StatusUpdate] No active statuses found for business {business_id}")
            return None
        
        # Normalize input label
        label_normalized = self._normalize_label(label)
        
        # Try exact match first
        for status in statuses:
            status_label_normalized = self._normalize_label(status.label)
            if label_normalized == status_label_normalized:
                log.info(f"[StatusUpdate] Exact match: '{label}' → '{status.name}'")
                return status.name
        
        # Try partial match (label contains or is contained in status label)
        for status in statuses:
            status_label_normalized = self._normalize_label(status.label)
            if label_normalized in status_label_normalized or status_label_normalized in label_normalized:
                log.info(f"[StatusUpdate] Partial match: '{label}' ≈ '{status.label}' → '{status.name}'")
                return status.name
        
        log.warning(f"[StatusUpdate] No match found for label '{label}' in business {business_id}")
        return None
    
    def _normalize_label(self, label: str) -> str:
        """
        Normalize Hebrew label for matching
        
        Args:
            label: Label to normalize
            
        Returns:
            Normalized label (lowercase, trimmed, normalized whitespace/quotes)
        """
        if not label:
            return ""
        
        # Trim and normalize whitespace
        normalized = ' '.join(label.split())
        
        # Normalize quotes
        normalized = normalized.replace('"', '"').replace('"', '"')
        normalized = normalized.replace("'", "'").replace("'", "'")
        
        # Lowercase for case-insensitive matching
        normalized = normalized.lower()
        
        return normalized
    
    def _send_push_notification(
        self,
        business_id: int,
        lead_id: int,
        old_status: str,
        new_status: str,
        source: str,
        confidence: Optional[float]
    ):
        """
        Send push notification about status change
        
        Args:
            business_id: Business ID
            lead_id: Lead ID
            old_status: Old status
            new_status: New status
            source: Source of change
            confidence: AI confidence score
        """
        try:
            from server.models_sql import Lead, Business, User
            from server.services.notifications.dispatcher import dispatch_push_to_user
            from server.services.push.webpush_sender import PushPayload
            
            # Get lead and business info
            lead = Lead.query.get(lead_id)
            business = Business.query.get(business_id)
            
            if not lead or not business:
                log.warning(f"[StatusUpdate] Cannot send push notification - lead or business not found")
                return
            
            # Get business owner/admin users
            users = User.query.filter_by(tenant_id=business_id).all()
            
            if not users:
                log.info(f"[StatusUpdate] No users found for business {business_id} - skipping push notification")
                return
            
            # Create notification payload
            source_mapping = {
                'whatsapp_summary': 'WhatsApp',
                'call_summary': 'שיחה'
            }
            source_name = source_mapping.get(source, f'מקור: {source}')  # Explicit fallback
            confidence_text = f" (ביטחון: {confidence:.0%})" if confidence else ""
            
            title = f"סטטוס עודכן: {lead.full_name or lead.phone_e164 or 'ליד'}"
            body = f"סטטוס שונה ל-'{new_status}' על פי סיכום {source_name}{confidence_text}"
            url = f"/leads/{lead_id}"
            
            payload = PushPayload(
                title=title,
                body=body,
                url=url,
                data={
                    'type': 'lead_status_change',
                    'lead_id': lead_id,
                    'old_status': old_status,
                    'new_status': new_status,
                    'source': source,
                    'confidence': confidence
                }
            )
            
            # Send to all business users (async, non-blocking)
            for user in users:
                try:
                    dispatch_push_to_user(
                        user_id=user.id,
                        business_id=business_id,
                        payload=payload,
                        background=True  # Async
                    )
                    log.info(f"[StatusUpdate] Push notification dispatched to user {user.id}")
                except Exception as e:
                    log.error(f"[StatusUpdate] Failed to dispatch push to user {user.id}: {e}")
            
        except Exception as e:
            log.error(f"[StatusUpdate] Failed to send push notification: {e}", exc_info=True)
            # Don't fail the status update if push notification fails


# Global service instance
_service_instance = None


def get_status_update_service():
    """Get or create the global service instance"""
    global _service_instance
    if _service_instance is None:
        _service_instance = LeadStatusUpdateService()
    return _service_instance
