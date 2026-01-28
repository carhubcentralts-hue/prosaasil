"""
Outbound Queue Worker - Complete Implementation
Handles outbound call processing with:
- Idempotent job claiming (atomic DB locks)
- Crash recovery (stale lock detection)
- Cancel support (checks before each operation)
- Business isolation (enforced on all queries)
- Cursor persistence (resume from last position)
"""
import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Optional, Tuple
from sqlalchemy import text

logger = logging.getLogger(__name__)

# Lock timeout - jobs locked longer than this are considered stale
LOCK_TIMEOUT_MINUTES = 5

# Heartbeat interval - worker updates this periodically
HEARTBEAT_INTERVAL_SECONDS = 30


def claim_outbound_run(business_id: int, worker_id: str) -> Optional[int]:
    """
    Atomically claim an outbound run for processing.
    
    Uses UPDATE ... WHERE ... RETURNING for atomic lock acquisition.
    Only claims runs that are:
    - In 'pending' or 'paused' status
    - Belong to the business
    - Not locked by another worker
    - OR locked but stale (lock_ts > LOCK_TIMEOUT_MINUTES ago)
    
    Args:
        business_id: Business ID for isolation
        worker_id: Unique worker identifier
    
    Returns:
        run_id if claimed successfully, None if no work available
    """
    from server.models_sql import db, OutboundCallRun
    from flask import current_app
    
    with current_app.app_context():
        try:
            now = datetime.utcnow()
            stale_threshold = now - timedelta(minutes=LOCK_TIMEOUT_MINUTES)
            
            # 🔒 ATOMIC CLAIM: Update and return in single query
            # This prevents race conditions where two workers claim the same run
            result = db.session.execute(
                text("""
                    UPDATE outbound_call_runs
                    SET 
                        locked_by_worker = :worker_id,
                        lock_ts = :now,
                        last_heartbeat_at = :now,
                        status = 'running'
                    WHERE id = (
                        SELECT id FROM outbound_call_runs
                        WHERE business_id = :business_id
                        AND status IN ('pending', 'paused')
                        AND (
                            locked_by_worker IS NULL
                            OR lock_ts < :stale_threshold
                        )
                        AND cancel_requested = FALSE
                        ORDER BY created_at ASC
                        LIMIT 1
                        FOR UPDATE SKIP LOCKED
                    )
                    RETURNING id
                """),
                {
                    'worker_id': worker_id,
                    'now': now,
                    'business_id': business_id,
                    'stale_threshold': stale_threshold
                }
            )
            
            row = result.fetchone()
            db.session.commit()
            
            if row:
                run_id = row[0]
                logger.info(f"[OUTBOUND-CLAIM] ✅ Claimed run {run_id} for worker {worker_id}")
                return run_id
            else:
                logger.debug(f"[OUTBOUND-CLAIM] No work available for business {business_id}")
                return None
                
        except Exception as e:
            logger.error(f"[OUTBOUND-CLAIM] ❌ Error claiming run: {e}", exc_info=True)
            db.session.rollback()
            return None


def update_heartbeat(run_id: int, worker_id: str) -> bool:
    """
    Update worker heartbeat for a run.
    
    Args:
        run_id: Run ID
        worker_id: Worker ID that owns the lock
    
    Returns:
        True if heartbeat updated, False if lock lost
    """
    from server.models_sql import db, OutboundCallRun
    from flask import current_app
    
    with current_app.app_context():
        try:
            now = datetime.utcnow()
            
            # Only update if we still own the lock
            result = db.session.execute(
                text("""
                    UPDATE outbound_call_runs
                    SET last_heartbeat_at = :now
                    WHERE id = :run_id
                    AND locked_by_worker = :worker_id
                    RETURNING id
                """),
                {
                    'now': now,
                    'run_id': run_id,
                    'worker_id': worker_id
                }
            )
            
            row = result.fetchone()
            db.session.commit()
            
            if row:
                logger.debug(f"[OUTBOUND-HEARTBEAT] ✅ Updated for run {run_id}")
                return True
            else:
                logger.warning(f"[OUTBOUND-HEARTBEAT] ⚠️ Lost lock on run {run_id}")
                return False
                
        except Exception as e:
            logger.error(f"[OUTBOUND-HEARTBEAT] ❌ Error: {e}")
            db.session.rollback()
            return False


def check_if_cancelled(run_id: int) -> bool:
    """
    Check if run has been cancelled.
    
    Args:
        run_id: Run ID to check
    
    Returns:
        True if cancelled, False otherwise
    """
    from server.models_sql import db, OutboundCallRun
    from flask import current_app
    
    with current_app.app_context():
        try:
            run = OutboundCallRun.query.filter_by(id=run_id).first()
            if run and run.cancel_requested:
                logger.info(f"[OUTBOUND-CANCEL] ✅ Run {run_id} has been cancelled")
                return True
            return False
        except Exception as e:
            logger.error(f"[OUTBOUND-CANCEL] ❌ Error checking cancel: {e}")
            return False


