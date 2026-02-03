"""
Appointment Automation API Routes
API endpoints for managing appointment confirmation automations

🎯 ENDPOINTS:
- GET    /api/automations/appointments              - List automations for business
- GET    /api/automations/appointments/:id          - Get specific automation
- POST   /api/automations/appointments              - Create automation
- PUT    /api/automations/appointments/:id          - Update automation
- DELETE /api/automations/appointments/:id          - Delete automation
- GET    /api/automations/appointments/:id/runs     - Get automation run history
- POST   /api/automations/appointments/:id/test     - Test automation message preview
"""
from flask import Blueprint, request, jsonify, session
from datetime import datetime, timedelta
from server.models_sql import (
    AppointmentAutomation,
    AppointmentAutomationRun,
    Appointment,
    Business,
    db
)
from server.routes_admin import require_api_auth
from server.routes_crm import get_business_id
from server.security.permissions import require_page_access
from server.jobs.send_appointment_confirmation_job import render_template
import logging

logger = logging.getLogger(__name__)

appointment_automations_bp = Blueprint('appointment_automations', __name__, url_prefix='/api/automations')


@appointment_automations_bp.route('/appointments', methods=['GET'])
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
@require_page_access('calendar')
def list_automations():
    """
    List all appointment automations for the current business.
    
    Query params:
        - enabled: Filter by enabled status (true/false)
    
    Returns:
        JSON array of automation objects
    """
    try:
        business_id = get_business_id()
        if not business_id:
            return jsonify({'error': 'Business ID required'}), 400
        
        # Build query
        query = AppointmentAutomation.query.filter_by(business_id=business_id)
        
        # Filter by enabled status if specified
        enabled_param = request.args.get('enabled')
        if enabled_param is not None:
            enabled = enabled_param.lower() == 'true'
            query = query.filter_by(enabled=enabled)
        
        automations = query.order_by(AppointmentAutomation.created_at.desc()).all()
        
        # Format response
        result = []
        for automation in automations:
            result.append({
                'id': automation.id,
                'name': automation.name,
                'enabled': automation.enabled,
                'trigger_status_ids': automation.trigger_status_ids or [],
                'schedule_offsets': automation.schedule_offsets or [],
                'channel': automation.channel,
                'message_template': automation.message_template,
                'send_once_per_offset': automation.send_once_per_offset,
                'cancel_on_status_exit': automation.cancel_on_status_exit,
                'created_at': automation.created_at.isoformat() if automation.created_at else None,
                'updated_at': automation.updated_at.isoformat() if automation.updated_at else None
            })
        
        return jsonify({
            'success': True,
            'automations': result,
            'count': len(result)
        })
        
    except Exception as e:
        logger.error(f"Error listing automations: {e}", exc_info=True)
        return jsonify({'error': 'Failed to list automations'}), 500


