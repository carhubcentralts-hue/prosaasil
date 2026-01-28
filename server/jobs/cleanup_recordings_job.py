"""
Recording Cleanup Job
Scheduled task to clean up old recordings (7+ days old)

This replaces the cleanup_thread in app_factory.py
Schedule: Daily at 3 AM or via periodic worker job
"""
import logging
from datetime import datetime, timedelta
from server.models_sql import db, CallLog

logger = logging.getLogger(__name__)


def cleanup_old_recordings_job(retention_days: int = 7, dry_run: bool = False):
    """
    Clean up recordings older than retention_days.
    
    Args:
        retention_days: Number of days to retain recordings (default: 7)
        dry_run: If True, only log what would be deleted without deleting
    
    Returns:
        dict: Summary of cleanup operation
    """
    from server.tasks_recording import auto_cleanup_old_recordings
    
    logger.info(f"[CLEANUP-JOB] Starting recording cleanup (retention={retention_days} days, dry_run={dry_run})")
    
    try:
        # Call existing cleanup function
        result = auto_cleanup_old_recordings(retention_days=retention_days, dry_run=dry_run)
        
        logger.info(f"[CLEANUP-JOB] ✅ Cleanup completed: {result}")
        return {
            'status': 'success',
            'result': result,
            'timestamp': datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"[CLEANUP-JOB] ❌ Cleanup failed: {e}", exc_info=True)
        return {
            'status': 'failed',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }
