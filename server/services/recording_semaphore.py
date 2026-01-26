"""
Recording Processing Semaphore System
======================================

Per-business 3-concurrent-processing limit using Redis.
Uses RecordingRun.id (run_id) as the unique identifier.

Redis Keys:
- rec_slots:{business_id} - SET of active run_id (not counter)
- rec_inflight:{business_id}:{run_id} - STRING with TTL 900s (processing marker)
- rec_queued:{business_id} - SET of run_ids waiting in queue
- rec_queue:{business_id} - FIFO LIST of waiting run_ids (RPUSH/LPOP)
"""
import logging
import os
from typing import Optional, Tuple

logger = logging.getLogger(__name__)
log = logging.getLogger("recording_semaphore")

# Max concurrent recordings per business
MAX_SLOTS_PER_BUSINESS = 3

# TTL values
INFLIGHT_TTL = 900  # 15 minutes - must be > max processing time
QUEUED_TTL = 1200  # 20 minutes - prevents re-adding to queue

# Redis client (initialized in init_redis)
_redis_client = None
REDIS_ENABLED = False


def init_redis():
    """Initialize Redis connection for semaphore system"""
    global _redis_client, REDIS_ENABLED
    
    try:
        import redis
        REDIS_URL = os.getenv('REDIS_URL')
        if REDIS_URL:
            _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
            _redis_client.ping()
            REDIS_ENABLED = True
            logger.info("✅ [RECORDING_SEM] Redis semaphore system enabled")
        else:
            logger.warning("⚠️ [RECORDING_SEM] REDIS_URL not set - semaphore system disabled")
    except Exception as e:
        logger.error(f"❌ [RECORDING_SEM] Redis initialization failed: {e}")
        REDIS_ENABLED = False


def acquire_slot(business_id: int, run_id: int) -> Tuple[bool, str]:
    """
    Try to acquire a processing slot for this business.
    
    Uses atomic Redis operations to prevent race conditions.
    Enforces hard limit of MAX_SLOTS_PER_BUSINESS concurrent recordings.
    
    Args:
        business_id: Business ID
        run_id: RecordingRun.id (unique identifier)
    
    Returns:
        (acquired: bool, status: str)
        - (True, "acquired") - Slot acquired, can process
        - (False, "queued") - No slots available, added to queue
        - (False, "inflight") - Already processing this run_id
        - (False, "already_queued") - Already in queue
    """
    if not REDIS_ENABLED or not _redis_client:
        # Fallback: allow processing without Redis
        logger.warning("[RECORDING_SEM] Redis not available, allowing without limit")
        return True, "no_redis"
    
    try:
        # 🔥 FIX: Clean up expired slots first (frees stuck slots)
        cleanup_expired_slots(business_id)
        
        inflight_key = f"rec_inflight:{business_id}:{run_id}"
        queued_set_key = f"rec_queued:{business_id}"
        
        # Check 1: Is this run_id already in flight?
        if _redis_client.exists(inflight_key):
            ttl = _redis_client.ttl(inflight_key)
            log.debug(f"[RECORDING_SEM] Run {run_id} already inflight (TTL: {ttl}s)")
            return False, "inflight"
        
        # Check 2: Is this run_id already in queue?
        if _redis_client.sismember(queued_set_key, str(run_id)):
            log.debug(f"[RECORDING_SEM] Run {run_id} already in queue")
            return False, "already_queued"
        
        # Check 3: Try to acquire slot atomically using Lua script
        slots_key = f"rec_slots:{business_id}"
        queue_list_key = f"rec_queue:{business_id}"
        
        # Lua script for atomic slot acquisition using SET
        # 🔥 ATOMIC: Both SADD and SETEX happen in same transaction
        # Returns 1 if slot acquired, 0 if all slots busy
        lua_script = """
        local slots_key = KEYS[1]
        local inflight_key = KEYS[2]
        local run_id = ARGV[1]
        local max_slots = tonumber(ARGV[2])
        local inflight_ttl = tonumber(ARGV[3])
        local current = redis.call('SCARD', slots_key)
        
        if current < max_slots then
            -- Atomically add to slots and mark as inflight
            redis.call('SADD', slots_key, run_id)
            redis.call('SETEX', inflight_key, inflight_ttl, 'processing')
            return 1
        else
            return 0
        end
        """
        
        # Execute atomic slot acquisition + inflight marking
        acquired = _redis_client.eval(
            lua_script, 
            2,  # 2 keys
            slots_key, 
            inflight_key,
            str(run_id), 
            MAX_SLOTS_PER_BUSINESS,
            INFLIGHT_TTL
        )
        
        if acquired == 1:
            # Slot acquired! (inflight already marked by Lua script)
            current_slots = int(_redis_client.scard(slots_key) or 0)
            logger.info(f"🎧 RECORDING_ENQUEUE business_id={business_id} run_id={run_id} active={current_slots}/{MAX_SLOTS_PER_BUSINESS}")
            return True, "acquired"
        else:
            # No slots available - add to queue atomically
            lua_queue_script = """
            local queued_set = KEYS[1]
            local queue_list = KEYS[2]
            local run_id = ARGV[1]
            local ttl = tonumber(ARGV[2])
            
            -- Check if already in set (double-check)
            if redis.call('SISMEMBER', queued_set, run_id) == 1 then
                return 0
            end
            
            -- Add to set with TTL (cleanup if never processed)
            redis.call('SADD', queued_set, run_id)
            redis.call('EXPIRE', queued_set, ttl)
            
            -- Add to list (FIFO)
            redis.call('RPUSH', queue_list, run_id)
            
            -- Get queue length
            local queue_len = redis.call('LLEN', queue_list)
            return queue_len
            """
            
            queue_len = _redis_client.eval(
                lua_queue_script, 
                2, 
                queued_set_key, 
                queue_list_key, 
                str(run_id),
                QUEUED_TTL
            )
            
            if queue_len == 0:
                # Already in queue
                return False, "already_queued"
            
            current_slots = int(_redis_client.scard(slots_key) or 0)
            logger.info(f"⏳ RECORDING_QUEUED business_id={business_id} run_id={run_id} active={current_slots}/{MAX_SLOTS_PER_BUSINESS} queue_len={queue_len}")
            return False, "queued"
            
    except Exception as e:
        logger.error(f"[RECORDING_SEM] Error acquiring slot: {e}")
        import traceback
        traceback.print_exc()
        # On error, allow processing (fail-open)
        return True, "error_fallback"


