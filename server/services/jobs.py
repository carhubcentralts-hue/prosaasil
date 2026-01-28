"""
Unified Job Enqueue Service
Single source of truth for enqueuing background jobs to RQ (Redis Queue)

Features:
- Business isolation (all jobs tagged with business_id)
- Correlation IDs for distributed tracing
- Unified logging (start/success/fail/retry)
- Deduplication support
- Job cancellation support
"""
import os
import logging
import uuid
from datetime import datetime
from typing import Callable, Any, Optional
from redis import Redis
from rq import Queue
from rq.job import Job

logger = logging.getLogger(__name__)

# Redis connection singleton
_redis_conn = None

def get_redis_connection():
    """Get or create Redis connection"""
    global _redis_conn
    if _redis_conn is None:
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        _redis_conn = Redis.from_url(redis_url)
    return _redis_conn


def enqueue_job(
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
    
    Args:
        queue_name: Queue to enqueue to ('high', 'default', 'low', 'maintenance', 'broadcasts', 'recordings')
        func: Function to execute (must be importable by worker)
        *args: Positional arguments for func
        business_id: Business ID for tenant isolation (CRITICAL for multi-tenant security)
        run_id: Optional run ID for job grouping
        job_id: Optional custom job ID (default: generated UUID)
        trace_id: Optional trace ID for distributed tracing
        ttl: Job TTL in seconds (how long job stays in queue before expiring)
        timeout: Job execution timeout in seconds
        retry: Number of retry attempts (None = no retry)
        description: Human-readable job description
        **kwargs: Keyword arguments for func
    
    Returns:
        rq.job.Job: The enqueued job
    """
    redis_conn = get_redis_connection()
    queue = Queue(queue_name, connection=redis_conn)
    
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
    job_kwargs = {
        'job_id': job_id,
        'meta': meta,
        'ttl': ttl,
        'timeout': timeout,
        'description': description or f"{func.__name__}",
    }
    
    # Add retry if specified
    if retry is not None:
        from rq import Retry
        job_kwargs['retry'] = Retry(max=retry)
    
    # Log enqueue
    log_context = f"[JOB-ENQUEUE] queue={queue_name} func={func.__name__} job_id={job_id[:8]}"
    if business_id:
        log_context += f" business_id={business_id}"
    if run_id:
        log_context += f" run_id={run_id}"
    logger.info(f"{log_context} trace_id={trace_id[:8]}")
    
    # Enqueue job
    job = queue.enqueue(
        func,
        *args,
        **kwargs,
        **job_kwargs
    )
    
    return job


def enqueue_unique(
    queue_name: str,
    func: Callable,
    dedup_key: str,
    *args,
    ttl: int = 600,
    timeout: int = 300,
    **kwargs
) -> Optional[Job]:
    """
    Enqueue a job with deduplication - only one job per dedup_key can be queued/running.
    
    Args:
        queue_name: Queue to enqueue to
        func: Function to execute
        dedup_key: Unique key for deduplication (e.g., "whatsapp_send:{business_id}:{phone}")
        *args: Positional arguments for func
        ttl: Job TTL in seconds
        timeout: Job execution timeout in seconds
        **kwargs: Keyword arguments for func (including business_id, etc.)
    
    Returns:
        rq.job.Job or None: The enqueued job, or None if duplicate already exists
    """
    redis_conn = get_redis_connection()
    queue = Queue(queue_name, connection=redis_conn)
    
    # Check if job already exists in queue or is running
    # Use Redis SET NX (set if not exists) for atomic deduplication
    lock_key = f"job_lock:{dedup_key}"
    lock_acquired = redis_conn.set(lock_key, "1", ex=ttl, nx=True)
    
    if not lock_acquired:
        logger.info(f"[JOB-DEDUP] Skipping duplicate job: {dedup_key}")
        return None
    
    # Enqueue job with automatic lock cleanup
    job_id = f"unique:{dedup_key}"
    
    try:
        job = enqueue_job(
            queue_name,
            func,
            *args,
            job_id=job_id,
            ttl=ttl,
            timeout=timeout,
            description=f"Unique job: {dedup_key}",
            **kwargs
        )
        
        # Store job ID in Redis for tracking
        redis_conn.setex(f"job_id:{dedup_key}", ttl, job.id)
        
        return job
    except Exception as e:
        # Release lock on failure
        redis_conn.delete(lock_key)
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
    redis_conn = get_redis_connection()
    cancelled_count = 0
    
    # Search all queues for jobs with matching run_id
    queue_names = ['high', 'default', 'low', 'maintenance', 'broadcasts', 'recordings']
    
    for queue_name in queue_names:
        queue = Queue(queue_name, connection=redis_conn)
        
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


def get_job_status(job_id: str) -> Optional[dict]:
    """
    Get status of a job by ID.
    
    Args:
        job_id: Job ID to query
    
    Returns:
        dict: Job status info or None if not found
    """
    try:
        redis_conn = get_redis_connection()
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


def cleanup_old_jobs(queue_name: str, max_age_hours: int = 24) -> int:
    """
    Clean up old finished/failed jobs from queue registry.
    
    Args:
        queue_name: Queue to clean up
        max_age_hours: Maximum age of jobs to keep (in hours)
    
    Returns:
        int: Number of jobs cleaned up
    """
    redis_conn = get_redis_connection()
    queue = Queue(queue_name, connection=redis_conn)
    
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
