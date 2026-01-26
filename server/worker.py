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

# Get queues to listen to from environment
# Queue purposes:
#   high       - High priority tasks
#   default    - Standard tasks (calls, general processing)
#   low        - Low priority background tasks  
#   maintenance - Database maintenance (bulk deletes, updates)
#   broadcasts  - WhatsApp broadcast processing
#   recordings  - Recording transcription and processing
RQ_QUEUES = os.getenv('RQ_QUEUES', 'high,default,low,maintenance,broadcasts,recordings')
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
    logger.info("=" * 70)
    logger.info("🔨 WORKER QUEUES CONFIGURATION")
    logger.info("=" * 70)
    logger.info(f"RQ_QUEUES env var: {RQ_QUEUES}")
    logger.info(f"Listening to {len(QUEUES)} queue(s): {LISTEN_QUEUES}")
    for q in LISTEN_QUEUES:
        logger.info(f"  → {q}")
    logger.info("=" * 70)
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
            from server.jobs.delete_receipts_job import delete_receipts_batch_job
            from server.jobs.broadcast_job import process_broadcast_job
            from server.jobs.delete_leads_job import delete_leads_batch_job
            from server.jobs.update_leads_job import update_leads_batch_job
            from server.jobs.delete_imported_leads_job import delete_imported_leads_batch_job
            from server.jobs.enqueue_outbound_calls_job import enqueue_outbound_calls_batch_job
            logger.info("✓ Job functions imported successfully")
            logger.info(f"  → sync_gmail_receipts_job: {sync_gmail_receipts_job}")
            logger.info(f"  → delete_receipts_batch_job: {delete_receipts_batch_job}")
            logger.info(f"  → process_broadcast_job: {process_broadcast_job}")
            logger.info(f"  → delete_leads_batch_job: {delete_leads_batch_job}")
            logger.info(f"  → update_leads_batch_job: {update_leads_batch_job}")
            logger.info(f"  → delete_imported_leads_batch_job: {delete_imported_leads_batch_job}")
            logger.info(f"  → enqueue_outbound_calls_batch_job: {enqueue_outbound_calls_batch_job}")
        except (ImportError, ModuleNotFoundError) as e:
            log_fatal_error("Importing job functions", e)
        
        # Create worker
        try:
            # Define custom job failure handler to log errors
            def failed_job_handler(job, connection, type, value, traceback, worker_name):
                """Log when job fails"""
                queue_name = getattr(job, 'origin', 'unknown')
                job_func_name = job.func_name if hasattr(job, 'func_name') else 'unknown'
                logger.error("=" * 60)
                logger.error(f"❌ JOB FAILED queue='{queue_name}' job_id={job.id} function={job_func_name}")
                logger.error(f"   → error: {value}")
                logger.error("=" * 60)
            
            worker = Worker(
                QUEUES,
                connection=redis_conn,
                name=f'prosaas-worker-{os.getpid()}',
                # Don't fork - run jobs in main process for simplicity
                # This is fine for our use case (Gmail sync, Playwright, etc.)
                disable_default_exception_handler=False,
            )
            
            # Monkey-patch the execute_job method to add logging
            original_execute_job = worker.execute_job
            def logged_execute_job(job, queue):
                """Wrapper that logs before executing job"""
                queue_name = queue.name if queue else 'unknown'
                job_func_name = job.func_name if hasattr(job, 'func_name') else 'unknown'
                logger.info("=" * 60)
                logger.info(f"🔨 JOB PICKED queue='{queue_name}' job_id={job.id} function={job_func_name}")
                logger.info(f"   → args: {getattr(job, 'args', ())}")
                logger.info(f"   → worker: {worker.name}")
                logger.info("=" * 60)
                
                # Call original implementation
                return original_execute_job(job, queue)
            
            worker.execute_job = logged_execute_job
            
            # Register custom failure handler for better logging
            import rq.worker
            worker.push_exc_handler(failed_job_handler)
            
            logger.info(f"✓ Worker created: {worker.name}")
            logger.info(f"✓ Worker will process jobs from queues: {[q.name for q in worker.queues]}")
            logger.info(f"✓ Worker will log: 🔨 JOB PICKED when picking up jobs")
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
        
        # 🚨 CRITICAL NOTE: Recording worker thread NOT started here
        # REASON: RECORDING_QUEUE is queue.Queue() (in-memory), NOT Redis!
        # IN-MEMORY QUEUES DON'T WORK ACROSS CONTAINERS:
        #   - API container enqueues to its memory
        #   - Worker container has separate memory
        #   - Jobs never consumed = infinite loop
        # 
        # SOLUTION: Convert recording jobs to use RQ (Redis Queue)
        # See: CRITICAL_RECORDING_QUEUE_ARCHITECTURE.md
        # 
        # When converted to RQ, worker will automatically process 'recordings' queue
        # because it's already in RQ_QUEUES configuration.
        
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
