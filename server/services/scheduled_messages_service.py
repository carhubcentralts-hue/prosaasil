"""
Scheduled WhatsApp Messages Service
Manages scheduling rules and message queue for WhatsApp messages triggered by lead status changes
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from sqlalchemy import text
from server.db import db
from server.models_sql import (
    ScheduledMessageRule,
    ScheduledRuleStatus,
    ScheduledMessagesQueue,
    LeadStatus,
    Lead,
    Business
)

logger = logging.getLogger(__name__)


def create_rule(
    business_id: int,
    name: str,
    message_text: str,
    status_ids: List[int],
    delay_minutes: int,
    created_by_user_id: int,
    template_name: Optional[str] = None,
    send_window_start: Optional[str] = None,
    send_window_end: Optional[str] = None,
    is_active: bool = True,
    provider: str = "baileys",
    delay_seconds: Optional[int] = None
) -> ScheduledMessageRule:
    """
    Create a new scheduling rule
    
    Args:
        business_id: Business ID for multi-tenant isolation
        name: User-friendly name for the rule
        message_text: Message content to send
        status_ids: List of lead status IDs that trigger this rule
        delay_minutes: Minutes to wait after status change (LEGACY - use delay_seconds)
        created_by_user_id: User creating the rule
        template_name: Optional template identifier
        send_window_start: Optional start time (HH:MM format)
        send_window_end: Optional end time (HH:MM format)
        is_active: Whether rule is active
        provider: WhatsApp provider to use ("baileys" | "meta" | "auto")
        delay_seconds: Seconds to wait after status change (NEW - preferred over delay_minutes)
    
    Returns:
        Created ScheduledMessageRule instance
    """
    # Determine delay_seconds (prefer delay_seconds over delay_minutes)
    if delay_seconds is None:
        delay_seconds = delay_minutes * 60
    
    # Validation
    if delay_seconds < 0 or delay_seconds > 2592000:  # 0 seconds to 30 days
        raise ValueError("delay_seconds must be between 0 and 2592000 (30 days)")
    
    # Validate delay_minutes for backward compatibility
    if delay_minutes < 1 or delay_minutes > 43200:  # 1 minute to 30 days
        raise ValueError("delay_minutes must be between 1 and 43200 (30 days)")
    
    if not status_ids:
        raise ValueError("At least one status_id is required")
    
    # Verify all status_ids belong to this business
    statuses = LeadStatus.query.filter(
        LeadStatus.id.in_(status_ids),
        LeadStatus.business_id == business_id
    ).all()
    
    if len(statuses) != len(status_ids):
        raise ValueError("One or more status_ids are invalid or don't belong to this business")
    
    # Validate provider
    if provider not in ("baileys", "meta", "auto"):
        raise ValueError("provider must be 'baileys', 'meta', or 'auto'")
    
    # Create rule
    rule = ScheduledMessageRule(
        business_id=business_id,
        name=name,
        message_text=message_text,
        delay_minutes=delay_minutes,
        delay_seconds=delay_seconds,
        created_by_user_id=created_by_user_id,
        template_name=template_name,
        send_window_start=send_window_start,
        send_window_end=send_window_end,
        is_active=is_active,
        provider=provider
    )
    
    db.session.add(rule)
    db.session.flush()  # Get rule.id
    
    # Create rule-status mappings
    for status_id in status_ids:
        rule_status = ScheduledRuleStatus(
            rule_id=rule.id,
            status_id=status_id
        )
        db.session.add(rule_status)
    
    db.session.commit()
    logger.info(f"[SCHEDULED-MSG] Created rule {rule.id}: '{name}' for business {business_id}")
    
    return rule


def update_rule(
    rule_id: int,
    business_id: int,
    name: Optional[str] = None,
    message_text: Optional[str] = None,
    status_ids: Optional[List[int]] = None,
    delay_minutes: Optional[int] = None,
    delay_seconds: Optional[int] = None,
    template_name: Optional[str] = None,
    send_window_start: Optional[str] = None,
    send_window_end: Optional[str] = None,
    is_active: Optional[bool] = None,
    provider: Optional[str] = None
) -> ScheduledMessageRule:
    """
    Update an existing scheduling rule
    
    Only provided parameters will be updated. Omitted parameters remain unchanged.
    """
    rule = ScheduledMessageRule.query.filter_by(
        id=rule_id,
        business_id=business_id
    ).first()
    
    if not rule:
        raise ValueError(f"Rule {rule_id} not found for business {business_id}")
    
    # Update fields
    if name is not None:
        rule.name = name
    if message_text is not None:
        rule.message_text = message_text
    if delay_minutes is not None:
        if delay_minutes < 1 or delay_minutes > 43200:
            raise ValueError("delay_minutes must be between 1 and 43200 (30 days)")
        rule.delay_minutes = delay_minutes
        # Also update delay_seconds
        rule.delay_seconds = delay_minutes * 60
    if delay_seconds is not None:
        if delay_seconds < 0 or delay_seconds > 2592000:
            raise ValueError("delay_seconds must be between 0 and 2592000 (30 days)")
        rule.delay_seconds = delay_seconds
        # Also update delay_minutes for backward compatibility
        rule.delay_minutes = max(1, delay_seconds // 60)
    if provider is not None:
        if provider not in ("baileys", "meta", "auto"):
            raise ValueError("provider must be 'baileys', 'meta', or 'auto'")
        rule.provider = provider
    if template_name is not None:
        rule.template_name = template_name
    if send_window_start is not None:
        rule.send_window_start = send_window_start
    if send_window_end is not None:
        rule.send_window_end = send_window_end
    if is_active is not None:
        rule.is_active = is_active
    
    # Update status mappings if provided
    if status_ids is not None:
        if not status_ids:
            raise ValueError("At least one status_id is required")
        
        # Verify all status_ids belong to this business
        statuses = LeadStatus.query.filter(
            LeadStatus.id.in_(status_ids),
            LeadStatus.business_id == business_id
        ).all()
        
        if len(statuses) != len(status_ids):
            raise ValueError("One or more status_ids are invalid or don't belong to this business")
        
        # Delete existing mappings
        ScheduledRuleStatus.query.filter_by(rule_id=rule_id).delete()
        
        # Create new mappings
        for status_id in status_ids:
            rule_status = ScheduledRuleStatus(
                rule_id=rule_id,
                status_id=status_id
            )
            db.session.add(rule_status)
    
    rule.updated_at = datetime.utcnow()
    db.session.commit()
    
    logger.info(f"[SCHEDULED-MSG] Updated rule {rule_id} for business {business_id}")
    
    return rule


def delete_rule(rule_id: int, business_id: int) -> bool:
    """
    Delete a scheduling rule
    
    This will cascade delete all rule-status mappings and pending messages.
    """
    rule = ScheduledMessageRule.query.filter_by(
        id=rule_id,
        business_id=business_id
    ).first()
    
    if not rule:
        return False
    
    # Delete rule (cascade will handle related records)
    db.session.delete(rule)
    db.session.commit()
    
    logger.info(f"[SCHEDULED-MSG] Deleted rule {rule_id} for business {business_id}")
    
    return True


def get_rules(business_id: int, is_active: Optional[bool] = None) -> List[ScheduledMessageRule]:
    """
    Get all scheduling rules for a business
    
    Args:
        business_id: Business ID
        is_active: Optional filter by active status
    
    Returns:
        List of ScheduledMessageRule instances
    """
    query = ScheduledMessageRule.query.filter_by(business_id=business_id)
    
    if is_active is not None:
        query = query.filter_by(is_active=is_active)
    
    return query.order_by(ScheduledMessageRule.created_at.desc()).all()


def get_rule(rule_id: int, business_id: int) -> Optional[ScheduledMessageRule]:
    """Get a single rule by ID"""
    return ScheduledMessageRule.query.filter_by(
        id=rule_id,
        business_id=business_id
    ).first()


def schedule_messages_for_lead_status_change(
    business_id: int,
    lead_id: int,
    new_status_id: int,
    old_status_id: Optional[int] = None,
    changed_at: Optional[datetime] = None
):
    """
    Create pending scheduled messages when a lead's status changes
    
    This is the TRIGGER function that should be called whenever a lead status changes.
    It finds all active rules for the new status and creates queue entries.
    
    Args:
        business_id: Business ID for multi-tenant isolation
        lead_id: Lead that changed status
        new_status_id: New status ID
        old_status_id: Previous status ID (optional, for tracking)
        changed_at: When the status changed (defaults to now)
    """
    if changed_at is None:
        changed_at = datetime.utcnow()
    
    # Find all active rules for this business and status
    rules = db.session.query(ScheduledMessageRule).join(
        ScheduledRuleStatus,
        ScheduledMessageRule.id == ScheduledRuleStatus.rule_id
    ).filter(
        ScheduledMessageRule.business_id == business_id,
        ScheduledMessageRule.is_active == True,
        ScheduledRuleStatus.status_id == new_status_id
    ).all()
    
    if not rules:
        logger.debug(f"[SCHEDULED-MSG] No active rules found for business {business_id}, status {new_status_id}")
        return
    
    logger.info(f"[SCHEDULED-MSG] Found {len(rules)} active rule(s) for lead {lead_id}, status {new_status_id}")
    
    # Get lead details with business info for template rendering
    lead = db.session.query(Lead).join(Business).filter(
        Lead.id == lead_id, 
        Lead.business_id == business_id
    ).first()
    
    if not lead:
        logger.error(f"[SCHEDULED-MSG] Lead {lead_id} not found for business {business_id}")
        return
    
    # Get status info for template rendering
    status = db.session.query(LeadStatus).filter_by(id=new_status_id).first()
    status_name = status.name if status else "unknown"
    status_label = status.label if status else "unknown"
    
    # Determine WhatsApp JID
    remote_jid = lead.whatsapp_jid or lead.reply_jid
    if not remote_jid:
        # Try to construct from phone
        if lead.phone_raw:
            # Remove non-digit characters, ensure only digits
            phone_clean = ''.join(c for c in lead.phone_raw if c.isdigit())
            if phone_clean:
                remote_jid = f"{phone_clean}@s.whatsapp.net"
            else:
                logger.warning(f"[SCHEDULED-MSG] Lead {lead_id} phone_raw contains no digits - skipping")
                return
        else:
            logger.warning(f"[SCHEDULED-MSG] Lead {lead_id} has no WhatsApp JID or phone - skipping")
            return
    
    # Create queue entries for each rule
    created_count = 0
    for rule in rules:
        try:
            # Render message template with variables
            message_text = render_message_template(
                template=rule.message_text,
                lead=lead,
                business=lead.business,
                status_name=status_name,
                status_label=status_label
            )
            
            # Calculate scheduled_for time using delay_seconds
            delay_seconds = rule.delay_seconds or (rule.delay_minutes * 60)
            scheduled_for = changed_at + timedelta(seconds=delay_seconds)
            
            # Create dedupe key: lead_status:{lead_id}:{rule_id}:{new_status_id}:{YYYYMMDDHHMM}
            # Using minute-level granularity for deduplication
            dedupe_timestamp = scheduled_for.strftime("%Y%m%d%H%M")
            dedupe_key = f"lead_status:{lead_id}:{rule.id}:{new_status_id}:{dedupe_timestamp}"
            
            # Determine provider (from rule or business default)
            provider = rule.provider or "baileys"
            
            # Try to create queue entry (ON CONFLICT DO NOTHING via dedupe_key)
            queue_entry = ScheduledMessagesQueue(
                business_id=business_id,
                rule_id=rule.id,
                lead_id=lead_id,
                channel='whatsapp',
                provider=provider,
                message_text=message_text,
                remote_jid=remote_jid,
                scheduled_for=scheduled_for,
                status='pending',
                dedupe_key=dedupe_key,
                attempts=0
            )
            
            db.session.add(queue_entry)
            db.session.flush()  # This will raise if dedupe_key exists
            
            created_count += 1
            logger.info(f"[SCHEDULED-MSG] Scheduled message {queue_entry.id} for lead {lead_id}, rule {rule.id}, send at {scheduled_for} via {provider}")
            
        except Exception as e:
            # Likely duplicate key violation - this is expected and OK
            if "duplicate key" in str(e).lower() or "unique constraint" in str(e).lower():
                logger.debug(f"[SCHEDULED-MSG] Message already scheduled for lead {lead_id}, rule {rule.id} - skipping")
                db.session.rollback()
            else:
                logger.error(f"[SCHEDULED-MSG] Error scheduling message for rule {rule.id}: {e}")
                db.session.rollback()
    
    if created_count > 0:
        db.session.commit()
        logger.info(f"[SCHEDULED-MSG] Created {created_count} scheduled message(s) for lead {lead_id}")


def render_message_template(
    template: str,
    lead,
    business,
    status_name: str,
    status_label: str
) -> str:
    """
    Render message template with available variables
    
    Supported variables:
    - {lead_name} - Lead's full name
    - {phone} - Lead's phone number
    - {business_name} - Business name
    - {status} - Status label (user-friendly)
    - {status_name} - Status name (technical)
    
    Args:
        template: Message template with placeholders
        lead: Lead object
        business: Business object
        status_name: Status technical name
        status_label: Status user-friendly label
    
    Returns:
        Rendered message text
    """
    # Build replacement dictionary
    replacements = {
        '{lead_name}': lead.full_name or lead.name or 'Customer',
        '{phone}': lead.phone_e164 or lead.phone_raw or '',
        '{business_name}': business.name if business else '',
        '{status}': status_label,
        '{status_name}': status_name
    }
    
    # Apply replacements
    rendered = template
    for placeholder, value in replacements.items():
        rendered = rendered.replace(placeholder, str(value))
    
    return rendered


def claim_pending_messages(batch_size: int = 50) -> List[ScheduledMessagesQueue]:
    """
    Claim pending messages that are ready to send (atomic operation)
    
    This uses FOR UPDATE SKIP LOCKED to ensure only one worker claims each message.
    
    Args:
        batch_size: Maximum number of messages to claim
    
    Returns:
        List of claimed ScheduledMessagesQueue entries
    """
    now = datetime.utcnow()
    
    # Use raw SQL for FOR UPDATE SKIP LOCKED
    query = text("""
        UPDATE scheduled_messages_queue
        SET locked_at = :now,
            updated_at = :now
        WHERE id IN (
            SELECT id FROM scheduled_messages_queue
            WHERE status = 'pending'
              AND scheduled_for <= :now
              AND locked_at IS NULL
            ORDER BY scheduled_for ASC
            LIMIT :batch_size
            FOR UPDATE SKIP LOCKED
        )
        RETURNING id
    """)
    
    result = db.session.execute(query, {
        'now': now,
        'batch_size': batch_size
    })
    
    claimed_ids = [row[0] for row in result]
    
    if claimed_ids:
        db.session.commit()
        
        # Fetch full objects
        messages = ScheduledMessagesQueue.query.filter(
            ScheduledMessagesQueue.id.in_(claimed_ids)
        ).all()
        
        logger.info(f"[SCHEDULED-MSG] Claimed {len(messages)} message(s) for sending")
        return messages
    
    return []


def mark_sent(message_id: int):
    """Mark a message as successfully sent"""
    message = ScheduledMessagesQueue.query.get(message_id)
    if message:
        message.status = 'sent'
        message.sent_at = datetime.utcnow()
        message.updated_at = datetime.utcnow()
        db.session.commit()
        logger.info(f"[SCHEDULED-MSG] Marked message {message_id} as sent")


def mark_failed(message_id: int, error_message: str):
    """Mark a message as failed with error details"""
    message = ScheduledMessagesQueue.query.get(message_id)
    if message:
        message.status = 'failed'
        message.error_message = error_message[:500]  # Limit error message length
        message.updated_at = datetime.utcnow()
        db.session.commit()
        logger.error(f"[SCHEDULED-MSG] Marked message {message_id} as failed: {error_message}")


def cancel_message(message_id: int, business_id: int) -> bool:
    """
    Cancel a pending message
    
    Args:
        message_id: Message ID to cancel
        business_id: Business ID for authorization
    
    Returns:
        True if cancelled, False if not found or already sent
    """
    message = ScheduledMessagesQueue.query.filter_by(
        id=message_id,
        business_id=business_id
    ).first()
    
    if not message:
        return False
    
    if message.status != 'pending':
        return False
    
    message.status = 'canceled'
    message.updated_at = datetime.utcnow()
    db.session.commit()
    
    logger.info(f"[SCHEDULED-MSG] Cancelled message {message_id}")
    return True


def cancel_pending_for_rule(rule_id: int, business_id: int) -> int:
    """
    Cancel all pending messages for a rule
    
    Args:
        rule_id: Rule ID
        business_id: Business ID for authorization
    
    Returns:
        Number of messages cancelled
    """
    # Verify rule belongs to business
    rule = ScheduledMessageRule.query.filter_by(
        id=rule_id,
        business_id=business_id
    ).first()
    
    if not rule:
        return 0
    
    # Cancel all pending messages for this rule
    result = db.session.query(ScheduledMessagesQueue).filter_by(
        rule_id=rule_id,
        business_id=business_id,
        status='pending'
    ).update({
        'status': 'canceled',
        'updated_at': datetime.utcnow()
    })
    
    db.session.commit()
    
    logger.info(f"[SCHEDULED-MSG] Cancelled {result} pending message(s) for rule {rule_id}")
    return result


def get_queue_messages(
    business_id: int,
    rule_id: Optional[int] = None,
    status: Optional[str] = None,
    page: int = 1,
    per_page: int = 50
) -> Dict:
    """
    Get queue messages with pagination
    
    Args:
        business_id: Business ID
        rule_id: Optional filter by rule
        status: Optional filter by status (pending/sent/failed/canceled)
        page: Page number (1-indexed)
        per_page: Results per page
    
    Returns:
        Dict with 'items', 'total', 'page', 'per_page'
    """
    query = ScheduledMessagesQueue.query.filter_by(business_id=business_id)
    
    if rule_id:
        query = query.filter_by(rule_id=rule_id)
    
    if status:
        query = query.filter_by(status=status)
    
    # Get total count
    total = query.count()
    
    # Get paginated results
    query = query.order_by(ScheduledMessagesQueue.scheduled_for.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    
    items = query.all()
    
    return {
        'items': items,
        'total': total,
        'page': page,
        'per_page': per_page
    }


def get_statistics(business_id: int, rule_id: Optional[int] = None) -> Dict:
    """
    Get statistics for scheduled messages
    
    Args:
        business_id: Business ID
        rule_id: Optional filter by rule
    
    Returns:
        Dict with counts by status
    """
    query = db.session.query(
        ScheduledMessagesQueue.status,
        db.func.count(ScheduledMessagesQueue.id)
    ).filter_by(business_id=business_id)
    
    if rule_id:
        query = query.filter_by(rule_id=rule_id)
    
    query = query.group_by(ScheduledMessagesQueue.status)
    
    results = query.all()
    
    stats = {
        'pending': 0,
        'sent': 0,
        'failed': 0,
        'canceled': 0
    }
    
    for status, count in results:
        stats[status] = count
    
    return stats
