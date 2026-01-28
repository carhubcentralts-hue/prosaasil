"""
Reminders Tick Job

This job checks for upcoming reminders and sends push notifications.
Replaces the reminder scheduler thread with proper RQ job scheduling.
"""
import logging
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def reminders_tick_job():
    """
    Check for reminders due in 30 or 15 minutes and send push notifications
    
    This job should be scheduled to run every 1 minute by the scheduler service.
    Uses DB-backed deduplication to prevent duplicate notifications.
    
    This job is idempotent - the check_and_send_reminder_notifications function
    handles deduplication via ReminderPushLog table.
    """
    logger.info("🔔 [REMINDERS_TICK] Starting reminder check")
    
    try:
        from flask import current_app
        from server.services.notifications.reminder_scheduler import check_and_send_reminder_notifications
        
        # Run in app context
        with current_app.app_context():
            # The function already has app context and handles all the logic
            result = check_and_send_reminder_notifications(current_app)
            
            logger.info(f"✅ [REMINDERS_TICK] Completed: {result}")
            return result
            
    except Exception as e:
        # Log but don't fail - DNS errors and transient issues should not crash the job
        logger.warning(f"⚠️ [REMINDERS_TICK] Error (will retry next cycle): {e}")
        # Don't re-raise - let the next scheduled run handle it
        return {'status': 'error', 'error': str(e)}


def reminders_cleanup_job():
    """
    Clean up old reminder push log entries (older than 7 days)
    
    This job should be scheduled to run daily by the scheduler service.
    """
    logger.info("🧹 [REMINDERS_CLEANUP] Starting cleanup")
    
    try:
        from flask import current_app
        from server.db import db
        from server.models_sql import ReminderPushLog
        from sqlalchemy import inspect
        
        with current_app.app_context():
            # Check if table exists
            inspector = inspect(db.engine)
            if 'reminder_push_log' not in inspector.get_table_names():
                logger.info("⚠️ [REMINDERS_CLEANUP] Table does not exist yet, skipping")
                return {'status': 'skipped', 'reason': 'table_not_exists'}
            
            # Delete old entries
            cutoff = datetime.utcnow() - timedelta(days=7)
            deleted = ReminderPushLog.query.filter(
                ReminderPushLog.sent_at < cutoff
            ).delete()
            
            db.session.commit()
            
            logger.info(f"✅ [REMINDERS_CLEANUP] Deleted {deleted} old entries")
            return {'status': 'success', 'deleted': deleted}
            
    except Exception as e:
        logger.error(f"❌ [REMINDERS_CLEANUP] Failed: {e}")
        import traceback
        traceback.print_exc()
        raise  # Re-raise for RQ to handle retry
