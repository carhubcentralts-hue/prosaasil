"""
Unified Job Enqueue Service
Single source of truth for enqueuing background jobs to RQ (Redis Queue)

✅ PRODUCTION-READY FEATURES:
- Single Redis connection (no inline Redis.from_url())
- Deterministic job IDs from external events (message_id, call_sid, etc.)
- Atomic deduplication via Redis SETNX
- Business isolation (all jobs tagged with business_id)
- Correlation IDs for distributed tracing
- Unified logging (start/success/fail/retry)
- Job cancellation support

⚠️ USAGE:
    from server.services.jobs import enqueue, enqueue_with_dedupe
    
    # Simple enqueue
    enqueue('default', my_job_func, business_id=123, arg1='value')
    
    # With deduplication (for webhooks, external events)
    enqueue_with_dedupe(
        'default', 
        webhook_process_job,
        dedupe_key='webhook:baileys:msg_ABC123',
        business_id=123,
        tenant_id='123',
        messages=[...]
    )
"""
import os
import logging
import uuid
import hashlib
from datetime import datetime
from typing import Callable, Any, Optional, Dict
from redis import Redis
from rq import Queue
from rq.job import Job
from rq import Retry

logger = logging.getLogger(__name__)

# Redis connection singleton - NEVER create Redis connections elsewhere!
_redis_conn = None
_redis_lock = __import__('threading').Lock()

def get_redis() -> Redis:
    """
    Get or create singleton Redis connection.
    
    ⚠️ CRITICAL: This is the ONLY place Redis connections should be created!
    Never use Redis.from_url() directly in routes or services.
    
    Returns:
        Redis: Singleton Redis connection
    """
    global _redis_conn
    if _redis_conn is None:
        with _redis_lock:
            if _redis_conn is None:  # Double-check pattern
                redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
                _redis_conn = Redis.from_url(
                    redis_url,
                    decode_responses=False,  # Keep binary for RQ compatibility
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True,
                    health_check_interval=30
                )
                logger.info(f"[JOBS] Redis connection established: {redis_url}")
    return _redis_conn


def get_queue(queue_name: str = 'default') -> Queue:
    """
    Get RQ queue by name.
    
    Args:
        queue_name: Queue name ('high', 'default', 'low', 'maintenance', 'broadcasts', 'recordings', 'receipts', 'receipts_sync')
    
    Returns:
        Queue: RQ queue instance
    """
    redis_conn = get_redis()
    return Queue(queue_name, connection=redis_conn)


def generate_deterministic_job_id(prefix: str, *identifiers) -> str:
    """
    Generate deterministic job ID from external identifiers.
    
    ⚠️ CRITICAL for deduplication: Same inputs = same job ID
    
    Args:
        prefix: Job type prefix (e.g., 'webhook', 'push', 'recording')
        *identifiers: Variable number of identifiers (message_id, call_sid, etc.)
    
    Returns:
        str: Deterministic job ID (e.g., 'webhook:abc123def456')
    
    Examples:
        >>> generate_deterministic_job_id('webhook', 'baileys', 'msg_ABC123')
        'webhook:3a7b9c...'
        >>> generate_deterministic_job_id('push', notification_id)
        'push:notification_123'
        >>> generate_deterministic_job_id('recording', call_sid, business_id)
        'recording:call_abc:biz_123'
    """
    # Join identifiers and hash them for consistent length
    identifier_str = ':'.join(str(i) for i in identifiers)
    hash_digest = hashlib.sha256(identifier_str.encode()).hexdigest()[:16]
    return f"{prefix}:{hash_digest}"


