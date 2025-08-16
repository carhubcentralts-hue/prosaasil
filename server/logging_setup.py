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
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
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
    
    # Reduce noise from external libraries
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    return root_logger

def set_request_context(call_sid=None, business_id=None):
    """Set request context for logging"""
    if call_sid:
        g.call_sid = call_sid
    if business_id:
        g.business_id = business_id