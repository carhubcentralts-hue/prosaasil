"""
AgentLocator v39 - Production Logging Setup
הגדרת לוגינג ברמה פרודקציונית עם JSON ופורמט מותאם
"""

import logging
import json
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging in production"""
    
    def format(self, record):
        log_obj = {
            "timestamp": self.formatTime(record, "%Y-%m-%d %H:%M:%S"),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
            
        # Add extra fields if present
        if hasattr(record, 'user_id'):
            log_obj["user_id"] = record.user_id
            
        if hasattr(record, 'business_id'):
            log_obj["business_id"] = record.business_id
            
        if hasattr(record, 'customer_id'):
            log_obj["customer_id"] = record.customer_id
            
        return json.dumps(log_obj, ensure_ascii=False)

class HebrewFormatter(logging.Formatter):
    """Hebrew-friendly formatter for development"""
    
    def format(self, record):
        timestamp = self.formatTime(record, "%H:%M:%S")
        return f"[{timestamp}] {record.levelname:8} {record.name:20} {record.getMessage()}"

def setup_logging(app):
    """Setup production-grade logging configuration"""
    
    env = os.getenv("FLASK_ENV", "development")
    log_level = logging.DEBUG if env == "development" else logging.INFO
    
    # Clear existing handlers
    app.logger.handlers.clear()
    app.logger.setLevel(log_level)
    
    # Console handler
    console_handler = logging.StreamHandler()
    
    if env == "production":
        # JSON logging for production
        console_handler.setFormatter(JsonFormatter())
        
        # File logging for production
        log_file = os.environ.get('LOG_FILE_PATH', './logs/app.log')
        log_dir = os.path.dirname(log_file)
        
        # Create logs directory
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=10
        )
        file_handler.setFormatter(JsonFormatter())
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        
    else:
        # Human-readable logging for development
        console_handler.setFormatter(HebrewFormatter())
        
    console_handler.setLevel(log_level)
    app.logger.addHandler(console_handler)
    
    # Configure library loggers to reduce noise
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    
    # Add context to all log messages
    @app.before_request
    def log_request_info():
        from flask import request, g
        if hasattr(g, 'user_id'):
            # Add user context to all subsequent logs in this request
            for handler in app.logger.handlers:
                handler.addFilter(lambda record: setattr(record, 'user_id', g.user_id) or True)
    
    startup_time = datetime.utcnow().isoformat()
    app.logger.info(f"📋 Logging setup complete for {env} environment")
    app.logger.info(f"🕐 Application startup time: {startup_time}")
    app.logger.info(f"🔧 Log level: {logging.getLevelName(log_level)}")
    
    if env == "production":
        app.logger.info("🚀 Production JSON logging enabled")
    else:
        app.logger.info("🔧 Development Hebrew logging enabled")