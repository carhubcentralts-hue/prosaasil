"""
Rate-limiting utilities for logging to prevent spam in loops/frequent events

Usage examples:
    from server.utils.log_rate_limit import log_every_n, log_throttle
    
    # Log every 100 iterations
    if log_every_n(logger, "audio_frames", 100):
        logger.debug(f"Processed {frame_count} frames")
    
    # Log at most once every 60 seconds
    if log_throttle(logger, "session_check", seconds=60):
        logger.info(f"Active sessions: {len(sessions)}")
"""
import time
import threading
from typing import Optional
import logging


# Global caches for rate limiting
_throttle_cache = {}
_throttle_lock = threading.Lock()

_counter_cache = {}
_counter_lock = threading.Lock()


def log_every_n(logger: logging.Logger, key: str, n: int = 100, level: str = "info", msg: Optional[str] = None) -> bool:
    """
    Log a message every N calls (counter-based rate limiting).
    
    Useful for loops where you want to log periodically based on iteration count.
    
    Args:
        logger: Logger instance to use
        key: Unique key for this log type (e.g., "audio_frame_processing")
        n: Log every N calls (default: 100)
        level: Log level - "debug", "info", "warning", "error" (default: "info")
        msg: Optional message to log. If None, returns True and you log manually.
    
    Returns:
        bool: True if should log (every Nth call), False otherwise
    
    Example:
        # Manual logging
        if log_every_n(logger, "frames", 100):
            logger.info(f"Processed {count} frames")
        
        # Automatic logging
        log_every_n(logger, "frames", 100, "info", f"Processed {count} frames")
    """
    with _counter_lock:
        count = _counter_cache.get(key, 0) + 1
        _counter_cache[key] = count
        
        should_log = (count % n == 0)
    
    if should_log and msg:
        log_func = getattr(logger, level.lower(), logger.info)
        log_func(msg)
    
    return should_log


def log_throttle(logger: logging.Logger, key: str, seconds: float = 60, level: str = "info", msg: Optional[str] = None) -> bool:
    """
    Log a message at most once every N seconds (time-based rate limiting).
    
    Useful for frequent events where you want to log periodically based on time.
    
    Args:
        logger: Logger instance to use
        key: Unique key for this log type (e.g., "stale_session_check")
        seconds: Minimum seconds between logs (default: 60)
        level: Log level - "debug", "info", "warning", "error" (default: "info")
        msg: Optional message to log. If None, returns True and you log manually.
    
    Returns:
        bool: True if should log (enough time passed), False otherwise
    
    Example:
        # Manual logging
        if log_throttle(logger, "health", seconds=30):
            logger.info(f"Health check passed: {status}")
        
        # Automatic logging
        log_throttle(logger, "health", 30, "info", f"Health: {status}")
    """
    now = time.time()
    
    with _throttle_lock:
        last_time = _throttle_cache.get(key, 0)
        should_log = (now - last_time >= seconds)
        
        if should_log:
            _throttle_cache[key] = now
    
    if should_log and msg:
        log_func = getattr(logger, level.lower(), logger.info)
        log_func(msg)
    
    return should_log


def reset_rate_limits(key: Optional[str] = None):
    """
    Reset rate limit counters/timers.
    
    Args:
        key: If provided, reset only this key. If None, reset all.
    
    Example:
        # Reset specific key
        reset_rate_limits("audio_frames")
        
        # Reset all
        reset_rate_limits()
    """
    with _counter_lock:
        if key:
            _counter_cache.pop(key, None)
        else:
            _counter_cache.clear()
    
    with _throttle_lock:
        if key:
            _throttle_cache.pop(key, None)
        else:
            _throttle_cache.clear()


# Backward compatibility with existing logging_setup.py
class RateLimiter:
    """
    Rate-limit helper to prevent log spam (backward compatible interface).
    
    Usage:
        rl = RateLimiter()
        if rl.every("audio_drain", 5.0):
            logger.debug(f"[AUDIO_DRAIN] tx={tx_q} out={out_q}")
    """
    def __init__(self):
        self.t = {}
        self._lock = threading.Lock()
    
    def every(self, key: str, sec: float) -> bool:
        """
        Check if enough time has passed since last log with this key.
        
        Args:
            key: Unique identifier for this log type
            sec: Minimum seconds between logs
            
        Returns:
            True if should log, False if should suppress
        """
        now = time.time()
        with self._lock:
            last_time = self.t.get(key, 0)
            if now - last_time >= sec:
                self.t[key] = now
                return True
        return False


class OncePerCall:
    """
    One-shot logging helper - logs appear only once per call.
    
    Usage:
        once = OncePerCall()
        if once.once("dsp_enabled"):
            logger.info("[DSP] enabled: highpass+limiter")
    """
    def __init__(self):
        self.seen = set()
        self._lock = threading.Lock()
    
    def once(self, key: str) -> bool:
        """
        Check if this key has been logged before.
        
        Args:
            key: Unique identifier for this log message
            
        Returns:
            True if first time (should log), False if already logged
        """
        with self._lock:
            if key in self.seen:
                return False
            self.seen.add(key)
            return True


# Global instances for convenience
rl = RateLimiter()
once_per_call = OncePerCall()