def enqueue(
    queue_name: str,
    func: Callable,
    *args,
    business_id: Optional[int] = None,
    run_id: Optional[int] = None,
    job_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    ttl: int = 600,
    timeout: int = 300,
    retry: Optional[int] = 3,
    description: Optional[str] = None,
    **kwargs
) -> Job:
    """
    Enqueue a job to RQ with unified metadata and logging.
    
    ✅ USE THIS for all job enqueuing (replaces inline Redis/Queue creation)
    
    Args:
        queue_name: Queue to enqueue to ('high', 'default', 'low', 'maintenance', 'broadcasts', 'recordings')
        func: Function to execute (must be importable by worker)
        *args: Positional arguments for func
        business_id: Business ID for tenant isolation (CRITICAL for multi-tenant security)
                    NOTE: This is stored in job.meta AND passed to the function if present in kwargs
        run_id: Optional run ID for job grouping
        job_id: Optional custom job ID (for deduplication - use generate_deterministic_job_id)
        trace_id: Optional trace ID for distributed tracing
        ttl: Job TTL in seconds (how long job stays in queue before expiring)
        timeout: Job execution timeout in seconds
        retry: Number of retry attempts (None = no retry)
        description: Human-readable job description
        **kwargs: Keyword arguments for func (all kwargs are passed to the function)
    
    Returns:
        rq.job.Job: The enqueued job
    
    Example:
        from server.services.jobs import enqueue
        from server.jobs.webhook_process_job import webhook_process_job
        
        enqueue(
            'default',
            webhook_process_job,
            business_id=123,
            tenant_id='123',
            messages=[...],
            job_id=generate_deterministic_job_id('webhook', 'baileys', message_id)
        )
    """
    redis_conn = get_redis()
    queue = get_queue(queue_name)
    
    # Generate IDs if not provided
    if not job_id:
        job_id = str(uuid.uuid4())
    if not trace_id:
        trace_id = str(uuid.uuid4())
    
    # Create job metadata
    meta = {
        'business_id': business_id,
        'run_id': run_id,
        'trace_id': trace_id,
        'enqueued_at': datetime.utcnow().isoformat(),
        'description': description or func.__name__
    }
    
    # Build job kwargs
    # Note: RQ expects 'job_timeout' (not 'timeout') as the parameter name
    # to configure job execution timeout. Using 'timeout' would pass it as
    # a kwarg to the job function instead.
    job_kwargs = {
        'job_id': job_id,
        'meta': meta,
        'ttl': ttl,
        'job_timeout': timeout,
        'description': description or f"{func.__name__}",
    }
    
    # Add retry if specified
    if retry is not None:
        job_kwargs['retry'] = Retry(max=retry)
    
    # Log enqueue
    log_context = f"[JOB-ENQUEUE] queue={queue_name} func={func.__name__} job_id={job_id[:8] if len(job_id) > 8 else job_id}"
    if business_id:
        log_context += f" business_id={business_id}"
    if run_id:
        log_context += f" run_id={run_id}"
    logger.info(f"{log_context} trace_id={trace_id[:8]}")
    
    # 🔥 CRITICAL FIX: Pass ALL kwargs to job function, including business_id if provided
    # Previously, business_id was only stored in job.meta and not passed to the function,
    # causing "missing required argument" errors for jobs that need business_id parameter.
    # Now we pass all kwargs to the function. If business_id is passed as a kwarg,
    # it will be sent to the function AND stored in job.meta for tracking.
    job_func_kwargs = dict(kwargs)
    
    # If business_id is provided but not in kwargs, add it to function kwargs
    # This ensures backward compatibility for jobs that expect business_id parameter
    if business_id is not None and 'business_id' not in job_func_kwargs:
        job_func_kwargs['business_id'] = business_id
    
    # Enqueue job
    try:
        job = queue.enqueue(
            func,
            *args,
            **job_func_kwargs,
            **job_kwargs
        )
        return job
    except Exception as e:
        logger.error(f"[JOB-ENQUEUE] Failed to enqueue {func.__name__}: {e}")
        raise


