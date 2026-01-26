"""
Outbound Calls Semaphore System
================================

Per-business 3-concurrent-calls limit using Redis.

Redis Keys:
- outbound_slots:{business_id} - SET of active job_id (not counter)
- outbound_inflight:{business_id}:{job_id} - STRING with TTL 600s (call duration + overhead)
- outbound_queued:{business_id} - SET of job_ids waiting in queue
- outbound_queue:{business_id} - FIFO LIST of waiting job_ids (RPUSH/LPOP)
"""
import logging
import os
from typing import Optional, Tuple

logger = logging.getLogger(__name__)
log = logging.getLogger("outbound_semaphore")

# Max concurrent outbound calls per business
MAX_CONCURRENT_OUTBOUND_PER_BUSINESS = 3

# TTL values
INFLIGHT_TTL = 600  # 10 minutes - typical call duration + overhead
QUEUED_TTL = 3600   # 1 hour - prevents memory leak if queue never processes

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
            logger.info("✅ [OUTBOUND_SEM] Redis semaphore system enabled")
        else:
            logger.warning("⚠️ [OUTBOUND_SEM] REDIS_URL not set - semaphore system disabled")
    except Exception as e:
        logger.error(f"❌ [OUTBOUND_SEM] Redis initialization failed: {e}")
        REDIS_ENABLED = False


