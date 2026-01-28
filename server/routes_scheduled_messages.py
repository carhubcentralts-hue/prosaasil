"""
API Routes for Scheduled WhatsApp Messages
Manage scheduling rules and message queue
"""
import logging
from flask import Blueprint, jsonify, request, session
from server.auth_api import require_api_auth
from server.security.permissions import require_page_access
from server.db import db
from server.services import scheduled_messages_service
from server.models_sql import ScheduledMessageRule, ScheduledMessagesQueue, LeadStatus

logger = logging.getLogger(__name__)

scheduled_messages_bp = Blueprint('scheduled_messages', __name__, url_prefix='/api/scheduled-messages')


def get_business_id_from_session() -> int:
    """
    Get business_id from session for multi-tenant isolation
    
    Returns:
        Business ID
    
    Raises:
        403 if no business context
    """
    user = session.get('al_user', {})
    business_id = session.get('impersonated_tenant_id') or user.get('business_id')
    
    if not business_id:
        from flask import abort
        abort(403, description="Business context required")
    
    return business_id


def get_user_id_from_session() -> int:
    """
    Get user_id from session
    
    Returns:
        User ID
    
    Raises:
        401 if not authenticated
    """
    user = session.get('al_user', {})
    user_id = user.get('id')
    
    if not user_id:
        from flask import abort
        abort(401, description="Authentication required")
    
    return user_id


# === RULES ENDPOINTS ===

