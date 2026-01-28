"""
Agent Warmup Job
Optional task to pre-warm AI agents and services

This replaces the warmup_thread in app_factory.py
Can be run on-demand or skipped entirely (lazy initialization)
"""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def warmup_agents_job(business_id: int = None):
    """
    Warm up AI agents for a business or all businesses.
    
    Args:
        business_id: Optional business ID to warm up (None = all businesses)
    
    Returns:
        dict: Summary of warmup operation
    """
    logger.info(f"[WARMUP-JOB] Starting agent warmup (business_id={business_id})")
    
    try:
        from server.agents.agent_locator import warmup_all_agents
        
        # Warm up agents
        warmup_all_agents()
        
        logger.info(f"[WARMUP-JOB] ✅ Agent warmup completed")
        return {
            'status': 'success',
            'business_id': business_id,
            'timestamp': datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.warning(f"[WARMUP-JOB] ⚠️ Agent warmup failed (non-critical): {e}")
        return {
            'status': 'failed',
            'error': str(e),
            'business_id': business_id,
            'timestamp': datetime.utcnow().isoformat()
        }
