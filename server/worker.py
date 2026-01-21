#!/usr/bin/env python3
"""
ProSaaS Background Worker
Processes heavy tasks from Redis queue:
- Gmail receipts sync
- Playwright screenshots
- PDF thumbnail generation
- OCR processing

Uses Redis Simple Queue (RSQ) for job management with:
- Per-business locks with TTL
- Heartbeat mechanism
- Progress tracking
- Automatic stale run recovery
"""
import os
import sys
import time
import logging
import signal
from datetime import datetime, timezone

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s [%(name)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Check required environment variables
REDIS_URL = os.getenv('REDIS_URL')
if not REDIS_URL:
    logger.error("❌ REDIS_URL environment variable not set")
    logger.error("For production, set: REDIS_URL=redis://redis:6379/0")
    logger.error("Worker cannot start without Redis")
    sys.exit(1)

# Mask password in Redis URL for logging
masked_redis_url = REDIS_URL
if '@' in REDIS_URL:
    # Format: redis://user:password@host:port/db -> redis://user:***@host:port/db
    parts = REDIS_URL.split('@')
    if ':' in parts[0]:
        user_pass = parts[0].split(':')
        masked_redis_url = f"{user_pass[0]}:{user_pass[1].split('//')[0]}//***@{parts[1]}"

logger.info(f"REDIS_URL: {masked_redis_url}")

# Initialize Flask app context (needed for DB access)
from server.app_factory import create_app
app = create_app()

# Import Redis and job processing modules
try:
    import redis
    from rq import Worker, Queue, Connection
    from rq.job import Job
except ImportError:
    logger.error("rq package not installed. Install with: pip install rq")
    sys.exit(1)

# Import job handlers
from server.jobs.gmail_sync_job import sync_gmail_receipts_job

# Connect to Redis
redis_conn = redis.from_url(REDIS_URL)

# Define queues by priority
QUEUE_HIGH = Queue('high', connection=redis_conn)
QUEUE_DEFAULT = Queue('default', connection=redis_conn)
QUEUE_LOW = Queue('low', connection=redis_conn)

# Graceful shutdown handler
shutdown_requested = False

def handle_shutdown(signum, frame):
    """Handle graceful shutdown on SIGTERM/SIGINT"""
    global shutdown_requested
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_requested = True

signal.signal(signal.SIGTERM, handle_shutdown)
signal.signal(signal.SIGINT, handle_shutdown)

def main():
    """Main worker loop"""
    logger.info("=" * 60)
    logger.info("🔔 WORKER_START: ProSaaS Background Worker")
    logger.info("=" * 60)
    logger.info(f"Redis URL: {masked_redis_url}")
    logger.info(f"Service Role: {os.getenv('SERVICE_ROLE', 'worker')}")
    logger.info(f"Environment: {os.getenv('FLASK_ENV', 'development')}")
    logger.info(f"Worker PID: {os.getpid()}")
    logger.info(f"Listening to queues: ['high', 'default', 'low'] (priority order)")
    logger.info("=" * 60)
    
    # Test Redis connection
    try:
        redis_conn.ping()
        logger.info("✓ Redis connection successful")
        
        # Check queue stats
        for queue_name in ['high', 'default', 'low']:
            queue = Queue(queue_name, connection=redis_conn)
            count = len(queue)
            logger.info(f"  → Queue '{queue_name}': {count} job(s) pending")
    except Exception as e:
        logger.error(f"✗ Redis connection failed: {e}")
        logger.error(f"Check that Redis is running and REDIS_URL is correct: {masked_redis_url}")
        sys.exit(1)
    
    # Create worker with Flask app context
    with app.app_context():
        logger.info("✓ Flask app context initialized")
        
        # Create worker
        worker = Worker(
            [QUEUE_HIGH, QUEUE_DEFAULT, QUEUE_LOW],
            connection=redis_conn,
            name=f'prosaas-worker-{os.getpid()}',
            # Don't fork - run jobs in main process for simplicity
            # This is fine for our use case (Gmail sync, Playwright, etc.)
            disable_default_exception_handler=False,
        )
        
        logger.info(f"✓ Worker created: {worker.name}")
        logger.info("Listening on queues: high, default, low (in priority order)")
        logger.info("-" * 60)
        logger.info("Worker is now ready to process jobs...")
        logger.info("Waiting for jobs to be enqueued...")
        logger.info("-" * 60)
        
        # Start worker
        try:
            worker.work(
                with_scheduler=False,  # We don't use scheduled jobs yet
                logging_level='INFO',
                max_jobs=None,  # Process jobs indefinitely
                burst=False,  # Don't exit after processing all jobs
            )
        except KeyboardInterrupt:
            logger.info("Worker interrupted by user")
        except Exception as e:
            logger.error(f"Worker error: {e}", exc_info=True)
            raise
        finally:
            logger.info("Worker shutting down")

if __name__ == '__main__':
    main()
