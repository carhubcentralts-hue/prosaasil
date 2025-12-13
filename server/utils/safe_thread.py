"""
Safe Thread Wrapper - Prevents background thread crashes from killing the server
All background threads (WhatsApp, calls, media processing) should use this wrapper.

Usage:
    from server.utils.safe_thread import safe_thread
    
    def my_background_loop():
        while True:
            # Do work...
            time.sleep(5)
    
    thread = safe_thread("WhatsAppProcessor", my_background_loop, daemon=True)
    thread.start()
"""
import logging
import threading
from typing import Callable, Optional

logger = logging.getLogger(__name__)


def safe_thread(name: str, fn: Callable, daemon: bool = True) -> threading.Thread:
    """
    Create a thread that never crashes the application.
    
    Wraps the target function with exception handling to prevent thread crashes
    from propagating to the parent process. All exceptions are logged but contained.
    
    Args:
        name: Thread name for logging and debugging
        fn: Function to run in the thread
        daemon: Whether thread should be daemon (default: True)
    
    Returns:
        Thread object (not started - caller must call .start())
    
    Example:
        def process_messages():
            while True:
                # If this crashes, it won't kill the server
                process_queue()
                time.sleep(1)
        
        thread = safe_thread("MessageProcessor", process_messages)
        thread.start()
    """
    def wrapped_fn():
        try:
            logger.info(f"[THREAD_START] {name} - background thread started")
            fn()
        except KeyboardInterrupt:
            logger.info(f"[THREAD_STOP] {name} - interrupted by keyboard")
            raise
        except Exception as e:
            logger.exception(f"[THREAD_CRASH] name={name} err={e}")
            logger.critical(
                f"[THREAD_CRASH] Background thread {name} crashed. "
                f"This should not happen. Error: {type(e).__name__}: {e}"
            )
        finally:
            logger.warning(f"[THREAD_EXIT] {name} - background thread exiting")
    
    thread = threading.Thread(
        target=wrapped_fn,
        daemon=daemon,
        name=name
    )
    
    return thread


def start_safe_thread(name: str, fn: Callable, daemon: bool = True) -> threading.Thread:
    """
    Create and start a safe thread in one call.
    
    Args:
        name: Thread name
        fn: Function to run
        daemon: Whether thread should be daemon
    
    Returns:
        Started thread object
    """
    thread = safe_thread(name, fn, daemon)
    thread.start()
    return thread
