"""
Centralized JSON logging with rotating files
"""
import logging
import logging.handlers
import json
import os
from datetime import datetime
from flask import g, request

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
    """Setup centralized logging with JSON format and file rotation"""
    
    # Create logs directory
    os.makedirs('logs', exist_ok=True)
    
    # Get log level from environment (default: INFO)
    log_level_str = os.getenv('LOG_LEVEL', 'INFO').upper()
    log_level = getattr(logging, log_level_str, logging.INFO)
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
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
    
    # 🔥 Reduce noise from external libraries - CRITICAL for performance
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('twilio.http_client').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
    
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