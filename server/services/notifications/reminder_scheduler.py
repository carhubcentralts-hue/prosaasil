"""
Reminder Push Notification Scheduler

Sends push notifications for upcoming reminders:
- 30 minutes before due time
- 15 minutes before due time

Uses DB-backed deduplication to work correctly with multiple workers/replicas.
"""
import logging
import socket
import threading
import time
from datetime import datetime, timedelta
from typing import Optional

log = logging.getLogger(__name__)

# Configuration constants
INITIAL_DELAY_SECONDS = 30  # Wait before first check after startup
CHECK_INTERVAL_SECONDS = 60  # Check every minute
CLEANUP_DAYS = 7  # Clean up push log entries older than this

# Scheduler state
_scheduler_running = False
_scheduler_thread: Optional[threading.Thread] = None


def _log_error_with_rate_limit(error_type: str, message: str, rate_limit: int = 5) -> None:
    """
    Log an error message with rate limiting to prevent log spam.
    
    Args:
        error_type: Type of error (used as counter key)
        message: Error message to log
        rate_limit: Log only every N occurrences
    """
    counter_attr = f'_error_count_{error_type}'
    
    if not hasattr(_log_error_with_rate_limit, counter_attr):
        setattr(_log_error_with_rate_limit, counter_attr, 0)
    
    count = getattr(_log_error_with_rate_limit, counter_attr) + 1
    setattr(_log_error_with_rate_limit, counter_attr, count)
    
    # Log only every N failures to prevent spam
    if count % rate_limit == 1:
        log.warning(f"[REMINDER_SCHEDULER] {message} (count={count})")


def _is_dns_error(exc: Exception) -> bool:
    """
    Check if an exception is caused by DNS resolution failure.
    
    DNS errors can manifest as:
    - OperationalError with "could not translate host name" message
    - OperationalError with "Name or service not known" message
    - socket.gaierror (explicit DNS failure)
    
    Args:
        exc: Exception to check
        
    Returns:
        True if this is a DNS-related error
    """
    # Check if this is a socket.gaierror directly
    if isinstance(exc, socket.gaierror):
        return True
    
    # Check error message for DNS-related strings
    msg = str(exc).lower()
    return ("could not translate host name" in msg or 
            "name or service not known" in msg or
            "temporary failure in name resolution" in msg)


def _try_send_with_dedupe(db, reminder, lead, offset_minutes: int) -> bool:
    """
    Try to send a reminder push with DB-backed deduplication.
    
    Flow:
    1. INSERT log entry (atomic claim)
    2. If INSERT fails (unique constraint) -> already sent, return False
    3. Try to send push
    4. If send fails -> DELETE log entry to allow retry, return False
    5. If send succeeds -> keep log entry, return True
    
    Returns True if notification was sent successfully.
    """
    from server.models_sql import ReminderPushLog
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy import inspect
    
    # 🔒 SAFETY CHECK: Verify table exists before attempting operations
    # This prevents "relation does not exist" errors during startup
    try:
        inspector = inspect(db.engine)
        if 'reminder_push_log' not in inspector.get_table_names():
            log.debug("reminder_push_log table does not exist yet, sending without deduplication")
            # Table doesn't exist yet - send without deduplication (one-time during migration)
            try:
                _send_reminder_push(reminder, lead, offset_minutes)
                return True
            except Exception as e:
                log.warning(f"⚠️ Push send failed (no deduplication available): {e}")
                return False
    except Exception as e:
        log.warning(f"Error checking table existence: {e}")
        # On error, proceed with normal flow (will fail if table doesn't exist)
    
    # Step 1: Try to claim this notification slot
    try:
        log_entry = ReminderPushLog(
            reminder_id=reminder.id,
            offset_minutes=offset_minutes,
            # 🔥 FIX: Use local time for consistency
            sent_at=datetime.now()
        )
        db.session.add(log_entry)
        db.session.commit()
    except IntegrityError:
        # Already sent by another worker
        db.session.rollback()
        return False
    except Exception as e:
        db.session.rollback()
        log.warning(f"Error claiming push log slot: {e}")
        return False
    
    # Step 2: Try to send the notification
    try:
        _send_reminder_push(reminder, lead, offset_minutes)
        return True
    except Exception as e:
        # Send failed - delete log entry to allow retry on next cycle
        log.warning(f"⚠️ Push send failed, removing log entry for retry: {e}")
        try:
            ReminderPushLog.query.filter_by(
                reminder_id=reminder.id,
                offset_minutes=offset_minutes
            ).delete()
            db.session.commit()
        except Exception as del_err:
            db.session.rollback()
            log.error(f"Failed to delete log entry for retry: {del_err}")
        return False


def _cleanup_old_push_logs(db):
    """Clean up old push log entries to prevent table from growing too large"""
    from server.models_sql import ReminderPushLog
    from sqlalchemy import text, inspect
    
    try:
        # 🔒 SAFETY CHECK: Verify table exists before attempting cleanup
        # This prevents "relation does not exist" errors during startup
        inspector = inspect(db.engine)
        if 'reminder_push_log' not in inspector.get_table_names():
            log.debug("reminder_push_log table does not exist yet, skipping cleanup")
            return
        
        # 🔥 FIX: Use local time for consistency
        cutoff = datetime.now() - timedelta(days=CLEANUP_DAYS)
        deleted = ReminderPushLog.query.filter(
            ReminderPushLog.sent_at < cutoff
        ).delete(synchronize_session=False)
        db.session.commit()
        if deleted > 0:
            log.info(f"🧹 Cleaned up {deleted} old push log entries")
    except Exception as e:
        db.session.rollback()
        log.warning(f"Error cleaning up push logs: {e}")