@appointment_automations_bp.route('/appointments/<int:automation_id>', methods=['GET'])
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
@require_page_access('calendar')
def get_automation(automation_id):
    """Get a specific automation by ID"""
    try:
        business_id = get_business_id()
        if not business_id:
            return jsonify({'error': 'Business ID required'}), 400
        
        automation = AppointmentAutomation.query.filter_by(
            id=automation_id,
            business_id=business_id
        ).first()
        
        if not automation:
            return jsonify({'error': 'Automation not found'}), 404
        
        return jsonify({
            'success': True,
            'automation': {
                'id': automation.id,
                'name': automation.name,
                'enabled': automation.enabled,
                'trigger_status_ids': automation.trigger_status_ids or [],
                'schedule_offsets': automation.schedule_offsets or [],
                'channel': automation.channel,
                'message_template': automation.message_template,
                'send_once_per_offset': automation.send_once_per_offset,
                'cancel_on_status_exit': automation.cancel_on_status_exit,
                'created_at': automation.created_at.isoformat() if automation.created_at else None,
                'updated_at': automation.updated_at.isoformat() if automation.updated_at else None
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting automation {automation_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to get automation'}), 500


@appointment_automations_bp.route('/appointments', methods=['POST'])
@require_api_auth(['system_admin', 'owner', 'admin'])
@require_page_access('calendar')
def create_automation():
    """
    Create a new appointment automation.
    
    Request body:
        - name: Automation name
        - enabled: Whether automation is enabled
        - trigger_status_ids: Array of appointment statuses
        - schedule_offsets: Array of offset configs
        - message_template: Message template with placeholders
        - channel: Communication channel (default: whatsapp)
    """
    try:
        business_id = get_business_id()
        if not business_id:
            return jsonify({'error': 'Business ID required'}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request data required'}), 400
        
        # Validate required fields
        if not data.get('name'):
            return jsonify({'error': 'Name is required'}), 400
        if not data.get('message_template'):
            return jsonify({'error': 'Message template is required'}), 400
        if not data.get('trigger_status_ids') or len(data['trigger_status_ids']) == 0:
            return jsonify({'error': 'At least one trigger status is required'}), 400
        if not data.get('schedule_offsets') or len(data['schedule_offsets']) == 0:
            return jsonify({'error': 'At least one schedule offset is required'}), 400
        
        # Get current user
        user_data = session.get('user') or session.get('al_user')
        user_id = user_data.get('id') if user_data else None
        
        # Create automation
        automation = AppointmentAutomation(
            business_id=business_id,
            name=data['name'],
            enabled=data.get('enabled', True),
            trigger_status_ids=data['trigger_status_ids'],
            schedule_offsets=data['schedule_offsets'],
            channel=data.get('channel', 'whatsapp'),
            message_template=data['message_template'],
            send_once_per_offset=data.get('send_once_per_offset', True),
            cancel_on_status_exit=data.get('cancel_on_status_exit', True),
            created_by=user_id
        )
        
        db.session.add(automation)
        db.session.commit()
        
        logger.info(f"Created automation {automation.id} for business {business_id}")
        
        return jsonify({
            'success': True,
            'automation_id': automation.id,
            'message': 'אוטומציה נוצרה בהצלחה'
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating automation: {e}", exc_info=True)
        return jsonify({'error': 'Failed to create automation'}), 500


@appointment_automations_bp.route('/appointments/<int:automation_id>', methods=['PUT'])
@require_api_auth(['system_admin', 'owner', 'admin'])
@require_page_access('calendar')
def update_automation(automation_id):
    """Update an existing automation"""
    try:
        business_id = get_business_id()
        if not business_id:
            return jsonify({'error': 'Business ID required'}), 400
        
        automation = AppointmentAutomation.query.filter_by(
            id=automation_id,
            business_id=business_id
        ).first()
        
        if not automation:
            return jsonify({'error': 'Automation not found'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request data required'}), 400
        
        # Update fields
        updatable_fields = [
            'name', 'enabled', 'trigger_status_ids', 'schedule_offsets',
            'channel', 'message_template', 'send_once_per_offset', 'cancel_on_status_exit'
        ]
        
        for field in updatable_fields:
            if field in data:
                setattr(automation, field, data[field])
        
        automation.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        logger.info(f"Updated automation {automation_id} for business {business_id}")
        
        return jsonify({
            'success': True,
            'message': 'אוטומציה עודכנה בהצלחה'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating automation {automation_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to update automation'}), 500


@appointment_automations_bp.route('/appointments/<int:automation_id>', methods=['DELETE'])
@require_api_auth(['system_admin', 'owner', 'admin'])
@require_page_access('calendar')
def delete_automation(automation_id):
    """Delete an automation"""
    try:
        business_id = get_business_id()
        if not business_id:
            return jsonify({'error': 'Business ID required'}), 400
        
        automation = AppointmentAutomation.query.filter_by(
            id=automation_id,
            business_id=business_id
        ).first()
        
        if not automation:
            return jsonify({'error': 'Automation not found'}), 404
        
        # Check if there are pending runs
        pending_runs = AppointmentAutomationRun.query.filter_by(
            automation_id=automation_id,
            status='pending'
        ).count()
        
        if pending_runs > 0:
            return jsonify({
                'error': f'Cannot delete automation with {pending_runs} pending runs. Disable it instead.',
                'pending_runs': pending_runs
            }), 400
        
        db.session.delete(automation)
        db.session.commit()
        
        logger.info(f"Deleted automation {automation_id} for business {business_id}")
        
        return jsonify({
            'success': True,
            'message': 'אוטומציה נמחקה בהצלחה'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting automation {automation_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to delete automation'}), 500


@appointment_automations_bp.route('/appointments/<int:automation_id>/runs', methods=['GET'])
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
@require_page_access('calendar')
def get_automation_runs(automation_id):
    """
    Get run history for an automation.
    
    Query params:
        - status: Filter by status (pending/sent/failed/canceled)
        - limit: Maximum number of runs to return (default: 100)
    """
    try:
        business_id = get_business_id()
        if not business_id:
            return jsonify({'error': 'Business ID required'}), 400
        
        # Verify automation exists and belongs to business
        automation = AppointmentAutomation.query.filter_by(
            id=automation_id,
            business_id=business_id
        ).first()
        
        if not automation:
            return jsonify({'error': 'Automation not found'}), 404
        
        # Build query
        query = AppointmentAutomationRun.query.filter_by(
            automation_id=automation_id,
            business_id=business_id
        )
        
        # Filter by status if specified
        status = request.args.get('status')
        if status:
            query = query.filter_by(status=status)
        
        # Limit results
        limit = int(request.args.get('limit', 100))
        runs = query.order_by(AppointmentAutomationRun.created_at.desc()).limit(limit).all()
        
        # Format response
        result = []
        for run in runs:
            result.append({
                'id': run.id,
                'appointment_id': run.appointment_id,
                'offset_signature': run.offset_signature,
                'scheduled_for': run.scheduled_for.isoformat() if run.scheduled_for else None,
                'status': run.status,
                'attempts': run.attempts,
                'last_error': run.last_error,
                'created_at': run.created_at.isoformat() if run.created_at else None,
                'sent_at': run.sent_at.isoformat() if run.sent_at else None,
                'canceled_at': run.canceled_at.isoformat() if run.canceled_at else None
            })
        
        return jsonify({
            'success': True,
            'runs': result,
            'count': len(result)
        })
        
    except Exception as e:
        logger.error(f"Error getting runs for automation {automation_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to get automation runs'}), 500


@appointment_automations_bp.route('/appointments/<int:automation_id>/test', methods=['POST'])
@require_api_auth(['system_admin', 'owner', 'admin'])
@require_page_access('calendar')
def test_automation_preview(automation_id):
    """
    Preview what an automation message would look like with sample data.
    
    Request body:
        - appointment_id: Optional appointment ID to use real data
    
    Returns:
        Rendered message preview
    """
    try:
        business_id = get_business_id()
        if not business_id:
            return jsonify({'error': 'Business ID required'}), 400
        
        # Get automation
        automation = AppointmentAutomation.query.filter_by(
            id=automation_id,
            business_id=business_id
        ).first()
        
        if not automation:
            return jsonify({'error': 'Automation not found'}), 404
        
        # Get business
        business = Business.query.get(business_id)
        
        data = request.get_json() or {}
        appointment_id = data.get('appointment_id')
        
        # Build context for template
        if appointment_id:
            # Use real appointment data
            appointment = Appointment.query.filter_by(
                id=appointment_id,
                business_id=business_id
            ).first()
            
            if not appointment:
                return jsonify({'error': 'Appointment not found'}), 404
            
            from server.jobs.send_appointment_confirmation_job import format_hebrew_date
            
            context = {
                'first_name': appointment.contact_name or 'לקוח יקר',
                'business_name': business.name if business else 'העסק',
                'appointment_date': format_hebrew_date(appointment.start_time),
                'appointment_time': appointment.start_time.strftime('%H:%M'),
                'appointment_location': appointment.location or 'המשרד שלנו',
                'rep_name': business.name if business else 'הנציג'
            }
        else:
            # Use sample data
            sample_date = datetime.now() + timedelta(days=1)
            from server.jobs.send_appointment_confirmation_job import format_hebrew_date
            
            context = {
                'first_name': 'יוסי',
                'business_name': business.name if business else 'העסק שלנו',
                'appointment_date': format_hebrew_date(sample_date),
                'appointment_time': '14:00',
                'appointment_location': 'רחוב הרצל 1, תל אביב',
                'rep_name': 'דני'
            }
        
        # Render message
        preview_message = render_template(automation.message_template, context)
        
        return jsonify({
            'success': True,
            'preview': preview_message,
            'context': context
        })
        
    except Exception as e:
        logger.error(f"Error testing automation {automation_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to preview automation'}), 500
