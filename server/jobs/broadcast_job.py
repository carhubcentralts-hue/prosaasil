"""
WhatsApp Broadcast Job
Background job for stable, batched broadcast processing

Features:
- Batch processing (50 recipients per batch)
- Cursor-based pagination (no OFFSET overhead)
- Throttling between batches (200ms)
- Progress tracking
- Retry logic for temporary failures
- Hard cap runtime with pause/resume
- Idempotent execution
"""
import logging
import time
import json
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Configuration
BATCH_SIZE = 50  # Process 50 recipients per batch
THROTTLE_MS = 200  # 200ms sleep between batches
MAX_RUNTIME_SECONDS = 300  # 5 minutes max runtime before pausing
MAX_BATCH_FAILURES = 10  # Stop job after 10 consecutive batch failures


def process_broadcast_job(job_id: int):
    """
    Background job for processing WhatsApp broadcast in batches
    
    This runs in a separate worker process and:
    1. Loads job state from database
    2. Processes recipients in batches of BATCH_SIZE
    3. Updates progress after each batch
    4. Pauses if runtime exceeds MAX_RUNTIME_SECONDS
    5. Handles errors gracefully with retry logic
    
    Args:
        job_id: BackgroundJob ID to track progress
    """
    # 🔥 CRITICAL: Log IMMEDIATELY when job starts (before any imports/setup)
    print(f"=" * 70)
    print(f"🔨 JOB PICKED: function=process_broadcast_job job_id={job_id}")
    print(f"=" * 70)
    logger.info(f"=" * 70)
    logger.info(f"🔨 JOB PICKED: queue=broadcasts function=process_broadcast_job job_id={job_id}")
    logger.info(f"=" * 70)
    
    try:
        from server.app_factory import create_app
        from server.models_sql import db, BackgroundJob, WhatsAppBroadcast, WhatsAppBroadcastRecipient
        from server.services.broadcast_worker import BroadcastWorker
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
    
    # Create app context for DB access
    try:
        app = create_app()
    except Exception as e:
        error_msg = f"App creation failed: {str(e)}"
        logger.error(f"❌ JOB APP CREATION ERROR: {e}")
        print(f"❌ FATAL APP CREATION ERROR: {e}")
        import traceback
        logger.error(traceback.format_exc())
        print(traceback.format_exc())
        return {
            "success": False,
            "error": error_msg
        }
    
    with app.app_context():
        # Load job
        job = BackgroundJob.query.get(job_id)
        if not job:
            logger.error(f"Job {job_id} not found")
            return {"success": False, "error": "Job not found"}
        
        business_id = job.business_id
        
        # Extract broadcast_id from job metadata
        metadata = job.cursor and json.loads(job.cursor) or {}
        broadcast_id = metadata.get('broadcast_id')
        
        if not broadcast_id:
            logger.error(f"No broadcast_id in job {job_id} metadata")
            return {"success": False, "error": "Missing broadcast_id"}
        
        logger.info("=" * 60)
        logger.info(f"📢 JOB start type=broadcast business_id={business_id} job_id={job_id}")
        logger.info(f"📤 [BROADCAST] JOB_START: Process WhatsApp broadcast")
        logger.info(f"  → job_id: {job_id}")
        logger.info(f"  → business_id: {business_id}")
        logger.info(f"  → broadcast_id: {broadcast_id}")
        logger.info(f"  → batch_size: {BATCH_SIZE}")
        logger.info(f"  → throttle: {THROTTLE_MS}ms")
        logger.info("=" * 60)
        
        # Load broadcast
        broadcast = WhatsAppBroadcast.query.get(broadcast_id)
        if not broadcast:
            logger.error(f"Broadcast {broadcast_id} not found")
            job.status = 'failed'
            job.last_error = f"Broadcast {broadcast_id} not found"
            job.finished_at = datetime.utcnow()
            db.session.commit()
            return {"success": False, "error": "Broadcast not found"}
        
        # Update job status to running
        job.status = 'running'
        job.started_at = datetime.utcnow()
        job.heartbeat_at = datetime.utcnow()
        
        # Initialize cursor if not set (starting fresh)
        if 'last_id' not in metadata:
            metadata['last_id'] = 0
            metadata['broadcast_id'] = broadcast_id
        
        # Count total if not set
        if job.total == 0:
            job.total = WhatsAppBroadcastRecipient.query.filter_by(
                broadcast_id=broadcast_id,
                status='queued'
            ).count()
            logger.info(f"  → Total recipients to process: {job.total}")
        
        job.cursor = json.dumps(metadata)
        db.session.commit()
        
        start_time = time.time()
        consecutive_failures = 0
        
        try:
            while True:
                # CRITICAL: Check if job was cancelled
                db.session.refresh(job)
                if job.status == 'cancelled':
                    logger.info(f"🛑 Job {job_id} was cancelled - stopping")
                    job.finished_at = datetime.utcnow()
                    job.updated_at = datetime.utcnow()
                    db.session.commit()
                    return {
                        "success": True,
                        "cancelled": True,
                        "message": "Job was cancelled by user",
                        "processed": job.processed,
                        "total": job.total
                    }
                
                # Check runtime limit
                elapsed = time.time() - start_time
                if elapsed > MAX_RUNTIME_SECONDS:
                    logger.warning(f"⏱️  Runtime limit reached ({MAX_RUNTIME_SECONDS}s) - pausing job")
                    job.status = 'paused'
                    job.updated_at = datetime.utcnow()
                    db.session.commit()
                    return {
                        "success": True,
                        "paused": True,
                        "message": f"Job paused after {elapsed:.1f}s. Resume to continue.",
                        "processed": job.processed,
                        "total": job.total
                    }
                
                # Load cursor
                metadata = json.loads(job.cursor)
                last_id = metadata.get('last_id', 0)
                
                # Fetch next batch using cursor (ID-based pagination)
                recipients = WhatsAppBroadcastRecipient.query.filter(
                    WhatsAppBroadcastRecipient.broadcast_id == broadcast_id,
                    WhatsAppBroadcastRecipient.status == 'queued',
                    WhatsAppBroadcastRecipient.id > last_id
                ).order_by(WhatsAppBroadcastRecipient.id).limit(BATCH_SIZE).all()
                
                # Check if we're done
                if not recipients:
                    logger.info("=" * 60)
                    logger.info(f"📢 JOB complete type=broadcast business_id={business_id} job_id={job_id}")
                    logger.info("✅ [BROADCAST] All recipients processed - job complete")
                    logger.info(f"  → Total processed: {job.processed}")
                    logger.info(f"  → Successfully sent: {job.succeeded}")
                    logger.info(f"  → Failed: {job.failed_count}")
                    logger.info("=" * 60)
                    job.status = 'completed'
                    job.finished_at = datetime.utcnow()
                    job.updated_at = datetime.utcnow()
                    
                    # Update broadcast status
                    broadcast.status = 'completed'
                    broadcast.sent_count = job.succeeded
                    broadcast.updated_at = datetime.utcnow()
                    
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
                                    operation_type='broadcast_whatsapp'
                                )
                    except Exception as e:
                        logger.warning(f"Failed to release BulkGate lock: {e}")
                    
                    return {
                        "success": True,
                        "message": "Broadcast completed successfully",
                        "total": job.total,
                        "succeeded": job.succeeded,
                        "failed_count": job.failed_count
                    }
                
                # Process batch
                batch_start = time.time()
                batch_succeeded = 0
                batch_failed = 0
                
                try:
                    # Process recipients using existing broadcast worker
                    # Note: Using BroadcastWorker._process_recipient directly
                    # This is acceptable as the worker is designed for this batch-based processing
                    for recipient in recipients:
                        try:
                            # Mark as processing
                            recipient.status = 'processing'
                            db.session.commit()
                            
                            # Use existing worker processing logic
                            worker = BroadcastWorker(broadcast_id)
                            worker.broadcast = broadcast  # Set the broadcast object
                            worker._process_recipient(recipient, job.processed + 1, job.total)
                            
                            # Check status after processing
                            db.session.refresh(recipient)
                            if recipient.status == 'sent':
                                batch_succeeded += 1
                            else:
                                batch_failed += 1
                                
                        except Exception as e:
                            logger.error(f"Failed to send to recipient {recipient.id}: {e}")
                            recipient.status = 'failed'
                            recipient.error_message = str(e)[:500]
                            batch_failed += 1
                            job.last_error = f"Recipient {recipient.id}: {str(e)[:200]}"
                            db.session.commit()
                    
                    # Update cursor to last processed ID
                    max_id = max(r.id for r in recipients)
                    metadata['last_id'] = max_id
                    job.cursor = json.dumps(metadata)
                    
                    # Update progress counters
                    job.processed += len(recipients)
                    job.succeeded += batch_succeeded
                    job.failed_count += batch_failed
                    job.updated_at = datetime.utcnow()
                    job.heartbeat_at = datetime.utcnow()
                    
                    # Update broadcast stats
                    broadcast.sent_count = job.succeeded
                    broadcast.failed_count = job.failed_count
                    broadcast.updated_at = datetime.utcnow()
                    
                    # Commit DB changes
                    db.session.commit()
                    
                    # Reset consecutive failures on successful batch
                    if batch_failed == 0:
                        consecutive_failures = 0
                    
                    logger.info(
                        f"  ✓ [BROADCAST] Batch complete: {batch_succeeded} sent, {batch_failed} failed "
                        f"({job.processed}/{job.total} = {job.percent:.1f}%) in {time.time() - batch_start:.2f}s"
                    )
                    
                except Exception as e:
                    logger.error(f"[BROADCAST] Batch processing failed: {e}", exc_info=True)
                    consecutive_failures += 1
                    job.failed_count += len(recipients)
                    job.last_error = str(e)[:200]
                    job.updated_at = datetime.utcnow()
                    db.session.rollback()
                    db.session.commit()
                    
                    # Check if we should stop due to repeated failures
                    if consecutive_failures >= MAX_BATCH_FAILURES:
                        logger.error(f"❌ [BROADCAST] Too many consecutive failures ({consecutive_failures}) - stopping job")
                        job.status = 'failed'
                        job.finished_at = datetime.utcnow()
                        broadcast.status = 'failed'
                        db.session.commit()
                        return {
                            "success": False,
                            "error": f"Job failed after {consecutive_failures} consecutive batch failures",
                            "last_error": job.last_error
                        }
                
                # Throttle between batches
                time.sleep(THROTTLE_MS / 1000.0)
        
        except Exception as e:
            logger.error("=" * 60)
            logger.error(f"📢 JOB failed type=broadcast business_id={business_id} job_id={job_id}")
            logger.error(f"[BROADCAST] Job failed with unexpected error: {e}", exc_info=True)
            logger.error("=" * 60)
            job.status = 'failed'
            job.last_error = str(e)[:200]
            job.finished_at = datetime.utcnow()
            job.updated_at = datetime.utcnow()
            broadcast.status = 'failed'
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
                            operation_type='broadcast_whatsapp'
                        )
            except Exception as lock_err:
                logger.warning(f"Failed to release BulkGate lock: {lock_err}")
            
            return {
                "success": False,
                "error": str(e)
            }
