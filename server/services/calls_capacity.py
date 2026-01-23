"""
Calls Capacity Management - Redis-based call slot tracking
P3-1: Production Stabilization - MAX_ACTIVE_CALLS guardrails

This module provides a reliable Redis-based counter to track active calls
and enforce capacity limits to prevent system overload.

Usage:
    from server.services.calls_capacity import try_acquire_call_slot, release_call_slot
    
    if not try_acquire_call_slot(call_id):
        # Reject call - at capacity
        return reject_response()
    
    try:
        # Process call
        ...
    finally:
        release_call_slot(call_id)
"""
import os
import logging
import redis
from typing import Optional

logger = logging.getLogger(__name__)

# Environment configuration with fail-safe defaults
def _get_max_active_calls() -> int:
    """
    Get MAX_ACTIVE_CALLS with safe fallback logic.
    Production default: 15
    Development default: 50
    """
    max_calls_env = os.getenv('MAX_ACTIVE_CALLS', '').strip()
    is_production = os.getenv('PRODUCTION', '0') == '1'
    
    if max_calls_env:
        try:
            return int(max_calls_env)
        except ValueError:
            logger.warning(f"Invalid MAX_ACTIVE_CALLS value: {max_calls_env}, using default")
    
    # Fail-safe defaults
    return 15 if is_production else 50


MAX_ACTIVE_CALLS = _get_max_active_calls()
CALLS_OVER_CAPACITY_BEHAVIOR = os.getenv('CALLS_OVER_CAPACITY_BEHAVIOR', 'reject')
CALLS_CAPACITY_LOG_LEVEL = os.getenv('CALLS_CAPACITY_LOG_LEVEL', 'WARNING')

# Redis configuration
REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379/0')

# Redis keys
CALLS_ACTIVE_SET = "calls:active"
CALL_KEY_PREFIX = "calls:active:"

# TTL settings (2 hours = 7200 seconds) - safety net for stuck slots
CALL_SLOT_TTL = 7200

# Redis connection (lazy initialization)
_redis_client: Optional[redis.Redis] = None


def _get_redis() -> redis.Redis:
    """Get or create Redis client (lazy initialization)"""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


def try_acquire_call_slot(call_id: str) -> bool:
    """
    Try to acquire a call slot for the given call_id.
    
    Returns:
        True if slot acquired successfully (call can proceed)
        False if at capacity (call should be rejected)
    
    Logic:
        1. Check current cardinality of active calls set
        2. If >= MAX_ACTIVE_CALLS, return False
        3. Otherwise, add call_id to set and set TTL key
        4. Return True
    """
    try:
        r = _get_redis()
        
        # Get current count of active calls
        current_count = r.scard(CALLS_ACTIVE_SET)
        
        if current_count >= MAX_ACTIVE_CALLS:
            # At capacity - reject
            log_level = getattr(logging, CALLS_CAPACITY_LOG_LEVEL, logging.WARNING)
            logger.log(
                log_level,
                f"[CAPACITY] REJECTED call_id={call_id} active_calls={current_count} max={MAX_ACTIVE_CALLS}"
            )
            return False
        
        # Acquire slot
        # Use pipeline for atomicity
        pipe = r.pipeline()
        pipe.sadd(CALLS_ACTIVE_SET, call_id)
        pipe.setex(f"{CALL_KEY_PREFIX}{call_id}", CALL_SLOT_TTL, "1")
        pipe.execute()
        
        new_count = current_count + 1
        logger.info(
            f"[CAPACITY] ACQUIRED call_id={call_id} active_calls={new_count}/{MAX_ACTIVE_CALLS}"
        )
        return True
        
    except redis.RedisError as e:
        # Redis error - fail open (allow call to proceed)
        logger.error(f"[CAPACITY] Redis error in try_acquire_call_slot: {e}")
        logger.error(f"[CAPACITY] FAIL-OPEN: Allowing call_id={call_id} to proceed despite Redis error")
        return True
    except Exception as e:
        # Unexpected error - fail open
        logger.exception(f"[CAPACITY] Unexpected error in try_acquire_call_slot: {e}")
        logger.error(f"[CAPACITY] FAIL-OPEN: Allowing call_id={call_id} to proceed")
        return True


def release_call_slot(call_id: str) -> None:
    """
    Release a call slot for the given call_id.
    
    Should be called in finally block when call ends, regardless of success/failure.
    Safe to call even if slot was never acquired (idempotent).
    """
    try:
        r = _get_redis()
        
        # Remove from active set and delete TTL key
        pipe = r.pipeline()
        pipe.srem(CALLS_ACTIVE_SET, call_id)
        pipe.delete(f"{CALL_KEY_PREFIX}{call_id}")
        pipe.execute()
        
        remaining_count = r.scard(CALLS_ACTIVE_SET)
        logger.info(
            f"[CAPACITY] RELEASED call_id={call_id} active_calls={remaining_count}/{MAX_ACTIVE_CALLS}"
        )
        
    except redis.RedisError as e:
        logger.error(f"[CAPACITY] Redis error in release_call_slot: {e}")
    except Exception as e:
        logger.exception(f"[CAPACITY] Unexpected error in release_call_slot: {e}")


def get_active_calls_count() -> int:
    """
    Get current count of active calls.
    
    Returns:
        Number of active calls (0 if Redis unavailable)
    """
    try:
        r = _get_redis()
        return r.scard(CALLS_ACTIVE_SET)
    except redis.RedisError as e:
        logger.error(f"[CAPACITY] Redis error in get_active_calls_count: {e}")
        return 0
    except Exception as e:
        logger.exception(f"[CAPACITY] Unexpected error in get_active_calls_count: {e}")
        return 0


def cleanup_expired_slots() -> int:
    """
    Cleanup expired slots from active set (maintenance task).
    
    Removes call_ids from the active set if their TTL key has expired.
    This is a safety mechanism - normally TTL handles cleanup automatically.
    
    Returns:
        Number of slots cleaned up
    """
    try:
        r = _get_redis()
        active_calls = r.smembers(CALLS_ACTIVE_SET)
        
        cleaned = 0
        for call_id in active_calls:
            # Check if TTL key exists
            if not r.exists(f"{CALL_KEY_PREFIX}{call_id}"):
                # Key expired but still in set - remove it
                r.srem(CALLS_ACTIVE_SET, call_id)
                cleaned += 1
                logger.info(f"[CAPACITY] CLEANUP: Removed expired slot call_id={call_id}")
        
        if cleaned > 0:
            logger.info(f"[CAPACITY] CLEANUP: Removed {cleaned} expired slots")
        
        return cleaned
        
    except redis.RedisError as e:
        logger.error(f"[CAPACITY] Redis error in cleanup_expired_slots: {e}")
        return 0
    except Exception as e:
        logger.exception(f"[CAPACITY] Unexpected error in cleanup_expired_slots: {e}")
        return 0
