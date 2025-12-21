"""
Centralized JSON logging with rotating files
"""
import logging
import logging.handlers
import json
import os
from datetime import datetime
from flask import g, request

# 🔥 Global DEBUG flag - Single source of truth
# DEBUG=1 → Production (minimal logs)
# DEBUG=0 → Development (full logs)
DEBUG = os.getenv("DEBUG", "1") == "1"

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
    - DEBUG=1 (default) → PRODUCTION: Minimal logs (WARNING level), quiet mode
    - DEBUG=0 → DEVELOPMENT: Full logs (DEBUG level), verbose mode
    """
    
    # Create logs directory
    os.makedirs('logs', exist_ok=True)
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    
    if DEBUG:
        # PRODUCTION MODE – minimal logs only (WARNING and above)
        root_logger.setLevel(logging.WARNING)
        
        # External libraries: ERROR only in production
        # 🔥 Set parent logger first, then child for proper propagation
        logging.getLogger("httpx").setLevel(logging.ERROR)
        logging.getLogger("uvicorn").setLevel(logging.ERROR)
        logging.getLogger("werkzeug").setLevel(logging.ERROR)
        logging.getLogger("urllib3").setLevel(logging.ERROR)
        
        # 🔥 Block Twilio HTTP client logs completely in production
        # This prevents "BEGIN Twilio API Request" spam
        # CRITICAL: Set propagate=False to prevent root handler from logging these
        for lib_name in ("twilio", "twilio.http_client", "twilio.rest"):
            lib_logger = logging.getLogger(lib_name)
            lib_logger.setLevel(logging.WARNING)
            lib_logger.propagate = False
    else:
        # DEBUG MODE – full logs (DEBUG and above)
        root_logger.setLevel(logging.DEBUG)
        
        # External libraries: normal levels in debug mode
        logging.getLogger("twilio").setLevel(logging.INFO)
        logging.getLogger("twilio.http_client").setLevel(logging.INFO)
        logging.getLogger("httpx").setLevel(logging.INFO)
        logging.getLogger("uvicorn").setLevel(logging.INFO)
        logging.getLogger("werkzeug").setLevel(logging.INFO)
        logging.getLogger("urllib3").setLevel(logging.INFO)
    
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
    
    # 🔥 CRITICAL: Re-enforce twilio.http_client blocking after handler setup
    # This ensures no handler can override the level settings
    if DEBUG:
        # Production: Block twilio logs completely with propagate=False
        for lib_name in ("twilio", "twilio.http_client", "twilio.rest"):
            lib_logger = logging.getLogger(lib_name)
            lib_logger.setLevel(logging.WARNING)
            lib_logger.propagate = False
    
    # 🔥 Verify twilio.http_client level in DEBUG mode only (when DEBUG=False, i.e., development)
    if not DEBUG:
        twilio_logger = logging.getLogger("twilio.http_client")
        print(f"[LOGGING_SETUP] twilio.http_client effectiveLevel: {logging.getLevelName(twilio_logger.getEffectiveLevel())}")
    
    return root_logger

def set_request_context(call_sid=None, business_id=None):
    """Set request context for logging"""
    if call_sid:
        g.call_sid = call_sid
    if business_id:
        g.business_id = business_id


# 🔥 Log throttling helper to prevent spam in loops/frequent events
_log_throttle_cache = {}
_log_throttle_lock = __import__('threading').Lock()

def log_every(logger, key, message, level=logging.INFO, seconds=5):
    """
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
    import time
    
    now = time.time()
    with _log_throttle_lock:
        last_time = _log_throttle_cache.get(key, 0)
        if now - last_time >= seconds:
            _log_throttle_cache[key] = now
            msg = message() if callable(message) else message
            logger.log(level, msg)
            return True
    return False