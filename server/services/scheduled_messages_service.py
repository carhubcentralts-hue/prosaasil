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
    ScheduledMessageRuleStep,
    ScheduledRuleStatus,
    ScheduledMessagesQueue,
    LeadStatus,
    Lead,
    Business
)
from server.agent_tools.phone_utils import normalize_phone

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
    delay_seconds: Optional[int] = None,
    send_immediately_on_enter: bool = False,
    immediate_message: Optional[str] = None,
    apply_mode: str = "ON_ENTER_ONLY",
    steps: Optional[List[Dict]] = None,
    active_weekdays: Optional[List[int]] = None,
    excluded_weekdays: Optional[List[int]] = None,
    schedule_type: str = "STATUS_CHANGE",
    recurring_times: Optional[List[str]] = None
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
        send_immediately_on_enter: Send immediate message when lead enters status
        immediate_message: Message to send immediately (if different from message_text)
        apply_mode: When to apply rule ("ON_ENTER_ONLY" | "ON_ENTER_AND_EXISTING")
        steps: Optional list of step dicts with step_index, message_template, delay_seconds
        active_weekdays: Optional list of weekday indices [0-6] where 0=Sunday
        schedule_type: "STATUS_CHANGE" (default) or "RECURRING_TIME"
        recurring_times: Optional list of times in "HH:MM" format for recurring schedules
    
    Returns:
        Created ScheduledMessageRule instance
    """
    # Validate schedule_type
    if schedule_type not in ("STATUS_CHANGE", "RECURRING_TIME"):
        raise ValueError("schedule_type must be 'STATUS_CHANGE' or 'RECURRING_TIME'")
    
    # Validate recurring schedule parameters
    if schedule_type == "RECURRING_TIME":
        if not recurring_times or len(recurring_times) == 0:
            raise ValueError("recurring_times is required when schedule_type is 'RECURRING_TIME'")
        
        # Validate time format
        import re
        time_pattern = re.compile(r'^([0-1][0-9]|2[0-3]):[0-5][0-9]$')
        for time_str in recurring_times:
            if not time_pattern.match(time_str):
                raise ValueError(f"Invalid time format '{time_str}'. Must be 'HH:MM' (e.g., '09:00', '15:30')")
    
    # Determine delay_seconds (prefer delay_seconds over delay_minutes)
    if delay_seconds is None:
        if delay_minutes is None:
            # For recurring schedules, delay is not used
            if schedule_type == "RECURRING_TIME":
                delay_minutes = 0
                delay_seconds = 0
            else:
                raise ValueError("Either delay_minutes or delay_seconds is required for STATUS_CHANGE schedules")
        else:
            delay_seconds = delay_minutes * 60
    
    # Validation for STATUS_CHANGE schedules only
    if schedule_type == "STATUS_CHANGE":
        has_steps = steps and len(steps) > 0
        
        # Validate delay_seconds
        if delay_seconds == 0 and not send_immediately_on_enter and not has_steps:
            raise ValueError("delay_seconds must be at least 1 for STATUS_CHANGE schedules (unless immediate send or steps are enabled)")
        if delay_seconds < 0 or delay_seconds > 2592000:  # 0-30 days
            raise ValueError("delay_seconds must be between 0 and 2592000 (30 days)")
    
        # Set delay_minutes for backward compatibility if not provided (delay_seconds already validated >= 0)
        if delay_minutes is None:
            delay_minutes = delay_seconds // 60
        
        # Validate delay_minutes for backward compatibility
        if not send_immediately_on_enter and not has_steps:
            # Require at least 1 minute for standard STATUS_CHANGE schedules
            if delay_minutes < 1 or delay_minutes > 43200:  # 1 minute to 30 days
                raise ValueError("delay_minutes must be between 1 and 43200 (30 days)")
        else:
            # For immediate sends or steps, allow 0
            if delay_minutes < 0 or delay_minutes > 43200:
                raise ValueError("delay_minutes must be between 0 and 43200 (30 days)")
    else:
        # For RECURRING_TIME schedules, set delay_minutes if not provided
        if delay_minutes is None:
            delay_minutes = delay_seconds // 60
    
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
        provider=provider,
        send_immediately_on_enter=send_immediately_on_enter,
        immediate_message=immediate_message,
        apply_mode=apply_mode,
        active_weekdays=active_weekdays,
        excluded_weekdays=excluded_weekdays,
        schedule_type=schedule_type,
        recurring_times=recurring_times
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
    
    # Create rule steps if provided
    if steps:
        create_rule_steps(rule.id, steps)
    
    db.session.commit()
    logger.info(f"[SCHEDULED-MSG] Created rule {rule.id}: '{name}' (type: {schedule_type}) for business {business_id}")
    
    return rule


def create_rule_steps(rule_id: int, steps: List[Dict]):
    """
    Create ScheduledMessageRuleStep entries for a rule
    
    Args:
        rule_id: Rule ID
        steps: List of dicts with step_index, message_template, delay_seconds
    """
    for step_data in steps:
        step = ScheduledMessageRuleStep(
            rule_id=rule_id,
            step_index=step_data['step_index'],
            message_template=step_data['message_template'],
            delay_seconds=step_data['delay_seconds'],
            enabled=step_data.get('enabled', True)
        )
        db.session.add(step)
    
    db.session.flush()
    logger.info(f"[SCHEDULED-MSG] Created {len(steps)} step(s) for rule {rule_id}")


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
    provider: Optional[str] = None,
    send_immediately_on_enter: Optional[bool] = None,
    immediate_message: Optional[str] = None,
    apply_mode: Optional[str] = None,
    steps: Optional[List[Dict]] = None,
    active_weekdays: Optional[List[int]] = None,
    excluded_weekdays: Optional[List[int]] = None,
    schedule_type: Optional[str] = None,
    recurring_times: Optional[List[str]] = None
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
    
    # Validate schedule_type if provided
    if schedule_type is not None:
        if schedule_type not in ("STATUS_CHANGE", "RECURRING_TIME"):
            raise ValueError("schedule_type must be 'STATUS_CHANGE' or 'RECURRING_TIME'")
        rule.schedule_type = schedule_type
    
    # Validate recurring_times if provided
    if recurring_times is not None:
        if recurring_times:  # Only validate if not empty
            import re
            time_pattern = re.compile(r'^([0-1][0-9]|2[0-3]):[0-5][0-9]$')
            for time_str in recurring_times:
                if not time_pattern.match(time_str):
                    raise ValueError(f"Invalid time format '{time_str}'. Must be 'HH:MM' (e.g., '09:00', '15:30')")
        rule.recurring_times = recurring_times
    
    # Update fields
    if name is not None:
        rule.name = name
    if message_text is not None:
        rule.message_text = message_text
    if delay_minutes is not None:
        # More lenient validation - allow 0 for immediate/recurring, but check schedule_type
        current_schedule_type = rule.schedule_type if hasattr(rule, 'schedule_type') else 'STATUS_CHANGE'
        current_immediate = rule.send_immediately_on_enter if hasattr(rule, 'send_immediately_on_enter') else False
        
        if current_schedule_type == 'RECURRING_TIME' or current_immediate:
            # Allow 0 for recurring schedules or immediate sends
            if delay_minutes < 0 or delay_minutes > 43200:
                raise ValueError("delay_minutes must be between 0 and 43200 (30 days)")
        else:
            # Regular STATUS_CHANGE requires >= 1
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
        rule.delay_minutes = max(0, delay_seconds // 60)
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
    if send_immediately_on_enter is not None:
        rule.send_immediately_on_enter = send_immediately_on_enter
    if immediate_message is not None:
        rule.immediate_message = immediate_message
    if apply_mode is not None:
        rule.apply_mode = apply_mode
    if active_weekdays is not None:
        rule.active_weekdays = active_weekdays
    if excluded_weekdays is not None:
        rule.excluded_weekdays = excluded_weekdays
    
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
    
    # Update steps if provided
    if steps is not None:
        # Delete existing steps
        ScheduledMessageRuleStep.query.filter_by(rule_id=rule_id).delete()
        
        # Create new steps
        if steps:
            create_rule_steps(rule_id, steps)
    
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


def add_rule_step(
    rule_id: int,
    step_index: int,
    message_template: str,
    delay_seconds: int,
    enabled: bool = True
) -> ScheduledMessageRuleStep:
    """
    Add a new step to an existing rule
    
    Args:
        rule_id: Rule ID
        step_index: Order of the step (0-based)
        message_template: Message template for the step
        delay_seconds: Delay in seconds after status change
        enabled: Whether step is active
    
    Returns:
        Created ScheduledMessageRuleStep instance
    """
    step = ScheduledMessageRuleStep(
        rule_id=rule_id,
        step_index=step_index,
        message_template=message_template,
        delay_seconds=delay_seconds,
        enabled=enabled
    )
    
    db.session.add(step)
    db.session.commit()
    
    logger.info(f"[SCHEDULED-MSG] Added step {step.id} to rule {rule_id}")
    
    return step


def update_rule_step(
    step_id: int,
    message_template: Optional[str] = None,
    delay_seconds: Optional[int] = None,
    enabled: Optional[bool] = None
) -> Optional[ScheduledMessageRuleStep]:
    """
    Update an existing rule step
    
    Args:
        step_id: Step ID
        message_template: New message template
        delay_seconds: New delay in seconds
        enabled: New enabled status
    
    Returns:
        Updated ScheduledMessageRuleStep instance or None if not found
    """
    step = ScheduledMessageRuleStep.query.get(step_id)
    
    if not step:
        return None
    
    if message_template is not None:
        step.message_template = message_template
    if delay_seconds is not None:
        step.delay_seconds = delay_seconds
    if enabled is not None:
        step.enabled = enabled
    
    step.updated_at = datetime.utcnow()
    db.session.commit()
    
    logger.info(f"[SCHEDULED-MSG] Updated step {step_id}")
    
    return step


def delete_rule_step(step_id: int) -> bool:
    """
    Delete a rule step
    
    Args:
        step_id: Step ID
    
    Returns:
        True if deleted, False if not found
    """
    step = ScheduledMessageRuleStep.query.get(step_id)
    
    if not step:
        return False
    
    db.session.delete(step)
    db.session.commit()
    
    logger.info(f"[SCHEDULED-MSG] Deleted step {step_id}")
    
    return True


def reorder_rule_steps(rule_id: int, step_ids: List[int]):
    """
    Reorder steps for a rule
    
    Args:
        rule_id: Rule ID
        step_ids: List of step IDs in desired order
    """
    for index, step_id in enumerate(step_ids):
        step = ScheduledMessageRuleStep.query.filter_by(
            id=step_id,
            rule_id=rule_id
        ).first()
        
        if step:
            step.step_index = index
            step.updated_at = datetime.utcnow()
    
    db.session.commit()
    
    logger.info(f"[SCHEDULED-MSG] Reordered {len(step_ids)} steps for rule {rule_id}")


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
    
    🆕 MULTI-STEP SUPPORT:
    - Updates lead.status_sequence_token and status_entered_at
    - Calls create_scheduled_tasks_for_lead for each matching rule
    - Handles both immediate send and multi-step sequences
    
    Args:
        business_id: Business ID for multi-tenant isolation
        lead_id: Lead that changed status
        new_status_id: New status ID
        old_status_id: Previous status ID (optional, for tracking)
        changed_at: When the status changed (defaults to now)
    """
    if changed_at is None:
        changed_at = datetime.utcnow()
    
    # Get lead and increment status_sequence_token
    lead = db.session.query(Lead).filter_by(
        id=lead_id,
        tenant_id=business_id
    ).first()
    
    if not lead:
        logger.error(f"[SCHEDULED-MSG] Lead {lead_id} not found for business {business_id}")
        return
    
    # Update lead's status tracking fields
    lead.status_sequence_token += 1
    lead.status_entered_at = changed_at
    
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
        # Still commit the token update
        db.session.commit()
        return
    
    logger.info(f"[SCHEDULED-MSG] Found {len(rules)} active rule(s) for lead {lead_id}, status {new_status_id}, token {lead.status_sequence_token}")
    
    # Create tasks for each matching rule
    created_count = 0
    for rule in rules:
        try:
            # Create scheduled tasks for this rule and lead
            tasks_created = create_scheduled_tasks_for_lead(
                rule_id=rule.id,
                lead_id=lead_id,
                triggered_at=changed_at
            )
            created_count += tasks_created
            
            logger.info(f"[SCHEDULED-MSG] Created {tasks_created} task(s) for rule {rule.id} ('{rule.name}')")
            
        except Exception as e:
            # Log error but continue with other rules
            logger.error(f"[SCHEDULED-MSG] Failed to create tasks for rule {rule.id}: {e}", exc_info=True)
            db.session.rollback()
    
    # Commit all changes (token update + all tasks)
    try:
        db.session.commit()
        logger.info(f"[SCHEDULED-MSG] Status change trigger complete: {created_count} total task(s) created for lead {lead_id}")
    except Exception as e:
        logger.error(f"[SCHEDULED-MSG] Failed to commit tasks: {e}", exc_info=True)
        db.session.rollback()