def try_acquire_slot(business_id: int, job_id: int) -> Tuple[bool, str]:
    """
    Try to acquire a call slot for this business.
    
    Uses atomic Redis operations to prevent race conditions.
    Enforces hard limit of MAX_CONCURRENT_OUTBOUND_PER_BUSINESS calls.
    
    Returns:
        (acquired: bool, status: str)
        - (True, "acquired") - Slot acquired, can start call
        - (False, "queued") - No slots available, added to queue
        - (False, "inflight") - Already processing this job_id
        - (False, "already_queued") - Already in queue
    """
    if not REDIS_ENABLED or not _redis_client:
        # Fallback: allow call without Redis
        logger.warning("[OUTBOUND_SEM] Redis not available, allowing call without limit enforcement")
        return True, "no_redis"
    
    try:
        # 🔥 FIX: Clean up expired slots first (frees stuck slots)
        cleanup_expired_slots(business_id)
        
        inflight_key = f"outbound_inflight:{business_id}:{job_id}"
        queued_set_key = f"outbound_queued:{business_id}"
        
        # Check 1: Is this job already in flight?
        if _redis_client.exists(inflight_key):
            ttl = _redis_client.ttl(inflight_key)
            log.debug(f"[OUTBOUND_SEM] Job {job_id} already inflight (TTL: {ttl}s)")
            return False, "inflight"
        
        # Check 2: Is this job already in queue?
        if _redis_client.sismember(queued_set_key, str(job_id)):
            log.debug(f"[OUTBOUND_SEM] Job {job_id} already in queue")
            return False, "already_queued"
        
        # Check 3: Try to acquire slot atomically using Lua script
        slots_key = f"outbound_slots:{business_id}"
        queue_list_key = f"outbound_queue:{business_id}"
        
        # Lua script for atomic slot acquisition using SET
        # 🔥 ATOMIC: Both SADD and SETEX happen in same transaction
        # Returns 1 if slot acquired, 0 if all slots busy
        lua_script = """
        local slots_key = KEYS[1]
        local inflight_key = KEYS[2]
        local job_id = ARGV[1]
        local max_slots = tonumber(ARGV[2])
        local inflight_ttl = tonumber(ARGV[3])
        local current = redis.call('SCARD', slots_key)
        
        if current < max_slots then
            -- Atomically add to slots and mark as inflight
            redis.call('SADD', slots_key, job_id)
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
            str(job_id), 
            MAX_CONCURRENT_OUTBOUND_PER_BUSINESS,
            INFLIGHT_TTL
        )
        
        if acquired == 1:
            # Slot acquired! (inflight already marked by Lua script)
            current_slots = int(_redis_client.scard(slots_key) or 0)
            logger.info(f"📞 OUTBOUND_ENQUEUE business_id={business_id} job_id={job_id} active={current_slots}/{MAX_CONCURRENT_OUTBOUND_PER_BUSINESS}")
            return True, "acquired"
        else:
            # No slots available - add to queue atomically
            # Use Lua to add to both SET and LIST atomically
            lua_queue_script = """
            local queued_set = KEYS[1]
            local queue_list = KEYS[2]
            local job_id = ARGV[1]
            local ttl = tonumber(ARGV[2])
            
            -- Check if already in set (double-check)
            if redis.call('SISMEMBER', queued_set, job_id) == 1 then
                return 0
            end
            
            -- Add to set with TTL (cleanup if never processed)
            redis.call('SADD', queued_set, job_id)
            redis.call('EXPIRE', queued_set, ttl)
            
            -- Add to list (FIFO)
            redis.call('RPUSH', queue_list, job_id)
            
            -- Get queue length
            local queue_len = redis.call('LLEN', queue_list)
            return queue_len
            """
            
            queue_len = _redis_client.eval(
                lua_queue_script, 
                2, 
                queued_set_key, 
                queue_list_key, 
                str(job_id),
                QUEUED_TTL
            )
            
            if queue_len == 0:
                # Already in queue
                return False, "already_queued"
            
            current_slots = int(_redis_client.scard(slots_key) or 0)
            logger.info(f"⏳ OUTBOUND_QUEUED business_id={business_id} job_id={job_id} active={current_slots}/{MAX_CONCURRENT_OUTBOUND_PER_BUSINESS} queue_len={queue_len}")
            return False, "queued"
            
    except Exception as e:
        logger.error(f"[OUTBOUND_SEM] Error acquiring slot: {e}")
        import traceback
        traceback.print_exc()
        # On error, allow call (fail-open)
        return True, "error_fallback"


def release_slot(business_id: int, job_id: int) -> Optional[int]:
    """
    Release a call slot and atomically get next job_id from queue.
    
    🔥 CRITICAL: Must be atomic to prevent race conditions.
    Uses Lua script to release slot and pop next job in single transaction.
    
    This is called in the finally block after call completes.
    
    Returns:
        next_job_id if there's work waiting, None otherwise
    """
    if not REDIS_ENABLED or not _redis_client:
        return None
    
    try:
        slots_key = f"outbound_slots:{business_id}"
        inflight_key = f"outbound_inflight:{business_id}:{job_id}"
        queued_set_key = f"outbound_queued:{business_id}"
        queue_list_key = f"outbound_queue:{business_id}"
        
        # 🔥 ATOMIC: Release slot + pop next from queue using Lua script
        lua_release_script = """
        local slots_key = KEYS[1]
        local inflight_key = KEYS[2]
        local queued_set = KEYS[3]
        local queue_list = KEYS[4]
        local job_id = ARGV[1]
        local inflight_ttl = tonumber(ARGV[2])
        local business_id = ARGV[3]
        
        -- Step 1: Remove from slots SET
        redis.call('SREM', slots_key, job_id)
        local current = redis.call('SCARD', slots_key)
        
        -- Step 2: Remove inflight marker
        redis.call('DEL', inflight_key)
        
        -- Step 3: Try to get next from queue
        local next_job_id = redis.call('LPOP', queue_list)
        
        if next_job_id then
            -- Step 4: Remove from queued set
            redis.call('SREM', queued_set, next_job_id)
            
            -- Step 5: Add next to slots SET
            redis.call('SADD', slots_key, next_job_id)
            
            -- Step 6: Mark next as inflight
            local next_inflight_key = 'outbound_inflight:' .. business_id .. ':' .. next_job_id
            redis.call('SETEX', next_inflight_key, inflight_ttl, 'processing')
            
            -- Return: [current_slots_after_release, next_job_id, new_slots_after_acquire]
            local new_count = redis.call('SCARD', slots_key)
            return {current, next_job_id, new_count}
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
            str(job_id),
            INFLIGHT_TTL,
            str(business_id)
        )
        
        slots_after_release = result[0]
        next_job_id = result[1] if len(result) > 1 and result[1] else None
        slots_after_acquire = result[2] if len(result) > 2 else slots_after_release
        
        if next_job_id:
            # Convert to int
            next_job_id = int(next_job_id)
            logger.info(f"✅ OUTBOUND_DONE business_id={business_id} job_id={job_id} active={slots_after_release}/{MAX_CONCURRENT_OUTBOUND_PER_BUSINESS}")
            logger.info(f"➡️ OUTBOUND_NEXT business_id={business_id} job_id={next_job_id} active={slots_after_acquire}/{MAX_CONCURRENT_OUTBOUND_PER_BUSINESS}")
            return next_job_id
        else:
            logger.info(f"✅ OUTBOUND_DONE business_id={business_id} job_id={job_id} active={slots_after_release}/{MAX_CONCURRENT_OUTBOUND_PER_BUSINESS}")
            return None
        
    except Exception as e:
        logger.error(f"[OUTBOUND_SEM] Error releasing slot: {e}")
        import traceback
        traceback.print_exc()
        return None


