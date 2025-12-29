"""
Internal API endpoints for Asterisk ARI integration.
These endpoints are called by the AsteriskARIService to notify the backend
of call lifecycle events.
"""
import logging
from flask import Blueprint, request, jsonify
from server.models_sql import db, CallLog, Business
from datetime import datetime

logger = logging.getLogger(__name__)

asterisk_internal_bp = Blueprint('asterisk_internal', __name__, url_prefix='/internal')


@asterisk_internal_bp.route('/calls/start', methods=['POST'])
def handle_call_start():
    """
    Handle call start notification from ARI service.
    
    Called when a call enters the Stasis application.
    Creates a CallLog entry and prepares for media streaming.
    """
    try:
        data = request.get_json()
        
        call_id = data.get('call_id')
        tenant_id = data.get('tenant_id', 1)
        direction = data.get('direction', 'inbound')
        from_number = data.get('from_number', '')
        to_number = data.get('to_number', '')
        lead_id = data.get('lead_id')
        provider = data.get('provider', 'asterisk')
        
        logger.info(f"[ASTERISK_INTERNAL] Call start: call_id={call_id}, tenant={tenant_id}, direction={direction}")
        
        # Validate tenant exists
        business = Business.query.filter_by(id=tenant_id, is_active=True).first()
        if not business:
            logger.error(f"[ASTERISK_INTERNAL] Invalid tenant_id: {tenant_id}")
            return jsonify({'error': 'invalid_tenant'}), 400
        
        # Check if CallLog already exists (idempotency)
        existing_call = CallLog.query.filter_by(call_sid=call_id).first()
        if existing_call:
            logger.info(f"[ASTERISK_INTERNAL] CallLog already exists: {call_id}")
            return jsonify({'status': 'ok', 'call_id': call_id, 'existing': True}), 200
        
        # Create CallLog entry
        call_log = CallLog(
            tenant_id=tenant_id,
            call_sid=call_id,
            direction=direction,
            from_number=from_number,
            to_number=to_number,
            status='in-progress',
            started_at=datetime.utcnow(),
            provider=provider
        )
        
        # Link to lead if provided
        if lead_id:
            try:
                call_log.lead_id = int(lead_id)
            except (ValueError, TypeError):
                logger.warning(f"[ASTERISK_INTERNAL] Invalid lead_id: {lead_id}")
        
        db.session.add(call_log)
        db.session.commit()
        
        logger.info(f"[ASTERISK_INTERNAL] ✅ CallLog created: id={call_log.id}, call_sid={call_id}")
        
        return jsonify({
            'status': 'ok',
            'call_id': call_id,
            'call_log_id': call_log.id,
            'existing': False
        }), 200
        
    except Exception as e:
        logger.error(f"[ASTERISK_INTERNAL] Error handling call start: {e}")
        db.session.rollback()
        return jsonify({'error': 'internal_error', 'message': str(e)}), 500


@asterisk_internal_bp.route('/calls/end', methods=['POST'])
def handle_call_end():
    """
    Handle call end notification from ARI service.
    
    Called when a call leaves the Stasis application (hangup).
    Updates CallLog status and triggers post-call processing.
    """
    try:
        data = request.get_json()
        
        call_id = data.get('call_id')
        provider = data.get('provider', 'asterisk')
        
        logger.info(f"[ASTERISK_INTERNAL] Call end: call_id={call_id}")
        
        # Find CallLog
        call_log = CallLog.query.filter_by(call_sid=call_id).first()
        if not call_log:
            logger.warning(f"[ASTERISK_INTERNAL] CallLog not found: {call_id}")
            return jsonify({'error': 'call_not_found'}), 404
        
        # Update status
        call_log.status = 'completed'
        call_log.ended_at = datetime.utcnow()
        
        # Calculate duration
        if call_log.started_at and call_log.ended_at:
            duration = (call_log.ended_at - call_log.started_at).total_seconds()
            call_log.duration = int(duration)
        
        db.session.commit()
        
        logger.info(f"[ASTERISK_INTERNAL] ✅ CallLog updated: id={call_log.id}, duration={call_log.duration}s")
        
        # Trigger post-call processing (recording transcription, etc.)
        # This will be handled by the recording worker
        
        return jsonify({
            'status': 'ok',
            'call_id': call_id,
            'duration': call_log.duration
        }), 200
        
    except Exception as e:
        logger.error(f"[ASTERISK_INTERNAL] Error handling call end: {e}")
        db.session.rollback()
        return jsonify({'error': 'internal_error', 'message': str(e)}), 500
