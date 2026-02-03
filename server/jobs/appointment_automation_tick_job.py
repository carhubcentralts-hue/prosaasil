"""
Appointment Automation Tick Job
Periodic job that checks for pending automation runs and enqueues send jobs

🎯 RESPONSIBILITIES:
- Query for pending runs that are due (scheduled_for <= now)
- Enqueue send_appointment_confirmation jobs for each run
- Run periodically via scheduler (e.g., every 1-5 minutes)

⚠️ USAGE:
    from server.jobs.appointment_automation_tick_job import appointment_automation_tick
    from server.services.jobs import enqueue
    
    # Schedule to run every 1 minute
    enqueue('default', appointment_automation_tick, schedule_interval='*/1 * * * *')
"""
import logging
from datetime import datetime
from server.services.appointment_automation_service import get_pending_automation_runs
from server.services.jobs import enqueue

logger = logging.getLogger(__name__)


def appointment_automation_tick():
    """
    Check for pending automation runs and enqueue send jobs.
    
    This job should run periodically (e.g., every 1-5 minutes) to process
    automation runs that are due to be sent.
    
    Returns:
        Dict with processing statistics
    """
    try:
        logger.info("[AUTOMATION_TICK] Starting appointment automation tick...")
        
        # Get pending runs that are due
        pending_runs = get_pending_automation_runs(limit=100)
        
        if not pending_runs:
            logger.debug("[AUTOMATION_TICK] No pending runs to process")
            return {
                'success': True,
                'processed': 0,
                'message': 'No pending runs'
            }
        
        logger.info(f"[AUTOMATION_TICK] Found {len(pending_runs)} pending runs to process")
        
        # Enqueue send job for each run
        enqueued_count = 0
        error_count = 0
        
        for run in pending_runs:
            try:
                # Enqueue send job
                enqueue(
                    'default',
                    'server.jobs.send_appointment_confirmation_job.send_appointment_confirmation',
                    run_id=run.id,
                    business_id=run.business_id
                )
                
                enqueued_count += 1
                logger.debug(f"[AUTOMATION_TICK] Enqueued job for run {run.id}")
                
            except Exception as e:
                error_count += 1
                logger.error(f"[AUTOMATION_TICK] Failed to enqueue job for run {run.id}: {e}")
        
        logger.info(f"[AUTOMATION_TICK] Completed: {enqueued_count} enqueued, {error_count} errors")
        
        return {
            'success': True,
            'processed': enqueued_count,
            'errors': error_count,
            'total_pending': len(pending_runs)
        }
        
    except Exception as e:
        logger.error(f"[AUTOMATION_TICK] Error in automation tick: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'processed': 0
        }


if __name__ == '__main__':
    # For testing
    result = appointment_automation_tick()
    print(f"Tick result: {result}")
