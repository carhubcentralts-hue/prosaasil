"""
Enqueue Outbound Calls Job
Background job for stable, batched processing of outbound call queue

Features:
- Respects concurrency limits
- Progress tracking
- Retry logic for temporary failures
- Hard cap runtime with pause/resume
- Idempotent execution

This job processes the OutboundCallRun queue and initiates calls via Twilio.
It reuses the existing process_bulk_call_run logic.
"""
import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)


def enqueue_outbound_calls_batch_job(job_id: int):
    """
    Background job for processing outbound call queue
    
    This wraps the existing process_bulk_call_run logic with BackgroundJob tracking.
    
    Args:
        job_id: BackgroundJob ID to track progress
    """
    # 🔥 CRITICAL: Log IMMEDIATELY when job starts (before any imports/setup)
    print(f"=" * 70)
    print(f"🔨 JOB PICKED: function=enqueue_outbound_calls_batch_job job_id={job_id}")
    print(f"=" * 70)
    logger.info(f"=" * 70)
    logger.info(f"🔨 JOB PICKED: queue=default function=enqueue_outbound_calls_batch_job job_id={job_id}")
    logger.info(f"=" * 70)
    
    try:
        from flask import current_app
        from server.models_sql import db, BackgroundJob, OutboundCallRun
        from server.routes_outbound import process_bulk_call_run
    except ImportError as e:
        error_msg = f"Import failed: {str(e)}"
        logger.error(f"❌ JOB IMPORT ERROR: {e}")
        print(f"❌ FATAL IMPORT ERROR: {e}")
        import traceback
        logger.error(traceback.format_exc())
        print(traceback.format_exc())
        return {
            "success": False,
            "error": error_msg
        }
    except Exception as e:
        error_msg = f"Import failed: {str(e)}"
        logger.error(f"❌ JOB IMPORT ERROR: {e}")
        print(f"❌ FATAL IMPORT ERROR: {e}")
        import traceback
        logger.error(traceback.format_exc())
        print(traceback.format_exc())
        return {
            "success": False,
            "error": error_msg
        }
    
    # Use current app context (worker already created it)
    # Load job
    job = BackgroundJob.query.get(job_id)
    if not job:
        logger.error(f"Job {job_id} not found")
        return {"success": False, "error": "Job not found"}
        
    business_id = job.business_id
        
    # Extract run_id from job metadata
    metadata = job.cursor and json.loads(job.cursor) or {}
    run_id = metadata.get('run_id')
        
    if not run_id:
        logger.error(f"No run_id in job {job_id} metadata")
        return {"success": False, "error": "Missing run_id"}
        
    logger.info("=" * 60)
    logger.info(f"📞 JOB start type=enqueue_outbound_calls business_id={business_id} job_id={job_id}")
    logger.info(f"📞 [OUTBOUND_CALLS] JOB_START: Process outbound call queue")
    logger.info(f"  → job_id: {job_id}")
    logger.info(f"  → business_id: {business_id}")
    logger.info(f"  → run_id: {run_id}")
    logger.info("=" * 60)
        
    # Load run
    run = OutboundCallRun.query.get(run_id)
    if not run:
        logger.error(f"OutboundCallRun {run_id} not found")
        job.status = 'failed'
        job.last_error = f"Run {run_id} not found"
        job.finished_at = datetime.utcnow()
        db.session.commit()
        return {"success": False, "error": "Run not found"}
        
    # Update job status to running
    job.status = 'running'
    job.started_at = datetime.utcnow()
    job.heartbeat_at = datetime.utcnow()
    db.session.commit()
        
    try:
        # Use existing process_bulk_call_run logic
        # This handles all the complexity of concurrency, retries, etc.
        process_bulk_call_run(run_id)
            
        # Refresh run to get final status
        db.session.refresh(run)
            
        # Update job with final results
        job.processed = run.total_leads
        job.succeeded = run.completed_count
        job.failed_count = run.failed_count
        job.status = 'completed'
        job.finished_at = datetime.utcnow()
        job.updated_at = datetime.utcnow()
        db.session.commit()
            
        # Release BulkGate lock
        try:
            import redis
            import os
            from server.services.bulk_gate import get_bulk_gate
            REDIS_URL = os.getenv('REDIS_URL')
            redis_conn = redis.from_url(REDIS_URL) if REDIS_URL else None
                
            if redis_conn:
                bulk_gate = get_bulk_gate(redis_conn)
                if bulk_gate:
                    bulk_gate.release_lock(
                        business_id=business_id,
                        operation_type='enqueue_outbound_calls'
                    )
        except Exception as e:
            logger.warning(f"Failed to release BulkGate lock: {e}")
            
        logger.info("=" * 60)
        logger.info(f"📞 JOB complete type=enqueue_outbound_calls business_id={business_id} job_id={job_id}")
        logger.info(f"✅ [OUTBOUND_CALLS] All calls processed")
        logger.info(f"  → Total processed: {job.processed}")
        logger.info(f"  → Successfully completed: {job.succeeded}")
        logger.info(f"  → Failed: {job.failed_count}")
        logger.info("=" * 60)
            
        return {
            "success": True,
            "message": "All outbound calls processed successfully",
            "total": job.total,
            "succeeded": job.succeeded,
            "failed_count": job.failed_count
        }
            
    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"📞 JOB failed type=enqueue_outbound_calls business_id={business_id} job_id={job_id}")
        logger.error(f"[OUTBOUND_CALLS] Job failed with unexpected error: {e}", exc_info=True)
        logger.error("=" * 60)
        job.status = 'failed'
        job.last_error = str(e)[:200]
        job.finished_at = datetime.utcnow()
        job.updated_at = datetime.utcnow()
        run.status = 'failed'
        db.session.commit()
            
        # Release BulkGate lock even on failure
        try:
            import redis
            import os
            from server.services.bulk_gate import get_bulk_gate
            REDIS_URL = os.getenv('REDIS_URL')
            redis_conn = redis.from_url(REDIS_URL) if REDIS_URL else None
                
            if redis_conn:
                bulk_gate = get_bulk_gate(redis_conn)
                if bulk_gate:
                    bulk_gate.release_lock(
                        business_id=business_id,
                        operation_type='enqueue_outbound_calls'
                    )
        except Exception as lock_err:
            logger.warning(f"Failed to release BulkGate lock: {lock_err}")
            
        return {
            "success": False,
            "error": str(e)
        }
