"""
Webhook Sending Job
Send webhooks with retry logic

This replaces the background thread in generic_webhook_service.py
"""
import logging
import time
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAYS = [2, 5, 10]  # seconds between retries
REQUEST_TIMEOUT = 10  # seconds


def send_webhook_job(
    url: str,
    payload: dict,
    event_type: str,
    business_id: int = None,
    secret: str = None
):
    """
    Send webhook with automatic retry logic.
    
    Args:
        url: Target webhook URL
        payload: JSON payload to send
        event_type: Type of event (for logging)
        business_id: Business ID for multi-tenant isolation
        secret: Optional webhook secret for authentication
    
    Returns:
        dict: Send result with success/failure status
    """
    from flask import current_app
    
    logger.info(f"[WEBHOOK-JOB] Sending {event_type} webhook to {url[:50]}...")
    
    with current_app.app_context():
        for attempt in range(MAX_RETRIES):
            try:
                headers = {'Content-Type': 'application/json'}
                if secret:
                    headers['X-Webhook-Secret'] = secret
                
                response = requests.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=REQUEST_TIMEOUT,
                    allow_redirects=True
                )
                
                if response.status_code in (200, 201, 202, 204):
                    logger.info(f"[WEBHOOK-JOB] ✅ Webhook sent successfully (status={response.status_code})")
                    return {
                        'status': 'success',
                        'status_code': response.status_code,
                        'event_type': event_type,
                        'attempts': attempt + 1,
                        'timestamp': datetime.utcnow().isoformat()
                    }
                else:
                    logger.warning(f"[WEBHOOK-JOB] ⚠️ Unexpected status code: {response.status_code}")
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_DELAYS[attempt])
                    
            except requests.exceptions.Timeout:
                logger.warning(f"[WEBHOOK-JOB] ⚠️ Request timeout (attempt {attempt + 1}/{MAX_RETRIES})")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAYS[attempt])
                    
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"[WEBHOOK-JOB] ⚠️ Connection error: {e} (attempt {attempt + 1}/{MAX_RETRIES})")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAYS[attempt])
                    
            except Exception as e:
                logger.error(f"[WEBHOOK-JOB] ❌ Error sending webhook: {e}", exc_info=True)
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAYS[attempt])
        
        # All retries failed
        logger.error(f"[WEBHOOK-JOB] ❌ Failed to send {event_type} webhook after {MAX_RETRIES} attempts")
        return {
            'status': 'failed',
            'event_type': event_type,
            'attempts': MAX_RETRIES,
            'error': 'All retry attempts failed',
            'timestamp': datetime.utcnow().isoformat()
        }
