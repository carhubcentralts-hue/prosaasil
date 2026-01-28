"""
Outbound Call Worker Job
Processes outbound call runs with complete crash recovery and cancel support
"""
import logging
import time
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)


def process_outbound_run_job(business_id: int, run_id: int = None):
    """
    Process outbound call run(s) for a business.
    
    If run_id is provided, processes that specific run.
    Otherwise, claims and processes any pending runs for the business.
    
    Args:
        business_id: Business ID for isolation
        run_id: Optional specific run ID to process
    
    Returns:
        dict: Processing result
    """
    from flask import current_app
    from server.services.outbound_queue import (
        claim_outbound_run, update_heartbeat, check_if_cancelled,
        claim_next_job, update_cursor_position, release_lock, recover_stale_runs
    )
    from twilio.rest import Client
    import os
    
    logger.info(f"[OUTBOUND-WORKER] Starting for business_id={business_id}, run_id={run_id}")
    
    with current_app.app_context():
        # Generate unique worker ID
        worker_id = f"worker-{uuid.uuid4().hex[:8]}"
        
        # Recover any stale runs first
        recover_stale_runs(business_id)
        
        # Claim a run
        if run_id is None:
            run_id = claim_outbound_run(business_id, worker_id)
            if run_id is None:
                logger.info(f"[OUTBOUND-WORKER] No work available for business {business_id}")
                return {
                    'status': 'no_work',
                    'business_id': business_id,
                    'timestamp': datetime.utcnow().isoformat()
                }
        
        try:
            # Initialize Twilio client
            twilio_sid = os.getenv('TWILIO_ACCOUNT_SID')
            twilio_token = os.getenv('TWILIO_AUTH_TOKEN')
            twilio_from = os.getenv('TWILIO_NUMBER')
            
            if not all([twilio_sid, twilio_token, twilio_from]):
                logger.error("[OUTBOUND-WORKER] Missing Twilio credentials")
                release_lock(run_id, worker_id, 'failed')
                return {
                    'status': 'error',
                    'error': 'Missing Twilio credentials',
                    'timestamp': datetime.utcnow().isoformat()
                }
            
            client = Client(twilio_sid, twilio_token)
            
            # Process jobs
            jobs_processed = 0
            last_heartbeat = time.time()
            
            while True:
                # Check for cancellation
                if check_if_cancelled(run_id):
                    logger.info(f"[OUTBOUND-WORKER] Run {run_id} cancelled, stopping")
                    release_lock(run_id, worker_id, 'cancelled')
                    return {
                        'status': 'cancelled',
                        'run_id': run_id,
                        'jobs_processed': jobs_processed,
                        'timestamp': datetime.utcnow().isoformat()
                    }
                
                # Update heartbeat periodically
                if time.time() - last_heartbeat > 30:
                    if not update_heartbeat(run_id, worker_id):
                        logger.error(f"[OUTBOUND-WORKER] Lost lock on run {run_id}, stopping")
                        return {
                            'status': 'lock_lost',
                            'run_id': run_id,
                            'jobs_processed': jobs_processed,
                            'timestamp': datetime.utcnow().isoformat()
                        }
                    last_heartbeat = time.time()
                
                # Claim next job
                job_result = claim_next_job(run_id, business_id)
                if job_result is None:
                    # No more jobs
                    logger.info(f"[OUTBOUND-WORKER] All jobs processed for run {run_id}")
                    release_lock(run_id, worker_id, 'completed')
                    return {
                        'status': 'completed',
                        'run_id': run_id,
                        'jobs_processed': jobs_processed,
                        'timestamp': datetime.utcnow().isoformat()
                    }
                
                job_id, lead_id, phone = job_result
                
                # Make the call
                try:
                    logger.info(f"[OUTBOUND-WORKER] Calling {phone} for job {job_id}")
                    
                    # Build TwiML URL
                    # This should point to your outbound call handler
                    twiml_url = f"https://your-domain.com/api/twilio/outbound?run_id={run_id}&job_id={job_id}&lead_id={lead_id}&business_id={business_id}"
                    
                    # Initiate call
                    call = client.calls.create(
                        to=phone,
                        from_=twilio_from,
                        url=twiml_url,
                        status_callback=f"https://your-domain.com/api/twilio/call_status",
                        status_callback_event=['initiated', 'ringing', 'answered', 'completed']
                    )
                    
                    logger.info(f"[OUTBOUND-WORKER] ✅ Call initiated: {call.sid}")
                    
                    # Update job with call SID
                    from server.models_sql import db, OutboundCallJob
                    job = OutboundCallJob.query.filter_by(
                        id=job_id,
                        business_id=business_id  # 🔒 BUSINESS ISOLATION
                    ).first()
                    if job:
                        job.twilio_call_sid = call.sid
                        job.status = 'calling'
                        db.session.commit()
                    
                    jobs_processed += 1
                    update_cursor_position(run_id, jobs_processed)
                    
                    # Rate limiting - don't hammer Twilio
                    time.sleep(2)
                    
                except Exception as call_error:
                    logger.error(f"[OUTBOUND-WORKER] ❌ Call failed for job {job_id}: {call_error}")
                    
                    # Mark job as failed
                    from server.models_sql import db, OutboundCallJob
                    job = OutboundCallJob.query.filter_by(
                        id=job_id,
                        business_id=business_id  # 🔒 BUSINESS ISOLATION
                    ).first()
                    if job:
                        job.status = 'failed'
                        job.error_message = str(call_error)
                        db.session.commit()
                    
                    continue
            
        except Exception as e:
            logger.error(f"[OUTBOUND-WORKER] ❌ Fatal error: {e}", exc_info=True)
            release_lock(run_id, worker_id, 'failed')
            return {
                'status': 'error',
                'error': str(e),
                'run_id': run_id,
                'jobs_processed': jobs_processed,
                'timestamp': datetime.utcnow().isoformat()
            }
