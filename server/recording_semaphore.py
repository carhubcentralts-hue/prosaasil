"""
Recording Download Semaphore System
====================================

Per-business 3-concurrent-downloads limit using Redis.

Redis Keys:
- rec_slots:{business_id} - Counter of active downloads (0-3)
- rec_inflight:{business_id}:{call_sid} - Dedup lock (TTL 20-30s)
- rec_queue:{business_id} - FIFO queue of waiting call_sids
"""
import logging
import os
from typing import Optional, Tuple

logger = logging.getLogger(__name__)
log = logging.getLogger("recording_semaphore")

# Max concurrent downloads per business
MAX_SLOTS_PER_BUSINESS = 3

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
    
    Returns:
        (acquired: bool, status: str)
        - (True, "acquired") - Slot acquired, can download
        - (False, "queued") - No slots available, added to queue
        - (False, "inflight") - Already processing this call_sid
    """
    if not REDIS_ENABLED or not _redis_client:
        # Fallback: allow download without Redis
        return True, "no_redis"
    
    try:
        # Check 1: Is this call_sid already in flight?
        inflight_key = f"rec_inflight:{business_id}:{call_sid}"
        if _redis_client.exists(inflight_key):
            ttl = _redis_client.ttl(inflight_key)
            log.debug(f"[RECORDING_SEM] Call {call_sid} already inflight (TTL: {ttl}s)")
            return False, "inflight"
        
        # Check 2: Do we have available slots?
        slots_key = f"rec_slots:{business_id}"
        current_slots = int(_redis_client.get(slots_key) or 0)
        
        if current_slots < MAX_SLOTS_PER_BUSINESS:
            # Slot available! Acquire it
            _redis_client.incr(slots_key)
            
            # Mark as inflight (20 second TTL for dedup)
            _redis_client.setex(inflight_key, 20, "processing")
            
            new_slots = current_slots + 1
            logger.info(f"🎧 RECORDING_ENQUEUE bid={business_id} sid={call_sid[:8]}... slots={new_slots}/{MAX_SLOTS_PER_BUSINESS}")
            return True, "acquired"
        else:
            # No slots available - add to queue
            queue_key = f"rec_queue:{business_id}"
            
            # Check if already in queue (prevent duplicates)
            queue_items = _redis_client.lrange(queue_key, 0, -1)
            if call_sid in queue_items:
                log.debug(f"[RECORDING_SEM] Call {call_sid} already in queue")
                return False, "already_queued"
            
            # Add to end of queue (FIFO)
            _redis_client.rpush(queue_key, call_sid)
            queue_len = _redis_client.llen(queue_key)
            
            logger.info(f"⏳ RECORDING_QUEUED bid={business_id} sid={call_sid[:8]}... slots={current_slots}/{MAX_SLOTS_PER_BUSINESS} queue_len={queue_len}")
            return False, "queued"
            
    except Exception as e:
        logger.error(f"[RECORDING_SEM] Error acquiring slot: {e}")
        # On error, allow download (fail-open)
        return True, "error_fallback"


def release_slot(business_id: int, call_sid: str) -> Optional[str]:
    """
    Release a download slot and get next call_sid from queue if available.
    
    Returns:
        next_call_sid if there's work waiting, None otherwise
    """
    if not REDIS_ENABLED or not _redis_client:
        return None
    
    try:
        slots_key = f"rec_slots:{business_id}"
        inflight_key = f"rec_inflight:{business_id}:{call_sid}"
        queue_key = f"rec_queue:{business_id}"
        
        # Remove inflight marker
        _redis_client.delete(inflight_key)
        
        # Decrement slots (with protection against going negative)
        current_slots = int(_redis_client.get(slots_key) or 0)
        if current_slots > 0:
            _redis_client.decr(slots_key)
            slots_now = current_slots - 1
        else:
            slots_now = 0
        
        logger.info(f"✅ RECORDING_DONE bid={business_id} sid={call_sid[:8]}... slots_now={slots_now}/{MAX_SLOTS_PER_BUSINESS}")
        
        # Check if there's work waiting in queue
        next_sid = _redis_client.lpop(queue_key)  # FIFO: pop from left
        
        if next_sid:
            # Acquire slot for next job
            _redis_client.incr(slots_key)
            
            # Mark as inflight
            next_inflight_key = f"rec_inflight:{business_id}:{next_sid}"
            _redis_client.setex(next_inflight_key, 20, "processing")
            
            new_slots = slots_now + 1
            logger.info(f"➡️ RECORDING_NEXT bid={business_id} next_sid={next_sid[:8]}... slots={new_slots}/{MAX_SLOTS_PER_BUSINESS}")
            return next_sid
        
        return None
        
    except Exception as e:
        logger.error(f"[RECORDING_SEM] Error releasing slot: {e}")
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
