"""
Database Retry Utility with Exponential Backoff
Prevents DB failures (Neon endpoint disabled, network issues) from crashing the server.

Usage:
    from server.utils.db_retry import db_retry
    
    result = db_retry("fetch_users", lambda: User.query.all())
    if result is None:
        # Handle gracefully - DB unavailable
        return jsonify({"error": "SERVICE_UNAVAILABLE"}), 503
"""
import time
import logging
from typing import Callable, Optional, TypeVar, Any
from sqlalchemy.exc import OperationalError, DisconnectionError
import psycopg2

from server.utils.db_health import is_neon_error, log_db_error

logger = logging.getLogger(__name__)

T = TypeVar('T')  # Generic type for return values from db operations


def db_retry(
    op_name: str,
    fn: Callable[[], T],
    max_tries: int = 5,
    base_sleep: float = 1.0
) -> Optional[T]:
    """
    Execute a database operation with retry and exponential backoff.
    
    If the operation fails due to DB connectivity issues (OperationalError),
    this will retry with exponential backoff. After max_tries, it returns None
    instead of raising an exception, allowing the caller to handle gracefully.
    
    Args:
        op_name: Operation name for logging (e.g., "fetch_stale_sessions")
        fn: Function to execute (should return a value or raise OperationalError)
        max_tries: Maximum number of retry attempts (default: 5)
        base_sleep: Base sleep duration in seconds for exponential backoff (default: 1.0)
    
    Returns:
        Result of fn() if successful, None if all retries exhausted
    
    Example:
        # Instead of:
        # sessions = WhatsAppConversation.query.filter(...).all()
        
        # Use:
        sessions = db_retry(
            "get_stale_sessions",
            lambda: WhatsAppConversation.query.filter(...).all()
        )
        if sessions is None:
            logger.warning("[WA] DB unavailable, skipping processing cycle")
            return
    """
    
    for attempt in range(max_tries):
        try:
            return fn()
            
        except (OperationalError, DisconnectionError, psycopg2.OperationalError) as e:
            sleep_s = base_sleep * (2 ** attempt)
            
            # Log with context
            log_db_error(e, context=op_name)
            
            if is_neon_error(e):
                logger.error(
                    f"[DB_DOWN] op={op_name} try={attempt + 1}/{max_tries} "
                    f"sleep={sleep_s}s reason=NeonEndpointDisabled"
                )
            else:
                logger.error(
                    f"[DB_DOWN] op={op_name} try={attempt + 1}/{max_tries} "
                    f"sleep={sleep_s}s err={str(e)[:100]}"
                )
            
            # If this was the last attempt, return None
            if attempt == max_tries - 1:
                logger.critical(
                    f"[DB_DOWN] op={op_name} FAILED after {max_tries} tries - "
                    f"returning None for graceful degradation"
                )
                return None
            
            # Sleep with exponential backoff before next retry
            time.sleep(sleep_s)
            
        except Exception as e:
            # Non-DB errors should still be raised (don't hide bugs)
            logger.error(f"[DB_RETRY] op={op_name} non-DB error: {type(e).__name__}: {e}")
            raise
    
    # Should never reach here, but type checker needs it
    return None


def db_operation_safe(op_name: str, fn: Callable[[], T], default: Any = None) -> T:
    """
    Wrapper for DB operations that should never crash the application.
    Similar to db_retry but allows specifying a default return value.
    
    Args:
        op_name: Operation name for logging
        fn: Function to execute
        default: Default value to return if operation fails (default: None)
    
    Returns:
        Result of fn() if successful, default value if failed
    
    Example:
        count = db_operation_safe(
            "count_active_chats",
            lambda: WhatsAppConversation.query.filter_by(is_open=True).count(),
            default=0
        )
    """
    result = db_retry(op_name, fn, max_tries=3, base_sleep=1.0)
    return result if result is not None else default
