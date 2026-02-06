"""
Appointment Automation Service
Manages automated WhatsApp confirmations based on appointment status changes

🎯 KEY FEATURES:
- Status-based triggers: Send messages when appointments enter specific statuses
- Flexible timing: before/after/immediate relative to appointment time
- Template support: Custom messages with placeholders
- Deduplication: Prevent duplicate sends
- Cancellation: Auto-cancel when appointment status changes out

⏰ TIMEZONE STRATEGY:
- All datetimes in this system are NAIVE and represent Israel local time (Asia/Jerusalem)
- Database stores naive datetimes (no timezone info) - treat as Israel time
- Use datetime.now() for current time (NOT datetime.utcnow() which returns UTC)
- Offset calculations preserve the exact hour (e.g., "1 day before" = exactly 24 hours)
- Example: Meeting at 18:30 today → "day before" trigger = yesterday at 18:30

⚠️ USAGE:
    from server.services.appointment_automation_service import (
        schedule_automation_jobs,
        cancel_automation_jobs,
        process_automation_triggers
    )
    
    # Schedule jobs when appointment created/updated
    schedule_automation_jobs(appointment_id, business_id)
    
    # Cancel jobs when appointment status changes out
    cancel_automation_jobs(appointment_id, business_id, old_status)
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from sqlalchemy import and_, or_
from server.db import db
from server.models_sql import (
    Appointment, 
    AppointmentAutomation, 
    AppointmentAutomationRun,
    Business,
    Lead,
    Customer
)
from server.services.jobs import enqueue
from server.jobs.send_appointment_confirmation_job import send_appointment_confirmation

logger = logging.getLogger(__name__)


def get_active_automations(
    business_id: int, 
    status_value: str,
    calendar_id: Optional[int] = None,
    appointment_type: Optional[str] = None
) -> List[AppointmentAutomation]:
    """
    Get all active automations that match appointment criteria.
    
    Args:
        business_id: Business ID
        status_value: Appointment status value (e.g., "scheduled", "confirmed")
        calendar_id: Optional calendar ID to filter by
        appointment_type: Optional appointment type key to filter by
    
    Returns:
        List of active AppointmentAutomation records that match all criteria
    """
    try:
        automations = AppointmentAutomation.query.filter(
            AppointmentAutomation.business_id == business_id,
            AppointmentAutomation.enabled.is_(True)
        ).all()
        
        logger.info(f"🔍 Found {len(automations)} active automations for business {business_id}")
        
        # Filter by multiple criteria
        matching = []
        for automation in automations:
            # Check status
            trigger_statuses = automation.trigger_status_ids or []
            logger.info(f"🔍 Automation {automation.id}: trigger_statuses={trigger_statuses}, looking for status_value='{status_value}'")
            if status_value not in trigger_statuses:
                logger.info(f"  ❌ Status mismatch")
                continue
            logger.info(f"  ✅ Status match!")
            logger.info(f"  ✅ Status match!")
            
            # Check calendar filter (null = all calendars)
            if automation.calendar_ids is not None and len(automation.calendar_ids) > 0:
                logger.info(f"  🔍 Calendar filter: automation.calendar_ids={automation.calendar_ids}, appointment calendar_id={calendar_id}")
                if calendar_id is None or calendar_id not in automation.calendar_ids:
                    logger.info(f"  ❌ Calendar mismatch")
                    continue
                logger.info(f"  ✅ Calendar match!")
            else:
                logger.info(f"  ℹ️  No calendar filter (applies to all)")
            
            # Check appointment type filter (null = all types)
            if automation.appointment_type_keys is not None and len(automation.appointment_type_keys) > 0:
                logger.info(f"  🔍 Type filter: automation.appointment_type_keys={automation.appointment_type_keys}, appointment type={appointment_type}")
                if appointment_type is None or appointment_type not in automation.appointment_type_keys:
                    logger.info(f"  ❌ Type mismatch")
                    continue
                logger.info(f"  ✅ Type match!")
            else:
                logger.info(f"  ℹ️  No type filter (applies to all)")
            
            logger.info(f"  🎯 Automation {automation.id} '{automation.name}' MATCHES!")
            matching.append(automation)
        
        logger.info(f"🎯 Returning {len(matching)} matching automations")
        return matching
    except Exception as e:
        logger.error(f"Error getting active automations for business {business_id}: {e}", exc_info=True)
        return []


def calculate_scheduled_time(
    appointment_start_time: datetime,
    offset_config: Dict[str, Any]
) -> Optional[datetime]:
    """
    Calculate when to send a message based on offset configuration.
    
    Args:
        appointment_start_time: Appointment start time
        offset_config: Offset configuration dict with 'type' and 'minutes'
                      e.g., {"type": "before", "minutes": 1440}
    
    Returns:
        Datetime when message should be sent, or None for immediate
    """
    offset_type = offset_config.get('type')
    minutes = offset_config.get('minutes', 0)
    
    if offset_type == 'immediate':
        return datetime.now()  # Naive Israel time (matches DB storage)
    elif offset_type == 'before':
        return appointment_start_time - timedelta(minutes=minutes)
    elif offset_type == 'after':
        return appointment_start_time + timedelta(minutes=minutes)
    else:
        logger.warning(f"Unknown offset type: {offset_type}")
        return None


def create_offset_signature(offset_config: Dict[str, Any]) -> str:
    """
    Create a unique signature for an offset configuration.
    Used for deduplication.
    
    Args:
        offset_config: Offset configuration dict
    
    Returns:
        String signature (e.g., "before_1440", "after_1440", "immediate")
    """
    offset_type = offset_config.get('type', 'unknown')
    minutes = offset_config.get('minutes', 0)
    
    if offset_type == 'immediate':
        return 'immediate'
    else:
        return f"{offset_type}_{minutes}"


def schedule_automation_jobs(
    appointment_id: int,
    business_id: int,
    force_reschedule: bool = False
) -> Dict[str, Any]:
    """
    Schedule automation jobs for an appointment based on its current status.
    
    This function:
    1. Finds all active automations that match the appointment's status
    2. Creates or updates automation runs for each offset
    3. Schedules jobs to send messages at the calculated times
    
    Args:
        appointment_id: Appointment ID
        business_id: Business ID
        force_reschedule: If True, reschedule even if runs already exist
    
    Returns:
        Dict with scheduling results and statistics
    """
    try:
        # Get appointment
        appointment = Appointment.query.filter_by(
            id=appointment_id,
            business_id=business_id
        ).first()
        
        if not appointment:
            logger.warning(f"Appointment {appointment_id} not found for business {business_id}")
            return {'error': 'Appointment not found', 'scheduled': 0}
        
        # Validate appointment has valid ID before creating runs
        if not appointment.id:
            logger.error(f"Appointment has no ID - skipping automation scheduling")
            return {'error': 'Invalid appointment ID', 'scheduled': 0}
        
        # Get active automations for this appointment's status, calendar, and type
        automations = get_active_automations(
            business_id, 
            appointment.status,
            calendar_id=appointment.calendar_id,
            appointment_type=appointment.appointment_type
        )
        
        if not automations:
            logger.debug(f"No active automations for status '{appointment.status}' in business {business_id}")
            return {'scheduled': 0, 'message': 'No matching automations'}
        
        scheduled_count = 0
        updated_count = 0
        skipped_count = 0
        
        for automation in automations:
            schedule_offsets = automation.schedule_offsets or []
            
            for offset_config in schedule_offsets:
                # Calculate when to send
                scheduled_for = calculate_scheduled_time(appointment.start_time, offset_config)
                
                if scheduled_for is None:
                    logger.warning(f"Could not calculate scheduled time for offset: {offset_config}")
                    continue
                
                # Check if scheduled_for falls on an active weekday
                if automation.active_weekdays is not None and isinstance(automation.active_weekdays, list):
                    # Convert Python weekday (0=Monday, 6=Sunday) to our format (0=Sunday, 1=Monday, ..., 6=Saturday)
                    python_weekday = scheduled_for.weekday()  # 0=Monday, 1=Tuesday, ..., 6=Sunday
                    our_weekday = (python_weekday + 1) % 7  # 0=Sunday, 1=Monday, ..., 6=Saturday
                    
                    if our_weekday not in automation.active_weekdays:
                        logger.info(f"Skipping automation {automation.id} for {scheduled_for.strftime('%A')} - not an active weekday")
                        skipped_count += 1
                        continue
                
                # Create offset signature for deduplication
                offset_sig = create_offset_signature(offset_config)
                
                # Check if run already exists
                existing_run = AppointmentAutomationRun.query.filter_by(
                    business_id=business_id,
                    appointment_id=appointment_id,
                    automation_id=automation.id,
                    offset_signature=offset_sig
                ).first()
                
                if existing_run:
                    if force_reschedule and existing_run.status == 'pending':
                        # Update scheduled_for time
                        existing_run.scheduled_for = scheduled_for
                        db.session.add(existing_run)
                        updated_count += 1
                        logger.info(f"Updated automation run {existing_run.id} to new time: {scheduled_for}")
                    else:
                        skipped_count += 1
                        logger.debug(f"Automation run already exists with status {existing_run.status}")
                    continue
                
                # Create new automation run
                run = AppointmentAutomationRun(
                    business_id=business_id,
                    appointment_id=appointment_id,
                    automation_id=automation.id,
                    offset_signature=offset_sig,
                    scheduled_for=scheduled_for,
                    status='pending'
                )
                db.session.add(run)
                db.session.flush()  # Get the run ID
                
                # Schedule job to send message
                # For immediate sends, execute right away
                if offset_config.get('type') == 'immediate':
                    enqueue(
                        'default',
                        send_appointment_confirmation,
                        run_id=run.id,
                        business_id=business_id
                    )
                else:
                    # Schedule for future execution
                    enqueue(
                        'default',
                        send_appointment_confirmation,
                        run_id=run.id,
                        business_id=business_id,
                        scheduled_for=scheduled_for
                    )
                
                scheduled_count += 1
                logger.info(f"Scheduled automation run {run.id} for {scheduled_for} (offset: {offset_sig})")
        
        db.session.commit()
        
        return {
            'scheduled': scheduled_count,
            'updated': updated_count,
            'skipped': skipped_count,
            'automations_matched': len(automations)
        }
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error scheduling automation jobs for appointment {appointment_id}: {e}", exc_info=True)
        return {'error': str(e), 'scheduled': 0}


def cancel_automation_jobs(
    appointment_id: int,
    business_id: int,
    old_status: Optional[str] = None
) -> Dict[str, Any]:
    """
    Cancel pending automation jobs for an appointment.
    
    This is called when:
    - Appointment status changes out of a trigger status
    - Appointment is deleted
    - Appointment is manually cancelled
    
    Args:
        appointment_id: Appointment ID
        business_id: Business ID
        old_status: Previous status (if available)
    
    Returns:
        Dict with cancellation results
    """
    try:
        # Find all pending runs for this appointment
        pending_runs = AppointmentAutomationRun.query.filter_by(
            business_id=business_id,
            appointment_id=appointment_id,
            status='pending'
        ).all()
        
        if not pending_runs:
            return {'canceled': 0, 'message': 'No pending runs to cancel'}
        
        canceled_count = 0
        
        for run in pending_runs:
            # Check if automation has cancel_on_status_exit enabled
            automation = AppointmentAutomation.query.get(run.automation_id)
            
            if automation and automation.cancel_on_status_exit:
                run.status = 'canceled'
                run.canceled_at = datetime.now()  # Naive Israel time (matches DB storage)
                db.session.add(run)
                canceled_count += 1
                logger.info(f"Canceled automation run {run.id} for appointment {appointment_id}")
        
        db.session.commit()
        
        return {
            'canceled': canceled_count,
            'total_pending': len(pending_runs)
        }
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error canceling automation jobs for appointment {appointment_id}: {e}", exc_info=True)
        return {'error': str(e), 'canceled': 0}


def process_appointment_status_change(
    appointment_id: int,
    business_id: int,
    old_status: str,
    new_status: str
) -> Dict[str, Any]:
    """
    Process automation triggers when appointment status changes.
    
    This function:
    1. Cancels pending jobs if old status had triggers
    2. Schedules new jobs if new status has triggers
    
    Args:
        appointment_id: Appointment ID
        business_id: Business ID
        old_status: Previous status
        new_status: New status
    
    Returns:
        Dict with processing results
    """
    results = {
        'canceled': 0,
        'scheduled': 0,
        'old_status': old_status,
        'new_status': new_status
    }
    
    try:
        # Cancel jobs for old status
        if old_status != new_status:
            cancel_result = cancel_automation_jobs(
                appointment_id=appointment_id,
                business_id=business_id,
                old_status=old_status
            )
            results['canceled'] = cancel_result.get('canceled', 0)
        
        # Schedule jobs for new status
        schedule_result = schedule_automation_jobs(
            appointment_id=appointment_id,
            business_id=business_id,
            force_reschedule=False
        )
        results['scheduled'] = schedule_result.get('scheduled', 0)
        results['updated'] = schedule_result.get('updated', 0)
        
        return results
        
    except Exception as e:
        logger.error(f"Error processing status change for appointment {appointment_id}: {e}", exc_info=True)
        return {'error': str(e), **results}


def get_pending_automation_runs(limit: int = 100) -> List[AppointmentAutomationRun]:
    """
    Get pending automation runs that are due to be executed.
    
    Args:
        limit: Maximum number of runs to return
    
    Returns:
        List of AppointmentAutomationRun records
    """
    try:
        now = datetime.now()  # Naive Israel time (matches DB storage)
        
        runs = AppointmentAutomationRun.query.filter(
            AppointmentAutomationRun.status == 'pending',
            AppointmentAutomationRun.scheduled_for <= now
        ).limit(limit).all()
        
        return runs
        
    except Exception as e:
        logger.error(f"Error getting pending automation runs: {e}", exc_info=True)
        return []