def create_scheduled_tasks_for_lead(rule_id: int, lead_id: int, triggered_at: Optional[datetime] = None):
    """
    Create scheduled tasks for a lead based on a rule and its steps
    
    This creates tasks for:
    - Immediate send (if send_immediately_on_enter is True)
    - All enabled steps with their respective delays
    
    Args:
        rule_id: Rule ID
        lead_id: Lead ID
        triggered_at: When the status change was triggered (defaults to now)
    """
    # Get rule
    rule = ScheduledMessageRule.query.get(rule_id)
    if not rule:
        logger.error(f"[SCHEDULED-MSG] Rule {rule_id} not found")
        return 0
    
    # Get lead with business info
    lead = db.session.query(Lead).join(Business).filter(
        Lead.id == lead_id,
        Lead.tenant_id == rule.business_id
    ).first()
    
    if not lead:
        logger.error(f"[SCHEDULED-MSG] Lead {lead_id} not found for business {rule.business_id}")
        return 0
    
    # Get status info
    current_status = db.session.query(LeadStatus).filter_by(
        business_id=rule.business_id,
        name=lead.status
    ).first()
    status_name = current_status.name if current_status else lead.status
    status_label = current_status.label if current_status else lead.status
    
    # Determine WhatsApp JID
    remote_jid = lead.whatsapp_jid or lead.reply_jid
    if not remote_jid:
        # Try to construct JID from phone number (prefer phone_e164, fallback to phone_raw)
        phone_to_use = lead.phone_e164 or lead.phone_raw
        if phone_to_use:
            # Normalize phone to WhatsApp JID format
            # First normalize the phone to E.164 format
            phone_normalized = normalize_phone(phone_to_use)
            if phone_normalized:
                # Extract just the digits from E.164 format (e.g., "+972501234567" -> "972501234567")
                phone_clean = ''.join(c for c in phone_normalized if c.isdigit())
                if phone_clean:
                    remote_jid = f"{phone_clean}@s.whatsapp.net"
                    logger.info(f"[SCHEDULED-MSG] Constructed JID from phone: {phone_to_use} -> {remote_jid}")
                else:
                    logger.warning(f"[SCHEDULED-MSG] Lead {lead_id} phone normalized but contains no digits - skipping")
                    return 0
            else:
                logger.warning(f"[SCHEDULED-MSG] Lead {lead_id} phone could not be normalized: {phone_to_use} - skipping")
                return 0
        else:
            logger.warning(f"[SCHEDULED-MSG] Lead {lead_id} has no WhatsApp JID or phone - skipping")
            return 0
    
    # Use provided triggered_at or default to now
    now = triggered_at if triggered_at is not None else datetime.utcnow()
    created_count = 0
    
    # Helper function to check if a date falls on an active weekday
    def is_active_on_weekday(scheduled_datetime: datetime, active_weekdays: list) -> bool:
        """
        Check if scheduled_datetime falls on an active weekday
        
        Args:
            scheduled_datetime: The datetime to check
            active_weekdays: List of active weekdays (0=Sunday, 1=Monday, ..., 6=Saturday) or None for all days
        
        Returns:
            True if active, False if should skip
        """
        if active_weekdays is None or not isinstance(active_weekdays, list):
            return True  # No restriction - all days active
        
        # Convert Python weekday (0=Monday, 6=Sunday) to our format (0=Sunday, 1=Monday, ..., 6=Saturday)
        python_weekday = scheduled_datetime.weekday()  # 0=Monday, 1=Tuesday, ..., 6=Sunday
        our_weekday = (python_weekday + 1) % 7  # 0=Sunday, 1=Monday, ..., 6=Saturday
        
        return our_weekday in active_weekdays
    
    # Helper function to check if a date falls on an excluded weekday
    def is_excluded_weekday(scheduled_datetime: datetime, excluded_weekdays: list) -> bool:
        """
        Check if scheduled_datetime falls on an excluded weekday
        
        Args:
            scheduled_datetime: The datetime to check
            excluded_weekdays: List of excluded weekdays (0=Sunday, 1=Monday, ..., 6=Saturday) or None for no exclusions
        
        Returns:
            True if excluded (should NOT send), False if allowed
        """
        if excluded_weekdays is None or not isinstance(excluded_weekdays, list) or len(excluded_weekdays) == 0:
            return False  # No exclusions - all days allowed
        
        # Convert Python weekday (0=Monday, 6=Sunday) to our format (0=Sunday, 1=Monday, ..., 6=Saturday)
        python_weekday = scheduled_datetime.weekday()  # 0=Monday, 1=Tuesday, ..., 6=Sunday
        our_weekday = (python_weekday + 1) % 7  # 0=Sunday, 1=Monday, ..., 6=Saturday
        
        return our_weekday in excluded_weekdays
    
    # Create immediate message if enabled
    if rule.send_immediately_on_enter:
        # Check if today is an excluded weekday (for STATUS_CHANGE schedules)
        if rule.schedule_type == 'STATUS_CHANGE' and is_excluded_weekday(now, getattr(rule, 'excluded_weekdays', None)):
            logger.info(f"[SCHEDULED-MSG] Skipping immediate message for lead {lead_id} - excluded weekday")
        # Check if today is an active weekday (for RECURRING_TIME schedules)
        elif not is_active_on_weekday(now, rule.active_weekdays):
            logger.info(f"[SCHEDULED-MSG] Skipping immediate message for lead {lead_id} - not an active weekday")
        else:
            try:
                # Use immediate_message if available, otherwise fall back to message_text
                template = rule.immediate_message if rule.immediate_message else rule.message_text

                message_text = render_message_template(
                    template=template,
                    lead=lead,
                    business=lead.tenant,
                    status_name=status_name,
                    status_label=status_label
                )

                dedupe_key = f"{rule.business_id}:{lead_id}:{rule_id}:0:{lead.status_sequence_token}"

                queue_entry = ScheduledMessagesQueue(
                    business_id=rule.business_id,
                    rule_id=rule.id,
                    lead_id=lead_id,
                    channel='whatsapp',
                    provider=rule.provider or "baileys",
                    message_text=message_text,
                    remote_jid=remote_jid,
                    scheduled_for=now,
                    status='pending',
                    dedupe_key=dedupe_key,
                    attempts=0
                )

                db.session.add(queue_entry)
                db.session.flush()
                created_count += 1
                logger.info(f"[SCHEDULED-MSG] Scheduled immediate message {queue_entry.id} for lead {lead_id}")

            except Exception as e:
                if "duplicate key" in str(e).lower() or "unique constraint" in str(e).lower():
                    logger.debug(f"[SCHEDULED-MSG] Immediate message already scheduled for lead {lead_id} - skipping")
                    db.session.rollback()
                else:
                    logger.error(f"[SCHEDULED-MSG] Error scheduling immediate message: {e}")
                    db.session.rollback()
    
    # Get all enabled steps
    steps = ScheduledMessageRuleStep.query.filter_by(
        rule_id=rule_id,
        enabled=True
    ).order_by(ScheduledMessageRuleStep.step_index).all()
    
    # Create tasks for each step
    for step in steps:
        try:
            message_text = render_message_template(
                template=step.message_template,
                lead=lead,
                business=lead.tenant,
                status_name=status_name,
                status_label=status_label
            )
            
            scheduled_for = now + timedelta(seconds=step.delay_seconds)
            
            # Check if scheduled_for falls on an excluded weekday (for STATUS_CHANGE schedules)
            if rule.schedule_type == 'STATUS_CHANGE' and is_excluded_weekday(scheduled_for, getattr(rule, 'excluded_weekdays', None)):
                logger.info(f"[SCHEDULED-MSG] Skipping step {step.id} for lead {lead_id} - excluded weekday ({scheduled_for.strftime('%A')})")
                continue
            
            # Check if scheduled_for falls on an active weekday (for RECURRING_TIME schedules)
            if not is_active_on_weekday(scheduled_for, rule.active_weekdays):
                logger.info(f"[SCHEDULED-MSG] Skipping step {step.id} for lead {lead_id} - scheduled for inactive weekday ({scheduled_for.strftime('%A')})")
                continue
            
            dedupe_key = f"{rule.business_id}:{lead_id}:{rule_id}:{step.id}:{lead.status_sequence_token}"
            
            queue_entry = ScheduledMessagesQueue(
                business_id=rule.business_id,
                rule_id=rule.id,
                lead_id=lead_id,
                channel='whatsapp',
                provider=rule.provider or "baileys",
                message_text=message_text,
                remote_jid=remote_jid,
                scheduled_for=scheduled_for,
                status='pending',
                dedupe_key=dedupe_key,
                attempts=0
            )
            
            db.session.add(queue_entry)
            db.session.flush()
            created_count += 1
            logger.info(f"[SCHEDULED-MSG] Scheduled step {step.id} message {queue_entry.id} for lead {lead_id}, send at {scheduled_for}")
            
        except Exception as e:
            if "duplicate key" in str(e).lower() or "unique constraint" in str(e).lower():
                logger.debug(f"[SCHEDULED-MSG] Step {step.id} message already scheduled for lead {lead_id} - skipping")
                db.session.rollback()
            else:
                logger.error(f"[SCHEDULED-MSG] Error scheduling step {step.id} message: {e}")
                db.session.rollback()
    
    if created_count > 0:
        db.session.commit()
        logger.info(f"[SCHEDULED-MSG] Created {created_count} scheduled task(s) for lead {lead_id}, rule {rule_id}")
    
    return created_count


