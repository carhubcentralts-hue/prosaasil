"""
Scheduler Service - Periodic Job Enqueuing

This service runs as a separate process and enqueues periodic jobs to RQ.
Uses Redis locks to prevent duplicate execution across multiple instances.

Architecture:
- Runs independently from API and Worker services
- Acquires Redis lock before each cycle
- Enqueues jobs to RQ queues
- Worker processes pick up and execute jobs
"""
import os
import sys
import time
import logging
import signal
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)-8s [%(name)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Global flag for graceful shutdown
_shutdown_requested = False


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    global _shutdown_requested
    logger.info(f"🛑 Shutdown signal received ({signum})")
    _shutdown_requested = True


def acquire_scheduler_lock(redis_client, lock_key: str, ttl_seconds: int = 90) -> bool:
    """
    Acquire a Redis lock for the scheduler
    
    Args:
        redis_client: Redis client instance
        lock_key: Key for the lock
        ttl_seconds: Time-to-live for the lock (default 90s)
    
    Returns:
        True if lock acquired, False otherwise
    """
    try:
        # SET NX (set if not exists) with expiration
        acquired = redis_client.set(lock_key, datetime.utcnow().isoformat(), ex=ttl_seconds, nx=True)
        return bool(acquired)
    except Exception as e:
        logger.error(f"❌ Failed to acquire lock: {e}")
        return False


def release_scheduler_lock(redis_client, lock_key: str):
    """Release the scheduler lock"""
    try:
        redis_client.delete(lock_key)
    except Exception as e:
        logger.warning(f"⚠️ Failed to release lock: {e}")


def enqueue_periodic_jobs(redis_url: str):
    """
    Enqueue all periodic jobs to RQ
    
    Args:
        redis_url: Redis connection URL
    """
    from redis import Redis
    from rq import Queue
    
    # Connect to Redis
    redis_conn = Redis.from_url(redis_url)
    
    # Create queues
    default_queue = Queue('default', connection=redis_conn)
    low_queue = Queue('low', connection=redis_conn)
    maintenance_queue = Queue('maintenance', connection=redis_conn)
    
    jobs_enqueued = 0
    
    # 1. Reminders tick (every minute) - HIGH PRIORITY
    try:
        from server.jobs.reminders_tick_job import reminders_tick_job
        default_queue.enqueue(
            reminders_tick_job,
            job_id=f"reminders_tick_{int(time.time())}",
            job_timeout='2m',
            result_ttl=300
        )
        jobs_enqueued += 1
        logger.info("✅ Enqueued: reminders_tick_job")
    except Exception as e:
        logger.error(f"❌ Failed to enqueue reminders_tick_job: {e}")
    
    # 2. WhatsApp sessions cleanup (every 5 minutes)
    # Only run if current minute is divisible by 5
    current_minute = datetime.now().minute
    if current_minute % 5 == 0:
        try:
            from server.jobs.whatsapp_sessions_cleanup_job import whatsapp_sessions_cleanup_job
            low_queue.enqueue(
                whatsapp_sessions_cleanup_job,
                job_id=f"wa_sessions_cleanup_{int(time.time())}",
                job_timeout='10m',
                result_ttl=3600
            )
            jobs_enqueued += 1
            logger.info("✅ Enqueued: whatsapp_sessions_cleanup_job")
        except Exception as e:
            logger.error(f"❌ Failed to enqueue whatsapp_sessions_cleanup_job: {e}")
    
    # 3. Reminders cleanup (once per day at 3 AM)
    current_hour = datetime.now().hour
    if current_hour == 3 and current_minute == 0:
        try:
            from server.jobs.reminders_tick_job import reminders_cleanup_job
            maintenance_queue.enqueue(
                reminders_cleanup_job,
                job_id=f"reminders_cleanup_{datetime.now().strftime('%Y%m%d')}",
                job_timeout='30m',
                result_ttl=86400
            )
            jobs_enqueued += 1
            logger.info("✅ Enqueued: reminders_cleanup_job")
        except Exception as e:
            logger.error(f"❌ Failed to enqueue reminders_cleanup_job: {e}")
    
    # 4. Recordings cleanup (once per day at 4 AM)
    if current_hour == 4 and current_minute == 0:
        try:
            from server.jobs.cleanup_recordings_job import cleanup_old_recordings_job
            maintenance_queue.enqueue(
                cleanup_old_recordings_job,
                job_id=f"cleanup_recordings_{datetime.now().strftime('%Y%m%d')}",
                job_timeout='1h',
                result_ttl=86400
            )
            jobs_enqueued += 1
            logger.info("✅ Enqueued: cleanup_old_recordings_job")
        except Exception as e:
            logger.error(f"❌ Failed to enqueue cleanup_old_recordings_job: {e}")
    
    logger.info(f"📊 Enqueued {jobs_enqueued} jobs this cycle")
    return jobs_enqueued


def run_scheduler():
    """
    Main scheduler loop
    
    Runs continuously, enqueuing periodic jobs with Redis lock protection.
    """
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Get configuration
    redis_url = os.getenv('REDIS_URL', 'redis://redis:6379/0')
    lock_key = 'scheduler:global_lock'
    lock_ttl = 90  # 90 seconds
    cycle_interval = 60  # Run every 60 seconds
    
    logger.info("🚀 Scheduler service starting")
    logger.info(f"📊 Configuration:")
    logger.info(f"   Redis URL: {redis_url}")
    logger.info(f"   Lock key: {lock_key}")
    logger.info(f"   Lock TTL: {lock_ttl}s")
    logger.info(f"   Cycle interval: {cycle_interval}s")
    
    # Connect to Redis
    from redis import Redis
    redis_client = Redis.from_url(redis_url)
    
    # Test connection
    try:
        redis_client.ping()
        logger.info("✅ Redis connection successful")
    except Exception as e:
        logger.error(f"❌ Failed to connect to Redis: {e}")
        sys.exit(1)
    
    # Wait a bit before first cycle (let services stabilize)
    logger.info("⏳ Waiting 30 seconds before first cycle...")
    time.sleep(30)
    
    cycle_count = 0
    
    while not _shutdown_requested:
        cycle_count += 1
        cycle_start = time.time()
        
        try:
            # Acquire lock
            if not acquire_scheduler_lock(redis_client, lock_key, lock_ttl):
                logger.info(f"⏭️ Lock held by another instance, skipping cycle {cycle_count}")
            else:
                logger.info(f"🔒 Lock acquired for cycle {cycle_count}")
                
                try:
                    # Enqueue jobs
                    jobs_enqueued = enqueue_periodic_jobs(redis_url)
                    
                    logger.info(f"✅ Cycle {cycle_count} completed: {jobs_enqueued} jobs enqueued")
                except Exception as e:
                    logger.error(f"❌ Error during cycle {cycle_count}: {e}")
                    import traceback
                    traceback.print_exc()
                finally:
                    # Release lock
                    release_scheduler_lock(redis_client, lock_key)
                    logger.info(f"🔓 Lock released for cycle {cycle_count}")
        
        except Exception as e:
            logger.error(f"❌ Fatal error in cycle {cycle_count}: {e}")
            import traceback
            traceback.print_exc()
        
        # Calculate sleep time to maintain consistent interval
        cycle_duration = time.time() - cycle_start
        sleep_time = max(0, cycle_interval - cycle_duration)
        
        if sleep_time > 0:
            logger.info(f"⏳ Sleeping {sleep_time:.1f}s until next cycle...")
            time.sleep(sleep_time)
        else:
            logger.warning(f"⚠️ Cycle took {cycle_duration:.1f}s (longer than {cycle_interval}s interval)")
    
    logger.info("🛑 Scheduler service shutting down gracefully")
    release_scheduler_lock(redis_client, lock_key)


if __name__ == '__main__':
    # Add project root to Python path
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    sys.path.insert(0, project_root)
    
    # Initialize Flask app for imports
    os.environ['MIGRATION_MODE'] = '0'  # Not migration mode
    
    logger.info("🔧 Initializing Flask app...")
    from server.app_factory import get_process_app
    app = get_process_app()
    
    with app.app_context():
        logger.info("✅ Flask app initialized")
        run_scheduler()
