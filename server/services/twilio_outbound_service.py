"""
Twilio Call Creation Service - Single Source of Truth
🎯 SSOT: All outbound call creation goes through here
💰 CRITICAL: Prevents duplicate Twilio API calls (saves money!)
"""
import logging
from typing import Dict, Any, Optional
from flask import request

log = logging.getLogger(__name__)


def create_outbound_call(
    to_phone: str,
    from_phone: str,
    business_id: int,
    lead_id: Optional[int] = None,
    template_id: Optional[int] = None,
    job_id: Optional[int] = None,
    business_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a single outbound Twilio call.
    
    🎯 SSOT: This is the ONLY place that calls client.calls.create() for outbound
    ✅ OWNER: All outbound call creation
    ❌ NEVER: Call Twilio API directly - always use this function
    
    💰 COST SAVINGS: Prevents duplicate API calls by centralizing logic
    
    Args:
        to_phone: Normalized phone number to call
        from_phone: Twilio phone number to call from
        business_id: Business ID
        lead_id: Optional lead ID
        template_id: Optional template ID
        job_id: Optional job ID for bulk calls
        business_name: Optional business name for webhook
        
    Returns:
        Dict with call_sid and status
        
    Raises:
        Exception if Twilio API call fails
    """
    from server.services.twilio_call_control import get_twilio_client
    from urllib.parse import quote
    
    # Build webhook URL
    host = request.headers.get("X-Forwarded-Host") or request.host
    webhook_url = f"https://{host}/twilio/outbound?business_id={business_id}"
    
    if lead_id:
        webhook_url += f"&lead_id={lead_id}"
    if template_id:
        webhook_url += f"&template_id={template_id}"
    if job_id:
        webhook_url += f"&job_id={job_id}"
    if business_name:
        webhook_url += f"&business_name={quote(business_name, safe='')}"
    
    # Get Twilio client
    client = get_twilio_client()
    
    # 🔥 SSOT: Single place for Twilio call creation
    # 💰 CRITICAL: This is the ONLY Twilio API call for outbound
    # 🎙️ NOTE: Recording is started separately via _start_recording_from_second_zero
    #          DO NOT use record=True here to avoid duplicate recording charges!
    log.info(f"[TWILIO_CALL] Creating outbound call: to={to_phone}, from={from_phone}, business_id={business_id}, lead_id={lead_id}")
    
    try:
        twilio_call = client.calls.create(
            to=to_phone,
            from_=from_phone,
            url=webhook_url,
            status_callback=f"https://{host}/webhook/call_status",
            status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
            # 🔥 SSOT: Recording is started via _start_recording_from_second_zero (not here)
            # record=True,  # ❌ REMOVED: Prevents duplicate recording costs
            recording_status_callback=f"https://{host}/webhook/handle_recording",
            recording_status_callback_event=['completed']
        )
        
        log.info(f"[TWILIO_CALL] ✅ Call created: call_sid={twilio_call.sid}")
        
        return {
            "call_sid": twilio_call.sid,
            "status": "initiated",
            "success": True
        }
        
    except Exception as e:
        log.error(f"[TWILIO_CALL] ❌ Failed to create call: {e}")
        raise


def create_outbound_call_for_bulk(
    to_phone: str,
    from_phone: str,
    business_id: int,
    job_id: int,
    business_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create outbound call for bulk queue system.
    
    🎯 SSOT: Delegates to create_outbound_call (single source)
    💰 Wrapper for bulk calling with job tracking
    
    Args:
        to_phone: Normalized phone number
        from_phone: Twilio number
        business_id: Business ID
        job_id: Job ID for tracking
        business_name: Optional business name
        
    Returns:
        Dict with call_sid and status
    """
    return create_outbound_call(
        to_phone=to_phone,
        from_phone=from_phone,
        business_id=business_id,
        job_id=job_id,
        business_name=business_name
    )
