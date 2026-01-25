"""
Recording Download Semaphore System
====================================

Per-business 3-concurrent-downloads limit using Redis.

Redis Keys:
- rec_slots:{business_id} - Counter of active downloads (0-3)
- rec_inflight:{business_id}:{call_sid} - Dedup lock (TTL 90s)
- rec_queued:{business_id} - SET of call_sids waiting in queue (TTL 20 min)
- rec_queue:{business_id} - FIFO LIST of waiting call_sids
"""
import logging
import os
from typing import Optional, Tuple

logger = logging.getLogger(__name__)
log = logging.getLogger("recording_semaphore")

# Max concurrent downloads per business
MAX_SLOTS_PER_BUSINESS = 3

# TTL values
INFLIGHT_TTL = 90  # 90 seconds - prevents double-clicks
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


def try_acquire_slot(business_id: int, call_sid: str) -> Tuple[bool, str]:
    """
    Try to acquire a download slot for this business.
    
    Uses atomic Redis operations to prevent race conditions.
    Checks both inflight and queued sets to prevent duplicates.
    
    Returns:
        (acquired: bool, status: str)
        - (True, "acquired") - Slot acquired, can download
        - (False, "queued") - No slots available, added to queue
        - (False, "inflight") - Already processing this call_sid
        - (False, "already_queued") - Already in queue
    """
    if not REDIS_ENABLED or not _redis_client:
        # Fallback: allow download without Redis
        return True, "no_redis"
    
    try:
        inflight_key = f"rec_inflight:{business_id}:{call_sid}"
        queued_set_key = f"rec_queued:{business_id}"
        
        # Check 1: Is this call_sid already in flight?
        if _redis_client.exists(inflight_key):
            ttl = _redis_client.ttl(inflight_key)
            log.debug(f"[RECORDING_SEM] Call {call_sid} already inflight (TTL: {ttl}s)")
            return False, "inflight"
        
        # Check 2: Is this call_sid already in queue?
        if _redis_client.sismember(queued_set_key, call_sid):
            log.debug(f"[RECORDING_SEM] Call {call_sid} already in queue")
            return False, "already_queued"
        
        # Check 3: Try to acquire slot atomically using Lua script
        slots_key = f"rec_slots:{business_id}"
        queue_list_key = f"rec_queue:{business_id}"
        
        # Lua script for atomic slot acquisition
        # Returns 1 if slot acquired, 0 if all slots busy
        lua_script = """
        local slots_key = KEYS[1]
        local max_slots = tonumber(ARGV[1])
        local current = tonumber(redis.call('GET', slots_key) or 0)
        
        if current < max_slots then
            redis.call('INCR', slots_key)
            return 1
        else
            return 0
        end
        """
        
        # Execute atomic slot acquisition
        acquired = _redis_client.eval(lua_script, 1, slots_key, MAX_SLOTS_PER_BUSINESS)
        
        if acquired == 1:
            # Slot acquired! Mark as inflight
            _redis_client.setex(inflight_key, INFLIGHT_TTL, "processing")
            
            # Get current count for logging
            current_slots = int(_redis_client.get(slots_key) or 0)
            logger.info(f"🎧 RECORDING_ENQUEUE bid={business_id} sid={call_sid[:8]}... slots={current_slots}/{MAX_SLOTS_PER_BUSINESS}")
            return True, "acquired"
        else:
            # No slots available - add to queue atomically
            # Use Lua to add to both SET and LIST atomically
            lua_queue_script = """
            local queued_set = KEYS[1]
            local queue_list = KEYS[2]
            local call_sid = ARGV[1]
            local ttl = tonumber(ARGV[2])
            
            -- Check if already in set (double-check)
            if redis.call('SISMEMBER', queued_set, call_sid) == 1 then
                return 0
            end
            
            -- Add to set with TTL
            redis.call('SADD', queued_set, call_sid)
            redis.call('EXPIRE', queued_set, ttl)
            
            -- Add to list (FIFO)
            redis.call('RPUSH', queue_list, call_sid)
            
            -- Get queue length
            local queue_len = redis.call('LLEN', queue_list)
            return queue_len
            """
            
            queue_len = _redis_client.eval(
                lua_queue_script, 
                2, 
                queued_set_key, 
                queue_list_key, 
                call_sid, 
                QUEUED_TTL
            )
            
            if queue_len == 0:
                # Already in queue
                return False, "already_queued"
            
            current_slots = int(_redis_client.get(slots_key) or 0)
            logger.info(f"⏳ RECORDING_QUEUED bid={business_id} sid={call_sid[:8]}... slots={current_slots}/{MAX_SLOTS_PER_BUSINESS} queue_len={queue_len}")
            return False, "queued"
            
    except Exception as e:
        logger.error(f"[RECORDING_SEM] Error acquiring slot: {e}")
        import traceback
        traceback.print_exc()
        # On error, allow download (fail-open)
        return True, "error_fallback"