def release_slot(business_id: int, run_id: int) -> Optional[int]:
    """
    Release a processing slot and atomically get next run_id from queue.
    
    🔥 CRITICAL: Must be atomic to prevent race conditions.
    Uses Lua script to release slot and pop next job in single transaction.
    
    This is called in the finally block after processing completes.
    
    Returns:
        next_run_id if there's work waiting, None otherwise
    """
    if not REDIS_ENABLED or not _redis_client:
        return None
    
    try:
        slots_key = f"rec_slots:{business_id}"
        inflight_key = f"rec_inflight:{business_id}:{run_id}"
        queued_set_key = f"rec_queued:{business_id}"
        queue_list_key = f"rec_queue:{business_id}"
        
        # 🔥 ATOMIC: Release slot + pop next from queue using Lua script
        lua_release_script = """
        local slots_key = KEYS[1]
        local inflight_key = KEYS[2]
        local queued_set = KEYS[3]
        local queue_list = KEYS[4]
        local run_id = ARGV[1]
        local inflight_ttl = tonumber(ARGV[2])
        local business_id = ARGV[3]
        
        -- Step 1: Remove from slots SET
        redis.call('SREM', slots_key, run_id)
        local current = redis.call('SCARD', slots_key)
        
        -- Step 2: Remove inflight marker
        redis.call('DEL', inflight_key)
        
        -- Step 3: Try to get next from queue
        local next_run_id = redis.call('LPOP', queue_list)
        
        if next_run_id then
            -- Step 4: Remove from queued set
            redis.call('SREM', queued_set, next_run_id)
            
            -- Step 5: Add next to slots SET
            redis.call('SADD', slots_key, next_run_id)
            
            -- Step 6: Mark next as inflight
            local next_inflight_key = 'rec_inflight:' .. business_id .. ':' .. next_run_id
            redis.call('SETEX', next_inflight_key, inflight_ttl, 'processing')
            
            -- Return: [current_slots_after_release, next_run_id, new_slots_after_acquire]
            local new_count = redis.call('SCARD', slots_key)
            return {current, next_run_id, new_count}
        else
            -- No work waiting
            return {current, nil, current}
        end
        """
        
        # Execute atomic release + pop next
        result = _redis_client.eval(
            lua_release_script,
            4,
            slots_key,
            inflight_key,
            queued_set_key,
            queue_list_key,
            str(run_id),
            INFLIGHT_TTL,
            str(business_id)
        )
        
        slots_after_release = result[0]
        next_run_id = result[1] if len(result) > 1 and result[1] else None
        slots_after_acquire = result[2] if len(result) > 2 else slots_after_release
        
        if next_run_id:
            # Convert to int
            next_run_id = int(next_run_id)
            logger.info(f"✅ RECORDING_DONE business_id={business_id} run_id={run_id} active={slots_after_release}/{MAX_SLOTS_PER_BUSINESS}")
            logger.info(f"➡️ RECORDING_NEXT business_id={business_id} run_id={next_run_id} active={slots_after_acquire}/{MAX_SLOTS_PER_BUSINESS}")
            return next_run_id
        else:
            logger.info(f"✅ RECORDING_DONE business_id={business_id} run_id={run_id} active={slots_after_release}/{MAX_SLOTS_PER_BUSINESS}")
            return None
        
    except Exception as e:
        logger.error(f"[RECORDING_SEM] Error releasing slot: {e}")
        import traceback
        traceback.print_exc()
        return None


