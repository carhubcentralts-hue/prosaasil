"""
Update Leads Job
Background job for stable, batched bulk update of leads

Features:
- Batch processing (50 leads per batch)
- Throttling between batches (200ms)
- Progress tracking
- Activity logging for each update
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


def update_leads_batch_job(job_id: int):
    """
    Background job for bulk updating leads in batches
    
    This runs in a separate worker process and:
    1. Loads job state from database
    2. Processes leads in batches of BATCH_SIZE
    3. Updates allowed fields (status, owner_user_id, tags)
    4. Logs activity for each update
    5. Updates progress after each batch
    6. Pauses if runtime exceeds MAX_RUNTIME_SECONDS
    7. Handles errors gracefully with retry logic
    
    Args:
        job_id: BackgroundJob ID to track progress
    """
    from server.app_factory import create_app
    from server.models_sql import db, BackgroundJob, Lead
    
    # Create app context for DB access
    app = create_app()
    
    with app.app_context():
        # Load job
        job = BackgroundJob.query.get(job_id)
        if not job:
            logger.error(f"Job {job_id} not found")
            return {"success": False, "error": "Job not found"}
        
        business_id = job.business_id
        
        # Extract lead_ids and updates from job metadata
        metadata = job.cursor and json.loads(job.cursor) or {}
        lead_ids = metadata.get('lead_ids', [])
        updates = metadata.get('updates', {})
        user_email = metadata.get('user_email', 'unknown')
        user_id = metadata.get('user_id')
        
        if not lead_ids or not updates:
            logger.error(f"No lead_ids or updates in job {job_id} metadata")
            return {"success": False, "error": "Missing lead_ids or updates"}
        
        logger.info("=" * 60)
        logger.info(f"📝 JOB start type=update_leads business_id={business_id} job_id={job_id}")
        logger.info(f"📝 [UPDATE_LEADS] JOB_START: Bulk update leads")
        logger.info(f"  → job_id: {job_id}")
        logger.info(f"  → business_id: {business_id}")
        logger.info(f"  → lead_ids: {len(lead_ids)} leads")
        logger.info(f"  → updates: {list(updates.keys())}")
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
            metadata['updates'] = updates
            metadata['user_email'] = user_email
            metadata['user_id'] = user_id
        
        # Count total if not set
        if job.total == 0:
            job.total = len(lead_ids)
            logger.info(f"  → Total leads to update: {job.total}")
        
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
                    logger.info(f"📝 JOB complete type=update_leads business_id={business_id} job_id={job_id}")
                    logger.info("✅ [UPDATE_LEADS] All leads processed - job complete")
                    logger.info(f"  → Total processed: {job.processed}")
                    logger.info(f"  → Successfully updated: {job.succeeded}")
                    logger.info(f"  → Failed: {job.failed_count}")
                    logger.info("=" * 60)
                    job.status = 'completed'
                    job.finished_at = datetime.utcnow()
                    job.updated_at = datetime.utcnow()
                    db.session.commit()
                    return {
                        "success": True,
                        "message": "All leads updated successfully",
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
                    # Import activity logging
                    from server.routes_leads import create_activity
                    
                    for lead in leads:
                        try:
                            changes = {}
                            
                            # Update allowed fields
                            for field in ['status', 'owner_user_id', 'tags']:
                                if field in updates:
                                    old_value = getattr(lead, field)
                                    new_value = updates[field]
                                    if old_value != new_value:
                                        changes[field] = {"from": old_value, "to": new_value}
                                        setattr(lead, field, new_value)
                            
                            if changes:
                                lead.updated_at = datetime.utcnow()
                                
                                # Log bulk update
                                create_activity(
                                    lead.id,
                                    "bulk_update",
                                    {
                                        "changes": changes,
                                        "updated_by": user_email
                                    },
                                    user_id
                                )
                                batch_succeeded += 1
                            else:
                                # No changes needed
                                batch_succeeded += 1
                                
                        except Exception as e:
                            logger.error(f"Failed to update lead {lead.id}: {e}")
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
                    
                    # Reset consecutive failures on successful batch
                    if batch_failed == 0:
                        consecutive_failures = 0
                    
                    logger.info(
                        f"  ✓ [UPDATE_LEADS] Batch complete: {batch_succeeded} updated, {batch_failed} failed "
                        f"({job.processed}/{job.total} = {job.percent:.1f}%) in {time.time() - batch_start:.2f}s"
                    )
                    
                except Exception as e:
                    logger.error(f"[UPDATE_LEADS] Batch processing failed: {e}", exc_info=True)
                    consecutive_failures += 1
                    job.failed_count += len(batch_ids)
                    job.last_error = str(e)[:200]
                    job.updated_at = datetime.utcnow()
                    db.session.rollback()
                    db.session.commit()
                    
                    # Check if we should stop due to repeated failures
                    if consecutive_failures >= MAX_BATCH_FAILURES:
                        logger.error(f"❌ [UPDATE_LEADS] Too many consecutive failures ({consecutive_failures}) - stopping job")
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
            logger.error(f"📝 JOB failed type=update_leads business_id={business_id} job_id={job_id}")
            logger.error(f"[UPDATE_LEADS] Job failed with unexpected error: {e}", exc_info=True)
            logger.error("=" * 60)
            job.status = 'failed'
            job.last_error = str(e)[:200]
            job.finished_at = datetime.utcnow()
            job.updated_at = datetime.utcnow()
            db.session.commit()
            return {
                "success": False,
                "error": str(e)
            }