def claim_next_job(run_id: int, business_id: int) -> Optional[Tuple[int, int, str]]:
    """
    Atomically claim next job in the run.
    
    Args:
        run_id: Run ID
        business_id: Business ID for isolation
    
    Returns:
        Tuple of (job_id, lead_id, phone) if claimed, None otherwise
    """
    from server.models_sql import db, OutboundCallJob, Lead
    from flask import current_app
    
    with current_app.app_context():
        try:
            # 🔒 ATOMIC CLAIM: Use dial_lock_token for idempotency
            lock_token = str(uuid.uuid4())
            now = datetime.utcnow()
            
            result = db.session.execute(
                text("""
                    UPDATE outbound_call_jobs
                    SET 
                        dial_lock_token = :lock_token,
                        dial_started_at = :now,
                        status = 'dialing'
                    WHERE id = (
                        SELECT ocj.id
                        FROM outbound_call_jobs ocj
                        INNER JOIN leads l ON ocj.lead_id = l.id
                        WHERE ocj.run_id = :run_id
                        AND ocj.business_id = :business_id
                        AND ocj.status = 'queued'
                        AND ocj.dial_lock_token IS NULL
                        AND l.phone_e164 IS NOT NULL
                        ORDER BY ocj.id ASC
                        LIMIT 1
                        FOR UPDATE SKIP LOCKED
                    )
                    RETURNING id, lead_id
                """),
                {
                    'lock_token': lock_token,
                    'now': now,
                    'run_id': run_id,
                    'business_id': business_id
                }
            )
            
            row = result.fetchone()
            
            if row:
                job_id, lead_id = row[0], row[1]
                
                # Get phone number
                lead = Lead.query.filter_by(
                    id=lead_id,
                    tenant_id=business_id  # 🔒 BUSINESS ISOLATION
                ).first()
                
                if lead and lead.phone_e164:
                    db.session.commit()
                    logger.info(f"[OUTBOUND-JOB] ✅ Claimed job {job_id} for lead {lead_id}")
                    return (job_id, lead_id, lead.phone_e164)
                else:
                    # No valid phone, mark as failed
                    db.session.rollback()
                    return None
            else:
                db.session.commit()
                return None
                
        except Exception as e:
            logger.error(f"[OUTBOUND-JOB] ❌ Error claiming job: {e}", exc_info=True)
            db.session.rollback()
            return None


def update_cursor_position(run_id: int, position: int):
    """
    Update cursor position for resume capability.
    
    Args:
        run_id: Run ID
        position: New cursor position (jobs processed so far)
    """
    from server.models_sql import db, OutboundCallRun
    from flask import current_app
    
    with current_app.app_context():
        try:
            db.session.execute(
                text("""
                    UPDATE outbound_call_runs
                    SET cursor_position = :position
                    WHERE id = :run_id
                """),
                {
                    'position': position,
                    'run_id': run_id
                }
            )
            db.session.commit()
        except Exception as e:
            logger.error(f"[OUTBOUND-CURSOR] ❌ Error updating cursor: {e}")
            db.session.rollback()


def release_lock(run_id: int, worker_id: str, final_status: str = 'completed'):
    """
    Release lock on run and set final status.
    
    Args:
        run_id: Run ID
        worker_id: Worker ID that owns the lock
        final_status: Final status ('completed', 'failed', 'cancelled')
    """
    from server.models_sql import db, OutboundCallRun
    from flask import current_app
    
    with current_app.app_context():
        try:
            now = datetime.utcnow()
            
            db.session.execute(
                text("""
                    UPDATE outbound_call_runs
                    SET 
                        locked_by_worker = NULL,
                        lock_ts = NULL,
                        status = :status,
                        finished_at = :now
                    WHERE id = :run_id
                    AND locked_by_worker = :worker_id
                """),
                {
                    'status': final_status,
                    'now': now,
                    'run_id': run_id,
                    'worker_id': worker_id
                }
            )
            db.session.commit()
            logger.info(f"[OUTBOUND-RELEASE] ✅ Released run {run_id} with status {final_status}")
        except Exception as e:
            logger.error(f"[OUTBOUND-RELEASE] ❌ Error releasing lock: {e}")
            db.session.rollback()


def recover_stale_runs(business_id: int):
    """
    Recover runs with stale locks (crashed workers).
    
    Marks runs as 'paused' so they can be reclaimed.
    
    Args:
        business_id: Business ID for isolation
    """
    from server.models_sql import db
    from flask import current_app
    
    with current_app.app_context():
        try:
            now = datetime.utcnow()
            stale_threshold = now - timedelta(minutes=LOCK_TIMEOUT_MINUTES)
            
            result = db.session.execute(
                text("""
                    UPDATE outbound_call_runs
                    SET 
                        status = 'paused',
                        locked_by_worker = NULL,
                        lock_ts = NULL
                    WHERE business_id = :business_id
                    AND status = 'running'
                    AND lock_ts < :stale_threshold
                    RETURNING id
                """),
                {
                    'business_id': business_id,
                    'stale_threshold': stale_threshold
                }
            )
            
            recovered = result.fetchall()
            db.session.commit()
            
            if recovered:
                run_ids = [r[0] for r in recovered]
                logger.warning(f"[OUTBOUND-RECOVERY] ⚠️ Recovered stale runs: {run_ids}")
            
        except Exception as e:
            logger.error(f"[OUTBOUND-RECOVERY] ❌ Error recovering runs: {e}")
            db.session.rollback()
