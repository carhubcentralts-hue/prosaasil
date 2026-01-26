"""
WhatsApp Broadcast Job
Background job for stable, batched broadcast processing

✅ SSOT: Uses WhatsAppBroadcast as single source of truth (no BackgroundJob)

Features:
- Batch processing (50 recipients per batch)
- Cursor-based pagination (no OFFSET overhead)
- Throttling between batches (200ms)
- Progress tracking via WhatsAppBroadcast model
- Retry logic for temporary failures
- Hard cap runtime with pause/resume
- Idempotent execution
- Real cancel support via cancel_requested flag
"""
import logging
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Configuration
BATCH_SIZE = 50  # Process 50 recipients per batch
THROTTLE_MS = 200  # 200ms sleep between batches
MAX_RUNTIME_SECONDS = 300  # 5 minutes max runtime before pausing
MAX_BATCH_FAILURES = 10  # Stop broadcast after 10 consecutive batch failures


def process_broadcast_job(broadcast_id: int):
    """
    Background job for processing WhatsApp broadcast in batches
    
    ✅ SSOT: Uses WhatsAppBroadcast as single source of truth (no BackgroundJob)
    
    This runs in a separate worker process and:
    1. Loads WhatsAppBroadcast from database
    2. Processes recipients in batches of BATCH_SIZE
    3. Updates progress after each batch (processed_count, sent_count, etc.)
    4. Pauses if runtime exceeds MAX_RUNTIME_SECONDS
    5. Checks cancel_requested before each batch
    6. Handles errors gracefully with retry logic
    
    Args:
        broadcast_id: WhatsAppBroadcast ID to process
    """
    # 🔥 CRITICAL: Log IMMEDIATELY when job starts (before any imports/setup)
    print(f"=" * 70)
    print(f"🔨 JOB PICKED: function=process_broadcast_job broadcast_id={broadcast_id}")
    print(f"=" * 70)
    logger.info(f"=" * 70)
    logger.info(f"🔨 JOB PICKED: queue=broadcasts function=process_broadcast_job broadcast_id={broadcast_id}")
    logger.info(f"=" * 70)
    
    try:
        from flask import current_app
        from server.models_sql import db, WhatsAppBroadcast, WhatsAppBroadcastRecipient
        from server.services.broadcast_worker import BroadcastWorker
    except ImportError as e:
        error_msg = f"Import failed: {str(e)}"
        logger.error(f"❌ IMPORT ERROR: broadcast_id={broadcast_id} error={e}")
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
        logger.error(f"❌ IMPORT ERROR: broadcast_id={broadcast_id} error={e}")
        print(f"❌ FATAL IMPORT ERROR: {e}")
        import traceback
        logger.error(traceback.format_exc())
        print(traceback.format_exc())
        return {
            "success": False,
            "error": error_msg
        }
    
    # Load broadcast (SSOT - single source of truth)
    broadcast = WhatsAppBroadcast.query.get(broadcast_id)
    if not broadcast:
        logger.error(f"❌ Broadcast {broadcast_id} not found")
        return {"success": False, "error": f"Broadcast {broadcast_id} not found"}
    
    business_id = broadcast.business_id
    
    logger.info("=" * 60)
    logger.info(f"📢 BROADCAST START: business_id={business_id} broadcast_id={broadcast_id}")
    logger.info(f"📤 [BROADCAST] Processing WhatsApp broadcast")
    logger.info(f"  → business_id: {business_id}")
    logger.info(f"  → broadcast_id: {broadcast_id}")
    logger.info(f"  → batch_size: {BATCH_SIZE}")
    logger.info(f"  → throttle: {THROTTLE_MS}ms")
    logger.info("=" * 60)
        
    # 🎯 FIX #5: Removed ALTER TABLE at runtime - this is now handled by migration_add_broadcast_cursor.py
    # Column last_processed_recipient_id MUST exist before this job runs
    # If it doesn't exist, the migration should be run first
        
    # Update broadcast status to running and set started_at if not set
    if not broadcast.started_at:
        broadcast.started_at = datetime.utcnow()
    broadcast.status = 'running'
    broadcast.updated_at = datetime.utcnow()
        
    # Initialize cursor if not set (starting fresh)
    if not hasattr(broadcast, 'last_processed_recipient_id') or broadcast.last_processed_recipient_id is None:
        broadcast.last_processed_recipient_id = 0
        
    # Count total recipients if not set
    if broadcast.total_recipients == 0:
        broadcast.total_recipients = WhatsAppBroadcastRecipient.query.filter_by(
            broadcast_id=broadcast_id,
            status='queued'
        ).count()
        logger.info(f"  → Total recipients to process: {broadcast.total_recipients}")
        
    db.session.commit()
        
    start_time = time.time()
    consecutive_failures = 0
        
    try:
        while True:
            # CRITICAL: Check if broadcast was cancelled
            db.session.refresh(broadcast)
            if broadcast.cancel_requested:
                logger.info(f"🛑 Broadcast {broadcast_id} was cancelled - stopping")
                
                # Mark all remaining queued recipients as cancelled
                remaining = WhatsAppBroadcastRecipient.query.filter(
                    WhatsAppBroadcastRecipient.broadcast_id == broadcast_id,
                    WhatsAppBroadcastRecipient.status == 'queued'
                ).all()
                
                for recipient in remaining:
                    recipient.status = 'cancelled'
                    broadcast.cancelled_count += 1
                
                broadcast.status = 'cancelled'
                broadcast.completed_at = datetime.utcnow()
                broadcast.updated_at = datetime.utcnow()
                db.session.commit()
                
                # Release BulkGate lock
                _release_bulk_gate_lock(business_id)
                
                return {
                    "success": True,
                    "cancelled": True,
                    "message": "Broadcast was cancelled by user",
                    "processed": broadcast.processed_count,
                    "sent": broadcast.sent_count,
                    "failed": broadcast.failed_count,
                    "cancelled": broadcast.cancelled_count,
                    "total": broadcast.total_recipients
                }
                
            # Check runtime limit
            elapsed = time.time() - start_time
            if elapsed > MAX_RUNTIME_SECONDS:
                logger.warning(f"⏱️  Runtime limit reached ({MAX_RUNTIME_SECONDS}s) - pausing broadcast")
                broadcast.status = 'paused'
                broadcast.updated_at = datetime.utcnow()
                db.session.commit()
                return {
                    "success": True,
                    "paused": True,
                    "message": f"Broadcast paused after {elapsed:.1f}s. Resume to continue.",
                    "processed": broadcast.processed_count,
                    "total": broadcast.total_recipients
                }
                
            # Get cursor (last processed recipient ID)
            last_id = broadcast.last_processed_recipient_id or 0
                
            # Fetch next batch using cursor (ID-based pagination)
            recipients = WhatsAppBroadcastRecipient.query.filter(
                WhatsAppBroadcastRecipient.broadcast_id == broadcast_id,
                WhatsAppBroadcastRecipient.status == 'queued',
                WhatsAppBroadcastRecipient.id > last_id
            ).order_by(WhatsAppBroadcastRecipient.id).limit(BATCH_SIZE).all()
                
            # Check if we're done
            if not recipients:
                logger.info("=" * 60)
                logger.info(f"📢 BROADCAST COMPLETE: business_id={business_id} broadcast_id={broadcast_id}")
                logger.info("✅ [BROADCAST] All recipients processed - broadcast complete")
                logger.info(f"  → Total processed: {broadcast.processed_count}")
                logger.info(f"  → Successfully sent: {broadcast.sent_count}")
                logger.info(f"  → Failed: {broadcast.failed_count}")
                logger.info(f"  → Cancelled: {broadcast.cancelled_count}")
                logger.info("=" * 60)
                
                broadcast.status = 'completed'
                broadcast.completed_at = datetime.utcnow()
                broadcast.updated_at = datetime.utcnow()
                db.session.commit()
                    
                # Release BulkGate lock
                _release_bulk_gate_lock(business_id)
                    
                return {
                    "success": True,
                    "message": "Broadcast completed successfully",
                    "total": broadcast.total_recipients,
                    "sent": broadcast.sent_count,
                    "failed": broadcast.failed_count,
                    "cancelled": broadcast.cancelled_count
                }
                
            # Process batch
            batch_start = time.time()
            batch_succeeded = 0
            batch_failed = 0
                
            try:
                # Process recipients using existing broadcast worker
                for recipient in recipients:
                    try:
                        # Mark as processing
                        recipient.status = 'processing'
                        db.session.commit()
                            
                        # Use existing worker processing logic
                        worker = BroadcastWorker(broadcast_id)
                        worker.broadcast = broadcast  # Set the broadcast object
                        worker._process_recipient(recipient, broadcast.processed_count + 1, broadcast.total_recipients)
                            
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
                        db.session.commit()
                    
                # Update cursor to last processed ID
                max_id = max(r.id for r in recipients)
                broadcast.last_processed_recipient_id = max_id
                    
                # Update progress counters
                broadcast.processed_count += len(recipients)
                broadcast.sent_count += batch_succeeded
                broadcast.failed_count += batch_failed
                broadcast.updated_at = datetime.utcnow()
                    
                # Commit DB changes
                db.session.commit()
                    
                # Reset consecutive failures on successful batch
                if batch_failed == 0:
                    consecutive_failures = 0
                
                # Calculate progress percentage
                progress_percent = (broadcast.processed_count / broadcast.total_recipients * 100) if broadcast.total_recipients > 0 else 0
                    
                logger.info(
                    f"  ✓ [BROADCAST] Batch complete: {batch_succeeded} sent, {batch_failed} failed "
                    f"({broadcast.processed_count}/{broadcast.total_recipients} = {progress_percent:.1f}%) in {time.time() - batch_start:.2f}s"
                )
                    
            except Exception as e:
                logger.error(f"[BROADCAST] Batch processing failed: {e}", exc_info=True)
                consecutive_failures += 1
                broadcast.failed_count += len(recipients)
                broadcast.updated_at = datetime.utcnow()
                db.session.rollback()
                db.session.commit()
                    
                # Check if we should stop due to repeated failures
                if consecutive_failures >= MAX_BATCH_FAILURES:
                    logger.error(f"❌ [BROADCAST] Too many consecutive failures ({consecutive_failures}) - stopping broadcast")
                    broadcast.status = 'failed'
                    broadcast.completed_at = datetime.utcnow()
                    db.session.commit()
                    
                    # Release BulkGate lock
                    _release_bulk_gate_lock(business_id)
                    
                    return {
                        "success": False,
                        "error": f"Broadcast failed after {consecutive_failures} consecutive batch failures"
                    }
                
            # Throttle between batches
            time.sleep(THROTTLE_MS / 1000.0)
        
    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"📢 BROADCAST FAILED: business_id={business_id} broadcast_id={broadcast_id}")
        logger.error(f"[BROADCAST] Broadcast failed with unexpected error: {e}", exc_info=True)
        logger.error("=" * 60)
        
        broadcast.status = 'failed'
        broadcast.completed_at = datetime.utcnow()
        broadcast.updated_at = datetime.utcnow()
        db.session.commit()
            
        # Release BulkGate lock even on failure
        _release_bulk_gate_lock(business_id)
            
        return {
            "success": False,
            "error": str(e)
        }


def _release_bulk_gate_lock(business_id: int):
    """
    Helper function to release BulkGate lock for a business
    
    Args:
        business_id: Business ID to release lock for
    """
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
                logger.info(f"✅ Released BulkGate lock for business_id={business_id}")
    except Exception as e:
        logger.warning(f"Failed to release BulkGate lock for business_id={business_id}: {e}")