def cleanup_expired_slots(business_id: int) -> int:
    """
    🔥 FIX: Clean up expired inflight markers that didn't get properly released.
    
    This can happen if:
    - Worker crashed during processing
    - Network issues caused processing to hang
    - Redis TTL expired but slot wasn't released
    
    Uses Lua script for atomic batch cleanup of all expired slots.
    
    Returns:
        Number of slots cleaned up
    """
    if not REDIS_ENABLED or not _redis_client:
        return 0
    
    try:
        slots_key = f"rec_slots:{business_id}"
        
        # 🔥 OPTIMIZATION: Use Lua script for atomic batch cleanup
        lua_cleanup_script = """
        local slots_key = KEYS[1]
        local business_id = ARGV[1]
        
        -- Get all run_ids in slots
        local run_ids = redis.call('SMEMBERS', slots_key)
        local cleaned = 0
        
        for _, run_id in ipairs(run_ids) do
            local inflight_key = 'rec_inflight:' .. business_id .. ':' .. run_id
            
            -- Check if inflight marker still exists
            if redis.call('EXISTS', inflight_key) == 0 then
                -- Inflight marker expired/missing but slot still occupied
                -- Remove from slots (this frees the slot)
                redis.call('SREM', slots_key, run_id)
                cleaned = cleaned + 1
            end
        end
        
        -- Return: [cleaned_count, current_slots_after_cleanup]
        local current = redis.call('SCARD', slots_key)
        return {cleaned, current}
        """
        
        result = _redis_client.eval(
            lua_cleanup_script,
            1,
            slots_key,
            str(business_id)
        )
        
        cleaned = int(result[0]) if result and len(result) > 0 else 0
        current_slots = int(result[1]) if result and len(result) > 1 else 0
        
        if cleaned > 0:
            logger.warning(f"🧹 [RECORDING_SEM] Cleaned {cleaned} expired slots for business {business_id}, active={current_slots}/{MAX_SLOTS_PER_BUSINESS}")
        
        return cleaned
        
    except Exception as e:
        logger.error(f"[RECORDING_SEM] Error during cleanup: {e}")
        return 0


def get_slot_status(business_id: int) -> dict:
    """
    Get current slot usage for a business.
    
    Returns:
        {
            "active": int,  # Number of active slots
            "max": int,     # Maximum slots
            "available": int  # Available slots
        }
    """
    if not REDIS_ENABLED or not _redis_client:
        return {"active": 0, "max": MAX_SLOTS_PER_BUSINESS, "available": MAX_SLOTS_PER_BUSINESS}
    
    try:
        slots_key = f"rec_slots:{business_id}"
        active = int(_redis_client.scard(slots_key) or 0)
        available = max(0, MAX_SLOTS_PER_BUSINESS - active)
        
        return {
            "active": active,
            "max": MAX_SLOTS_PER_BUSINESS,
            "available": available
        }
    except Exception as e:
        logger.error(f"[RECORDING_SEM] Error getting slot status: {e}")
        return {"active": 0, "max": MAX_SLOTS_PER_BUSINESS, "available": MAX_SLOTS_PER_BUSINESS}


def check_status(business_id: int, call_sid: str) -> tuple[str, dict]:
    """
    Check the status of a recording download request.
    
    🚫 DEPRECATED: This function is for backwards compatibility only.
    New code should use RecordingRun model to track job status.
    
    Args:
        business_id: Business ID
        call_sid: Call SID (NOTE: old API used call_sid, new system uses run_id)
    
    Returns:
        (status, info)
        - ("unknown", {}) - Status unknown (use RecordingRun instead)
    """
    logger.debug(f"[RECORDING_SEM] check_status called with call_sid (deprecated) - use RecordingRun model instead")
    
    # Try to find RecordingRun by call_sid
    try:
        from server.models_sql import RecordingRun
        from server.app_factory import get_process_app
        
        app = get_process_app()
        with app.app_context():
            run = RecordingRun.query.filter_by(
                business_id=business_id,
                call_sid=call_sid
            ).order_by(RecordingRun.created_at.desc()).first()
            
            if run:
                if run.status == 'running':
                    return "processing", {"run_id": run.id}
                elif run.status == 'queued':
                    return "queued", {"run_id": run.id}
                elif run.status == 'failed':
                    return "failed", {"run_id": run.id, "error": run.error_message}
                elif run.status == 'completed':
                    return "completed", {"run_id": run.id}
            
            return "unknown", {}
    except Exception as e:
        logger.error(f"[RECORDING_SEM] Error in check_status: {e}")
        return "unknown", {}


# Initialize Redis on module import
init_redis()
