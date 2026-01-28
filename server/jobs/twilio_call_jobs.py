"""
Lead Creation Job
Create or update leads from incoming/outbound calls

This replaces the background thread in routes_twilio.py
"""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def create_lead_from_call_job(
    call_sid: str,
    from_number: str,
    to_number: str,
    business_id: int,
    direction: str
):
    """
    Create or update lead from call information.
    
    Args:
        call_sid: Twilio call SID
        from_number: Caller phone number
        to_number: Called phone number
        business_id: Business ID for multi-tenant isolation
        direction: Call direction ('inbound' or 'outbound')
    
    Returns:
        dict: Lead creation result
    """
    from flask import current_app
    
    logger.info(f"[LEAD-CREATE-JOB] Creating lead from call {call_sid}, direction={direction}, business_id={business_id}")
    
    with current_app.app_context():
        try:
            # Import the actual function from routes_twilio
            # This function already exists and handles all the logic
            from server.routes_twilio import _create_lead_from_call
            
            # Call the existing function
            _create_lead_from_call(call_sid, from_number, to_number, business_id, direction)
            
            logger.info(f"[LEAD-CREATE-JOB] ✅ Lead created/updated for call {call_sid}")
            return {
                'status': 'success',
                'call_sid': call_sid,
                'direction': direction,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"[LEAD-CREATE-JOB] ❌ Failed to create lead: {e}", exc_info=True)
            return {
                'status': 'error',
                'error': str(e),
                'call_sid': call_sid,
                'timestamp': datetime.utcnow().isoformat()
            }


def prebuild_prompt_job(
    call_sid: str,
    business_id: int,
    direction: str
):
    """
    Pre-build AI prompt for call to reduce first-greeting latency.
    
    Args:
        call_sid: Twilio call SID
        business_id: Business ID for multi-tenant isolation
        direction: Call direction ('inbound' or 'outbound')
    
    Returns:
        dict: Prompt build result
    """
    from flask import current_app
    
    logger.info(f"[PROMPT-BUILD-JOB] Pre-building prompt for call {call_sid}, direction={direction}")
    
    with current_app.app_context():
        try:
            # Import the actual functions from routes_twilio
            if direction == 'inbound':
                from server.routes_twilio import _prebuild_prompts_async
                _prebuild_prompts_async(call_sid, business_id)
            else:
                from server.routes_twilio import _prebuild_prompts_async_outbound
                _prebuild_prompts_async_outbound(call_sid, business_id)
            
            logger.info(f"[PROMPT-BUILD-JOB] ✅ Prompt pre-built for call {call_sid}")
            return {
                'status': 'success',
                'call_sid': call_sid,
                'direction': direction,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"[PROMPT-BUILD-JOB] ❌ Failed to pre-build prompt: {e}", exc_info=True)
            return {
                'status': 'error',
                'error': str(e),
                'call_sid': call_sid,
                'timestamp': datetime.utcnow().isoformat()
            }
