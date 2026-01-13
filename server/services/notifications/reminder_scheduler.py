"""
Reminder Push Notification Scheduler

Sends push notifications for upcoming reminders:
- 30 minutes before due time
- 15 minutes before due time

Also handles immediate notifications for urgent events.
"""
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Optional, List, Set

log = logging.getLogger(__name__)

# Configuration constants
INITIAL_DELAY_SECONDS = 30  # Wait before first check after startup
CHECK_INTERVAL_SECONDS = 60  # Check every minute
MAX_NOTIFICATION_CACHE_SIZE = 10000  # Clear cache when it exceeds this size

# Track which reminders have been notified to avoid duplicates
# Key: f"{reminder_id}_{minutes_before}" e.g. "123_30" or "123_15"
_notified_reminders: Set[str] = set()
_notified_lock = threading.Lock()

# Scheduler state
_scheduler_running = False
_scheduler_thread: Optional[threading.Thread] = None


def _get_notification_key(reminder_id: int, minutes_before: int) -> str:
    """Generate unique key for tracking sent notifications"""
    return f"{reminder_id}_{minutes_before}"


def _mark_as_notified(reminder_id: int, minutes_before: int) -> bool:
    """
    Mark a reminder as notified for a specific time window.
    Returns True if this is a new notification, False if already sent.
    """
    key = _get_notification_key(reminder_id, minutes_before)
    with _notified_lock:
        if key in _notified_reminders:
            return False
        _notified_reminders.add(key)
        return True


def _cleanup_old_notifications():
    """Clean up old notification tracking entries (run periodically)"""
    # Keep the set from growing too large - clear when exceeds threshold
    # Since we only track by ID, we can safely clear periodically
    global _notified_reminders
    with _notified_lock:
        if len(_notified_reminders) > MAX_NOTIFICATION_CACHE_SIZE:
            _notified_reminders = set()
            log.info("🧹 Cleared notification tracking cache")


def check_and_send_reminder_notifications(app):
    """
    Check for reminders approaching their due time and send push notifications.
    
    Sends notifications at:
    - 30 minutes before
    - 15 minutes before
    
    Args:
        app: Flask application instance for context
    """
    from server.db import db
    from server.models_sql import LeadReminder, Lead, User
    from server.services.notifications.dispatcher import dispatch_push_for_notification
    
    try:
        with app.app_context():
            now = datetime.utcnow()
            
            # Time windows for notifications
            window_30_start = now + timedelta(minutes=29)
            window_30_end = now + timedelta(minutes=31)
            window_15_start = now + timedelta(minutes=14)
            window_15_end = now + timedelta(minutes=16)
            
            # Query reminders that are due soon (within next 35 minutes)
            # and haven't been completed
            upcoming_reminders = db.session.query(LeadReminder, Lead).outerjoin(
                Lead, LeadReminder.lead_id == Lead.id
            ).filter(
                LeadReminder.completed_at.is_(None),
                LeadReminder.due_at > now,
                LeadReminder.due_at <= now + timedelta(minutes=35)
            ).all()
            
            notifications_sent = 0
            
            for reminder, lead in upcoming_reminders:
                # Skip system notifications - they're sent immediately when created
                if reminder.reminder_type and reminder.reminder_type.startswith('system_'):
                    continue
                
                # Check if due in ~30 minutes
                if window_30_start <= reminder.due_at <= window_30_end:
                    if _mark_as_notified(reminder.id, 30):
                        _send_reminder_push(reminder, lead, 30)
                        notifications_sent += 1
                
                # Check if due in ~15 minutes
                elif window_15_start <= reminder.due_at <= window_15_end:
                    if _mark_as_notified(reminder.id, 15):
                        _send_reminder_push(reminder, lead, 15)
                        notifications_sent += 1
            
            if notifications_sent > 0:
                log.info(f"🔔 Sent {notifications_sent} reminder push notification(s)")
            
            # Periodic cleanup
            _cleanup_old_notifications()
            
    except Exception as e:
        log.error(f"❌ Error in reminder notification scheduler: {e}")
        import traceback
        traceback.print_exc()


def _send_reminder_push(reminder, lead, minutes_before: int):
    """Send a push notification for an upcoming reminder"""
    from server.services.notifications.dispatcher import (
        dispatch_push_for_notification,
        dispatch_push_to_business_owners
    )
    
    try:
        # Build notification content
        if minutes_before == 30:
            title = "⏰ תזכורת בעוד חצי שעה"
            time_text = "30 דקות"
        else:
            title = "⏰ תזכורת בעוד רבע שעה!"
            time_text = "15 דקות"
        
        # Build body with lead name if available
        if lead and lead.full_name:
            body = f"{lead.full_name}: {reminder.note or 'משימה'} - בעוד {time_text}"
        else:
            body = f"{reminder.note or 'משימה'} - בעוד {time_text}"
        
        # Determine URL
        if reminder.lead_id:
            url = f"/app/leads/{reminder.lead_id}?tab=reminders"
        else:
            url = "/app/crm?tab=reminders"
        
        # Get the user to notify (creator or business owners)
        user_id = reminder.created_by
        business_id = reminder.tenant_id
        
        if user_id:
            dispatch_push_for_notification(
                user_id=user_id,
                business_id=business_id,
                notification_type='reminder_approaching',
                title=title,
                body=body,
                url=url,
                entity_id=str(reminder.id),
                tag=f"reminder_{reminder.id}_{minutes_before}"
            )
            log.info(f"📱 Sent {minutes_before}-min reminder push for reminder {reminder.id} to user {user_id}")
        else:
            # No specific user - notify business owners
            dispatch_push_to_business_owners(
                business_id=business_id,
                notification_type='reminder_approaching',
                title=title,
                body=body,
                url=url,
                entity_id=str(reminder.id)
            )
            log.info(f"📱 Sent {minutes_before}-min reminder push for reminder {reminder.id} to business owners")
            
    except Exception as e:
        log.warning(f"⚠️ Failed to send reminder push: {e}")


def start_reminder_scheduler(app):
    """
    Start the background scheduler for reminder notifications.
    
    Args:
        app: Flask application instance
    """
    global _scheduler_running, _scheduler_thread
    
    if _scheduler_running:
        log.warning("Reminder scheduler already running")
        return
    
    def scheduler_loop():
        global _scheduler_running
        log.info("🔔 Reminder notification scheduler started")
        
        # Wait a bit before first check
        time.sleep(INITIAL_DELAY_SECONDS)
        
        while _scheduler_running:
            try:
                check_and_send_reminder_notifications(app)
            except Exception as e:
                log.error(f"Scheduler error: {e}")
            
            # Check at configured interval
            time.sleep(CHECK_INTERVAL_SECONDS)
        
        log.info("🔔 Reminder notification scheduler stopped")
    
    _scheduler_running = True
    _scheduler_thread = threading.Thread(
        target=scheduler_loop,
        daemon=True,
        name="ReminderNotificationScheduler"
    )
    _scheduler_thread.start()
    log.info("🔔 Reminder notification scheduler thread started")


def stop_reminder_scheduler():
    """Stop the reminder scheduler"""
    global _scheduler_running
    _scheduler_running = False
    log.info("🔔 Reminder scheduler stop requested")
