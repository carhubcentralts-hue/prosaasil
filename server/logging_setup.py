"""
Centralized JSON logging with rotating files

🎯 NEW PRODUCTION LOGGING POLICY:
DEBUG=1 (Production/Deployment):
  - Only INFO "macro" events: start/end call, session.updated, response.created/done, barge-in once, metrics summary
  - ERROR/WARNING always enabled (but no repeated spam)
  - ZERO per-frame logs (RMS, audio.delta, queues, transcript.delta → FORBIDDEN)

DEBUG=0 (Development/Not deployment):
  - Normal INFO + focused DEBUG (but still with rate-limit)
  - Deep debug allowed when needed, but not every 20ms
"""
import logging
import logging.handlers
import json
import os
import time
import threading
from datetime import datetime
from flask import g, request

# 🔥 Global DEBUG flag - Single source of truth
# DEBUG=1 → Production (minimal logs)
# DEBUG=0 → Development (full logs)
DEBUG = os.getenv("DEBUG", "1") == "1"

# ═══════════════════════════════════════════════════════════════════════════════
# 🚀 RATE-LIMITING HELPER - Prevents log spam in loops/frequent events
# ═══════════════════════════════════════════════════════════════════════════════
class RateLimiter:
    """
    Rate-limit helper to prevent log spam.
    
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


# ═══════════════════════════════════════════════════════════════════════════════
# 🎯 ONCE-PER-CALL HELPER - Ensures logs appear only once per call
# ═══════════════════════════════════════════════════════════════════════════════
class OncePerCall:
    """
    One-shot logging helper - logs appear only once per call.
    
    Usage:
        once = OncePerCall()
        if DEBUG and once.once("dsp_enabled"):
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


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
    
    def format(self, record):
        log_entry = {
            'ts': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'module': record.module,
            'msg': record.getMessage()
        }
        
        # Add request context if available
        try:
            if hasattr(g, 'call_sid'):
                log_entry['call_sid'] = g.call_sid
            if hasattr(g, 'business_id'):
                log_entry['business_id'] = g.business_id
        except RuntimeError:
            # Outside of request context
            pass
        
        try:
            if request:
                log_entry['path'] = request.path
        except RuntimeError:
            # Outside of request context
            pass
            
        # Add extra fields
        if hasattr(record, '__dict__'):
            for key, value in record.__dict__.items():
                if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 'filename', 'module', 'lineno', 'funcName', 'created', 'msecs', 'relativeCreated', 'thread', 'threadName', 'processName', 'process', 'getMessage', 'exc_info', 'exc_text', 'stack_info']:
                    log_entry[key] = value
        
        return json.dumps(log_entry, ensure_ascii=False)