@scheduled_messages_bp.route('/rules', methods=['GET'])
@require_api_auth
def get_rules():
    """
    Get all scheduling rules for the current business
    
    Query params:
        is_active (optional): Filter by active status (true/false)
    
    Returns:
        {
            "rules": [
                {
                    "id": int,
                    "name": str,
                    "is_active": bool,
                    "message_text": str,
                    "delay_minutes": int,
                    "statuses": [{"id": int, "name": str, "label": str}],
                    "created_at": str,
                    "updated_at": str
                }
            ]
        }
    """
    try:
        business_id = get_business_id_from_session()
        
        # Optional filter
        is_active = request.args.get('is_active')
        if is_active is not None:
            is_active = is_active.lower() == 'true'
        
        rules = scheduled_messages_service.get_rules(business_id, is_active=is_active)
        
        # Serialize rules
        rules_data = []
        for rule in rules:
            rules_data.append({
                'id': rule.id,
                'name': rule.name,
                'is_active': rule.is_active,
                'message_text': rule.message_text,
                'delay_minutes': rule.delay_minutes,
                'template_name': rule.template_name,
                'send_window_start': rule.send_window_start,
                'send_window_end': rule.send_window_end,
                'statuses': [
                    {
                        'id': status.id,
                        'name': status.name,
                        'label': status.label,
                        'color': status.color
                    }
                    for status in rule.statuses
                ],
                'created_by_user_id': rule.created_by_user_id,
                'created_at': rule.created_at.isoformat() if rule.created_at else None,
                'updated_at': rule.updated_at.isoformat() if rule.updated_at else None
            })
        
        return jsonify({'rules': rules_data})
        
    except Exception as e:
        logger.error(f"[SCHEDULED-MSG-API] Error getting rules: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@scheduled_messages_bp.route('/rules', methods=['POST'])
@require_api_auth
def create_rule():
    """
    Create a new scheduling rule
    
    Body:
        {
            "name": str,  # Required
            "message_text": str,  # Required
            "status_ids": [int],  # Required - list of lead status IDs
            "delay_minutes": int,  # Required - 1 to 43200
            "template_name": str,  # Optional
            "send_window_start": str,  # Optional - HH:MM format
            "send_window_end": str,  # Optional - HH:MM format
            "is_active": bool  # Optional - defaults to true
        }
    
    Returns:
        {
            "rule": {rule object},
            "message": "Rule created successfully"
        }
    """
    try:
        business_id = get_business_id_from_session()
        user_id = get_user_id_from_session()
        data = request.get_json()
        
        # Validate required fields
        if not data.get('name'):
            return jsonify({'error': 'name is required'}), 400
        
        if not data.get('message_text'):
            return jsonify({'error': 'message_text is required'}), 400
        
        if not data.get('status_ids') or not isinstance(data['status_ids'], list):
            return jsonify({'error': 'status_ids must be a non-empty array'}), 400
        
        if 'delay_minutes' not in data:
            return jsonify({'error': 'delay_minutes is required'}), 400
        
        delay_minutes = int(data['delay_minutes'])
        if delay_minutes < 1 or delay_minutes > 43200:
            return jsonify({'error': 'delay_minutes must be between 1 and 43200 (30 days)'}), 400
        
        # Create rule
        rule = scheduled_messages_service.create_rule(
            business_id=business_id,
            name=data['name'],
            message_text=data['message_text'],
            status_ids=data['status_ids'],
            delay_minutes=delay_minutes,
            created_by_user_id=user_id,
            template_name=data.get('template_name'),
            send_window_start=data.get('send_window_start'),
            send_window_end=data.get('send_window_end'),
            is_active=data.get('is_active', True)
        )
        
        logger.info(f"[SCHEDULED-MSG-API] Created rule {rule.id} for business {business_id}")
        
        return jsonify({
            'rule': {
                'id': rule.id,
                'name': rule.name,
                'is_active': rule.is_active,
                'message_text': rule.message_text,
                'delay_minutes': rule.delay_minutes,
                'statuses': [
                    {
                        'id': status.id,
                        'name': status.name,
                        'label': status.label,
                        'color': status.color
                    }
                    for status in rule.statuses
                ],
                'created_at': rule.created_at.isoformat()
            },
            'message': 'Rule created successfully'
        }), 201
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"[SCHEDULED-MSG-API] Error creating rule: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@scheduled_messages_bp.route('/rules/<int:rule_id>', methods=['PATCH'])
@require_api_auth
def update_rule(rule_id: int):
    """
    Update an existing scheduling rule
    
    Body (all fields optional):
        {
            "name": str,
            "message_text": str,
            "status_ids": [int],
            "delay_minutes": int,
            "template_name": str,
            "send_window_start": str,
            "send_window_end": str,
            "is_active": bool
        }
    
    Returns:
        {
            "rule": {rule object},
            "message": "Rule updated successfully"
        }
    """
    try:
        business_id = get_business_id_from_session()
        data = request.get_json()
        
        # Validate delay_minutes if provided
        if 'delay_minutes' in data:
            delay_minutes = int(data['delay_minutes'])
            if delay_minutes < 1 or delay_minutes > 43200:
                return jsonify({'error': 'delay_minutes must be between 1 and 43200 (30 days)'}), 400
        
        # Update rule
        rule = scheduled_messages_service.update_rule(
            rule_id=rule_id,
            business_id=business_id,
            **data
        )
        
        logger.info(f"[SCHEDULED-MSG-API] Updated rule {rule_id} for business {business_id}")
        
        return jsonify({
            'rule': {
                'id': rule.id,
                'name': rule.name,
                'is_active': rule.is_active,
                'message_text': rule.message_text,
                'delay_minutes': rule.delay_minutes,
                'statuses': [
                    {
                        'id': status.id,
                        'name': status.name,
                        'label': status.label
                    }
                    for status in rule.statuses
                ],
                'updated_at': rule.updated_at.isoformat()
            },
            'message': 'Rule updated successfully'
        })
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"[SCHEDULED-MSG-API] Error updating rule: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@scheduled_messages_bp.route('/rules/<int:rule_id>', methods=['DELETE'])
@require_api_auth
def delete_rule(rule_id: int):
    """
    Delete a scheduling rule
    
    This will cascade delete all rule-status mappings and pending messages.
    
    Returns:
        {"message": "Rule deleted successfully"}
    """
    try:
        business_id = get_business_id_from_session()
        
        success = scheduled_messages_service.delete_rule(rule_id, business_id)
        
        if not success:
            return jsonify({'error': 'Rule not found'}), 404
        
        logger.info(f"[SCHEDULED-MSG-API] Deleted rule {rule_id} for business {business_id}")
        
        return jsonify({'message': 'Rule deleted successfully'})
        
    except Exception as e:
        logger.error(f"[SCHEDULED-MSG-API] Error deleting rule: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@scheduled_messages_bp.route('/rules/<int:rule_id>/cancel-pending', methods=['POST'])
@require_api_auth
def cancel_pending_for_rule(rule_id: int):
    """
    Cancel all pending messages for a rule
    
    Returns:
        {
            "cancelled_count": int,
            "message": "Cancelled N pending message(s)"
        }
    """
    try:
        business_id = get_business_id_from_session()
        
        count = scheduled_messages_service.cancel_pending_for_rule(rule_id, business_id)
        
        logger.info(f"[SCHEDULED-MSG-API] Cancelled {count} pending message(s) for rule {rule_id}")
        
        return jsonify({
            'cancelled_count': count,
            'message': f'Cancelled {count} pending message(s)'
        })
        
    except Exception as e:
        logger.error(f"[SCHEDULED-MSG-API] Error cancelling pending messages: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


# === QUEUE ENDPOINTS ===

@scheduled_messages_bp.route('/queue', methods=['GET'])
@require_api_auth
def get_queue():
    """
    Get scheduled messages queue with pagination
    
    Query params:
        rule_id (optional): Filter by rule ID
        status (optional): Filter by status (pending/sent/failed/canceled)
        page (optional): Page number (default 1)
        per_page (optional): Results per page (default 50, max 100)
    
    Returns:
        {
            "items": [
                {
                    "id": int,
                    "rule_id": int,
                    "rule_name": str,
                    "lead_id": int,
                    "lead_name": str,
                    "message_text": str,
                    "scheduled_for": str,
                    "status": str,
                    "sent_at": str,
                    "error_message": str
                }
            ],
            "total": int,
            "page": int,
            "per_page": int
        }
    """
    try:
        business_id = get_business_id_from_session()
        
        # Parse query params
        rule_id = request.args.get('rule_id', type=int)
        status = request.args.get('status')
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 50, type=int), 100)
        
        # Get queue messages
        result = scheduled_messages_service.get_queue_messages(
            business_id=business_id,
            rule_id=rule_id,
            status=status,
            page=page,
            per_page=per_page
        )
        
        # Serialize items
        items_data = []
        for item in result['items']:
            items_data.append({
                'id': item.id,
                'rule_id': item.rule_id,
                'rule_name': item.rule.name if item.rule else None,
                'lead_id': item.lead_id,
                'lead_name': item.lead.full_name if item.lead else None,
                'message_text': item.message_text,
                'remote_jid': item.remote_jid,
                'scheduled_for': item.scheduled_for.isoformat() if item.scheduled_for else None,
                'status': item.status,
                'sent_at': item.sent_at.isoformat() if item.sent_at else None,
                'error_message': item.error_message,
                'created_at': item.created_at.isoformat() if item.created_at else None
            })
        
        return jsonify({
            'items': items_data,
            'total': result['total'],
            'page': result['page'],
            'per_page': result['per_page']
        })
        
    except Exception as e:
        logger.error(f"[SCHEDULED-MSG-API] Error getting queue: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@scheduled_messages_bp.route('/queue/<int:message_id>/cancel', methods=['POST'])
@require_api_auth
def cancel_message(message_id: int):
    """
    Cancel a pending message
    
    Returns:
        {"message": "Message cancelled successfully"}
    """
    try:
        business_id = get_business_id_from_session()
        
        success = scheduled_messages_service.cancel_message(message_id, business_id)
        
        if not success:
            return jsonify({'error': 'Message not found or already sent'}), 404
        
        logger.info(f"[SCHEDULED-MSG-API] Cancelled message {message_id}")
        
        return jsonify({'message': 'Message cancelled successfully'})
        
    except Exception as e:
        logger.error(f"[SCHEDULED-MSG-API] Error cancelling message: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


# === STATISTICS ENDPOINT ===

@scheduled_messages_bp.route('/stats', methods=['GET'])
@require_api_auth
def get_stats():
    """
    Get statistics for scheduled messages
    
    Query params:
        rule_id (optional): Filter by rule ID
    
    Returns:
        {
            "pending": int,
            "sent": int,
            "failed": int,
            "canceled": int
        }
    """
    try:
        business_id = get_business_id_from_session()
        rule_id = request.args.get('rule_id', type=int)
        
        stats = scheduled_messages_service.get_statistics(business_id, rule_id=rule_id)
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"[SCHEDULED-MSG-API] Error getting stats: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