def cleanup_expired_slots(business_id: int) -> int:
    """
    🔥 FIX: Clean up expired inflight markers that didn't get properly released.
    
    This can happen if:
    - Worker crashed during call
    - Network issues caused call to hang
    - Redis TTL expired but slot wasn't released
    
    Uses Lua script for atomic batch cleanup of all expired slots.
    
    Returns:
        Number of slots cleaned up
    """
    if not REDIS_ENABLED or not _redis_client:
        return 0
    
    try:
        slots_key = f"outbound_slots:{business_id}"
        
        # 🔥 OPTIMIZATION: Use Lua script for atomic batch cleanup
        lua_cleanup_script = """
        local slots_key = KEYS[1]
        local business_id = ARGV[1]
        
        -- Get all job_ids in slots
        local job_ids = redis.call('SMEMBERS', slots_key)
        local cleaned = 0
        
        for _, job_id in ipairs(job_ids) do
            local inflight_key = 'outbound_inflight:' .. business_id .. ':' .. job_id
            
            -- Check if inflight marker still exists
            if redis.call('EXISTS', inflight_key) == 0 then
                -- Inflight marker expired/missing but slot still occupied
                -- Remove from slots (this frees the slot)
                redis.call('SREM', slots_key, job_id)
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
            logger.warning(f"🧹 [OUTBOUND_SEM] Cleaned {cleaned} expired slots for business {business_id}, active={current_slots}/{MAX_CONCURRENT_OUTBOUND_PER_BUSINESS}")
        
        return cleaned
        
    except Exception as e:
        logger.error(f"[OUTBOUND_SEM] Error during cleanup: {e}")
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
        return {"active": 0, "max": MAX_CONCURRENT_OUTBOUND_PER_BUSINESS, "available": MAX_CONCURRENT_OUTBOUND_PER_BUSINESS}
    
    try:
        slots_key = f"outbound_slots:{business_id}"
        active = int(_redis_client.scard(slots_key) or 0)
        available = MAX_CONCURRENT_OUTBOUND_PER_BUSINESS - active
        
        return {
            "active": active,
            "max": MAX_CONCURRENT_OUTBOUND_PER_BUSINESS,
            "available": available
        }
    except Exception as e:
        logger.error(f"[OUTBOUND_SEM] Error getting slot status: {e}")
        return {"active": 0, "max": MAX_CONCURRENT_OUTBOUND_PER_BUSINESS, "available": MAX_CONCURRENT_OUTBOUND_PER_BUSINESS}


# Initialize Redis on module import
init_redis()
