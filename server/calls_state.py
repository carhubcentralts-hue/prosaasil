"""
server/calls_state.py — Redis-backed Call State Management
============================================================
Moves call session state from in-memory to Redis, enabling
horizontal scaling of the calls service (multiple replicas).

Strategy: Stateless Calls + Redis State (Option 1 from scaling plan)

Key design:
- All call state is stored in Redis with call_sid as key prefix
- Active calls counter enforces MAX_CONCURRENT_CALLS globally
- Any calls service replica can handle any call (no sticky routing needed)
- TTL on all keys prevents state leaks on crashes
"""

import json
import os
import time
import logging

logger = logging.getLogger(__name__)

# Default TTL for call state (1 hour — well beyond any call duration)
CALL_STATE_TTL = 3600
# Max concurrent calls (0 = unlimited, but we enforce a real default)
DEFAULT_MAX_CONCURRENT = 50

ACTIVE_CALLS_KEY = "calls:active_count"
CALL_STATE_PREFIX = "calls:state:"
CALL_LOCK_PREFIX = "calls:lock:"


class CallStateManager:
    """Redis-backed call state manager for horizontal scaling."""

    def __init__(self, redis_client=None):
        self._redis = redis_client
        self._max_concurrent = int(os.environ.get("MAX_CONCURRENT_CALLS", str(DEFAULT_MAX_CONCURRENT)))
        if self._max_concurrent <= 0:
            self._max_concurrent = DEFAULT_MAX_CONCURRENT
            logger.warning(
                "MAX_CONCURRENT_CALLS was 0 or negative, using default=%d",
                DEFAULT_MAX_CONCURRENT,
            )

    @property
    def redis(self):
        if self._redis is None:
            import redis as redis_lib
            redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
            self._redis = redis_lib.from_url(redis_url, decode_responses=True)
        return self._redis

    # ─── Active calls counter ────────────────────────────

    def get_active_count(self) -> int:
        """Get the current number of active calls (globally)."""
        try:
            val = self.redis.get(ACTIVE_CALLS_KEY)
            return int(val) if val else 0
        except Exception:
            return 0

    def can_accept_call(self) -> bool:
        """Check if we can accept a new call (under max concurrent limit)."""
        current = self.get_active_count()
        return current < self._max_concurrent

    def increment_active(self, call_sid: str) -> bool:
        """
        Atomically try to increment active calls.
        Returns True if call was accepted, False if over limit.
        Uses Redis WATCH/MULTI for atomic check-and-increment.
        """
        try:
            pipe = self.redis.pipeline(True)
            max_retries = 5
            for attempt in range(max_retries):
                try:
                    pipe.watch(ACTIVE_CALLS_KEY)
                    current = int(pipe.get(ACTIVE_CALLS_KEY) or 0)
                    if current >= self._max_concurrent:
                        pipe.unwatch()
                        logger.warning(
                            "Call rejected: active=%d, max=%d, call_sid=%s",
                            current, self._max_concurrent, call_sid,
                        )
                        return False
                    pipe.multi()
                    pipe.incr(ACTIVE_CALLS_KEY)
                    pipe.execute()
                    return True
                except Exception as retry_err:
                    logger.debug("Redis WATCH retry %d/%d: %s", attempt + 1, max_retries, retry_err)
                    continue
            logger.error("Failed to increment after %d retries, call_sid=%s", max_retries, call_sid)
            return False
        except Exception as e:
            logger.error("Failed to increment active calls: %s", e)
            return False

    def decrement_active(self, call_sid: str):
        """Decrement active calls counter (on call end)."""
        try:
            result = self.redis.decr(ACTIVE_CALLS_KEY)
            # Prevent negative counts
            if result is not None and int(result) < 0:
                self.redis.set(ACTIVE_CALLS_KEY, 0)
        except Exception as e:
            logger.error("Failed to decrement active calls: %s", e)

    # ─── Call session state ──────────────────────────────

    def save_state(self, call_sid: str, state: dict):
        """Save call session state to Redis."""
        try:
            key = f"{CALL_STATE_PREFIX}{call_sid}"
            self.redis.setex(key, CALL_STATE_TTL, json.dumps(state, default=str))
        except Exception as e:
            logger.error("Failed to save call state for %s: %s", call_sid, e)

    def get_state(self, call_sid: str) -> dict | None:
        """Retrieve call session state from Redis."""
        try:
            key = f"{CALL_STATE_PREFIX}{call_sid}"
            data = self.redis.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            logger.error("Failed to get call state for %s: %s", call_sid, e)
            return None

    def delete_state(self, call_sid: str):
        """Remove call state (call ended)."""
        try:
            key = f"{CALL_STATE_PREFIX}{call_sid}"
            self.redis.delete(key)
        except Exception as e:
            logger.error("Failed to delete call state for %s: %s", call_sid, e)

    def update_state(self, call_sid: str, updates: dict):
        """Merge updates into existing call state."""
        state = self.get_state(call_sid) or {}
        state.update(updates)
        state["updated_at"] = time.time()
        self.save_state(call_sid, state)

    # ─── Call lifecycle ──────────────────────────────────

    def start_call(self, call_sid: str, initial_state: dict) -> bool:
        """
        Start a new call. Returns False if max concurrent reached.
        This is the entry point for all new calls.
        """
        if not self.increment_active(call_sid):
            return False
        initial_state["started_at"] = time.time()
        initial_state["call_sid"] = call_sid
        self.save_state(call_sid, initial_state)
        return True

    def end_call(self, call_sid: str):
        """End a call and clean up state."""
        self.decrement_active(call_sid)
        self.delete_state(call_sid)

    # ─── Diagnostics ─────────────────────────────────────

    def health(self) -> dict:
        """Return health info for /health endpoint."""
        try:
            active = self.get_active_count()
            return {
                "status": "healthy",
                "active_calls": active,
                "max_concurrent_calls": self._max_concurrent,
                "capacity_pct": round((active / self._max_concurrent) * 100, 1)
                if self._max_concurrent > 0
                else 0,
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}


# Global singleton (lazy init)
_call_state_manager = None


def get_call_state_manager() -> CallStateManager:
    """Get or create the global CallStateManager singleton."""
    global _call_state_manager
    if _call_state_manager is None:
        _call_state_manager = CallStateManager()
    return _call_state_manager
