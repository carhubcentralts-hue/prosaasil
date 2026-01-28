"""
WhatsApp Session Auto-Summary Job
Periodic task to check for inactive WhatsApp sessions and generate summaries

This replaces the session processor thread in whatsapp_session_service.py
Schedule: Every 5 minutes
"""
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def process_whatsapp_sessions_job(business_id: int = None):
    """
    Process all inactive WhatsApp sessions and generate summaries.
    
    Args:
        business_id: Optional business ID to process (None = all businesses)
    
    Returns:
        dict: Summary of processing operation
    """
    from server.services.whatsapp_session_service import process_inactive_sessions
    
    logger.info(f"[WA-SESSION-JOB] Starting WhatsApp session processing (business_id={business_id})")
    
    try:
        # Process inactive sessions (15+ minutes of inactivity)
        result = process_inactive_sessions()
        
        logger.info(f"[WA-SESSION-JOB] ✅ Processing completed: {result}")
        return {
            'status': 'success',
            'result': result,
            'business_id': business_id,
            'timestamp': datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"[WA-SESSION-JOB] ❌ Processing failed: {e}", exc_info=True)
        return {
            'status': 'failed',
            'error': str(e),
            'business_id': business_id,
            'timestamp': datetime.utcnow().isoformat()
        }
