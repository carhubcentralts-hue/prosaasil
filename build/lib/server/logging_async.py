"""
⚡ PHASE 1: Async logging for Eventlet-based applications
Prevents blocking I/O in hot path by using Queue + green thread worker
"""
import logging
import queue
import eventlet
import sys

_log_q = queue.Queue(maxsize=10000)

class QueueHandler(logging.Handler):
    """Handler that puts log records into a queue without blocking"""
    def emit(self, record):
        try:
            _log_q.put_nowait(record)
        except queue.Full:
            pass  # Drop silently if queue is full (prevents blocking)

def _log_worker():
    """Green thread worker that consumes log records and prints them"""
    while True:
        rec = _log_q.get()
        try:
            msg = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
            ).format(rec)
            print(msg, file=sys.stderr, flush=False)
        except Exception:
            pass
        eventlet.sleep(0)  # Yield to other green threads

def setup_async_root(level=logging.INFO):
    """
    Setup async logging with Eventlet-compatible worker
    
    Safe for Flask + Eventlet + WebSocket environments.
    Uses eventlet.spawn instead of threading.Thread to avoid conflicts.
    """
    root = logging.getLogger()
    root.setLevel(level)
    
    # Remove existing handlers
    for h in list(root.handlers):
        root.removeHandler(h)
    
    # Add queue handler
    root.addHandler(QueueHandler())
    
    # Spawn green thread worker
    eventlet.spawn(_log_worker)
    
    return root
