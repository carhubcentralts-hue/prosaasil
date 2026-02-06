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
@require_page_access('scheduled_messages')
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
                'delay_seconds': getattr(rule, 'delay_seconds', rule.delay_minutes * 60 if rule.delay_minutes else 0),  # Fallback for migration
                'provider': getattr(rule, 'provider', 'baileys'),  # Fallback for migration
                'template_name': rule.template_name,
                'send_window_start': rule.send_window_start,
                'send_window_end': rule.send_window_end,
                'send_immediately_on_enter': getattr(rule, 'send_immediately_on_enter', False),
                'immediate_message': getattr(rule, 'immediate_message', None),
                'apply_mode': getattr(rule, 'apply_mode', 'ON_ENTER_ONLY'),
                'statuses': [
                    {
                        'id': status.id,
                        'name': status.name,
                        'label': status.label,
                        'color': status.color
                    }
                    for status in rule.statuses
                ],
                'steps': [
                    {
                        'id': step.id,
                        'step_index': step.step_index,
                        'message_template': step.message_template,
                        'delay_seconds': step.delay_seconds,
                        'enabled': step.enabled,
                        'created_at': step.created_at.isoformat() if step.created_at else None,
                        'updated_at': step.updated_at.isoformat() if step.updated_at else None
                    }
                    for step in getattr(rule, 'steps', [])
                ],
                'active_weekdays': getattr(rule, 'active_weekdays', None),
                'excluded_weekdays': getattr(rule, 'excluded_weekdays', None),
                'schedule_type': getattr(rule, 'schedule_type', 'STATUS_CHANGE'),
                'recurring_times': getattr(rule, 'recurring_times', None),
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
@require_page_access('scheduled_messages')
def create_rule():
    """
    Create a new scheduling rule
    
    Body:
        {
            "name": str,  # Required
            "message_text": str,  # Required
            "status_ids": [int],  # Required - list of lead status IDs
            "delay_minutes": int,  # Optional - 1 to 43200 (for backward compatibility)
            "delay_seconds": int,  # Optional - 0 to 2592000 (preferred)
            "template_name": str,  # Optional
            "send_window_start": str,  # Optional - HH:MM format
            "send_window_end": str,  # Optional - HH:MM format
            "is_active": bool,  # Optional - defaults to true
            "provider": str,  # Optional - "baileys" | "meta" | "auto" - defaults to "baileys"
            "send_immediately_on_enter": bool,  # Optional - send immediately on status change
            "apply_mode": str,  # Optional - "ON_ENTER_ONLY" | "WHILE_IN_STATUS"
            "steps": [{"step_index": int, "message_template": str, "delay_seconds": int, "enabled": bool}]  # Optional
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
        
        # Get schedule_type (default to STATUS_CHANGE)
        schedule_type = data.get('schedule_type', 'STATUS_CHANGE')
        if schedule_type not in ('STATUS_CHANGE', 'RECURRING_TIME'):
            return jsonify({'error': 'schedule_type must be "STATUS_CHANGE" or "RECURRING_TIME"'}), 400
        
        # Validate based on schedule_type
        if schedule_type == 'RECURRING_TIME':
            # For recurring schedules, validate recurring_times
            recurring_times = data.get('recurring_times')
            if not recurring_times or not isinstance(recurring_times, list) or len(recurring_times) == 0:
                return jsonify({'error': 'recurring_times is required for RECURRING_TIME schedules'}), 400
            
            # Validate time format
            import re
            time_pattern = re.compile(r'^([0-1][0-9]|2[0-3]):[0-5][0-9]$')
            for time_str in recurring_times:
                if not time_pattern.match(time_str):
                    return jsonify({'error': f'Invalid time format "{time_str}". Must be HH:MM (e.g., "09:00", "15:30")'}), 400
            
            # For recurring schedules, delay is not required
            delay_seconds = 0
            delay_minutes = 0
        else:
            # For STATUS_CHANGE schedules, validate message and delay
            recurring_times = None
        
        # message_text is optional if steps are provided or if send_immediately_on_enter with immediate_message
        # But at least one message source must be provided
        has_message_text = bool(data.get('message_text', '').strip())
        has_steps = data.get('steps') and isinstance(data.get('steps'), list) and len(data.get('steps')) > 0
        has_immediate = data.get('send_immediately_on_enter') and bool(data.get('immediate_message', '').strip())
        
        if not has_message_text and not has_steps and not has_immediate:
            return jsonify({'error': 'At least one message must be provided (message_text, steps, or immediate_message)'}), 400
        
        if not data.get('status_ids') or not isinstance(data['status_ids'], list):
            return jsonify({'error': 'status_ids must be a non-empty array'}), 400
        
        # Handle delay for STATUS_CHANGE schedules
        if schedule_type == 'STATUS_CHANGE':
            delay_seconds = data.get('delay_seconds')
            delay_minutes = data.get('delay_minutes')
        
        if schedule_type == 'STATUS_CHANGE' and delay_seconds is None and delay_minutes is None:
            return jsonify({'error': 'Either delay_minutes or delay_seconds is required for STATUS_CHANGE schedules'}), 400
        
        # Convert delay_minutes to delay_seconds if needed (for STATUS_CHANGE)
        if schedule_type == 'STATUS_CHANGE':
            # Check if we have steps or immediate send - allows 0 delay
            has_steps = steps and len(steps) > 0
            has_immediate_send = data.get('send_immediately_on_enter', False)
            allow_zero_delay = has_steps or has_immediate_send
            
            if delay_seconds is None:
                try:
                    delay_minutes = int(delay_minutes)
                except (TypeError, ValueError):
                    return jsonify({'error': 'delay_minutes must be a valid integer'}), 400
                
                # Allow 0 if we have steps or immediate send
                min_delay = 0 if allow_zero_delay else 1
                if delay_minutes < min_delay or delay_minutes > 43200:
                    return jsonify({'error': f'delay_minutes must be between {min_delay} and 43200 (30 days)'}), 400
                
                delay_seconds = delay_minutes * 60
            else:
                try:
                    delay_seconds = int(delay_seconds)
                except (TypeError, ValueError):
                    return jsonify({'error': 'delay_seconds must be a valid integer'}), 400
                
                if delay_seconds < 0 or delay_seconds > 2592000:
                    return jsonify({'error': 'delay_seconds must be between 0 and 2592000 (30 days)'}), 400
                
                # Set delay_minutes for backward compatibility (exact conversion, ensure non-negative)
                delay_minutes = max(0, delay_seconds // 60)
        
        # Get provider (default to baileys)
        provider = data.get('provider', 'baileys')
        if provider not in ('baileys', 'meta', 'auto'):
            return jsonify({'error': 'provider must be "baileys", "meta", or "auto"'}), 400
        
        # Validate apply_mode if provided
        apply_mode = data.get('apply_mode', 'ON_ENTER_ONLY')
        if apply_mode not in ('ON_ENTER_ONLY', 'WHILE_IN_STATUS'):
            return jsonify({'error': 'apply_mode must be "ON_ENTER_ONLY" or "WHILE_IN_STATUS"'}), 400
        
        # Validate steps if provided
        steps = data.get('steps')
        if steps is not None:
            if not isinstance(steps, list):
                return jsonify({'error': 'steps must be an array'}), 400
            
            for step in steps:
                if not isinstance(step, dict):
                    return jsonify({'error': 'Each step must be an object'}), 400
                
                if 'step_index' not in step or 'message_template' not in step or 'delay_seconds' not in step:
                    return jsonify({'error': 'Each step must have step_index, message_template, and delay_seconds'}), 400
                
                try:
                    step_index = int(step['step_index'])
                    if step_index < 1:
                        return jsonify({'error': 'step_index must be >= 1'}), 400
                except (TypeError, ValueError):
                    return jsonify({'error': 'step_index must be a valid integer'}), 400
                
                if not step['message_template'] or not isinstance(step['message_template'], str):
                    return jsonify({'error': 'message_template must be a non-empty string'}), 400
                
                try:
                    delay_seconds = int(step['delay_seconds'])
                    if delay_seconds < 0 or delay_seconds > 2592000:
                        return jsonify({'error': 'step delay_seconds must be between 0 and 2592000'}), 400
                except (TypeError, ValueError):
                    return jsonify({'error': 'step delay_seconds must be a valid integer'}), 400
        
        # Create rule
        rule = scheduled_messages_service.create_rule(
            business_id=business_id,
            name=data['name'],
            message_text=data.get('message_text', ''),  # Default to empty string for steps-only rules
            status_ids=data['status_ids'],
            delay_minutes=delay_minutes,
            delay_seconds=delay_seconds,
            created_by_user_id=user_id,
            template_name=data.get('template_name'),
            send_window_start=data.get('send_window_start'),
            send_window_end=data.get('send_window_end'),
            is_active=data.get('is_active', True),
            provider=provider,
            send_immediately_on_enter=data.get('send_immediately_on_enter', False),
            immediate_message=data.get('immediate_message'),
            apply_mode=apply_mode,
            steps=steps,
            active_weekdays=data.get('active_weekdays'),  # Optional: null means all days
            excluded_weekdays=data.get('excluded_weekdays'),  # Optional: null means no exclusions
            schedule_type=schedule_type,
            recurring_times=recurring_times
        )
        
        logger.info(f"[SCHEDULED-MSG-API] Created rule {rule.id} for business {business_id}")
        
        return jsonify({
            'rule': {
                'id': rule.id,
                'name': rule.name,
                'is_active': rule.is_active,
                'message_text': rule.message_text,
                'delay_minutes': rule.delay_minutes,
                'delay_seconds': rule.delay_seconds,
                'provider': rule.provider,
                'send_immediately_on_enter': getattr(rule, 'send_immediately_on_enter', False),
                'immediate_message': getattr(rule, 'immediate_message', None),
                'apply_mode': getattr(rule, 'apply_mode', 'ON_ENTER_ONLY'),
                'statuses': [
                    {
                        'id': status.id,
                        'name': status.name,
                        'label': status.label,
                        'color': status.color
                    }
                    for status in rule.statuses
                ],
                'steps': [
                    {
                        'id': step.id,
                        'step_index': step.step_index,
                        'message_template': step.message_template,
                        'delay_seconds': step.delay_seconds,
                        'enabled': step.enabled
                    }
                    for step in getattr(rule, 'steps', [])
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
@require_page_access('scheduled_messages')
def update_rule(rule_id: int):
    """
    Update an existing scheduling rule
    
    Body (all fields optional):
        {
            "name": str,
            "message_text": str,
            "status_ids": [int],
            "delay_minutes": int,
            "delay_seconds": int,
            "template_name": str,
            "send_window_start": str,
            "send_window_end": str,
            "is_active": bool,
            "provider": str,  # "baileys" | "meta" | "auto"
            "send_immediately_on_enter": bool,
            "apply_mode": str,  # "ON_ENTER_ONLY" | "WHILE_IN_STATUS"
            "steps": [{"step_index": int, "message_template": str, "delay_seconds": int, "enabled": bool}]
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
        
        # Validate schedule_type if provided
        if 'schedule_type' in data:
            if data['schedule_type'] not in ('STATUS_CHANGE', 'RECURRING_TIME'):
                return jsonify({'error': 'schedule_type must be "STATUS_CHANGE" or "RECURRING_TIME"'}), 400
        
        # Validate recurring_times if provided
        if 'recurring_times' in data and data['recurring_times']:
            import re
            time_pattern = re.compile(r'^([0-1][0-9]|2[0-3]):[0-5][0-9]$')
            for time_str in data['recurring_times']:
                if not time_pattern.match(time_str):
                    return jsonify({'error': f'Invalid time format "{time_str}". Must be HH:MM (e.g., "09:00", "15:30")'}), 400
        
        # Validate delay_minutes if provided (more lenient - allow 0 for immediate sends and recurring)
        if 'delay_minutes' in data and data['delay_minutes'] is not None and data['delay_minutes'] != '':
            try:
                delay_minutes = int(data['delay_minutes'])
            except (TypeError, ValueError):
                return jsonify({'error': 'delay_minutes must be a valid integer'}), 400
            
            # Allow 0 for immediate or recurring schedules    
            if delay_minutes < 0 or delay_minutes > 43200:
                return jsonify({'error': 'delay_minutes must be between 0 and 43200 (30 days)'}), 400
            data['delay_minutes'] = delay_minutes
        
        # Validate delay_seconds if provided (more lenient)
        if 'delay_seconds' in data and data['delay_seconds'] is not None and data['delay_seconds'] != '':
            try:
                delay_seconds = int(data['delay_seconds'])
            except (TypeError, ValueError):
                return jsonify({'error': 'delay_seconds must be a valid integer'}), 400
                
            if delay_seconds < 0 or delay_seconds > 2592000:
                return jsonify({'error': 'delay_seconds must be between 0 and 2592000 (30 days)'}), 400
            data['delay_seconds'] = delay_seconds
        
        # Validate provider if provided
        if 'provider' in data:
            if data['provider'] not in ('baileys', 'meta', 'auto'):
                return jsonify({'error': 'provider must be "baileys", "meta", or "auto"'}), 400
        
        # Validate apply_mode if provided
        if 'apply_mode' in data:
            if data['apply_mode'] not in ('ON_ENTER_ONLY', 'WHILE_IN_STATUS'):
                return jsonify({'error': 'apply_mode must be "ON_ENTER_ONLY" or "WHILE_IN_STATUS"'}), 400
        
        # Validate steps if provided
        if 'steps' in data:
            steps = data['steps']
            if not isinstance(steps, list):
                return jsonify({'error': 'steps must be an array'}), 400
            
            for step in steps:
                if not isinstance(step, dict):
                    return jsonify({'error': 'Each step must be an object'}), 400
                
                if 'step_index' not in step or 'message_template' not in step or 'delay_seconds' not in step:
                    return jsonify({'error': 'Each step must have step_index, message_template, and delay_seconds'}), 400
                
                try:
                    step_index = int(step['step_index'])
                    if step_index < 1:
                        return jsonify({'error': 'step_index must be >= 1'}), 400
                except (TypeError, ValueError):
                    return jsonify({'error': 'step_index must be a valid integer'}), 400
                
                if not step['message_template'] or not isinstance(step['message_template'], str):
                    return jsonify({'error': 'message_template must be a non-empty string'}), 400
                
                try:
                    delay_seconds = int(step['delay_seconds'])
                    if delay_seconds < 0 or delay_seconds > 2592000:
                        return jsonify({'error': 'step delay_seconds must be between 0 and 2592000'}), 400
                except (TypeError, ValueError):
                    return jsonify({'error': 'step delay_seconds must be a valid integer'}), 400
        
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
                'delay_seconds': getattr(rule, 'delay_seconds', rule.delay_minutes * 60 if rule.delay_minutes else 0),
                'provider': getattr(rule, 'provider', 'baileys'),
                'send_immediately_on_enter': getattr(rule, 'send_immediately_on_enter', False),
                'immediate_message': getattr(rule, 'immediate_message', None),
                'apply_mode': getattr(rule, 'apply_mode', 'ON_ENTER_ONLY'),
                'statuses': [
                    {
                        'id': status.id,
                        'name': status.name,
                        'label': status.label
                    }
                    for status in rule.statuses
                ],
                'steps': [
                    {
                        'id': step.id,
                        'step_index': step.step_index,
                        'message_template': step.message_template,
                        'delay_seconds': step.delay_seconds,
                        'enabled': step.enabled
                    }
                    for step in getattr(rule, 'steps', [])
                ],
                'active_weekdays': getattr(rule, 'active_weekdays', None),
                'excluded_weekdays': getattr(rule, 'excluded_weekdays', None),
                'schedule_type': getattr(rule, 'schedule_type', 'STATUS_CHANGE'),
                'recurring_times': getattr(rule, 'recurring_times', None),
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
@require_page_access('scheduled_messages')
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
@require_page_access('scheduled_messages')
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
@require_page_access('scheduled_messages')
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
@require_page_access('scheduled_messages')
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
@require_page_access('scheduled_messages')
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


# === STEP MANAGEMENT ENDPOINTS ===

@scheduled_messages_bp.route('/rules/<int:rule_id>/steps', methods=['POST'])
@require_api_auth
@require_page_access('scheduled_messages')
def add_step(rule_id: int):
    """
    Add a new step to a scheduling rule
    
    Body:
        {
            "step_index": int,  # Required - position in sequence (1-indexed)
            "message_template": str,  # Required - message content
            "delay_seconds": int,  # Required - delay after status change (0-2592000)
            "enabled": bool  # Optional - defaults to true
        }
    
    Returns:
        {
            "step": {step object},
            "message": "Step added successfully"
        }
    """
    try:
        business_id = get_business_id_from_session()
        data = request.get_json()
        
        # Validate required fields
        if 'step_index' not in data:
            return jsonify({'error': 'step_index is required'}), 400
        
        if 'message_template' not in data:
            return jsonify({'error': 'message_template is required'}), 400
        
        if 'delay_seconds' not in data:
            return jsonify({'error': 'delay_seconds is required'}), 400
        
        # Validate step_index
        try:
            step_index = int(data['step_index'])
            if step_index < 1:
                return jsonify({'error': 'step_index must be >= 1'}), 400
        except (TypeError, ValueError):
            return jsonify({'error': 'step_index must be a valid integer'}), 400
        
        # Validate message_template
        if not data['message_template'] or not isinstance(data['message_template'], str):
            return jsonify({'error': 'message_template must be a non-empty string'}), 400
        
        # Validate delay_seconds
        try:
            delay_seconds = int(data['delay_seconds'])
            if delay_seconds < 0 or delay_seconds > 2592000:
                return jsonify({'error': 'delay_seconds must be between 0 and 2592000 (30 days)'}), 400
        except (TypeError, ValueError):
            return jsonify({'error': 'delay_seconds must be a valid integer'}), 400
        
        # Add step
        step = scheduled_messages_service.add_rule_step(
            rule_id=rule_id,
            business_id=business_id,
            step_index=step_index,
            message_template=data['message_template'],
            delay_seconds=delay_seconds,
            enabled=data.get('enabled', True)
        )
        
        logger.info(f"[SCHEDULED-MSG-API] Added step {step.id} to rule {rule_id}")
        
        return jsonify({
            'step': {
                'id': step.id,
                'rule_id': step.rule_id,
                'step_index': step.step_index,
                'message_template': step.message_template,
                'delay_seconds': step.delay_seconds,
                'enabled': step.enabled,
                'created_at': step.created_at.isoformat()
            },
            'message': 'Step added successfully'
        }), 201
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"[SCHEDULED-MSG-API] Error adding step: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@scheduled_messages_bp.route('/rules/<int:rule_id>/steps/<int:step_id>', methods=['PATCH'])
@require_api_auth
@require_page_access('scheduled_messages')
def update_step(rule_id: int, step_id: int):
    """
    Update an existing step in a scheduling rule
    
    Body (all fields optional):
        {
            "step_index": int,
            "message_template": str,
            "delay_seconds": int,
            "enabled": bool
        }
    
    Returns:
        {
            "step": {step object},
            "message": "Step updated successfully"
        }
    """
    try:
        business_id = get_business_id_from_session()
        data = request.get_json()
        
        # Validate step_index if provided
        if 'step_index' in data:
            try:
                step_index = int(data['step_index'])
                if step_index < 1:
                    return jsonify({'error': 'step_index must be >= 1'}), 400
                data['step_index'] = step_index
            except (TypeError, ValueError):
                return jsonify({'error': 'step_index must be a valid integer'}), 400
        
        # Validate message_template if provided
        if 'message_template' in data:
            if not data['message_template'] or not isinstance(data['message_template'], str):
                return jsonify({'error': 'message_template must be a non-empty string'}), 400
        
        # Validate delay_seconds if provided
        if 'delay_seconds' in data:
            try:
                delay_seconds = int(data['delay_seconds'])
                if delay_seconds < 0 or delay_seconds > 2592000:
                    return jsonify({'error': 'delay_seconds must be between 0 and 2592000 (30 days)'}), 400
                data['delay_seconds'] = delay_seconds
            except (TypeError, ValueError):
                return jsonify({'error': 'delay_seconds must be a valid integer'}), 400
        
        # Update step
        step = scheduled_messages_service.update_rule_step(
            step_id=step_id,
            rule_id=rule_id,
            business_id=business_id,
            **data
        )
        
        logger.info(f"[SCHEDULED-MSG-API] Updated step {step_id} in rule {rule_id}")
        
        return jsonify({
            'step': {
                'id': step.id,
                'rule_id': step.rule_id,
                'step_index': step.step_index,
                'message_template': step.message_template,
                'delay_seconds': step.delay_seconds,
                'enabled': step.enabled,
                'updated_at': step.updated_at.isoformat()
            },
            'message': 'Step updated successfully'
        })
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"[SCHEDULED-MSG-API] Error updating step: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@scheduled_messages_bp.route('/rules/<int:rule_id>/steps/<int:step_id>', methods=['DELETE'])
@require_api_auth
@require_page_access('scheduled_messages')
def delete_step(rule_id: int, step_id: int):
    """
    Delete a step from a scheduling rule
    
    Returns:
        {"message": "Step deleted successfully"}
    """
    try:
        business_id = get_business_id_from_session()
        
        success = scheduled_messages_service.delete_rule_step(step_id)
        
        if not success:
            return jsonify({'error': 'Step not found'}), 404
        
        logger.info(f"[SCHEDULED-MSG-API] Deleted step {step_id} from rule {rule_id}")
        
        return jsonify({'message': 'Step deleted successfully'})
        
    except Exception as e:
        logger.error(f"[SCHEDULED-MSG-API] Error deleting step: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@scheduled_messages_bp.route('/rules/<int:rule_id>/steps/reorder', methods=['PUT'])
@require_api_auth
@require_page_access('scheduled_messages')
def reorder_steps(rule_id: int):
    """
    Reorder steps in a scheduling rule
    
    Body:
        {
            "step_ids": [int]  # Required - ordered list of step IDs
        }
    
    Returns:
        {"message": "Steps reordered successfully"}
    """
    try:
        business_id = get_business_id_from_session()
        data = request.get_json()
        
        # Validate required field
        if 'step_ids' not in data:
            return jsonify({'error': 'step_ids is required'}), 400
        
        step_ids = data['step_ids']
        
        if not isinstance(step_ids, list):
            return jsonify({'error': 'step_ids must be an array'}), 400
        
        if not step_ids:
            return jsonify({'error': 'step_ids cannot be empty'}), 400
        
        # Validate all step_ids are integers
        try:
            step_ids = [int(sid) for sid in step_ids]
        except (TypeError, ValueError):
            return jsonify({'error': 'All step_ids must be valid integers'}), 400
        
        # Reorder steps
        scheduled_messages_service.reorder_rule_steps(rule_id, step_ids)
        
        logger.info(f"[SCHEDULED-MSG-API] Reordered steps for rule {rule_id}")
        
        return jsonify({'message': 'Steps reordered successfully'})
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"[SCHEDULED-MSG-API] Error reordering steps: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