def render_message_template(
    template: str,
    lead,
    business,
    status_name: str,
    status_label: str
) -> str:
    """
    Render message template with available variables
    
    Supported variables (English):
    - {lead_name} - Lead's full name
    - {first_name} - Lead's first name only
    - {phone} - Lead's phone number
    - {business_name} - Business name
    - {status} - Status label (user-friendly)
    - {status_name} - Status name (technical)
    
    Supported variables (Hebrew - with double braces):
    - {{שם}} - Lead's full name (same as {lead_name})
    - {{שם פרטי}} - Lead's first name only (same as {first_name})
    - {{טלפון}} - Lead's phone number (same as {phone})
    - {{עסק}} - Business name (same as {business_name})
    - {{סטטוס}} - Status label (same as {status})
    
    Args:
        template: Message template with placeholders
        lead: Lead object
        business: Business object
        status_name: Status technical name
        status_label: Status user-friendly label
    
    Returns:
        Rendered message text
    """
    # Get lead name with fallback
    lead_full_name = lead.full_name or lead.name or 'Customer'
    
    # Extract first name with proper fallbacks
    if lead.first_name:
        lead_first_name = lead.first_name
    elif lead_full_name.strip() and lead_full_name != 'Customer':
        # Try to extract first word from full name
        name_parts = lead_full_name.split()
        lead_first_name = name_parts[0] if name_parts else 'Customer'
    else:
        lead_first_name = 'Customer'
    
    # Build replacement dictionary - English placeholders
    replacements = {
        '{lead_name}': lead_full_name,
        '{first_name}': lead_first_name,
        '{phone}': lead.phone_e164 or lead.phone_raw or '',
        '{business_name}': business.name if business else '',
        '{status}': status_label,
        '{status_name}': status_name
    }
    
    # Hebrew placeholders (with double braces for easier typing)
    hebrew_replacements = {
        '{{שם}}': lead_full_name,
        '{{שם פרטי}}': lead_first_name,
        '{{טלפון}}': lead.phone_e164 or lead.phone_raw or '',
        '{{עסק}}': business.name if business else '',
        '{{סטטוס}}': status_label
    }
    
    # Apply replacements - Hebrew first (to handle {{}} before single {})
    rendered = template
    for placeholder, value in hebrew_replacements.items():
        rendered = rendered.replace(placeholder, str(value))
    
    for placeholder, value in replacements.items():
        rendered = rendered.replace(placeholder, str(value))
    
    return rendered
    
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
    """Mark a message as failed with error details and increment attempts"""
    message = ScheduledMessagesQueue.query.get(message_id)
    if message:
        message.status = 'failed'
        message.error_message = error_message[:500]  # Limit error message length
        # ℹ️ Using getattr for migration compatibility - Migration 122 adds attempts column
        # After migration runs, this becomes message.attempts + 1
        message.attempts = getattr(message, 'attempts', 0) + 1
        message.updated_at = datetime.utcnow()
        db.session.commit()
        logger.error(f"[SCHEDULED-MSG] Marked message {message_id} as failed (attempt {message.attempts}): {error_message}")


def mark_cancelled(message_id: int, reason: str = None):
    """
    Mark a message as cancelled
    
    Args:
        message_id: Message ID to cancel
        reason: Optional cancellation reason
    """
    message = ScheduledMessagesQueue.query.get(message_id)
    if message:
        message.status = 'canceled'  # Note: DB uses 'canceled' (one 'l')
        if reason:
            message.error_message = f"Cancelled: {reason[:480]}"  # Leave room for prefix
        message.updated_at = datetime.utcnow()
        db.session.commit()
        logger.info(f"[SCHEDULED-MSG] Marked message {message_id} as cancelled{': ' + reason if reason else ''}")


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
