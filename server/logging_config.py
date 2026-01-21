"""
Centralized logging configuration for ProSaaS
Implements production-safe logging with minimal noise

🎯 PRODUCTION (LOG_LEVEL=INFO):
- Only essential INFO logs: call start/end, session updates, errors
- WARNING for exceptional cases
- ERROR/EXCEPTION with full stacktrace
- NO DEBUG/TRACE spam

🎯 DEVELOPMENT (LOG_LEVEL=DEBUG):
- Full DEBUG logging enabled
- All logs visible for troubleshooting
"""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler


def configure_logging():
    """
    Configure centralized logging for the entire application.
    
    Environment Variables:
        LOG_LEVEL: Logging level (DEBUG, INFO, WARNING, ERROR). Default: INFO
        LOG_JSON: Enable JSON logging format (0 or 1). Default: 0
        PYTHONUNBUFFERED: Set to 1 for immediate log output
    
    Production Settings:
        - LOG_LEVEL=INFO (minimal logs)
        - Noisy libraries (uvicorn, sqlalchemy, httpx, websockets) set to WARNING
        - Access logs disabled or minimal
    
    Development Settings:
        - LOG_LEVEL=DEBUG (full logs)
        - Noisy libraries set to INFO
    """
    
    # Get log level from environment (default: INFO for production)
    log_level_str = os.getenv('LOG_LEVEL', 'INFO').upper()
    
    # Map string to logging level
    log_level_map = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    
    log_level = log_level_map.get(log_level_str, None)
    
    # Validate and warn if invalid level provided
    if log_level is None:
        # Use a direct print here since logging isn't configured yet
        print(f"⚠️ WARNING: Invalid LOG_LEVEL '{log_level_str}', defaulting to INFO", file=sys.stderr)
        log_level = logging.INFO
        log_level_str = 'INFO'
    
    is_production = log_level >= logging.INFO
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(log_level)
    
    # Create logs directory
    os.makedirs('logs', exist_ok=True)
    
    # Configure formatter
    use_json = os.getenv('LOG_JSON', '0') == '1'
    
    if use_json:
        # JSON format for production log aggregation
        formatter = logging.Formatter(
            '{"timestamp":"%(asctime)s","level":"%(levelname)s","module":"%(name)s","message":"%(message)s"}',
            datefmt='%Y-%m-%dT%H:%M:%S'
        )
    else:
        # Human-readable format
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)-8s [%(name)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)
    root_logger.addHandler(console_handler)
    
    # File handler with rotation (10MB, keep 5 files)
    file_handler = RotatingFileHandler(
        'logs/app.log',
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)
    root_logger.addHandler(file_handler)
    
    # ========================================================================
    # SILENCE NOISY LIBRARIES
    # ========================================================================
    # These libraries generate excessive logs that are not useful in production
    
    if is_production:
        # PRODUCTION MODE - Silence noisy libraries to WARNING/ERROR only
        noisy_libs = {
            # Web frameworks
            'uvicorn': logging.WARNING,
            'uvicorn.access': logging.ERROR,  # Disable access logs in prod
            'uvicorn.error': logging.WARNING,
            'werkzeug': logging.WARNING,
            
            # Database
            'sqlalchemy': logging.WARNING,
            'sqlalchemy.engine': logging.WARNING,
            'sqlalchemy.pool': logging.WARNING,
            'sqlalchemy.orm': logging.WARNING,
            
            # HTTP clients
            'httpx': logging.WARNING,
            'urllib3': logging.WARNING,
            'urllib3.connectionpool': logging.WARNING,
            'requests': logging.WARNING,
            
            # WebSocket
            'websockets': logging.WARNING,
            'websockets.server': logging.WARNING,
            'websockets.protocol': logging.WARNING,
            
            # External APIs
            'openai': logging.WARNING,
            'twilio': logging.ERROR,  # Twilio is very noisy
            'twilio.http_client': logging.ERROR,
            'twilio.rest': logging.ERROR,
        }
    else:
        # DEVELOPMENT MODE - Keep libraries at INFO level
        noisy_libs = {
            'uvicorn': logging.INFO,
            'uvicorn.access': logging.INFO,
            'werkzeug': logging.INFO,
            'sqlalchemy.engine': logging.INFO,
            'httpx': logging.INFO,
            'websockets': logging.INFO,
            'twilio': logging.INFO,
        }
    
    # Apply library log levels
    for lib_name, lib_level in noisy_libs.items():
        lib_logger = logging.getLogger(lib_name)
        lib_logger.setLevel(lib_level)
        
        # For extremely noisy libraries in production, prevent propagation
        if is_production and lib_level >= logging.ERROR:
            lib_logger.propagate = False
    
    # ========================================================================
    # SILENCE NOISY APPLICATION MODULES
    # ========================================================================
    # Internal modules that generate spam in production
    
    if is_production:
        # These modules log too frequently in production
        noisy_modules = [
            'server.media_ws_ai',           # Frame-by-frame audio logs
            'server.services.audio_dsp',    # Audio processing spam
            'server.services.openai_realtime_client',  # Realtime API spam
            'server.routes_leads',          # GET requests spam
            'server.routes_status_management',  # Status API spam
            'server.tasks_recording',       # "Found 0" spam
        ]
        
        for module_name in noisy_modules:
            module_logger = logging.getLogger(module_name)
            module_logger.setLevel(logging.WARNING)
    
    # ========================================================================
    # LOG CONFIGURATION SUMMARY
    # ========================================================================
    # Always log configuration at startup (helps troubleshoot config issues)
    if is_production:
        # In production, use root logger directly (already configured) to ensure visibility
        root_logger.info('=' * 70)
        root_logger.info(f'LOGGING CONFIGURED: level={log_level_str}, json={use_json}, production={is_production}')
        root_logger.info('=' * 70)
    else:
        # In development, can be more verbose
        root_logger.info('=' * 70)
        root_logger.info(f'LOGGING CONFIGURED: level={log_level_str}, json={use_json}')
        root_logger.info(f'Production mode: {is_production}')
        root_logger.info('=' * 70)
    
    return root_logger


# ============================================================================
# EXPORT FOR BACKWARD COMPATIBILITY
# ============================================================================
# Allow other modules to use these helpers
IS_PROD = os.getenv('LOG_LEVEL', 'INFO').upper() in ['INFO', 'WARNING', 'ERROR', 'CRITICAL']

# Re-export rate limiting helpers from logging_setup if available
try:
    from server.logging_setup import RateLimiter, OncePerCall, rl, once_per_call
    __all__ = ['configure_logging', 'IS_PROD', 'RateLimiter', 'OncePerCall', 'rl', 'once_per_call']
except ImportError:
    # If logging_setup doesn't exist or doesn't have these, define minimal versions
    __all__ = ['configure_logging', 'IS_PROD']
