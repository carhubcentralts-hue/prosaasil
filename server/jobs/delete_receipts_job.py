"""
Delete Receipts Job
Background job for stable, batched deletion of all receipts

Features:
- Batch processing (50 items per batch)
- Cursor-based pagination (no OFFSET overhead)
- Throttling between batches (200ms)
- Progress tracking
- Safe attachment deletion
- Retry logic for temporary failures
- Hard cap runtime with pause/resume
- Idempotent execution
"""
import os
import logging
import time
import json
import traceback
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# Configuration
BATCH_SIZE = 50  # Process 50 receipts per batch
THROTTLE_MS = 200  # 200ms sleep between batches
MAX_RUNTIME_SECONDS = 300  # 5 minutes max runtime before pausing
MAX_BATCH_FAILURES = 10  # Stop job after 10 consecutive batch failures


def delete_receipts_batch_job(job_id: int):
    """
    Background job for deleting all receipts in batches
    
    This runs in a separate worker process and:
    1. Loads job state from database
    2. Processes receipts in batches of BATCH_SIZE
    3. Deletes attachments safely after DB commit
    4. Updates progress after each batch
    5. Pauses if runtime exceeds MAX_RUNTIME_SECONDS
    6. Handles errors gracefully with retry logic
    
    Args:
        job_id: BackgroundJob ID to track progress
    """
    # 🔥 CRITICAL: Log IMMEDIATELY when job starts (before any imports/setup)
    print(f"=" * 70)
    print(f"🔨 JOB PICKED: function=delete_receipts_batch_job job_id={job_id}")
    print(f"=" * 70)
    logger.info(f"=" * 70)
    logger.info(f"🔨 JOB PICKED: queue=maintenance function=delete_receipts_batch_job job_id={job_id}")
    logger.info(f"=" * 70)
    
    try:
        from flask import current_app
        from server.models_sql import db, BackgroundJob, Receipt, Attachment
    except ImportError as e:
        error_msg = f"Import failed: {str(e)}"
        logger.error(f"❌ JOB IMPORT ERROR: {e}")
        logger.error(traceback.format_exc())
        print(f"❌ FATAL IMPORT ERROR: {e}")
        print(traceback.format_exc())
        # Cannot proceed without imports - return error immediately
        return {
            "success": False,
            "error": error_msg
        }
    except Exception as e:
        error_msg = f"Import failed: {str(e)}"
        logger.error(f"❌ JOB IMPORT ERROR: {e}")
        logger.error(traceback.format_exc())
        print(f"❌ FATAL IMPORT ERROR: {e}")
        print(traceback.format_exc())
        return {
            "success": False,
            "error": error_msg
        }
    
    # Use current app context (worker already created it)
    # No need to create new app - we're running inside worker's app_context
    # Load job
    job = BackgroundJob.query.get(job_id)
    if not job:
        logger.error(f"Job {job_id} not found")
        return {"success": False, "error": "Job not found"}
    
    business_id = job.business_id
        
    logger.info("=" * 60)
    logger.info(f"🧾 JOB start type=delete_receipts business_id={business_id} job_id={job_id}")
    logger.info(f"🗑️  [RECEIPTS_DELETE] JOB_START: Delete all receipts")
    logger.info(f"  → job_id: {job_id}")
    logger.info(f"  → business_id: {business_id}")
    logger.info(f"  → batch_size: {BATCH_SIZE}")
    logger.info(f"  → throttle: {THROTTLE_MS}ms")
    logger.info("=" * 60)
        
    # Update job status to running
    job.status = 'running'
    job.started_at = datetime.utcnow()
    job.heartbeat_at = datetime.utcnow()  # Initialize heartbeat
        
    # Initialize cursor if not set (starting fresh)
    if not job.cursor:
        job.cursor = json.dumps({"last_id": 0})
        
    # Count total if not set
    if job.total == 0:
        job.total = Receipt.query.filter_by(
            business_id=business_id,
            is_deleted=False
        ).count()
        logger.info(f"  → Total receipts to delete: {job.total}")
        
    db.session.commit()
        
    start_time = time.time()
    consecutive_failures = 0
        
    try:
        while True:
            # CRITICAL: Check if job was cancelled
            db.session.refresh(job)  # Reload job from DB to get latest status
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
            cursor_data = json.loads(job.cursor)
            last_id = cursor_data.get("last_id", 0)
                
            # Fetch next batch using cursor (ID-based pagination)
            receipts = Receipt.query.filter(
                Receipt.business_id == business_id,
                Receipt.is_deleted == False,
                Receipt.id > last_id
            ).order_by(Receipt.id).limit(BATCH_SIZE).all()
                
            # Check if we're done
            if not receipts:
                logger.info("=" * 60)
                logger.info(f"🧾 JOB complete type=delete_receipts business_id={business_id} job_id={job_id}")
                logger.info("✅ [RECEIPTS_DELETE] All receipts processed - job complete")
                logger.info(f"  → Total processed: {job.processed}")
                logger.info(f"  → Successfully deleted: {job.succeeded}")
                logger.info(f"  → Failed: {job.failed_count}")
                logger.info("=" * 60)
                job.status = 'completed'
                job.finished_at = datetime.utcnow()
                job.updated_at = datetime.utcnow()
                db.session.commit()
                return {
                    "success": True,
                    "message": "All receipts deleted successfully",
                    "total": job.total,
                    "succeeded": job.succeeded,
                    "failed_count": job.failed_count
                }
                
            # Process batch
            batch_start = time.time()
            attachment_ids_to_delete = set()
            batch_succeeded = 0
            batch_failed = 0
            
            # 🔥 VISIBILITY: Log batch start details
            logger.info(f"  🔄 [RECEIPTS_DELETE] Processing batch: {len(receipts)} receipts (IDs {receipts[0].id}-{receipts[-1].id})")
                
            try:
                # Collect attachment IDs before deletion
                for receipt in receipts:
                    if receipt.attachment_id:
                        attachment_ids_to_delete.add(receipt.attachment_id)
                    if receipt.preview_attachment_id:
                        attachment_ids_to_delete.add(receipt.preview_attachment_id)
                    
                # Soft delete receipts in DB
                for receipt in receipts:
                    try:
                        receipt.is_deleted = True
                        receipt.deleted_at = datetime.utcnow()
                        receipt.updated_at = datetime.utcnow()
                        batch_succeeded += 1
                    except Exception as e:
                        logger.error(f"Failed to delete receipt {receipt.id}: {e}")
                        batch_failed += 1
                        job.last_error = f"Receipt {receipt.id}: {str(e)[:200]}"
                    
                # Update cursor to last processed ID
                max_id = max(r.id for r in receipts)
                cursor_data["last_id"] = max_id
                job.cursor = json.dumps(cursor_data)
                    
                # Update progress counters
                job.processed += len(receipts)
                job.succeeded += batch_succeeded
                job.failed_count += batch_failed
                job.updated_at = datetime.utcnow()
                job.heartbeat_at = datetime.utcnow()  # Update heartbeat every batch
                    
                # Commit DB changes
                db.session.commit()
                    
                # Reset consecutive failures on successful batch
                if batch_failed == 0:
                    consecutive_failures = 0
                    
                logger.info(
                    f"  ✓ [RECEIPTS_DELETE] Batch complete: {batch_succeeded} deleted, {batch_failed} failed "
                    f"({job.processed}/{job.total} = {job.percent:.1f}%) in {time.time() - batch_start:.2f}s"
                )
                    
            except Exception as e:
                logger.error(f"[RECEIPTS_DELETE] Batch processing failed: {e}", exc_info=True)
                consecutive_failures += 1
                job.failed_count += len(receipts)
                job.last_error = str(e)[:200]
                job.updated_at = datetime.utcnow()
                db.session.rollback()
                db.session.commit()
                    
                # Check if we should stop due to repeated failures
                if consecutive_failures >= MAX_BATCH_FAILURES:
                    logger.error(f"❌ [RECEIPTS_DELETE] Too many consecutive failures ({consecutive_failures}) - stopping job")
                    job.status = 'failed'
                    job.finished_at = datetime.utcnow()
                    db.session.commit()
                    return {
                        "success": False,
                        "error": f"Job failed after {consecutive_failures} consecutive batch failures",
                        "last_error": job.last_error
                    }
                
                # 🔥 BACKOFF: Add exponential backoff on consecutive failures (retry with delay)
                # This helps with transient DB/Redis connection issues
                if consecutive_failures > 0:
                    backoff_seconds = min(2 ** consecutive_failures, 30)  # Cap at 30 seconds
                    logger.warning(f"⏳ [RECEIPTS_DELETE] Backing off {backoff_seconds}s after {consecutive_failures} failures")
                    time.sleep(backoff_seconds)
                
            # Delete attachments from storage (outside transaction, after DB commit)
            if attachment_ids_to_delete:
                deleted_attachments = 0
                failed_attachments = 0
                try:
                    from server.services.attachment_service import get_attachment_service
                    attachment_service = get_attachment_service()
                        
                    logger.info(f"    → [RECEIPTS_DELETE] Deleting {len(attachment_ids_to_delete)} attachments from R2/storage")
                        
                    for att_id in attachment_ids_to_delete:
                        try:
                            attachment = Attachment.query.get(att_id)
                            if attachment and attachment.purpose in ('receipt_source', 'receipt_preview'):
                                # Delete from storage (R2/S3)
                                try:
                                    attachment_service.delete_file(
                                        storage_key=attachment.storage_path
                                    )
                                except Exception as storage_err:
                                    logger.warning(f"⚠️  Failed to delete attachment {att_id} from R2: {storage_err}")
                                    failed_attachments += 1
                                    
                                # Delete from database
                                db.session.delete(attachment)
                                deleted_attachments += 1
                        except Exception as att_err:
                            logger.error(f"❌ Failed to delete attachment {att_id}: {att_err}")
                            failed_attachments += 1
                        
                    # Commit attachment deletions
                    if deleted_attachments > 0:
                        db.session.commit()
                        logger.info(f"    → [RECEIPTS_DELETE] R2 cleanup: {deleted_attachments} deleted, {failed_attachments} failed")
                    
                except Exception as e:
                    logger.error(f"[RECEIPTS_DELETE] Attachment deletion failed (non-fatal): {e}")
                    db.session.rollback()
                
            # Throttle between batches
            time.sleep(THROTTLE_MS / 1000.0)
        
    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"🧾 JOB failed type=delete_receipts business_id={business_id} job_id={job_id}")
        logger.error(f"[RECEIPTS_DELETE] Job failed with unexpected error: {e}", exc_info=True)
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


def resume_job(job_id: int):
    """
    Resume a paused job
    
    Simply calls delete_receipts_batch_job again - it will read cursor and continue
    """
    return delete_receipts_batch_job(job_id)
