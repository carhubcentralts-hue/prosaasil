"""
Lead Creation Job
Create or update leads from incoming/outbound calls

This replaces the background thread in routes_twilio.py
"""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def create_lead_from_call_job(call_sid: str):
    """
    Create or update lead from call information.
    
    🔥 SELF-CONTAINED: Fetches all data from CallLog by call_sid
    This prevents issues with RQ retry losing arguments.
    
    Args:
        call_sid: Twilio call SID (only parameter needed)
    
    Returns:
        dict: Lead creation result
    """
    from flask import current_app
    
    logger.info(f"[LEAD-CREATE-JOB] Creating lead from call {call_sid}")
    
    with current_app.app_context():
        try:
            from server.models_sql import CallLog
            from server.db import db
            
            # 🔥 FIX: Fetch CallLog to get business_id and other params
            call_log = CallLog.query.filter_by(call_sid=call_sid).first()
            
            if not call_log:
                logger.error(f"[LEAD-CREATE-JOB] ❌ CallLog not found for call_sid={call_sid}")
                return {
                    'status': 'error',
                    'error': 'CallLog not found',
                    'call_sid': call_sid,
                    'timestamp': datetime.utcnow().isoformat()
                }
            
            # Extract parameters from CallLog
            business_id = call_log.business_id
            from_number = call_log.from_number
            to_number = call_log.to_number
            direction = call_log.direction
            
            logger.info(f"[LEAD-CREATE-JOB] Fetched from DB: business_id={business_id}, direction={direction}")
            
            # Import the actual function from routes_twilio
            # This function already exists and handles all the logic
            from server.routes_twilio import _create_lead_from_call
            
            # Call the existing function with data from CallLog
            _create_lead_from_call(call_sid, from_number, to_number, business_id, direction)
            
            logger.info(f"[LEAD-CREATE-JOB] ✅ Lead created/updated for call {call_sid}")
            return {
                'status': 'success',
                'call_sid': call_sid,
                'direction': direction,
                'business_id': business_id,
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
