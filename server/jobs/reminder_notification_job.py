"""
Reminder Notification Job
Periodic task to send push notifications for upcoming reminders

This replaces the reminder scheduler thread in reminder_scheduler.py
Schedule: Every 1 minute (checks for 30min and 15min before reminders)
"""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def send_reminder_notifications_job(business_id: int = None):
    """
    Check for upcoming reminders and send push notifications.
    
    Sends notifications at:
    - 30 minutes before reminder time
    - 15 minutes before reminder time
    
    Args:
        business_id: Optional business ID to process (None = all businesses)
    
    Returns:
        dict: Summary of notification operation
    """
    from server.services.notifications.reminder_scheduler import process_pending_reminders
    
    logger.info(f"[REMINDER-JOB] Starting reminder notification processing (business_id={business_id})")
    
    try:
        # Process pending reminders
        result = process_pending_reminders(business_id=business_id)
        
        logger.info(f"[REMINDER-JOB] ✅ Processing completed: {result}")
        return {
            'status': 'success',
            'result': result,
            'business_id': business_id,
            'timestamp': datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"[REMINDER-JOB] ❌ Processing failed: {e}", exc_info=True)
        return {
            'status': 'failed',
            'error': str(e),
            'business_id': business_id,
            'timestamp': datetime.utcnow().isoformat()
        }