def check_and_send_reminder_notifications(app):
    """
    Check for reminders approaching their due time and send push notifications.
    
    Sends notifications at:
    - 30 minutes before
    - 15 minutes before
    - 5 minutes before
    
    Uses DB-backed deduplication to prevent duplicate sends across workers.
    Implements retry logic with exponential backoff for transient DNS/connection failures.
    
    Args:
        app: Flask application instance for context
    """
    from server.db import db
    from server.models_sql import LeadReminder, Lead
    from sqlalchemy.exc import OperationalError
    
    # 🔥 DNS RESILIENCE: Retry with exponential backoff on transient DNS failures
    # Backoff: 30s, 60s, 120s (max 3 attempts)
    max_attempts = 3
    backoff_times = [30, 60, 120]  # seconds
    
    for attempt in range(max_attempts):
        try:
            with app.app_context():
                # 🔥 FIX: Use local Israel time instead of UTC
                # Since reminders are stored as naive datetime in local Israel time,
                # we must compare against local time, not UTC
                now = datetime.now()  # Local Israel time (naive datetime)
                
                # Time windows for notifications (with tolerance for drift)
                window_30_start = now + timedelta(minutes=29)
                window_30_end = now + timedelta(minutes=31)
                window_15_start = now + timedelta(minutes=14)
                window_15_end = now + timedelta(minutes=16)
                window_5_start = now + timedelta(minutes=4)
                window_5_end = now + timedelta(minutes=6)
                
                # Query reminders that are due soon (within next 35 minutes)
                # and haven't been completed - limited scope for efficiency
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
                        # DB-backed deduplication with retry on failure
                        if _try_send_with_dedupe(db, reminder, lead, 30):
                            notifications_sent += 1
                    
                    # Check if due in ~15 minutes
                    elif window_15_start <= reminder.due_at <= window_15_end:
                        # DB-backed deduplication with retry on failure
                        if _try_send_with_dedupe(db, reminder, lead, 15):
                            notifications_sent += 1
                    
                    # Check if due in ~5 minutes
                    elif window_5_start <= reminder.due_at <= window_5_end:
                        # DB-backed deduplication with retry on failure
                        if _try_send_with_dedupe(db, reminder, lead, 5):
                            notifications_sent += 1
                
                if notifications_sent > 0:
                    log.info(f"🔔 Sent {notifications_sent} reminder push notification(s)")
                
                # Periodic cleanup of old log entries
                _cleanup_old_push_logs(db)
                
                # Success - exit retry loop
                return
                
        except OperationalError as e:
            # 🔥 DNS RESILIENCE: Handle transient DNS failures gracefully with backoff
            if _is_dns_error(e) and attempt < max_attempts - 1:
                # Graduated backoff: 30s, 60s
                sleep_time = backoff_times[attempt]
                # Only log WARNING on first failure, DEBUG on subsequent
                if attempt == 0:
                    log.warning(f"[REMINDER_SCHEDULER] DB DNS error (attempt {attempt + 1}/{max_attempts}), retry in {sleep_time}s")
                else:
                    log.debug(f"[REMINDER_SCHEDULER] DB DNS error (attempt {attempt + 1}/{max_attempts}), retry in {sleep_time}s: {e}")
                time.sleep(sleep_time)
                continue
            # Last attempt failed or non-DNS error - use rate-limited logging
            _log_error_with_rate_limit('operational', f"DB unavailable: {str(e)[:100]}")
            return
            
        except socket.gaierror as e:
            # 🔥 DNS RESILIENCE: Explicit DNS error - use same backoff logic
            if attempt < max_attempts - 1:
                # Graduated backoff: 30s, 60s
                sleep_time = backoff_times[attempt]
                if attempt == 0:
                    log.warning(f"[REMINDER_SCHEDULER] DNS failure (attempt {attempt + 1}/{max_attempts}), retry in {sleep_time}s")
                else:
                    log.debug(f"[REMINDER_SCHEDULER] DNS failure (attempt {attempt + 1}/{max_attempts}), retry in {sleep_time}s: {e}")
                time.sleep(sleep_time)
                continue
            # Last attempt failed - use rate-limited logging
            _log_error_with_rate_limit('dns', f"DNS failure after retries: {str(e)[:100]}")
            return
            
        except Exception as e:
            # Unexpected error - check if it's DNS-related before logging full traceback
            if _is_dns_error(e):
                # DNS-related - use rate-limited logging
                _log_error_with_rate_limit('generic_dns', f"DB connection issue: {str(e)[:100]}")
            else:
                # Truly unexpected error - log with full traceback (but only in DEBUG mode)
                if log.isEnabledFor(logging.DEBUG):
                    log.error(f"❌ Error in reminder notification scheduler: {e}", exc_info=True)
                else:
                    # Production: log without traceback
                    log.error(f"❌ Reminder scheduler error: {str(e)[:200]}")
            return


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
        elif minutes_before == 15:
            title = "⏰ תזכורת בעוד רבע שעה!"
            time_text = "15 דקות"
        elif minutes_before == 5:
            title = "🔔 תזכורת בעוד 5 דקות!"
            time_text = "5 דקות"
        else:
            title = f"⏰ תזכורת בעוד {minutes_before} דקות"
            time_text = f"{minutes_before} דקות"
        
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