def enqueue_with_dedupe(
    queue_name: str,
    func: Callable,
    dedupe_key: str,
    *args,
    business_id: Optional[int] = None,
    ttl: int = 600,
    timeout: int = 300,
    retry: Optional[int] = 3,
    **kwargs
) -> Optional[Job]:
    """
    Enqueue a job with Redis SETNX deduplication.
    
    ⚠️ CRITICAL: Use this for all external events (webhooks, Twilio callbacks, etc.)
    
    Atomically checks if job already exists and enqueues only if not.
    Uses Redis SET NX (set if not exists) for atomic deduplication.
    
    Args:
        queue_name: Queue to enqueue to
        func: Function to execute
        dedupe_key: Unique key for deduplication (e.g., "webhook:baileys:msg_ABC123")
        *args: Positional arguments for func
        business_id: Business ID for tenant isolation
        ttl: Job TTL in seconds (also used for dedupe lock TTL)
        timeout: Job execution timeout in seconds
        retry: Number of retry attempts
        **kwargs: Keyword arguments for func
    
    Returns:
        rq.job.Job or None: The enqueued job, or None if duplicate already exists
    
    Example:
        from server.services.jobs import enqueue_with_dedupe
        
        job = enqueue_with_dedupe(
            'default',
            webhook_process_job,
            dedupe_key=f'webhook:baileys:{message_id}',
            business_id=123,
            tenant_id='123',
            messages=[...]
        )
        
        if job is None:
            logger.info("Duplicate webhook - skipped")
    """
    redis_conn = get_redis()
    
    # Atomic deduplication: SET NX (set if not exists) with TTL
    lock_key = f"job_lock:{dedupe_key}"
    lock_acquired = redis_conn.set(lock_key, "1", ex=ttl, nx=True)
    
    if not lock_acquired:
        logger.info(f"[JOB-DEDUPE] Skipping duplicate: {dedupe_key}")
        return None
    
    # Generate deterministic job ID from dedupe key
    job_id = f"deduped:{dedupe_key}"
    
    try:
        job = enqueue(
            queue_name,
            func,
            *args,
            business_id=business_id,
            job_id=job_id,
            ttl=ttl,
            timeout=timeout,
            retry=retry,
            description=f"Deduplicated job: {dedupe_key}",
            **kwargs
        )
        
        logger.info(f"[JOB-DEDUPE] Enqueued unique job: {dedupe_key}")
        return job
        
    except Exception as e:
        # Release lock on failure so it can be retried
        redis_conn.delete(lock_key)
        logger.error(f"[JOB-DEDUPE] Failed to enqueue {dedupe_key}, released lock: {e}")
        raise


def cancel_jobs_for_run(run_id: int, business_id: Optional[int] = None) -> int:
    """
    Cancel all jobs associated with a specific run_id.
    
    Args:
        run_id: The run ID to cancel jobs for
        business_id: Optional business ID for additional validation
    
    Returns:
        int: Number of jobs cancelled
    """
    redis_conn = get_redis()
    cancelled_count = 0
    
    # Search all queues for jobs with matching run_id
    queue_names = ['high', 'default', 'low', 'maintenance', 'broadcasts', 'recordings', 'receipts', 'receipts_sync']
    
    for queue_name in queue_names:
        queue = get_queue(queue_name)
        
        # Get all jobs in queue
        for job in queue.jobs:
            meta = job.meta or {}
            
            # Check if job matches run_id (and business_id if provided)
            if meta.get('run_id') == run_id:
                if business_id is None or meta.get('business_id') == business_id:
                    try:
                        job.cancel()
                        cancelled_count += 1
                        logger.info(f"[JOB-CANCEL] Cancelled job {job.id[:8]} for run_id={run_id}")
                    except Exception as e:
                        logger.error(f"[JOB-CANCEL] Failed to cancel job {job.id}: {e}")
    
    logger.info(f"[JOB-CANCEL] Cancelled {cancelled_count} jobs for run_id={run_id}")
    return cancelled_count


def get_job_status(job_id: str) -> Optional[Dict[str, Any]]:
    """
    Get status of a job by ID.
    
    Args:
        job_id: Job ID to query
    
    Returns:
        dict: Job status info or None if not found
    """
    try:
        redis_conn = get_redis()
        job = Job.fetch(job_id, connection=redis_conn)
        
        return {
            'job_id': job.id,
            'status': job.get_status(),
            'created_at': job.created_at.isoformat() if job.created_at else None,
            'started_at': job.started_at.isoformat() if job.started_at else None,
            'ended_at': job.ended_at.isoformat() if job.ended_at else None,
            'result': job.result,
            'exc_info': job.exc_info,
            'meta': job.meta
        }
    except Exception as e:
        logger.error(f"[JOB-STATUS] Failed to fetch job {job_id}: {e}")
        return None


def get_queue_stats() -> Dict[str, Dict[str, int]]:
    """
    Get statistics for all queues.
    
    Returns:
        dict: Queue statistics by queue name
        
    Example:
        {
            'default': {'queued': 5, 'started': 2, 'finished': 100, 'failed': 3},
            'high': {'queued': 0, 'started': 0, 'finished': 50, 'failed': 0},
            ...
        }
    """
    from rq.registry import StartedJobRegistry, FinishedJobRegistry, FailedJobRegistry
    
    redis_conn = get_redis()
    stats = {}
    
    queue_names = ['high', 'default', 'low', 'maintenance', 'broadcasts', 'recordings', 'receipts', 'receipts_sync']
    
    for queue_name in queue_names:
        try:
            queue = get_queue(queue_name)
            started_registry = StartedJobRegistry(queue=queue)
            finished_registry = FinishedJobRegistry(queue=queue)
            failed_registry = FailedJobRegistry(queue=queue)
            
            stats[queue_name] = {
                'queued': len(queue),
                'started': len(started_registry),
                'finished': len(finished_registry),
                'failed': len(failed_registry)
            }
        except Exception as e:
            logger.error(f"[QUEUE-STATS] Failed to get stats for {queue_name}: {e}")
            stats[queue_name] = {'error': str(e)}
    
    return stats


