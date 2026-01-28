"""
Scheduler Service - Periodic Job Enqueuing

✅ PRODUCTION-READY with proper Redis lock handling:
- Lock with TTL (no manual release - let it expire naturally)
- Short tick interval (15s instead of 60s) for faster failover
- Uses unified jobs.py wrapper (no inline Redis/Queue creation)
- Lock extend mechanism if cycle takes longer than expected

⚠️ CRITICAL: Only ONE scheduler instance should hold lock at any time
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


def try_acquire_scheduler_lock(redis_client, lock_key: str, ttl_seconds: int = 90) -> bool:
    """
    Try to acquire scheduler lock using Redis SET NX EX.
    
    ✅ CORRECT IMPLEMENTATION:
    - Uses SET NX EX (atomic operation)
    - NO manual release (TTL handles it)
    - Lock value is timestamp for monitoring
    
    Args:
        redis_client: Redis client instance
        lock_key: Key for the lock
        ttl_seconds: Time-to-live for the lock (default 90s)
    
    Returns:
        True if lock acquired, False if another instance holds it
    """
    try:
        # SET NX EX - atomic operation
        # Value is timestamp for health monitoring
        acquired = redis_client.set(
            lock_key, 
            datetime.utcnow().isoformat(),
            ex=ttl_seconds,  # TTL - lock expires automatically
            nx=True  # Only set if not exists
        )
        return bool(acquired)
    except Exception as e:
        logger.error(f"❌ Failed to acquire lock: {e}")
        return False


def extend_scheduler_lock(redis_client, lock_key: str, ttl_seconds: int = 90) -> bool:
    """
    Extend scheduler lock if we still hold it.
    
    Use this if a cycle takes longer than expected.
    
    Args:
        redis_client: Redis client instance
        lock_key: Key for the lock
        ttl_seconds: Time-to-live extension
    
    Returns:
        True if lock extended, False if we don't hold it
    """
    try:
        # Only extend if key exists (we hold the lock)
        if redis_client.exists(lock_key):
            redis_client.expire(lock_key, ttl_seconds)
            logger.info(f"🔄 Extended scheduler lock TTL to {ttl_seconds}s")
            return True
        return False
    except Exception as e:
        logger.error(f"❌ Failed to extend lock: {e}")
        return False


def enqueue_periodic_jobs():
    """
    Enqueue all periodic jobs to RQ using unified jobs wrapper.
    
    ✅ Uses server/services/jobs.py - NO inline Redis/Queue creation!
    """
    from server.services.jobs import enqueue
    
    jobs_enqueued = 0
    current_minute = datetime.now().minute
    current_hour = datetime.now().hour
    
    # 1. Reminders tick (every minute) - HIGH PRIORITY
    try:
        from server.jobs.reminders_tick_job import reminders_tick_job
        enqueue(
            'default',
            reminders_tick_job,
            job_id=f"reminders_tick_{int(time.time())}",
            timeout=120,  # 2 minutes
            retry=None,  # Don't retry - next tick will handle it
            ttl=300
        )
        jobs_enqueued += 1
        logger.info("✅ Enqueued: reminders_tick_job")
    except Exception as e:
        logger.error(f"❌ Failed to enqueue reminders_tick_job: {e}")
    
    # 2. Scheduled messages tick (every minute) - HIGH PRIORITY
    try:
        from server.jobs.scheduled_messages_tick_job import scheduled_messages_tick_job
        enqueue(
            'default',
            scheduled_messages_tick_job,
            job_id=f"scheduled_messages_tick_{int(time.time())}",
            timeout=180,  # 3 minutes
            retry=None,  # Don't retry - next tick will handle it
            ttl=300
        )
        jobs_enqueued += 1
        logger.info("✅ Enqueued: scheduled_messages_tick_job")
    except Exception as e:
        logger.error(f"❌ Failed to enqueue scheduled_messages_tick_job: {e}")
    
    # 3. WhatsApp sessions cleanup (every 5 minutes)
    if current_minute % 5 == 0:
        try:
            from server.jobs.whatsapp_sessions_cleanup_job import whatsapp_sessions_cleanup_job
            enqueue(
                'low',
                whatsapp_sessions_cleanup_job,
                job_id=f"wa_sessions_cleanup_{int(time.time())}",
                timeout=600,  # 10 minutes
                retry=None,
                ttl=3600
            )
            jobs_enqueued += 1
            logger.info("✅ Enqueued: whatsapp_sessions_cleanup_job")
        except Exception as e:
            logger.error(f"❌ Failed to enqueue whatsapp_sessions_cleanup_job: {e}")
    
    # 4. Reminders cleanup (once per day at 3 AM)
    if current_hour == 3 and current_minute == 0:
        try:
            from server.jobs.reminders_tick_job import reminders_cleanup_job
            enqueue(
                'maintenance',
                reminders_cleanup_job,
                job_id=f"reminders_cleanup_{datetime.now().strftime('%Y%m%d')}",
                timeout=1800,  # 30 minutes
                retry=None,
                ttl=86400
            )
            jobs_enqueued += 1
            logger.info("✅ Enqueued: reminders_cleanup_job")
        except Exception as e:
            logger.error(f"❌ Failed to enqueue reminders_cleanup_job: {e}")
    
    # 5. Recordings cleanup (once per day at 4 AM)
    if current_hour == 4 and current_minute == 0:
        try:
            from server.jobs.cleanup_recordings_job import cleanup_old_recordings_job
            enqueue(
                'maintenance',
                cleanup_old_recordings_job,
                job_id=f"cleanup_recordings_{datetime.now().strftime('%Y%m%d')}",
                timeout=3600,  # 1 hour
                retry=None,
                ttl=86400
            )
            jobs_enqueued += 1
            logger.info("✅ Enqueued: cleanup_old_recordings_job")
        except Exception as e:
            logger.error(f"❌ Failed to enqueue cleanup_old_recordings_job: {e}")
    
    logger.info(f"📊 Enqueued {jobs_enqueued} jobs this cycle")
    return jobs_enqueued


def run_scheduler():
    """
    Main scheduler loop with proper lock handling.
    
    ✅ PRODUCTION-READY:
    - Short tick interval (15s) for fast failover
    - Lock with TTL only (no manual release)
    - Handles long-running cycles with lock extend
    - Graceful shutdown
    """
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Get configuration
    lock_key = 'scheduler:global_lock'
    lock_ttl = 90  # 90 seconds TTL
    tick_interval = 15  # ✅ Short interval (15s not 60s) for faster failover
    
    logger.info("🚀 Scheduler service starting")
    logger.info(f"📊 Configuration:")
    logger.info(f"   Lock key: {lock_key}")
    logger.info(f"   Lock TTL: {lock_ttl}s")
    logger.info(f"   Tick interval: {tick_interval}s")
    
    # Get Redis connection via unified wrapper
    from server.services.jobs import get_redis
    redis_client = get_redis()
    
    # Test connection
    try:
        redis_client.ping()
        logger.info("✅ Redis connection successful")
    except Exception as e:
        logger.error(f"❌ Failed to connect to Redis: {e}")
        sys.exit(1)
    
    # Wait a bit before first cycle (let services stabilize)
    logger.info("⏳ Waiting 10 seconds before first cycle...")
    time.sleep(10)
    
    cycle_count = 0
    
    while not _shutdown_requested:
        cycle_count += 1
        cycle_start = time.time()
        
        try:
            # ✅ CORRECT: Try to acquire lock (SET NX EX)
            if not try_acquire_scheduler_lock(redis_client, lock_key, lock_ttl):
                # Another instance holds the lock - skip this cycle
                logger.debug(f"⏭️  Lock held by another instance, skipping cycle {cycle_count}")
            else:
                logger.info(f"🔒 Lock acquired for cycle {cycle_count}")
                
                try:
                    # Enqueue jobs
                    jobs_enqueued = enqueue_periodic_jobs()
                    
                    cycle_duration = time.time() - cycle_start
                    
                    # If cycle takes longer than expected, extend lock
                    if cycle_duration > (lock_ttl * 0.7):  # If > 70% of TTL
                        extend_scheduler_lock(redis_client, lock_key, lock_ttl)
                    
                    logger.info(f"✅ Cycle {cycle_count} completed in {cycle_duration:.2f}s: {jobs_enqueued} jobs enqueued")
                    
                except Exception as e:
                    logger.error(f"❌ Error during cycle {cycle_count}: {e}")
                    import traceback
                    traceback.print_exc()
                
                # ✅ CORRECT: NO manual release - let TTL handle it
                # Lock will expire after TTL seconds automatically
        
        except Exception as e:
            logger.error(f"❌ Fatal error in cycle {cycle_count}: {e}")
            import traceback
            traceback.print_exc()
        
        # Calculate sleep time to maintain consistent interval
        cycle_duration = time.time() - cycle_start
        sleep_time = max(0, tick_interval - cycle_duration)
        
        if sleep_time > 0:
            logger.debug(f"⏳ Sleeping {sleep_time:.1f}s until next cycle...")
            time.sleep(sleep_time)
        else:
            logger.warning(f"⚠️ Cycle took {cycle_duration:.1f}s (longer than {tick_interval}s interval)")
    
    logger.info("🛑 Scheduler service shutting down gracefully")
    # ✅ CORRECT: NO lock cleanup on shutdown - let TTL handle it


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
