"""
Database Health Check Utility
Provides resilient DB connectivity checking with caching to prevent
Neon/Postgres outages from crashing background loops.
"""
import logging
import time
from typing import Optional
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, DisconnectionError

logger = logging.getLogger(__name__)

# Cache for DB health status (avoid spamming DB with health checks)
_db_health_cache: Optional[dict] = None
_CACHE_TTL_SECONDS = 3  # Cache health status for 3 seconds


def db_ping() -> bool:
    """
    Check if database is accessible with SELECT 1 query.
    
    Results are cached for 3 seconds to avoid spamming the database.
    This is safe for background loops that check frequently.
    
    Returns:
        True if DB is accessible, False otherwise
    """
    global _db_health_cache
    
    now = time.time()
    
    # Check cache
    if _db_health_cache and (now - _db_health_cache['timestamp']) < _CACHE_TTL_SECONDS:
        return _db_health_cache['healthy']
    
    # Perform health check
    try:
        from server.db import db
        
        # Simple SELECT 1 query
        result = db.session.execute(text("SELECT 1")).scalar()
        is_healthy = (result == 1)
        
        # Update cache
        _db_health_cache = {
            'healthy': is_healthy,
            'timestamp': now
        }
        
        if is_healthy:
            logger.debug("[DB_HEALTH] Database is healthy")
        else:
            logger.warning("[DB_HEALTH] Database ping returned unexpected result")
        
        return is_healthy
        
    except (OperationalError, DisconnectionError) as e:
        logger.warning(f"[DB_HEALTH] Database not accessible: {e}")
        
        # Update cache with unhealthy status
        _db_health_cache = {
            'healthy': False,
            'timestamp': now
        }
        
        return False
        
    except Exception as e:
        logger.error(f"[DB_HEALTH] Unexpected error during health check: {e}")
        
        # Update cache with unhealthy status
        _db_health_cache = {
            'healthy': False,
            'timestamp': now
        }
        
        return False


def is_neon_error(error: Exception) -> bool:
    """
    Check if error is Neon-specific (endpoint disabled/suspended).
    
    Args:
        error: Exception to check
    
    Returns:
        True if error appears to be from Neon endpoint being disabled
    """
    error_str = str(error).lower()
    
    # Check for Neon-specific error messages
    neon_indicators = [
        'endpoint has been disabled',
        'neon.tech',
        'endpoint is disabled',
        'compute endpoint',
    ]
    
    return any(indicator in error_str for indicator in neon_indicators)


def log_db_error(error: Exception, context: str = "") -> None:
    """
    Log database error with Neon-specific hints.
    
    Args:
        error: Exception that occurred
        context: Context string for logging (e.g., "whatsapp_session")
    """
    error_str = str(error)
    
    if is_neon_error(error):
        logger.error(
            f"[NEON] {context} - Neon endpoint disabled/sleep detected. "
            f"action=resume endpoint or upgrade plan | error={error_str}",
            exc_info=True
        )
    else:
        logger.error(
            f"[DB] {context} - Database error: {error_str}",
            exc_info=True
        )