def setup_logging():
    """Setup centralized logging with JSON format and file rotation
    
    🔥 PRODUCTION vs DEBUG MODE:
    - DEBUG=1 (default) → PRODUCTION: Minimal logs (INFO for macro events, WARNING for noisy modules)
    - DEBUG=0 → DEVELOPMENT: Full logs (DEBUG level for code, INFO for noisy modules)
    """
    
    # Create logs directory
    os.makedirs('logs', exist_ok=True)
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # 🎯 SET LOG LEVELS BASED ON DEBUG FLAG
    # ═══════════════════════════════════════════════════════════════════════════════
    if DEBUG:
        # PRODUCTION MODE (DEBUG=1) - quiet, only macro events
        BASE_LEVEL = logging.INFO       # Macro events only (CALL_START, CALL_END, etc.)
        NOISY_LEVEL = logging.WARNING   # Noisy modules → WARNING only
    else:
        # DEVELOPMENT MODE (DEBUG=0) - full debugging
        BASE_LEVEL = logging.DEBUG      # Full debug info
        NOISY_LEVEL = logging.INFO      # Noisy modules → INFO level
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(BASE_LEVEL)
    
    # Console handler with JSON
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(console_handler)
    
    # Rotating file handler
    file_handler = logging.handlers.RotatingFileHandler(
        'logs/app.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(file_handler)
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # 🔇 SILENCE NOISY MODULES
    # ═══════════════════════════════════════════════════════════════════════════════
    # List of noisy modules that spam logs
    noisy = [
        "server.media_ws_ai",
        "server.services.audio_dsp",
        "websockets",
        "urllib3",
        "httpx",
        "openai",
    ]
    
    for name in noisy:
        logging.getLogger(name).setLevel(NOISY_LEVEL)
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # 🔥 SPECIAL HANDLING FOR EXTERNAL LIBRARIES
    # ═══════════════════════════════════════════════════════════════════════════════
    if DEBUG:
        # PRODUCTION MODE - maximum silence for external libs
        # Twilio: ERROR only + propagate=False to block completely
        for lib_name in ("twilio", "twilio.http_client", "twilio.rest"):
            lib_logger = logging.getLogger(lib_name)
            lib_logger.setLevel(logging.ERROR)
            lib_logger.propagate = False  # CRITICAL: prevent root handler from logging
        
        # Other external libraries: ERROR only in production
        logging.getLogger("httpx").setLevel(logging.ERROR)
        logging.getLogger("httpx.client").setLevel(logging.ERROR)
        logging.getLogger("uvicorn").setLevel(logging.WARNING)
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("werkzeug").setLevel(logging.ERROR)
        logging.getLogger("urllib3").setLevel(logging.ERROR)
    else:
        # DEVELOPMENT MODE - normal levels for external libs
        logging.getLogger("twilio").setLevel(logging.INFO)
        logging.getLogger("twilio.http_client").setLevel(logging.INFO)
        logging.getLogger("httpx").setLevel(logging.INFO)
        logging.getLogger("uvicorn").setLevel(logging.INFO)
        logging.getLogger("werkzeug").setLevel(logging.INFO)
        logging.getLogger("urllib3").setLevel(logging.INFO)
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # 🔒 RE-ENFORCE BLOCKING AFTER HANDLER SETUP
    # ═══════════════════════════════════════════════════════════════════════════════
    if DEBUG:
        # Production: Block twilio logs completely with ERROR level + propagate=False
        for lib_name in ("twilio", "twilio.http_client", "twilio.rest"):
            lib_logger = logging.getLogger(lib_name)
            lib_logger.setLevel(logging.ERROR)
            lib_logger.propagate = False
        
        # Also quiet uvicorn.access (health check spam)
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("uvicorn.access").propagate = False
    
    # 🔥 Verify settings in DEVELOPMENT mode only
    if not DEBUG:
        print(f"[LOGGING_SETUP] Development mode - BASE_LEVEL={logging.getLevelName(BASE_LEVEL)}, NOISY_LEVEL={logging.getLevelName(NOISY_LEVEL)}")
    
    return root_logger

def set_request_context(call_sid=None, business_id=None):
    """Set request context for logging"""
    if call_sid:
        g.call_sid = call_sid
    if business_id:
        g.business_id = business_id


# ═══════════════════════════════════════════════════════════════════════════════
# 🔥 DEPRECATED - Use RateLimiter class instead
# ═══════════════════════════════════════════════════════════════════════════════
# Legacy helper kept for backward compatibility
_log_throttle_cache = {}
_log_throttle_lock = threading.Lock()

def log_every(logger, key, message, level=logging.INFO, seconds=5):
    """
    DEPRECATED: Use RateLimiter class instead.
    
    Log a message at most once every N seconds for the same key.
    
    Use this in loops or frequently called code to prevent log spam.
    
    Args:
        logger: Logger instance
        key: Unique key for this log message (e.g., "audio_tx_loop")
        message: Message to log (can be a callable for lazy evaluation)
        level: Log level (default: INFO)
        seconds: Minimum seconds between logs for this key
    
    Example:
        log_every(logger, "ws_frames", lambda: f"Processed {count} frames", seconds=5)
    """
    now = time.time()
    with _log_throttle_lock:
        last_time = _log_throttle_cache.get(key, 0)
        if now - last_time >= seconds:
            _log_throttle_cache[key] = now
            msg = message() if callable(message) else message
            logger.log(level, msg)
            return True
    return False