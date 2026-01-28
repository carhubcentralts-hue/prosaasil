"""
Call Log Background Jobs
Create, update, and finalize call logs without blocking real-time audio

These replace the background threads in media_ws_ai.py
"""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def create_call_log_job(
    call_sid: str,
    business_id: int,
    from_number: str,
    to_number: str,
    direction: str,
    stream_sid: str = None
):
    """
    Create initial call_log record on call start.
    
    Args:
        call_sid: Twilio call SID
        business_id: Business ID for multi-tenant isolation
        from_number: Caller phone number
        to_number: Called phone number
        direction: Call direction ('inbound' or 'outbound')
        stream_sid: Optional Twilio stream SID
    
    Returns:
        dict: Creation result
    """
    from server.models_sql import CallLog, db
    from flask import current_app
    
    logger.info(f"[CALL-LOG-CREATE-JOB] Creating call_log for {call_sid}, business_id={business_id}")
    
    with current_app.app_context():
        try:
            # Check if already exists (race condition guard)
            existing = CallLog.query.filter_by(call_sid=call_sid).first()
            if existing:
                logger.warning(f"[CALL-LOG-CREATE-JOB] ⚠️ Call log already exists: {call_sid}")
                return {
                    'status': 'exists',
                    'call_log_id': existing.id,
                    'timestamp': datetime.utcnow().isoformat()
                }
            
            # Create new call log
            call_log = CallLog(
                call_sid=call_sid,
                tenant_id=business_id,
                from_number=from_number,
                to_number=to_number,
                direction=direction,
                status='in_progress',
                stream_sid=stream_sid,
                started_at=datetime.utcnow()
            )
            db.session.add(call_log)
            db.session.commit()
            
            logger.info(f"[CALL-LOG-CREATE-JOB] ✅ Call log created: id={call_log.id}, call_sid={call_sid}")
            return {
                'status': 'created',
                'call_log_id': call_log.id,
                'call_sid': call_sid,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"[CALL-LOG-CREATE-JOB] ❌ Failed to create call_log: {e}", exc_info=True)
            db.session.rollback()
            return {
                'status': 'error',
                'error': str(e),
                'call_sid': call_sid,
                'timestamp': datetime.utcnow().isoformat()
            }


def save_conversation_turn_job(
    call_sid: str,
    business_id: int,
    user_text: str,
    bot_reply: str,
    turn_index: int = None
):
    """
    Save a conversation turn to the database.
    
    Args:
        call_sid: Twilio call SID
        business_id: Business ID for multi-tenant isolation
        user_text: User's text input
        bot_reply: Bot's text response
        turn_index: Optional turn index for ordering
    
    Returns:
        dict: Save result
    """
    from server.models_sql import ConversationTurn, CallLog, db
    from flask import current_app
    
    logger.info(f"[CONVERSATION-TURN-JOB] Saving turn for {call_sid}, business_id={business_id}")
    
    with current_app.app_context():
        try:
            # Find call_log
            call_log = CallLog.query.filter_by(call_sid=call_sid).first()
            if not call_log:
                logger.warning(f"[CONVERSATION-TURN-JOB] ⚠️ Call log not found for {call_sid}")
                return {
                    'status': 'no_call_log',
                    'call_sid': call_sid,
                    'timestamp': datetime.utcnow().isoformat()
                }
            
            # Create conversation turn
            turn = ConversationTurn(
                call_log_id=call_log.id,
                user_text=user_text,
                bot_reply=bot_reply,
                turn_index=turn_index,
                created_at=datetime.utcnow()
            )
            db.session.add(turn)
            db.session.commit()
            
            logger.info(f"[CONVERSATION-TURN-JOB] ✅ Turn saved: id={turn.id}, call_log_id={call_log.id}")
            return {
                'status': 'saved',
                'turn_id': turn.id,
                'call_log_id': call_log.id,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"[CONVERSATION-TURN-JOB] ❌ Failed to save turn: {e}", exc_info=True)
            db.session.rollback()
            return {
                'status': 'error',
                'error': str(e),
                'call_sid': call_sid,
                'timestamp': datetime.utcnow().isoformat()
            }


def finalize_call_log_job(
    call_sid: str,
    business_id: int,
    status: str = 'completed',
    duration_seconds: int = None,
    transcript: str = None,
    recording_url: str = None
):
    """
    Finalize call_log record on call end.
    
    Args:
        call_sid: Twilio call SID
        business_id: Business ID for multi-tenant isolation
        status: Final call status ('completed', 'failed', 'no-answer', etc.)
        duration_seconds: Call duration in seconds
        transcript: Full conversation transcript
        recording_url: Recording URL if available
    
    Returns:
        dict: Finalization result
    """
    from server.models_sql import CallLog, db
    from flask import current_app
    
    logger.info(f"[CALL-LOG-FINALIZE-JOB] Finalizing call_log for {call_sid}, business_id={business_id}")
    
    with current_app.app_context():
        try:
            # Load fresh call_log from DB
            call_log = CallLog.query.filter_by(call_sid=call_sid).first()
            if not call_log:
                logger.warning(f"[CALL-LOG-FINALIZE-JOB] ⚠️ No call_log found for {call_sid}")
                return {
                    'status': 'no_call_log',
                    'call_sid': call_sid,
                    'timestamp': datetime.utcnow().isoformat()
                }
            
            # Update call log
            call_log.status = status
            call_log.ended_at = datetime.utcnow()
            
            if duration_seconds is not None:
                call_log.duration_seconds = duration_seconds
            
            if transcript:
                call_log.transcript = transcript
            
            if recording_url:
                call_log.recording_url = recording_url
            
            db.session.commit()
            
            logger.info(f"[CALL-LOG-FINALIZE-JOB] ✅ Call log finalized: id={call_log.id}, status={status}")
            return {
                'status': 'finalized',
                'call_log_id': call_log.id,
                'call_sid': call_sid,
                'final_status': status,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"[CALL-LOG-FINALIZE-JOB] ❌ Failed to finalize call_log: {e}", exc_info=True)
            db.session.rollback()
            return {
                'status': 'error',
                'error': str(e),
                'call_sid': call_sid,
                'timestamp': datetime.utcnow().isoformat()
            }
