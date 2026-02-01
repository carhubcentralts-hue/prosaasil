"""
Scheduled Messages Tick Job
Runs every minute to check for pending WhatsApp messages and enqueue them for sending
"""
import logging
from server.services import scheduled_messages_service
from server.services.jobs import enqueue

logger = logging.getLogger(__name__)


def scheduled_messages_tick_job():
    """
    Scheduler job that runs every minute to process pending scheduled messages
    
    This job:
    1. Claims pending messages that are ready to send (scheduled_for <= now)
    2. Enqueues each message to the send_scheduled_whatsapp_job worker
    
    Uses atomic claim operation with FOR UPDATE SKIP LOCKED to prevent duplicates.
    """
    logger.info("[SCHEDULED-MSG-TICK] Starting scheduled messages tick")
    
    try:
        # Claim up to 100 pending messages
        messages = scheduled_messages_service.claim_pending_messages(batch_size=100)
        
        if not messages:
            logger.debug("[SCHEDULED-MSG-TICK] No messages ready to send")
            return {
                'status': 'success',
                'claimed': 0,
                'enqueued': 0
            }
        
        logger.info(f"[SCHEDULED-MSG-TICK] ✅ Claimed {len(messages)} message(s) ready to send")
        
        # Enqueue each message to worker
        enqueued_count = 0
        failed_count = 0
        for message in messages:
            try:
                # Import the job function
                from server.jobs.send_scheduled_whatsapp_job import send_scheduled_whatsapp_job
                
                logger.info(f"[SCHEDULED-MSG-TICK] Enqueuing message {message.id} for lead {message.lead_id}, business {message.business_id}")
                
                # Enqueue to RQ worker
                # 🔥 CRITICAL FIX: Pass message_id as POSITIONAL argument, not kwarg
                # send_scheduled_whatsapp_job expects: def send_scheduled_whatsapp_job(message_id: int, *args, **kwargs)
                job = enqueue(
                    'default',  # Use default queue for WhatsApp messages
                    send_scheduled_whatsapp_job,
                    message.id,  # ✅ POSITIONAL: first positional argument (message_id)
                    business_id=message.business_id,  # Add business_id for proper tracking
                    job_id=f"scheduled_wa_{message.id}",
                    timeout=300,  # 5 minutes timeout
                    retry=None,  # Don't auto-retry (we'll handle failures)
                    ttl=3600,  # 1 hour TTL
                    description=f"Send scheduled WhatsApp to lead {message.lead_id}"
                )
                
                enqueued_count += 1
                logger.info(f"[SCHEDULED-MSG-TICK] ✅ Enqueued message {message.id} as job {job.id}")
                
            except Exception as e:
                failed_count += 1
                logger.error(f"[SCHEDULED-MSG-TICK] ❌ Failed to enqueue message {message.id}: {e}", exc_info=True)
                # Mark as failed
                try:
                    scheduled_messages_service.mark_failed(message.id, f"Failed to enqueue: {str(e)}")
                except Exception as mark_err:
                    logger.error(f"[SCHEDULED-MSG-TICK] Could not mark message {message.id} as failed: {mark_err}")
        
        logger.info(f"[SCHEDULED-MSG-TICK] ✅ Successfully enqueued {enqueued_count}/{len(messages)} message(s), failed={failed_count}")
        
        return {
            'status': 'success',
            'claimed': len(messages),
            'enqueued': enqueued_count,
            'failed': failed_count
        }
        
    except Exception as e:
        logger.error(f"[SCHEDULED-MSG-TICK] ❌ Critical error in tick job: {e}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e)
        }