def get_scheduler_health() -> Dict[str, Any]:
    """
    Get scheduler health information.
    
    Returns:
        dict: Scheduler health data
        
    Example:
        {
            'last_tick': '2026-01-28T19:00:00Z',
            'lock_held': True,
            'lock_ttl': 75  # seconds remaining
        }
    """
    redis_conn = get_redis()
    
    try:
        # Check scheduler lock
        lock_key = 'scheduler:global_lock'
        lock_value = redis_conn.get(lock_key)
        lock_ttl = redis_conn.ttl(lock_key) if lock_value else None
        
        return {
            'last_tick': lock_value.decode() if lock_value else None,
            'lock_held': bool(lock_value),
            'lock_ttl': lock_ttl if lock_ttl and lock_ttl > 0 else None
        }
    except Exception as e:
        logger.error(f"[SCHEDULER-HEALTH] Failed to get health: {e}")
        return {'error': str(e)}


def get_worker_config() -> Dict[str, Any]:
    """
    Get worker configuration information.
    
    This helps debug "job not picked up" issues by showing:
    - Which queues the worker is configured to listen to
    - Environment variables affecting worker behavior
    
    Returns:
        dict: Worker configuration data
        
    Example:
        {
            'configured_queues': ['high', 'default', 'low', 'maintenance', ...],
            'rq_queues_env': 'high,default,low,maintenance,broadcasts,recordings,receipts,receipts_sync',
            'service_role': 'worker'
        }
    """
    import os
    
    # Get RQ_QUEUES from environment (what docker-compose.yml configures)
    rq_queues_env = os.getenv('RQ_QUEUES', 'high,default,low,maintenance,broadcasts,recordings')
    configured_queues = [q.strip() for q in rq_queues_env.split(',') if q.strip()]
    
    return {
        'configured_queues': configured_queues,
        'rq_queues_env': rq_queues_env,
        'service_role': os.getenv('SERVICE_ROLE', 'unknown'),
        'listens_to_maintenance': 'maintenance' in configured_queues,
        'all_known_queues': ['high', 'default', 'low', 'maintenance', 'broadcasts', 'recordings', 'receipts', 'receipts_sync']
    }


def cleanup_old_jobs(queue_name: str, max_age_hours: int = 24) -> int:
    """
    Clean up old finished/failed jobs from queue registry.
    
    Args:
        queue_name: Queue to clean up
        max_age_hours: Maximum age of jobs to keep (in hours)
    
    Returns:
        int: Number of jobs cleaned up
    """
    redis_conn = get_redis()
    queue = get_queue(queue_name)
    
    from rq.registry import FinishedJobRegistry, FailedJobRegistry
    from datetime import timedelta
    
    cleaned_count = 0
    max_age = timedelta(hours=max_age_hours)
    
    # Clean finished jobs
    finished_registry = FinishedJobRegistry(queue=queue)
    for job_id in finished_registry.get_job_ids():
        try:
            job = Job.fetch(job_id, connection=redis_conn)
            if job.ended_at and (datetime.utcnow() - job.ended_at) > max_age:
                job.delete()
                cleaned_count += 1
        except Exception:
            pass
    
    # Clean failed jobs
    failed_registry = FailedJobRegistry(queue=queue)
    for job_id in failed_registry.get_job_ids():
        try:
            job = Job.fetch(job_id, connection=redis_conn)
            if job.ended_at and (datetime.utcnow() - job.ended_at) > max_age:
                job.delete()
                cleaned_count += 1
        except Exception:
            pass
    
    if cleaned_count > 0:
        logger.info(f"[JOB-CLEANUP] Cleaned up {cleaned_count} old jobs from {queue_name}")
    
    return cleaned_count


# Backwards compatibility aliases
enqueue_job = enqueue  # Old name
enqueue_unique = enqueue_with_dedupe  # Old name
get_redis_connection = get_redis  # Old name
