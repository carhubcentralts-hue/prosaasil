"""
Job Health and Monitoring Endpoints

Provides visibility into RQ job system health:
- Queue statistics (queued, started, finished, failed)
- Scheduler health (last tick, lock status)
- Worker status
"""
import logging
from flask import Blueprint, jsonify
from server.extensions import csrf

logger = logging.getLogger(__name__)

jobs_bp = Blueprint('jobs', __name__, url_prefix='/api/jobs')


@jobs_bp.route('/health', methods=['GET'])
@csrf.exempt  # Health checks don't need CSRF
def jobs_health():
    """
    Get job system health information
    
    Returns:
        JSON with queue stats and scheduler health
        
    Example response:
        {
            "status": "healthy",
            "queues": {
                "default": {"queued": 5, "started": 2, "finished": 100, "failed": 3},
                "high": {"queued": 0, "started": 0, "finished": 50, "failed": 0},
                ...
            },
            "scheduler": {
                "last_tick": "2026-01-28T19:00:00Z",
                "lock_held": true,
                "lock_ttl": 75
            }
        }
    """
    try:
        from server.services.jobs import get_queue_stats, get_scheduler_health, get_worker_config
        
        queue_stats = get_queue_stats()
        scheduler_health = get_scheduler_health()
        worker_config = get_worker_config()
        
        # Determine overall health
        total_failed = sum(q.get('failed', 0) for q in queue_stats.values() if isinstance(q, dict))
        total_queued = sum(q.get('queued', 0) for q in queue_stats.values() if isinstance(q, dict))
        
        # Health is degraded if too many failures or huge queue
        status = "healthy"
        if total_failed > 100:
            status = "degraded"
        if total_queued > 1000:
            status = "degraded"
        if not scheduler_health.get('lock_held'):
            status = "warning"  # No scheduler running
        
        return jsonify({
            "status": status,
            "queues": queue_stats,
            "scheduler": scheduler_health,
            "worker": worker_config,
            "summary": {
                "total_queued": total_queued,
                "total_failed": total_failed
            }
        })
        
    except Exception as e:
        logger.error(f"[JOBS-HEALTH] Error: {e}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), 500


@jobs_bp.route('/stats', methods=['GET'])
@csrf.exempt
def jobs_stats():
    """
    Get detailed job statistics
    
    Returns:
        JSON with detailed queue statistics
    """
    try:
        from server.services.jobs import get_queue_stats
        
        return jsonify({
            "queues": get_queue_stats()
        })
        
    except Exception as e:
        logger.error(f"[JOBS-STATS] Error: {e}")
        return jsonify({
            "error": str(e)
        }), 500


@jobs_bp.route('/scheduler', methods=['GET'])
@csrf.exempt
def scheduler_status():
    """
    Get scheduler status
    
    Returns:
        JSON with scheduler health information
    """
    try:
        from server.services.jobs import get_scheduler_health
        
        return jsonify(get_scheduler_health())
        
    except Exception as e:
        logger.error(f"[SCHEDULER-STATUS] Error: {e}")
        return jsonify({
            "error": str(e)
        }), 500


@jobs_bp.route('/worker/config', methods=['GET'])
@csrf.exempt
def worker_config():
    """
    Get worker configuration
    
    Returns:
        JSON with worker configuration including which queues it listens to.
        This helps debug "job not picked up" issues.
        
    Example response:
        {
            "configured_queues": ["high", "default", "low", "maintenance", ...],
            "rq_queues_env": "high,default,low,maintenance,...",
            "service_role": "worker",
            "listens_to_maintenance": true
        }
    """
    try:
        from server.services.jobs import get_worker_config
        
        return jsonify(get_worker_config())
        
    except Exception as e:
        logger.error(f"[WORKER-CONFIG] Error: {e}")
        return jsonify({
            "error": str(e)
        }), 500
