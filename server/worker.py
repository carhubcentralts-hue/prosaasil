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
import traceback
import threading
from datetime import datetime, timezone

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s [%(name)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def log_fatal_error(stage, error):
    """Log a fatal error with full context and exit"""
    logger.error("=" * 80)
    logger.error(f"❌ WORKER BOOTSTRAP FAILED AT: {stage}")
    logger.error("=" * 80)
    logger.error(f"Python executable: {sys.executable}")
    logger.error(f"Python version: {sys.version.split()[0]}")
    logger.error(f"Error type: {type(error).__name__}")
    logger.error(f"Error message: {error}")
    logger.error("-" * 80)
    logger.error("Full traceback:")
    logger.error(traceback.format_exc())
    logger.error("=" * 80)
    sys.exit(1)

# Check required environment variables
# 🔥 CRITICAL: Validate DATABASE_URL using unified validator
try:
    from server.database_validation import validate_database_url
    validate_database_url()
except SystemExit:
    # validate_database_url already logged the error
    raise
except Exception as e:
    logger.error("=" * 80)
    logger.error(f"❌ CRITICAL: Failed to validate DATABASE_URL: {e}")
    logger.error("=" * 80)
    sys.exit(1)

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

# 🔥 PYTHON DIAGNOSTICS: Log Python interpreter info for debugging
logger.info(f"Python executable: {sys.executable}")
logger.info(f"Python version: {sys.version.split()[0]}")

# Get queues to listen to from environment (default: high,default,low)
RQ_QUEUES = os.getenv('RQ_QUEUES', 'high,default,low')
LISTEN_QUEUES = [q.strip() for q in RQ_QUEUES.split(',') if q.strip()]
logger.info(f"RQ_QUEUES configuration: {RQ_QUEUES}")
logger.info(f"Will listen to queues: {LISTEN_QUEUES}")

# Initialize Flask app context (needed for DB access)
try:
    from server.app_factory import create_app
    app = create_app()
    logger.info("✓ Flask app initialized")
except Exception as e:
    log_fatal_error("Flask app initialization", e)

# Import Redis and job processing modules
try:
    import redis
    from rq import Worker, Queue
    from rq.job import Job
    logger.info("✓ Redis and RQ modules imported successfully")
except Exception as e:
    log_fatal_error("Importing redis/rq modules", e)

# Connect to Redis
try:
    redis_conn = redis.from_url(REDIS_URL)
    redis_conn.ping()  # Test connection immediately
    logger.info("✓ Redis connection established")
except Exception as e:
    log_fatal_error("Connecting to Redis", e)

# Define queues dynamically based on RQ_QUEUES environment variable
# Create Queue objects for each configured queue
try:
    QUEUES = [Queue(q, connection=redis_conn) for q in LISTEN_QUEUES]
    logger.info(f"✓ Created {len(QUEUES)} queue(s): {LISTEN_QUEUES}")
except Exception as e:
    log_fatal_error("Creating RQ queues", e)

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
    logger.info("✅ RECEIPTS WORKER BOOTED pid=%s", os.getpid())
    logger.info("🔔 WORKER_START: ProSaaS Background Worker")
    logger.info("=" * 60)
    logger.info(f"Redis URL: {masked_redis_url}")
    logger.info(f"Service Role: {os.getenv('SERVICE_ROLE', 'worker')}")
    logger.info(f"Environment: {os.getenv('FLASK_ENV', 'development')}")
    logger.info(f"Worker PID: {os.getpid()}")
    logger.info(f"Listening to queues: {LISTEN_QUEUES} (priority order)")
    logger.info(f"Queue system: RQ (Redis Queue)")
    logger.info("=" * 60)
    
    # Test Redis connection
    try:
        redis_conn.ping()
        logger.info("✓ Redis connection successful")
        
        # CRITICAL: Log Redis signature for debugging connection mismatches
        try:
            redis_info = redis_conn.info('server')
            redis_id = f"{redis_info.get('redis_version', 'unknown')}@{redis_info.get('tcp_port', 'unknown')}"
            logger.info(f"📍 REDIS SIGNATURE (WORKER): {masked_redis_url} | Redis: {redis_id}")
        except Exception as info_error:
            logger.warning(f"Could not get Redis info: {info_error}")
            logger.info(f"📍 REDIS SIGNATURE (WORKER): {masked_redis_url}")
        
        # Check queue stats
        for queue in QUEUES:
            count = len(queue)
            logger.info(f"  → Queue '{queue.name}': {count} job(s) pending")
        
        # Log which queues this worker will listen to (CRITICAL for debugging)
        logger.info(f"📍 WORKER QUEUES: This worker will listen to: {LISTEN_QUEUES}")
        logger.info(f"📍 CRITICAL: Worker WILL process jobs from 'default' queue: {'default' in LISTEN_QUEUES}")
    except Exception as e:
        logger.error(f"✗ Redis connection failed: {e}")
        logger.error(f"Check that Redis is running and REDIS_URL is correct: {masked_redis_url}")
        sys.exit(1)
    
    # Create worker with Flask app context
    with app.app_context():
        logger.info("✓ Flask app context initialized")
        
        # Test that we can import job functions
        try:
            from server.jobs.gmail_sync_job import sync_gmail_receipts_job
            logger.info("✓ Job functions imported successfully")
            logger.info(f"  → sync_gmail_receipts_job: {sync_gmail_receipts_job}")
        except (ImportError, ModuleNotFoundError) as e:
            log_fatal_error("Importing job functions", e)
        
        # Create worker
        try:
            worker = Worker(
                QUEUES,
                connection=redis_conn,
                name=f'prosaas-worker-{os.getpid()}',
                # Don't fork - run jobs in main process for simplicity
                # This is fine for our use case (Gmail sync, Playwright, etc.)
                disable_default_exception_handler=False,
            )
            logger.info(f"✓ Worker created: {worker.name}")
            logger.info(f"✓ Worker will process jobs from queues: {[q.name for q in worker.queues]}")
        except Exception as e:
            log_fatal_error("Creating RQ Worker instance", e)
        logger.info("-" * 60)
        logger.info("🚀 Worker is now READY and LISTENING for jobs...")
        logger.info(f"📩 Waiting for jobs to be enqueued to {LISTEN_QUEUES} queues...")
        logger.info(f"📍 CRITICAL: Worker handles ALL receipt operations:")
        logger.info(f"   - Generate receipts (receipt generation)")
        logger.info(f"   - Sync receipts (Gmail sync)")
        logger.info(f"   - Delete receipts (batch delete)")
        logger.info(f"   - Fetch receipt PDF (download operations)")
        logger.info("-" * 60)
        
        # Heartbeat thread for monitoring
        def heartbeat_log():
            """Log worker heartbeat every 30 seconds"""
            while not shutdown_requested:
                time.sleep(30)
                try:
                    queue_stats = []
                    for queue in QUEUES:
                        count = len(queue)
                        queue_stats.append(f"{queue.name}={count}")
                    logger.debug(f"💓 receipts_worker heartbeat pid={os.getpid()} queues=[{', '.join(queue_stats)}]")
                except Exception as e:
                    logger.error(f"Heartbeat log error: {e}")
        
        heartbeat_thread = threading.Thread(target=heartbeat_log, daemon=True)
        heartbeat_thread.start()
        logger.info("✅ Heartbeat monitoring started (logs every 30s)")
        
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
            log_fatal_error("Worker runtime execution", e)
        finally:
            logger.info("Worker shutting down")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        log_fatal_error("Worker main() execution", e)
