"""
Gmail Receipts Sync Job
Background job for syncing receipts from Gmail

Features:
- Redis lock per business (prevents concurrent syncs)
- Heartbeat mechanism to prevent stale runs
- Progress tracking
- Automatic recovery from failures
"""
import os
import logging
import time
import redis
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# Redis connection
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
redis_conn = redis.from_url(REDIS_URL)

# Lock configuration
LOCK_TTL = 3600  # 1 hour - max sync duration
HEARTBEAT_INTERVAL = 30  # Update heartbeat every 30 seconds

def sync_gmail_receipts_job(
    business_id: int,
    mode: str = 'incremental',
    max_messages: Optional[int] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    months_back: int = 36
):
    """
    Background job for syncing Gmail receipts
    
    This runs in a separate worker process and:
    1. Acquires a Redis lock for the business
    2. Fetches emails from Gmail
    3. Processes attachments and generates previews
    4. Updates heartbeat periodically
    5. Releases lock on completion
    
    Args:
        business_id: Business ID to sync for
        mode: 'incremental' or 'full_backfill'
        max_messages: Optional limit on messages to process
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        months_back: Months to go back for full backfill
    """
    from server.models_sql import db, ReceiptSyncRun
    from server.services.gmail_sync_service import sync_gmail_receipts
    
    lock_key = f"receipt_sync_lock:{business_id}"
    
    # Try to acquire lock
    lock_acquired = redis_conn.set(lock_key, "locked", nx=True, ex=LOCK_TTL)
    
    if not lock_acquired:
        logger.warning(f"Could not acquire lock for business {business_id} - sync already running")
        return {
            "success": False,
            "error": "Sync already in progress for this business"
        }
    
    try:
        logger.info(f"🔔 JOB START: Gmail sync for business_id={business_id}, mode={mode}")
        
        # Create sync run record
        sync_run = ReceiptSyncRun(
            business_id=business_id,
            mode=mode,
            status='running',
            started_at=datetime.now(timezone.utc),
            last_heartbeat_at=datetime.now(timezone.utc)
        )
        db.session.add(sync_run)
        db.session.commit()
        
        # Heartbeat updater function
        last_heartbeat = time.time()
        
        def update_heartbeat():
            """Update heartbeat if enough time has passed"""
            nonlocal last_heartbeat
            now = time.time()
            if now - last_heartbeat >= HEARTBEAT_INTERVAL:
                try:
                    sync_run.last_heartbeat_at = datetime.now(timezone.utc)
                    db.session.commit()
                    last_heartbeat = now
                    # Refresh lock TTL
                    redis_conn.expire(lock_key, LOCK_TTL)
                except Exception as e:
                    logger.error(f"Failed to update heartbeat: {e}")
        
        # Call the actual sync service with heartbeat callback (if supported)
        # Note: heartbeat_callback is optional - only used if sync service supports it
        try:
            result = sync_gmail_receipts(
                business_id=business_id,
                mode=mode,
                max_messages=max_messages,
                from_date=from_date,
                to_date=to_date,
                months_back=months_back,
                heartbeat_callback=update_heartbeat
            )
        except TypeError:
            # Fallback if heartbeat_callback not supported
            logger.warning("sync_gmail_receipts doesn't support heartbeat_callback, using without it")
            result = sync_gmail_receipts(
                business_id=business_id,
                mode=mode,
                max_messages=max_messages,
                from_date=from_date,
                to_date=to_date,
                months_back=months_back
            )
        
        # Update sync run with results
        sync_run.status = 'completed'
        sync_run.finished_at = datetime.now(timezone.utc)
        sync_run.messages_scanned = result.get('messages_scanned', 0)
        sync_run.saved_receipts = result.get('saved_receipts', 0)
        sync_run.errors_count = result.get('errors_count', 0)
        db.session.commit()
        
        logger.info(
            f"🔔 JOB COMPLETE: Gmail sync for business_id={business_id}, "
            f"scanned={result.get('messages_scanned', 0)}, "
            f"saved={result.get('saved_receipts', 0)}"
        )
        
        return {
            "success": True,
            "messages_scanned": result.get('messages_scanned', 0),
            "saved_receipts": result.get('saved_receipts', 0),
            "errors_count": result.get('errors_count', 0)
        }
        
    except Exception as e:
        logger.error(f"🔔 JOB FAILED: Gmail sync for business_id={business_id}: {e}", exc_info=True)
        
        # Update sync run status
        try:
            sync_run.status = 'failed'
            sync_run.error_message = str(e)[:500]
            sync_run.finished_at = datetime.now(timezone.utc)
            db.session.commit()
        except Exception as update_error:
            logger.error(f"Failed to update sync run status: {update_error}")
        
        raise
    
    finally:
        # Always release lock
        try:
            redis_conn.delete(lock_key)
            logger.info(f"Released lock for business {business_id}")
        except Exception as e:
            logger.error(f"Failed to release lock: {e}")