def release_slot(business_id: int, call_sid: str) -> Optional[str]:
    """
    Release a download slot and atomically get next call_sid from queue.
    
    🔥 CRITICAL: Must be atomic to prevent race conditions.
    Uses Lua script to release slot and pop next job in single transaction.
    
    This is called by the WORKER (not API) in the finally block.
    
    Returns:
        next_call_sid if there's work waiting, None otherwise
    """
    if not REDIS_ENABLED or not _redis_client:
        return None
    
    try:
        slots_key = f"rec_slots:{business_id}"
        inflight_key = f"rec_inflight:{business_id}:{call_sid}"
        queued_set_key = f"rec_queued:{business_id}"
        queue_list_key = f"rec_queue:{business_id}"
        
        # 🔥 ATOMIC: Release slot + pop next from queue using Lua script
        # This prevents race conditions where multiple workers compete for slots
        lua_release_script = """
        local slots_key = KEYS[1]
        local inflight_key = KEYS[2]
        local queued_set = KEYS[3]
        local queue_list = KEYS[4]
        local inflight_ttl = tonumber(ARGV[1])
        
        -- Step 1: Remove inflight marker
        redis.call('DEL', inflight_key)
        
        -- Step 2: Decrement slots (with protection against negative)
        local current = tonumber(redis.call('GET', slots_key) or 0)
        if current > 0 then
            redis.call('DECR', slots_key)
            current = current - 1
        end
        
        -- Step 3: Try to get next from queue
        local next_sid = redis.call('LPOP', queue_list)
        
        if next_sid then
            -- Step 4: Remove from queued set
            redis.call('SREM', queued_set, next_sid)
            
            -- Step 5: Increment slots for next job
            redis.call('INCR', slots_key)
            
            -- Step 6: Mark next as inflight
            local next_inflight_key = 'rec_inflight:' .. ARGV[2] .. ':' .. next_sid
            redis.call('SETEX', next_inflight_key, inflight_ttl, 'processing')
            
            -- Return: [current_slots_after_release, next_sid, new_slots_after_acquire]
            return {current, next_sid, current + 1}
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
            INFLIGHT_TTL,
            str(business_id)  # Used to construct next_inflight_key
        )
        
        slots_after_release = result[0]
        next_sid = result[1] if len(result) > 1 and result[1] else None
        slots_after_acquire = result[2] if len(result) > 2 else slots_after_release
        
        if next_sid:
            logger.info(f"✅ RECORDING_DONE bid={business_id} sid={call_sid[:8]}... slots_now={slots_after_release}/{MAX_SLOTS_PER_BUSINESS}")
            logger.info(f"➡️ RECORDING_NEXT bid={business_id} next_sid={next_sid[:8]}... slots={slots_after_acquire}/{MAX_SLOTS_PER_BUSINESS}")
            return next_sid
        else:
            logger.info(f"✅ RECORDING_DONE bid={business_id} sid={call_sid[:8]}... slots_now={slots_after_release}/{MAX_SLOTS_PER_BUSINESS}")
            return None
        
    except Exception as e:
        logger.error(f"[RECORDING_SEM] Error releasing slot: {e}")
        import traceback
        traceback.print_exc()
        return None


def check_status(business_id: int, call_sid: str) -> Tuple[str, dict]:
    """
    Check the status of a recording download request.
    
    Returns:
        (status, info)
        - ("processing", {...}) - Download in progress
        - ("queued", {...}) - Waiting in queue
        - ("unknown", {...}) - Not found in system
    """
    if not REDIS_ENABLED or not _redis_client:
        return "unknown", {}
    
    try:
        # Check if inflight
        inflight_key = f"rec_inflight:{business_id}:{call_sid}"
        if _redis_client.exists(inflight_key):
            ttl = _redis_client.ttl(inflight_key)
            return "processing", {"ttl": ttl}
        
        # Check if in queue
        queue_key = f"rec_queue:{business_id}"
        queue_items = _redis_client.lrange(queue_key, 0, -1)
        if call_sid in queue_items:
            position = queue_items.index(call_sid) + 1
            queue_len = len(queue_items)
            return "queued", {"position": position, "queue_length": queue_len}
        
        return "unknown", {}
        
    except Exception as e:
        logger.error(f"[RECORDING_SEM] Error checking status: {e}")
        return "unknown", {}


# Initialize Redis on module import
init_redis()
