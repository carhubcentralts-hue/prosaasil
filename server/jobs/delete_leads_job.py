"""
Delete Leads Job
Background job for stable, batched deletion of leads

Features:
- Batch processing (50 leads per batch)
- Cursor-based pagination (no OFFSET overhead)
- Throttling between batches (200ms)
- Progress tracking
- Proper cascade cleanup (activities, notes, reminders)
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
BATCH_SIZE = 50  # Process 50 leads per batch
THROTTLE_MS = 200  # 200ms sleep between batches
MAX_RUNTIME_SECONDS = 300  # 5 minutes max runtime before pausing
MAX_BATCH_FAILURES = 10  # Stop job after 10 consecutive batch failures


def delete_leads_batch_job(job_id: int):
    """
    Background job for deleting leads in batches with proper cascade cleanup
    
    This runs in a separate worker process and:
    1. Loads job state from database
    2. Processes leads in batches of BATCH_SIZE
    3. Deletes related records (activities, notes, reminders)
    4. Updates progress after each batch
    5. Pauses if runtime exceeds MAX_RUNTIME_SECONDS
    6. Handles errors gracefully with retry logic
    
    Args:
        job_id: BackgroundJob ID to track progress
    """
    # 🔥 CRITICAL: Log IMMEDIATELY when job starts (before any imports/setup)
    print(f"=" * 70)
    print(f"🔨 JOB PICKED: function=delete_leads_batch_job job_id={job_id}")
    print(f"=" * 70)
    logger.info(f"=" * 70)
    logger.info(f"🔨 JOB PICKED: queue=maintenance function=delete_leads_batch_job job_id={job_id}")
    logger.info(f"=" * 70)
    
    try:
        from flask import current_app
        from server.models_sql import db, BackgroundJob, Lead, LeadActivity, LeadReminder, LeadNote, LeadMergeCandidate
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
        
    # Extract lead_ids from job metadata
    metadata = job.cursor and json.loads(job.cursor) or {}
    lead_ids = metadata.get('lead_ids', [])
        
    if not lead_ids:
        logger.error(f"No lead_ids in job {job_id} metadata")
        return {"success": False, "error": "Missing lead_ids"}
        
    logger.info("=" * 60)
    logger.info(f"🗑️  JOB start type=delete_leads business_id={business_id} job_id={job_id}")
    logger.info(f"🗑️  [DELETE_LEADS] JOB_START: Delete leads with cascade cleanup")
    logger.info(f"  → job_id: {job_id}")
    logger.info(f"  → business_id: {business_id}")
    logger.info(f"  → lead_ids: {len(lead_ids)} leads")
    logger.info(f"  → batch_size: {BATCH_SIZE}")
    logger.info(f"  → throttle: {THROTTLE_MS}ms")
    logger.info("=" * 60)
        
    # Update job status to running
    job.status = 'running'
    job.started_at = datetime.utcnow()
    job.heartbeat_at = datetime.utcnow()
        
    # Initialize cursor if not set (starting fresh)
    if 'processed_ids' not in metadata:
        metadata['processed_ids'] = []
        metadata['lead_ids'] = lead_ids
        
    # Count total if not set
    if job.total == 0:
        job.total = len(lead_ids)
        logger.info(f"  → Total leads to delete: {job.total}")
        
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
            processed_ids = metadata.get('processed_ids', [])
            remaining_ids = [lid for lid in lead_ids if lid not in processed_ids]
                
            # Check if we're done
            if not remaining_ids:
                logger.info("=" * 60)
                logger.info(f"🗑️  JOB complete type=delete_leads business_id={business_id} job_id={job_id}")
                logger.info("✅ [DELETE_LEADS] All leads processed - job complete")
                logger.info(f"  → Total processed: {job.processed}")
                logger.info(f"  → Successfully deleted: {job.succeeded}")
                logger.info(f"  → Failed: {job.failed_count}")
                logger.info("=" * 60)
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
                                operation_type='delete_leads_bulk'
                            )
                except Exception as e:
                    logger.warning(f"Failed to release BulkGate lock: {e}")
                    
                return {
                    "success": True,
                    "message": "All leads deleted successfully",
                    "total": job.total,
                    "succeeded": job.succeeded,
                    "failed_count": job.failed_count
                }
                
            # Get next batch
            batch_ids = remaining_ids[:BATCH_SIZE]
                
            # Fetch leads for this batch
            leads = Lead.query.filter(
                Lead.id.in_(batch_ids),
                Lead.tenant_id == business_id
            ).all()
                
            # Process batch
            batch_start = time.time()
            batch_succeeded = 0
            batch_failed = 0
                
            try:
                actual_lead_ids = [lead.id for lead in leads]
                    
                if actual_lead_ids:
                    # Delete related records FIRST to avoid FK constraint violations
                        
                    # Delete LeadActivity records
                    LeadActivity.query.filter(
                        LeadActivity.lead_id.in_(actual_lead_ids)
                    ).delete(synchronize_session=False)
                        
                    # Delete LeadReminder records
                    LeadReminder.query.filter(
                        LeadReminder.lead_id.in_(actual_lead_ids)
                    ).delete(synchronize_session=False)
                        
                    # Delete LeadNote records (handle missing table gracefully)
                    try:
                        LeadNote.query.filter(
                            LeadNote.lead_id.in_(actual_lead_ids)
                        ).delete(synchronize_session=False)
                    except Exception as note_err:
                        err_str = str(note_err).lower()
                        if 'undefinedtable' in err_str or 'does not exist' in err_str or 'lead_notes' in err_str:
                            logger.warning(f"⚠️ LeadNote delete skipped (table does not exist)")
                        else:
                            raise
                        
                    # Delete LeadMergeCandidate records (handle missing table gracefully)
                    try:
                        LeadMergeCandidate.query.filter(
                            db.or_(
                                LeadMergeCandidate.lead_id.in_(actual_lead_ids),
                                LeadMergeCandidate.duplicate_lead_id.in_(actual_lead_ids)
                            )
                        ).delete(synchronize_session=False)
                    except Exception as merge_err:
                        err_str = str(merge_err).lower()
                        if 'undefinedtable' in err_str or 'does not exist' in err_str or 'lead_merge_candidates' in err_str:
                            logger.warning(f"⚠️ LeadMergeCandidate delete skipped (table does not exist)")
                        else:
                            raise
                        
                    # Clear lead_id references in WhatsAppConversation (set to NULL)
                    try:
                        from server.models_sql import WhatsAppConversation
                        WhatsAppConversation.query.filter(
                            WhatsAppConversation.lead_id.in_(actual_lead_ids)
                        ).update(
                            {'lead_id': None},  # Use dict with string key for column update
                            synchronize_session=False
                        )
                    except Exception as wa_err:
                        logger.warning(f"⚠️ WhatsAppConversation update skipped: {wa_err}")
                        
                    # Delete the leads themselves
                    for lead in leads:
                        try:
                            db.session.delete(lead)
                            batch_succeeded += 1
                        except Exception as e:
                            logger.error(f"Failed to delete lead {lead.id}: {e}")
                            batch_failed += 1
                            job.last_error = f"Lead {lead.id}: {str(e)[:200]}"
                    
                # Update processed_ids
                processed_ids.extend(batch_ids)
                metadata['processed_ids'] = processed_ids
                job.cursor = json.dumps(metadata)
                    
                # Update progress counters
                job.processed += len(batch_ids)
                job.succeeded += batch_succeeded
                job.failed_count += batch_failed
                job.updated_at = datetime.utcnow()
                job.heartbeat_at = datetime.utcnow()
                    
                # Commit DB changes
                db.session.commit()
                    
                # Refresh BulkGate lock TTL on heartbeat
                try:
                    import redis
                    import os
                    from server.services.bulk_gate import get_bulk_gate
                    REDIS_URL = os.getenv('REDIS_URL')
                    redis_conn = redis.from_url(REDIS_URL) if REDIS_URL else None
                        
                    if redis_conn:
                        bulk_gate = get_bulk_gate(redis_conn)
                        if bulk_gate:
                            bulk_gate.refresh_lock_ttl(
                                business_id=business_id,
                                operation_type='delete_leads_bulk'
                            )
                except Exception as lock_err:
                    logger.debug(f"Failed to refresh lock TTL: {lock_err}")
                    
                # Reset consecutive failures on successful batch
                if batch_failed == 0:
                    consecutive_failures = 0
                    
                logger.info(
                    f"  ✓ [DELETE_LEADS] Batch complete: {batch_succeeded} deleted, {batch_failed} failed "
                    f"({job.processed}/{job.total} = {job.percent:.1f}%) in {time.time() - batch_start:.2f}s"
                )
                    
            except Exception as e:
                logger.error(f"[DELETE_LEADS] Batch processing failed: {e}", exc_info=True)
                consecutive_failures += 1
                job.failed_count += len(batch_ids)
                job.last_error = str(e)[:200]
                job.updated_at = datetime.utcnow()
                db.session.rollback()
                db.session.commit()
                    
                # Check if we should stop due to repeated failures
                if consecutive_failures >= MAX_BATCH_FAILURES:
                    logger.error(f"❌ [DELETE_LEADS] Too many consecutive failures ({consecutive_failures}) - stopping job")
                    job.status = 'failed'
                    job.finished_at = datetime.utcnow()
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
        logger.error(f"🗑️  JOB failed type=delete_leads business_id={business_id} job_id={job_id}")
        logger.error(f"[DELETE_LEADS] Job failed with unexpected error: {e}", exc_info=True)
        logger.error("=" * 60)
        job.status = 'failed'
        job.last_error = str(e)[:200]
        job.finished_at = datetime.utcnow()
        job.updated_at = datetime.utcnow()
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
                        operation_type='delete_leads_bulk'
                    )
        except Exception as lock_err:
            logger.warning(f"Failed to release BulkGate lock: {lock_err}")
            
        return {
            "success": False,
            "error": str(e)
        }
