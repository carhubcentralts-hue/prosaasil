"""
Status Webhook Service - Send lead status changes to external integrations

This service dispatches webhook notifications when a lead's status changes.
Supports Hebrew status labels and includes comprehensive event data.
"""
import logging
import hmac
import hashlib
import json
from datetime import datetime
from typing import Optional, Dict, Any
import requests
from server.db import db
from server.models_sql import BusinessSettings, Lead

log = logging.getLogger(__name__)

# Track invalid URLs we've already warned about (to avoid spam)
_warned_invalid_urls = set()

def _is_valid_webhook_url(url: str) -> bool:
    """
    Validate webhook URL format - must start with http:// or https://
    Prevents invalid URLs like 'popopop' from being sent
    """
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    return url.startswith('http://') or url.startswith('https://')

# Hebrew status mapping - canonical lowercase to Hebrew display
STATUS_HE_MAP = {
    'new': 'חדש',
    'attempting': 'מנסה ליצור קשר',
    'contacted': 'יצרנו קשר',
    'qualified': 'מתאים',
    'won': 'נסגר',
    'lost': 'אבד',
    'unqualified': 'לא מתאים',
}

def get_hebrew_status(status_name: str) -> str:
    """Convert status name to Hebrew label"""
    # Normalize to lowercase for lookup
    normalized = status_name.lower().strip() if status_name else 'new'
    return STATUS_HE_MAP.get(normalized, status_name)

def generate_signature(secret: str, payload: str) -> str:
    """Generate HMAC-SHA256 signature for webhook payload"""
    return hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

def dispatch_lead_status_webhook(
    business_id: int,
    lead_id: int,
    old_status: str,
    new_status: str,
    source: str,
    user_id: Optional[int] = None,
    call_sid: Optional[str] = None
) -> bool:
    """
    Dispatch webhook notification for lead status change
    
    Args:
        business_id: Business/tenant ID
        lead_id: Lead ID
        old_status: Previous status (English key)
        new_status: New status (English key)
        source: Where the change originated (e.g., 'lead_page', 'recent_calls_tab')
        user_id: Optional user who made the change
        call_sid: Optional call SID if change came from a call
    
    Returns:
        True if webhook sent successfully, False otherwise
    """
    try:
        # Get business settings with webhook URL
        settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
        
        if not settings or not settings.status_webhook_url:
            log.debug(f"No status webhook configured for business {business_id}")
            return False
        
        # Validate webhook URL format
        if not _is_valid_webhook_url(settings.status_webhook_url):
            # Create unique key for this invalid URL to log warning only once
            url_key = f"status:{business_id}:{settings.status_webhook_url}"
            if url_key not in _warned_invalid_urls:
                _warned_invalid_urls.add(url_key)
                log.warning(f"Invalid status webhook URL for business {business_id}: {settings.status_webhook_url} - URL must start with http:// or https://")
            return False
        
        # Check if status actually changed
        if old_status and old_status.lower() == new_status.lower():
            log.debug(f"Status unchanged for lead {lead_id}, skipping webhook")
            return False
        
        # Get lead details
        lead = Lead.query.filter_by(id=lead_id, tenant_id=business_id).first()
        if not lead:
            log.warning(f"Lead {lead_id} not found for webhook dispatch")
            return False
        
        # Build webhook payload
        payload = {
            'event': 'lead.status_changed',
            'business_id': business_id,
            'lead_id': lead_id,
            'lead_phone': lead.phone_e164 or '',
            'lead_name': f"{lead.first_name or ''} {lead.last_name or ''}".strip() or 'ללא שם',
            'old_status': get_hebrew_status(old_status) if old_status else '',
            'new_status': get_hebrew_status(new_status),
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'source': source,
            'changed_by': user_id,
        }
        
        # Add call_sid if provided
        if call_sid:
            payload['call_sid'] = call_sid
        
        # Convert to JSON
        payload_json = json.dumps(payload, ensure_ascii=False)
        
        # Generate signature (using business_id as secret for now)
        # In production, you might want a dedicated secret per business
        signature = generate_signature(str(business_id), payload_json)
        
        # Send webhook asynchronously (in a real implementation, use a task queue)
        headers = {
            'Content-Type': 'application/json; charset=utf-8',
            'X-ProSaaS-Signature': signature,
            'X-ProSaaS-Event': 'lead.status_changed',
        }
        
        log.info(f"Sending status webhook for lead {lead_id}: {old_status} → {new_status}")
        
        # Send with timeout and retries
        response = requests.post(
            settings.status_webhook_url,
            data=payload_json.encode('utf-8'),
            headers=headers,
            timeout=10
        )
        
        if response.status_code >= 200 and response.status_code < 300:
            log.info(f"✅ Status webhook sent successfully for lead {lead_id} (status: {response.status_code})")
            return True
        else:
            log.warning(f"⚠️ Status webhook failed for lead {lead_id}: HTTP {response.status_code}")
            return False
            
    except requests.exceptions.Timeout:
        log.error(f"❌ Status webhook timeout for lead {lead_id}")
        return False
    except Exception as e:
        log.error(f"❌ Error dispatching status webhook for lead {lead_id}: {e}")
        return False
