"""
Calendar API endpoints for appointments management
Handles all appointment CRUD operations with full security and role-based permissions
"""
from flask import Blueprint, request, jsonify, session, g
from datetime import datetime, timedelta
from server.models_sql import Appointment, Business, Customer, Deal, CallLog, WhatsAppMessage, User, db
from server.routes_admin import require_api_auth  # Standardized import per guidelines
from server.routes_crm import get_business_id
from server.services.notifications.dispatcher import notify_user
from server.security.permissions import require_page_access  # Page access decorator
import json
from sqlalchemy import and_, or_, desc, asc
import pytz
import logging


logger = logging.getLogger(__name__)

log = logging.getLogger(__name__)

# 🔥 Israel timezone for converting naive datetimes to timezone-aware
tz = pytz.timezone("Asia/Jerusalem")

calendar_bp = Blueprint('calendar', __name__, url_prefix='/api/calendar')

# ================================================================================
# HELPER FUNCTIONS
# ================================================================================

def check_appointment_overlap(business_id: int, start_time: datetime, end_time: datetime, exclude_id: int = None):
    """
    Check if a new appointment overlaps with existing appointments
    
    Args:
        business_id: Business ID to check
        start_time: Proposed start time (naive datetime in local Israel time)
        end_time: Proposed end time (naive datetime in local Israel time)
        exclude_id: Appointment ID to exclude from check (for updates)
    
    Returns:
        Existing overlapping appointment if found, None otherwise
    """
    query = Appointment.query.filter(
        Appointment.business_id == business_id,
        Appointment.start_time < end_time,
        Appointment.end_time > start_time,
        Appointment.status.in_(['scheduled', 'confirmed'])
    )
    
    # Exclude specific appointment (for updates)
    if exclude_id:
        query = query.filter(Appointment.id != exclude_id)
    
    return query.first()

def get_user_business_filter():
    """Get business filter based on user role and permissions"""
    user_data = session.get('user') or session.get('al_user')
    if not user_data:
        return None
    
    user_role = user_data.get('role')
    business_id = get_business_id()
    
    # System admin can see all appointments
    if user_role == 'system_admin':
        if business_id:
            return Appointment.business_id == business_id
        else:
            return True  # No filter - see all
    
    # Owner/Admin/Agent filter by their business
    if user_role in ['owner', 'admin', 'agent']:
        if business_id:
            return Appointment.business_id == business_id
        else:
            # Fallback to user's own business_id if available
            user_business = user_data.get('business_id')
            if user_business:
                return Appointment.business_id == user_business
    
    return None

@calendar_bp.route('/appointments', methods=['GET'])
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
@require_page_access('calendar')
def get_appointments():
    """Get all appointments for the current user's business or all businesses (admin/manager)"""
    try:
        # Get business filter based on user permissions
        business_filter = get_user_business_filter()
        if business_filter is None:
            return jsonify({'error': 'Access denied'}), 403
        
        # Parse query parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        status = request.args.get('status')
        appointment_type = request.args.get('type')
        search = request.args.get('search', '').strip()
        lead_id = request.args.get('lead_id')  # Filter by lead_id
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 50)), 100)  # Max 100 per page
        
        # Build query
        query = db.session.query(Appointment)
        
        # Apply business filter
        if business_filter is not True:  # True means no filter
            query = query.filter(business_filter)
        
        # Date range filter
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                # 🔥 CRITICAL: Convert to Israel timezone FIRST, then strip timezone
                # This ensures UTC/Z inputs map to correct local naive values
                # Example: "2025-11-05T00:00:00Z" → "2025-11-05T02:00:00+02:00" → "2025-11-05 02:00" (naive)
                if start_dt.tzinfo is not None:
                    start_dt = start_dt.astimezone(tz)  # Convert to Israel time
                    start_dt = start_dt.replace(tzinfo=None)  # Strip timezone
                query = query.filter(Appointment.start_time >= start_dt)
            except ValueError:
                return jsonify({'error': 'Invalid start_date format'}), 400
        
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                # 🔥 CRITICAL: Convert to Israel timezone FIRST, then strip timezone
                if end_dt.tzinfo is not None:
                    end_dt = end_dt.astimezone(tz)  # Convert to Israel time
                    end_dt = end_dt.replace(tzinfo=None)  # Strip timezone
                query = query.filter(Appointment.end_time <= end_dt)
            except ValueError:
                return jsonify({'error': 'Invalid end_date format'}), 400
        
        # Status filter
        if status and status != 'all':
            query = query.filter(Appointment.status == status)
        
        # Type filter
        if appointment_type and appointment_type != 'all':
            query = query.filter(Appointment.appointment_type == appointment_type)
        
        # Lead ID filter - filter appointments linked to a specific lead
        if lead_id:
            try:
                lead_id_int = int(lead_id)
                query = query.filter(Appointment.lead_id == lead_id_int)
            except ValueError:
                return jsonify({'error': 'Invalid lead_id format'}), 400
        
        # Search filter
        if search:
            search_term = f'%{search}%'
            query = query.filter(or_(
                Appointment.title.ilike(search_term),
                Appointment.description.ilike(search_term),
                Appointment.contact_name.ilike(search_term),
                Appointment.contact_phone.ilike(search_term),
                Appointment.location.ilike(search_term)
            ))
        
        # Pagination and ordering
        query = query.order_by(desc(Appointment.start_time))
        
        # Get total count before pagination
        total = query.count()
        
        # Apply pagination
        appointments_query = query.offset((page - 1) * per_page).limit(per_page)
        appointments = appointments_query.all()
        
        # Format appointments for response
        appointments_data = []
        for apt in appointments:
            # 🔥 Convert naive datetime to timezone-aware before isoformat()
            # DB stores naive datetimes (local Israel time), so we add timezone back for Frontend
            # This ensures Frontend gets "2025-11-05T14:00:00+02:00" instead of "2025-11-05T14:00:00"
            start_time_aware = tz.localize(apt.start_time) if apt.start_time and apt.start_time.tzinfo is None else apt.start_time
            end_time_aware = tz.localize(apt.end_time) if apt.end_time and apt.end_time.tzinfo is None else apt.end_time
            
            appointment_data = {
                'id': apt.id,
                'business_id': apt.business_id,
                'customer_id': apt.customer_id,
                'deal_id': apt.deal_id,
                'lead_id': apt.lead_id,
                'call_log_id': apt.call_log_id,
                'whatsapp_message_id': apt.whatsapp_message_id,
                'title': apt.title,
                'description': apt.description,
                'start_time': start_time_aware.isoformat() if start_time_aware else None,
                'end_time': end_time_aware.isoformat() if end_time_aware else None,
                'location': apt.location,
                'status': apt.status,
                'appointment_type': apt.appointment_type,
                'priority': apt.priority,
                'contact_name': apt.contact_name,
                'contact_phone': apt.contact_phone,
                'contact_email': apt.contact_email,
                'notes': apt.notes,
                'outcome': apt.outcome,
                'follow_up_needed': apt.follow_up_needed,
                'follow_up_date': apt.follow_up_date.isoformat() if apt.follow_up_date else None,
                'auto_generated': apt.auto_generated,
                'source': apt.source,
                'created_at': apt.created_at.isoformat() if apt.created_at else None,
                'updated_at': apt.updated_at.isoformat() if apt.updated_at else None,
                
                # ✅ BUILD 144: Include call summary and transcript from source call
                'call_summary': apt.call_summary,
                'call_transcript': apt.call_transcript,
                'dynamic_summary': apt.dynamic_summary,
                
                # Related data
                'business_name': None,
                'customer_name': None,
                'from_phone': None  # Derived from call_log, not stored in appointment
            }
            
            # Add business info for admin/manager views
            if apt.business_id:
                business = Business.query.get(apt.business_id)
                if business:
                    appointment_data['business_name'] = business.name
            
            # Add customer info if available
            if apt.customer_id:
                customer = Customer.query.get(apt.customer_id)
                if customer:
                    appointment_data['customer_name'] = customer.name
            
            # Add phone number from multiple sources (priority order):
            # 1. Call log (most specific)
            # 2. Lead phone (if linked to lead)
            # 3. Contact phone (from appointment itself)
            if apt.call_log_id:
                call_log = CallLog.query.get(apt.call_log_id)
                if call_log and call_log.from_number:
                    appointment_data['from_phone'] = call_log.from_number
            
            # If no phone from call_log, try to get from lead
            if not appointment_data['from_phone'] and apt.lead_id:
                from server.models_sql import Lead
                lead = Lead.query.get(apt.lead_id)
                if lead and lead.phone_e164:
                    appointment_data['from_phone'] = lead.phone_e164
            
            # If still no phone, use contact_phone from appointment
            if not appointment_data['from_phone'] and apt.contact_phone:
                appointment_data['from_phone'] = apt.contact_phone
            
            appointments_data.append(appointment_data)
        
        return jsonify({
            'appointments': appointments_data,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page
            }
        })
        
    except Exception as e:
        logger.error(f"Error fetching appointments: {e}")
        return jsonify({'error': 'שגיאה בטעינת הפגישות'}), 500

@calendar_bp.route('/appointments', methods=['POST'])
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
@require_page_access('calendar')
def create_appointment():
    """Create a new appointment"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Missing request data'}), 400
        
        # Validate required fields
        required_fields = ['title', 'start_time', 'end_time']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'שדה חובה חסר: {field}'}), 400
        
        # Get business ID based on user permissions
        business_id = get_business_id()
        user_data = session.get('user') or session.get('al_user')
        user_role = user_data.get('role') if user_data else None
        
        # For business users, must use their business_id
        if user_role == 'business':
            if not business_id:
                return jsonify({'error': 'לא נמצא עסק לחשבון זה'}), 400
        # For admin/manager, can specify business_id or use default
        elif user_role in ['admin', 'manager']:
            if 'business_id' in data and data['business_id']:
                # Validate the specified business exists
                if not Business.query.get(data['business_id']):
                    return jsonify({'error': 'עסק לא נמצא'}), 404
                business_id = data['business_id']
            elif not business_id:
                return jsonify({'error': 'יש לציין עסק'}), 400
        
        # Parse and validate dates
        try:
            # 🔥 FIX: Handle both formats - with and without timezone
            # If the datetime string doesn't have timezone info, treat it as local Israel time
            start_str = data['start_time']
            end_str = data['end_time']
            
            # Remove 'Z' if present (legacy format)
            if start_str.endswith('Z'):
                start_str = start_str[:-1]
            if end_str.endswith('Z'):
                end_str = end_str[:-1]
            
            # Parse as naive datetime (no timezone) - this is local Israel time
            start_time = datetime.fromisoformat(start_str)
            end_time = datetime.fromisoformat(end_str)
            
            # Ensure naive datetime (remove timezone if somehow present)
            if start_time.tzinfo is not None:
                start_time = start_time.replace(tzinfo=None)
            if end_time.tzinfo is not None:
                end_time = end_time.replace(tzinfo=None)
        except ValueError:
            return jsonify({'error': 'פורמט תאריך לא תקין'}), 400
        
        if end_time <= start_time:
            return jsonify({'error': 'זמן סיום חייב להיות אחרי זמן התחלה'}), 400
        
        # 🔥 CRITICAL: Check for overlapping appointments
        existing = check_appointment_overlap(business_id, start_time, end_time)
        if existing:
            # Format the conflict message
            conflict_start = tz.localize(existing.start_time) if existing.start_time.tzinfo is None else existing.start_time
            return jsonify({
                'error': f'קיימת חפיפה עם פגישה "{existing.title}" בשעה {conflict_start.strftime("%H:%M")}. אנא בחר זמן אחר.',
                'conflict': True,
                'conflicting_appointment': {
                    'id': existing.id,
                    'title': existing.title,
                    'start_time': conflict_start.isoformat()
                }
            }), 409  # 409 Conflict
        
        # Create new appointment
        appointment = Appointment()
        appointment.business_id = business_id
        appointment.customer_id = data.get('customer_id')
        appointment.deal_id = data.get('deal_id')
        appointment.lead_id = data.get('lead_id')  # 🔥 FIX: Accept lead_id from request
        appointment.call_log_id = data.get('call_log_id')
        appointment.whatsapp_message_id = data.get('whatsapp_message_id')
        appointment.title = data['title']
        appointment.description = data.get('description')
        appointment.start_time = start_time  # Now naive datetime (local Israel time)
        appointment.end_time = end_time      # Now naive datetime (local Israel time)
        appointment.location = data.get('location')
        appointment.status = data.get('status', 'scheduled')
        appointment.appointment_type = data.get('appointment_type', 'appointment')  # Generic default
        appointment.priority = data.get('priority', 'medium')
        appointment.contact_name = data.get('contact_name')
        appointment.contact_phone = data.get('contact_phone')
        appointment.contact_email = data.get('contact_email')
        appointment.notes = data.get('notes')
        appointment.follow_up_needed = data.get('follow_up_needed', False)
        appointment.follow_up_date = datetime.fromisoformat(data['follow_up_date'].replace('Z', '+00:00')) if data.get('follow_up_date') else None
        appointment.created_by = user_data.get('id') if user_data else None
        appointment.auto_generated = data.get('auto_generated', False)
        appointment.source = data.get('source', 'manual')
        
        db.session.add(appointment)
        db.session.commit()
        
        # 🔔 Send notification for new appointment (in-app bell + push)
        try:
            created_by_user_id = user_data.get('id') if user_data else None
            if created_by_user_id and business_id:
                # Format start time for notification
                start_time_local = tz.localize(start_time) if start_time.tzinfo is None else start_time
                time_str = start_time_local.strftime('%d/%m %H:%M')
                
                notify_user(
                    event_type='appointment_created',
                    title='📅 פגישה חדשה נקבעה',
                    body=f'{appointment.title} - {time_str}',
                    url=f'/app/calendar?appointment={appointment.id}',
                    user_id=created_by_user_id,
                    business_id=business_id,
                    entity_id=str(appointment.id),
                    priority='medium',
                    save_to_bell=True
                )
                log.info(f"🔔 Notification sent for new appointment {appointment.id}")
        except Exception as notify_error:
            log.warning(f"⚠️ Failed to send appointment notification: {notify_error}")
            # Don't fail the request if notification fails
        
        return jsonify({
            'success': True,
            'appointment_id': appointment.id,
            'message': 'הפגישה נוצרה בהצלחה'
        }), 201
        
    except Exception as e:
        db.session.rollback()
        log.error(f"Error creating appointment: {e}")
        return jsonify({'error': 'שגיאה ביצירת הפגישה'}), 500

@calendar_bp.route('/appointments/<int:appointment_id>', methods=['GET'])
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
@require_page_access('calendar')
def get_appointment(appointment_id):
    """Get a specific appointment by ID"""
    try:
        # Get business filter
        business_filter = get_user_business_filter()
        if business_filter is None:
            return jsonify({'error': 'Access denied'}), 403
        
        # Find appointment
        query = db.session.query(Appointment).filter(Appointment.id == appointment_id)
        
        # Apply business filter
        if business_filter is not True:
            query = query.filter(business_filter)
        
        appointment = query.first()
        if not appointment:
            return jsonify({'error': 'פגישה לא נמצאה'}), 404
        
        # Get related data
        business = Business.query.get(appointment.business_id) if appointment.business_id else None
        customer = Customer.query.get(appointment.customer_id) if appointment.customer_id else None
        deal = Deal.query.get(appointment.deal_id) if appointment.deal_id else None
        call_log = CallLog.query.get(appointment.call_log_id) if appointment.call_log_id else None
        
        # 🔥 Convert naive datetime to timezone-aware before isoformat()
        # DB stores naive datetimes (local Israel time), so we add timezone back for Frontend
        start_time_aware = tz.localize(appointment.start_time) if appointment.start_time and appointment.start_time.tzinfo is None else appointment.start_time
        end_time_aware = tz.localize(appointment.end_time) if appointment.end_time and appointment.end_time.tzinfo is None else appointment.end_time
        
        appointment_data = {
            'id': appointment.id,
            'business_id': appointment.business_id,
            'customer_id': appointment.customer_id,
            'deal_id': appointment.deal_id,
            'lead_id': appointment.lead_id,
            'call_log_id': appointment.call_log_id,
            'whatsapp_message_id': appointment.whatsapp_message_id,
            'title': appointment.title,
            'description': appointment.description,
            'start_time': start_time_aware.isoformat() if start_time_aware else None,
            'end_time': end_time_aware.isoformat() if end_time_aware else None,
            'location': appointment.location,
            'status': appointment.status,
            'appointment_type': appointment.appointment_type,
            'priority': appointment.priority,
            'contact_name': appointment.contact_name,
            'contact_phone': appointment.contact_phone,
            'contact_email': appointment.contact_email,
            'notes': appointment.notes,
            'outcome': appointment.outcome,
            'follow_up_needed': appointment.follow_up_needed,
            'follow_up_date': appointment.follow_up_date.isoformat() if appointment.follow_up_date else None,
            'auto_generated': appointment.auto_generated,
            'source': appointment.source,
            'created_at': appointment.created_at.isoformat() if appointment.created_at else None,
            'updated_at': appointment.updated_at.isoformat() if appointment.updated_at else None,
            
            # Call summary data
            'call_summary': appointment.call_summary,
            'call_transcript': appointment.call_transcript,
            'dynamic_summary': appointment.dynamic_summary,
            
            # Phone number from multiple sources
            'from_phone': None,
            
            # Related data
            'business': {'id': business.id, 'name': business.name} if business else None,
            'customer': {'id': customer.id, 'name': customer.name, 'phone': customer.phone} if customer else None,
            'deal': {'id': deal.id, 'title': deal.title, 'stage': deal.stage, 'amount': deal.amount} if deal else None,
            'call_log': {'id': call_log.id, 'from_number': call_log.from_number, 'status': call_log.status} if call_log else None
        }
        
        # Fill from_phone from multiple sources (priority order)
        if call_log and call_log.from_number:
            appointment_data['from_phone'] = call_log.from_number
        elif appointment.lead_id:
            from server.models_sql import Lead
            lead = Lead.query.get(appointment.lead_id)
            if lead and lead.phone_e164:
                appointment_data['from_phone'] = lead.phone_e164
        elif appointment.contact_phone:
            appointment_data['from_phone'] = appointment.contact_phone
        
        return jsonify({'appointment': appointment_data})
        
    except Exception as e:
        logger.error(f"Error fetching appointment {appointment_id}: {e}")
        return jsonify({'error': 'שגיאה בטעינת הפגישה'}), 500

@calendar_bp.route('/appointments/<int:appointment_id>', methods=['PUT'])
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
@require_page_access('calendar')
def update_appointment(appointment_id):
    """Update an existing appointment"""
    try:
        # Get business filter
        business_filter = get_user_business_filter()
        if business_filter is None:
            return jsonify({'error': 'Access denied'}), 403
        
        # Find appointment
        query = db.session.query(Appointment).filter(Appointment.id == appointment_id)
        
        # Apply business filter
        if business_filter is not True:
            query = query.filter(business_filter)
        
        appointment = query.first()
        if not appointment:
            return jsonify({'error': 'פגישה לא נמצאה'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Missing request data'}), 400
        
        # Update allowed fields
        updatable_fields = [
            'title', 'description', 'location', 'status', 'appointment_type', 
            'priority', 'contact_name', 'contact_phone', 'contact_email', 
            'notes', 'outcome', 'follow_up_needed', 'lead_id'  # 🔥 FIX: Allow updating lead_id
        ]
        
        for field in updatable_fields:
            if field in data:
                setattr(appointment, field, data[field])
        
        # Handle date fields
        if 'start_time' in data:
            try:
                # 🔥 FIX: Handle both formats - with and without timezone
                start_str = data['start_time']
                if start_str.endswith('Z'):
                    start_str = start_str[:-1]
                start_time = datetime.fromisoformat(start_str)
                # Ensure naive datetime (local Israel time)
                appointment.start_time = start_time.replace(tzinfo=None) if start_time.tzinfo else start_time
            except ValueError:
                return jsonify({'error': 'פורמט זמן התחלה לא תקין'}), 400
        
        if 'end_time' in data:
            try:
                # 🔥 FIX: Handle both formats - with and without timezone
                end_str = data['end_time']
                if end_str.endswith('Z'):
                    end_str = end_str[:-1]
                end_time = datetime.fromisoformat(end_str)
                # Ensure naive datetime (local Israel time)
                appointment.end_time = end_time.replace(tzinfo=None) if end_time.tzinfo else end_time
            except ValueError:
                return jsonify({'error': 'פורמט זמן סיום לא תקין'}), 400
        
        if 'follow_up_date' in data and data['follow_up_date']:
            try:
                appointment.follow_up_date = datetime.fromisoformat(data['follow_up_date'].replace('Z', '+00:00'))
            except ValueError:
                return jsonify({'error': 'פורמט תאריך מעקב לא תקין'}), 400
        
        # Validate dates (only if both exist)
        if appointment.end_time and appointment.start_time and appointment.end_time <= appointment.start_time:
            return jsonify({'error': 'זמן סיום חייב להיות אחרי זמן התחלה'}), 400
        
        # 🔥 CRITICAL: Check for overlapping appointments (exclude current appointment)
        if appointment.start_time and appointment.end_time and appointment.business_id:
            existing = check_appointment_overlap(
                appointment.business_id, 
                appointment.start_time, 
                appointment.end_time,
                exclude_id=appointment_id  # Exclude current appointment from overlap check
            )
            if existing:
                conflict_start = tz.localize(existing.start_time) if existing.start_time.tzinfo is None else existing.start_time
                return jsonify({
                    'error': f'קיימת חפיפה עם פגישה "{existing.title}" בשעה {conflict_start.strftime("%H:%M")}. אנא בחר זמן אחר.',
                    'conflict': True,
                    'conflicting_appointment': {
                        'id': existing.id,
                        'title': existing.title,
                        'start_time': conflict_start.isoformat()
                    }
                }), 409  # 409 Conflict
        
        appointment.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'הפגישה עודכנה בהצלחה'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating appointment {appointment_id}: {e}")
        return jsonify({'error': 'שגיאה בעדכון הפגישה'}), 500

@calendar_bp.route('/appointments/<int:appointment_id>', methods=['DELETE'])
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
@require_page_access('calendar')
def delete_appointment(appointment_id):
    """Delete an appointment"""
    try:
        # Get business filter
        business_filter = get_user_business_filter()
        if business_filter is None:
            return jsonify({'error': 'Access denied'}), 403
        
        # Find appointment
        query = db.session.query(Appointment).filter(Appointment.id == appointment_id)
        
        # Apply business filter
        if business_filter is not True:
            query = query.filter(business_filter)
        
        appointment = query.first()
        if not appointment:
            return jsonify({'error': 'פגישה לא נמצאה'}), 404
        
        # Check if appointment can be deleted
        user_data = session.get('user') or session.get('al_user')
        user_role = user_data.get('role') if user_data else None
        
        # Business users can only delete their own appointments that are not completed
        if user_role == 'business' and appointment.status == 'completed':
            return jsonify({'error': 'לא ניתן למחוק פגישה שהושלמה'}), 403
        
        db.session.delete(appointment)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'הפגישה נמחקה בהצלחה'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting appointment {appointment_id}: {e}")
        return jsonify({'error': 'שגיאה במחיקת הפגישה'}), 500

@calendar_bp.route('/stats', methods=['GET'])
@require_api_auth(['system_admin', 'owner', 'admin', 'agent'])
@require_page_access('calendar')
def get_calendar_stats():
    """Get calendar statistics for dashboard"""
    try:
        # Get business filter
        business_filter = get_user_business_filter()
        if business_filter is None:
            return jsonify({'error': 'Access denied'}), 403
        
        # Base query
        query = db.session.query(Appointment)
        if business_filter is not True:
            query = query.filter(business_filter)
        
        # Date ranges
        today = datetime.now().date()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)
        
        # 🔥 PERFORMANCE FIX: Convert to datetime ranges for efficient index usage
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())
        week_start_dt = datetime.combine(week_start, datetime.min.time())
        month_start_dt = datetime.combine(month_start, datetime.min.time())
        
        # Calculate stats
        stats = {
            'today': query.filter(
                Appointment.start_time >= today_start,
                Appointment.start_time <= today_end
            ).count(),
            
            'this_week': query.filter(
                Appointment.start_time >= week_start_dt
            ).count(),
            
            'this_month': query.filter(
                Appointment.start_time >= month_start_dt
            ).count(),
            
            'scheduled': query.filter(Appointment.status == 'scheduled').count(),
            'confirmed': query.filter(Appointment.status == 'confirmed').count(),
            'completed': query.filter(Appointment.status == 'completed').count(),
            'cancelled': query.filter(Appointment.status == 'cancelled').count(),
            'no_show': query.filter(Appointment.status == 'no_show').count(),
            
            'ai_generated': query.filter(Appointment.auto_generated == True).count(),
            'phone_sourced': query.filter(Appointment.source == 'phone_call').count(),
            'whatsapp_sourced': query.filter(Appointment.source == 'whatsapp').count(),
            
            'high_priority': query.filter(Appointment.priority == 'high').count(),
            'urgent': query.filter(Appointment.priority == 'urgent').count(),
            
            'follow_up_needed': query.filter(Appointment.follow_up_needed == True).count()
        }
        
        return jsonify({'stats': stats})
        
    except Exception as e:
        logger.error(f"Error fetching calendar stats: {e}")
        return jsonify({'error': 'שגיאה בטעינת סטטיסטיקות'}), 500

# ================================================================================
# BUSINESS CALENDARS MANAGEMENT
# ================================================================================

@calendar_bp.route('/calendars', methods=['GET'])
@require_api_auth(['system_admin', 'owner', 'admin'])
@require_page_access('calendar')
def get_business_calendars():
    """Get all calendars for the current user's business"""
    try:
        business_id = get_business_id()
        if not business_id:
            return jsonify({'error': 'Business ID required'}), 400
        
        from server.models_sql import BusinessCalendar
        
        calendars = BusinessCalendar.query.filter(
            BusinessCalendar.business_id == business_id
        ).order_by(BusinessCalendar.priority.desc(), BusinessCalendar.name).all()
        
        result = [{
            'id': cal.id,
            'business_id': cal.business_id,
            'name': cal.name,
            'type_key': cal.type_key,
            'provider': cal.provider,
            'calendar_external_id': cal.calendar_external_id,
            'is_active': cal.is_active,
            'priority': cal.priority,
            'default_duration_minutes': cal.default_duration_minutes,
            'buffer_before_minutes': cal.buffer_before_minutes,
            'buffer_after_minutes': cal.buffer_after_minutes,
            'allowed_tags': cal.allowed_tags or [],
            'created_at': cal.created_at.isoformat() if cal.created_at else None,
            'updated_at': cal.updated_at.isoformat() if cal.updated_at else None,
        } for cal in calendars]
        
        return jsonify({'calendars': result})
        
    except Exception as e:
        logger.error(f"Error fetching calendars: {e}")
        return jsonify({'error': 'שגיאה בטעינת לוחות שנה'}), 500

@calendar_bp.route('/calendars', methods=['POST'])
@require_api_auth(['system_admin', 'owner', 'admin'])
@require_page_access('calendar')
def create_calendar():
    """Create a new calendar for the business"""
    try:
        business_id = get_business_id()
        if not business_id:
            return jsonify({'error': 'Business ID required'}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body required'}), 400
        
        # Validate required fields
        if not data.get('name') or not data.get('name').strip():
            return jsonify({'error': 'שם לוח השנה נדרש'}), 400
        
        # Validate provider
        valid_providers = ['internal', 'google', 'outlook']
        provider = data.get('provider', 'internal')
        if provider not in valid_providers:
            return jsonify({'error': f'ספק לא חוקי. חייב להיות אחד מ: {", ".join(valid_providers)}'}), 400
        
        # Validate numeric fields
        default_duration = data.get('default_duration_minutes', 60)
        buffer_before = data.get('buffer_before_minutes', 0)
        buffer_after = data.get('buffer_after_minutes', 0)
        priority = data.get('priority', 0)
        
        try:
            default_duration = int(default_duration)
            buffer_before = int(buffer_before)
            buffer_after = int(buffer_after)
            priority = int(priority)
        except (ValueError, TypeError):
            return jsonify({'error': 'ערכים מספריים חייבים להיות מספרים שלמים'}), 400
        
        if default_duration <= 0:
            return jsonify({'error': 'משך זמן ברירת מחדל חייב להיות גדול מ-0'}), 400
        if buffer_before < 0 or buffer_after < 0:
            return jsonify({'error': 'זמני חיץ חייבים להיות לא שליליים'}), 400
        
        # Validate allowed_tags
        allowed_tags = data.get('allowed_tags', [])
        if not isinstance(allowed_tags, list):
            return jsonify({'error': 'allowed_tags חייב להיות מערך'}), 400
        if not all(isinstance(tag, str) for tag in allowed_tags):
            return jsonify({'error': 'כל התגיות ב-allowed_tags חייבות להיות מחרוזות'}), 400
        
        from server.models_sql import BusinessCalendar
        
        # Create new calendar
        calendar = BusinessCalendar(
            business_id=business_id,
            name=data['name'].strip(),
            type_key=data.get('type_key'),
            provider=provider,
            calendar_external_id=data.get('calendar_external_id'),
            is_active=data.get('is_active', True),
            priority=priority,
            default_duration_minutes=default_duration,
            buffer_before_minutes=buffer_before,
            buffer_after_minutes=buffer_after,
            allowed_tags=allowed_tags
        )
        
        db.session.add(calendar)
        db.session.commit()
        
        logger.info(f"✅ Created calendar '{calendar.name}' (id={calendar.id}) for business_id={business_id}")
        
        return jsonify({
            'success': True,
            'calendar': {
                'id': calendar.id,
                'name': calendar.name,
                'type_key': calendar.type_key,
                'provider': calendar.provider,
                'is_active': calendar.is_active,
                'priority': calendar.priority,
                'default_duration_minutes': calendar.default_duration_minutes,
                'buffer_before_minutes': calendar.buffer_before_minutes,
                'buffer_after_minutes': calendar.buffer_after_minutes,
                'allowed_tags': calendar.allowed_tags or []
            }
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating calendar: {e}")
        db.session.rollback()
        return jsonify({'error': 'שגיאה ביצירת לוח שנה'}), 500

@calendar_bp.route('/calendars/<int:calendar_id>', methods=['PUT'])
@require_api_auth(['system_admin', 'owner', 'admin'])
@require_page_access('calendar')
def update_calendar(calendar_id):
    """Update an existing calendar"""
    try:
        business_id = get_business_id()
        if not business_id:
            return jsonify({'error': 'Business ID required'}), 400
        
        from server.models_sql import BusinessCalendar
        
        # Find calendar and verify ownership
        calendar = BusinessCalendar.query.filter(
            BusinessCalendar.id == calendar_id,
            BusinessCalendar.business_id == business_id
        ).first()
        
        if not calendar:
            return jsonify({'error': 'לוח שנה לא נמצא'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body required'}), 400
        
        # Validate name if provided
        if 'name' in data:
            if not data['name'] or not data['name'].strip():
                return jsonify({'error': 'שם לוח השנה לא יכול להיות ריק'}), 400
            calendar.name = data['name'].strip()
        
        # Validate provider if provided
        if 'provider' in data:
            valid_providers = ['internal', 'google', 'outlook']
            if data['provider'] not in valid_providers:
                return jsonify({'error': f'ספק לא חוקי. חייב להיות אחד מ: {", ".join(valid_providers)}'}), 400
            calendar.provider = data['provider']
        
        # Validate numeric fields if provided
        if 'default_duration_minutes' in data:
            try:
                duration = int(data['default_duration_minutes'])
                if duration <= 0:
                    return jsonify({'error': 'משך זמן ברירת מחדל חייב להיות גדול מ-0'}), 400
                calendar.default_duration_minutes = duration
            except (ValueError, TypeError):
                return jsonify({'error': 'משך זמן חייב להיות מספר שלם'}), 400
        
        if 'buffer_before_minutes' in data:
            try:
                buffer_before = int(data['buffer_before_minutes'])
                if buffer_before < 0:
                    return jsonify({'error': 'זמן חיץ לפני חייב להיות לא שלילי'}), 400
                calendar.buffer_before_minutes = buffer_before
            except (ValueError, TypeError):
                return jsonify({'error': 'זמן חיץ חייב להיות מספר שלם'}), 400
        
        if 'buffer_after_minutes' in data:
            try:
                buffer_after = int(data['buffer_after_minutes'])
                if buffer_after < 0:
                    return jsonify({'error': 'זמן חיץ אחרי חייב להיות לא שלילי'}), 400
                calendar.buffer_after_minutes = buffer_after
            except (ValueError, TypeError):
                return jsonify({'error': 'זמן חיץ חייב להיות מספר שלם'}), 400
        
        if 'priority' in data:
            try:
                calendar.priority = int(data['priority'])
            except (ValueError, TypeError):
                return jsonify({'error': 'עדיפות חייבת להיות מספר שלם'}), 400
        
        # Validate allowed_tags if provided
        if 'allowed_tags' in data:
            if not isinstance(data['allowed_tags'], list):
                return jsonify({'error': 'allowed_tags חייב להיות מערך'}), 400
            if not all(isinstance(tag, str) for tag in data['allowed_tags']):
                return jsonify({'error': 'כל התגיות ב-allowed_tags חייבות להיות מחרוזות'}), 400
            calendar.allowed_tags = data['allowed_tags']
        
        # Update other fields
        if 'type_key' in data:
            calendar.type_key = data['type_key']
        if 'calendar_external_id' in data:
            calendar.calendar_external_id = data['calendar_external_id']
        if 'is_active' in data:
            calendar.is_active = data['is_active']
            calendar.buffer_before_minutes = data['buffer_before_minutes']
        if 'buffer_after_minutes' in data:
            calendar.buffer_after_minutes = data['buffer_after_minutes']
        if 'allowed_tags' in data:
            calendar.allowed_tags = data['allowed_tags']
        
        db.session.commit()
        
        logger.info(f"✅ Updated calendar id={calendar_id} for business_id={business_id}")
        
        return jsonify({
            'success': True,
            'calendar': {
                'id': calendar.id,
                'name': calendar.name,
                'type_key': calendar.type_key,
                'provider': calendar.provider,
                'is_active': calendar.is_active,
                'priority': calendar.priority,
                'default_duration_minutes': calendar.default_duration_minutes,
                'buffer_before_minutes': calendar.buffer_before_minutes,
                'buffer_after_minutes': calendar.buffer_after_minutes,
                'allowed_tags': calendar.allowed_tags or []
            }
        })
        
    except Exception as e:
        logger.error(f"Error updating calendar: {e}")
        db.session.rollback()
        return jsonify({'error': 'שגיאה בעדכון לוח שנה'}), 500

@calendar_bp.route('/calendars/<int:calendar_id>', methods=['DELETE'])
@require_api_auth(['system_admin', 'owner', 'admin'])
@require_page_access('calendar')
def delete_calendar(calendar_id):
    """Deactivate a calendar (soft delete)"""
    try:
        business_id = get_business_id()
        if not business_id:
            return jsonify({'error': 'Business ID required'}), 400
        
        from server.models_sql import BusinessCalendar
        
        # Find calendar and verify ownership
        calendar = BusinessCalendar.query.filter(
            BusinessCalendar.id == calendar_id,
            BusinessCalendar.business_id == business_id
        ).first()
        
        if not calendar:
            return jsonify({'error': 'לוח שנה לא נמצא'}), 404
        
        # Check if this is the last active calendar
        active_calendars_count = BusinessCalendar.query.filter(
            BusinessCalendar.business_id == business_id,
            BusinessCalendar.is_active == True
        ).count()
        
        if active_calendars_count <= 1:
            return jsonify({'error': 'לא ניתן להשבית את לוח השנה האחרון של העסק'}), 400
        
        # Soft delete - just deactivate
        calendar.is_active = False
        db.session.commit()
        
        logger.info(f"✅ Deactivated calendar id={calendar_id} for business_id={business_id}")
        
        return jsonify({
            'success': True,
            'message': 'לוח השנה הושבת בהצלחה'
        })
        
    except Exception as e:
        logger.error(f"Error deleting calendar: {e}")
        db.session.rollback()
        return jsonify({'error': 'שגיאה במחיקת לוח שנה'}), 500

# ================================================================================
# CALENDAR ROUTING RULES MANAGEMENT
# ================================================================================

@calendar_bp.route('/routing-rules', methods=['GET'])
@require_api_auth(['system_admin', 'owner', 'admin'])
@require_page_access('calendar')
def get_routing_rules():
    """Get all routing rules for the current user's business"""
    try:
        business_id = get_business_id()
        if not business_id:
            return jsonify({'error': 'Business ID required'}), 400
        
        from server.models_sql import CalendarRoutingRule
        
        rules = CalendarRoutingRule.query.filter(
            CalendarRoutingRule.business_id == business_id
        ).order_by(CalendarRoutingRule.priority.desc()).all()
        
        result = [{
            'id': rule.id,
            'business_id': rule.business_id,
            'calendar_id': rule.calendar_id,
            'match_labels': rule.match_labels or [],
            'match_keywords': rule.match_keywords or [],
            'channel_scope': rule.channel_scope,
            'when_ambiguous_ask': rule.when_ambiguous_ask,
            'question_text': rule.question_text,
            'priority': rule.priority,
            'is_active': rule.is_active,
            'created_at': rule.created_at.isoformat() if rule.created_at else None,
            'updated_at': rule.updated_at.isoformat() if rule.updated_at else None,
        } for rule in rules]
        
        return jsonify({'rules': result})
        
    except Exception as e:
        logger.error(f"Error fetching routing rules: {e}")
        return jsonify({'error': 'שגיאה בטעינת חוקי ניתוב'}), 500

@calendar_bp.route('/routing-rules', methods=['POST'])
@require_api_auth(['system_admin', 'owner', 'admin'])
@require_page_access('calendar')
def create_routing_rule():
    """Create a new routing rule"""
    try:
        business_id = get_business_id()
        if not business_id:
            return jsonify({'error': 'Business ID required'}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body required'}), 400
        
        # Validate required fields
        if not data.get('calendar_id'):
            return jsonify({'error': 'מזהה לוח שנה נדרש'}), 400
        
        from server.models_sql import CalendarRoutingRule, BusinessCalendar
        
        # Verify calendar belongs to this business
        calendar = BusinessCalendar.query.filter(
            BusinessCalendar.id == data['calendar_id'],
            BusinessCalendar.business_id == business_id
        ).first()
        
        if not calendar:
            return jsonify({'error': 'לוח שנה לא נמצא'}), 404
        
        # Validate match_labels
        match_labels = data.get('match_labels', [])
        if not isinstance(match_labels, list):
            return jsonify({'error': 'match_labels חייב להיות מערך'}), 400
        if not all(isinstance(label, str) for label in match_labels):
            return jsonify({'error': 'כל התוויות ב-match_labels חייבות להיות מחרוזות'}), 400
        
        # Validate match_keywords
        match_keywords = data.get('match_keywords', [])
        if not isinstance(match_keywords, list):
            return jsonify({'error': 'match_keywords חייב להיות מערך'}), 400
        if not all(isinstance(kw, str) for kw in match_keywords):
            return jsonify({'error': 'כל מילות המפתח ב-match_keywords חייבות להיות מחרוזות'}), 400
        
        # Validate channel_scope
        valid_scopes = ['all', 'calls', 'whatsapp']
        channel_scope = data.get('channel_scope', 'all')
        if channel_scope not in valid_scopes:
            return jsonify({'error': f'channel_scope חייב להיות אחד מ: {", ".join(valid_scopes)}'}), 400
        
        # Create new routing rule
        rule = CalendarRoutingRule(
            business_id=business_id,
            calendar_id=data['calendar_id'],
            match_labels=match_labels,
            match_keywords=match_keywords,
            channel_scope=channel_scope,
            when_ambiguous_ask=data.get('when_ambiguous_ask', False),
            question_text=data.get('question_text'),
            priority=data.get('priority', 0),
            is_active=data.get('is_active', True)
        )
        
        db.session.add(rule)
        db.session.commit()
        
        logger.info(f"✅ Created routing rule (id={rule.id}) for calendar_id={data['calendar_id']}")
        
        return jsonify({
            'success': True,
            'rule': {
                'id': rule.id,
                'calendar_id': rule.calendar_id,
                'match_labels': rule.match_labels or [],
                'match_keywords': rule.match_keywords or [],
                'channel_scope': rule.channel_scope,
                'when_ambiguous_ask': rule.when_ambiguous_ask,
                'question_text': rule.question_text,
                'priority': rule.priority,
                'is_active': rule.is_active
            }
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating routing rule: {e}")
        db.session.rollback()
        return jsonify({'error': 'שגיאה ביצירת חוק ניתוב'}), 500

@calendar_bp.route('/routing-rules/<int:rule_id>', methods=['PUT'])
@require_api_auth(['system_admin', 'owner', 'admin'])
@require_page_access('calendar')
def update_routing_rule(rule_id):
    """Update an existing routing rule"""
    try:
        business_id = get_business_id()
        if not business_id:
            return jsonify({'error': 'Business ID required'}), 400
        
        from server.models_sql import CalendarRoutingRule
        
        # Find rule and verify ownership
        rule = CalendarRoutingRule.query.filter(
            CalendarRoutingRule.id == rule_id,
            CalendarRoutingRule.business_id == business_id
        ).first()
        
        if not rule:
            return jsonify({'error': 'חוק ניתוב לא נמצא'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body required'}), 400
        
        # Update fields
        if 'calendar_id' in data:
            # Verify new calendar belongs to this business
            from server.models_sql import BusinessCalendar
            calendar = BusinessCalendar.query.filter(
                BusinessCalendar.id == data['calendar_id'],
                BusinessCalendar.business_id == business_id
            ).first()
            if not calendar:
                return jsonify({'error': 'לוח שנה לא נמצא'}), 404
            rule.calendar_id = data['calendar_id']
        
        if 'match_labels' in data:
            if not isinstance(data['match_labels'], list):
                return jsonify({'error': 'match_labels חייב להיות מערך'}), 400
            if not all(isinstance(label, str) for label in data['match_labels']):
                return jsonify({'error': 'כל התוויות ב-match_labels חייבות להיות מחרוזות'}), 400
            rule.match_labels = data['match_labels']
        
        if 'match_keywords' in data:
            if not isinstance(data['match_keywords'], list):
                return jsonify({'error': 'match_keywords חייב להיות מערך'}), 400
            if not all(isinstance(kw, str) for kw in data['match_keywords']):
                return jsonify({'error': 'כל מילות המפתח ב-match_keywords חייבות להיות מחרוזות'}), 400
            rule.match_keywords = data['match_keywords']
        
        if 'channel_scope' in data:
            valid_scopes = ['all', 'calls', 'whatsapp']
            if data['channel_scope'] not in valid_scopes:
                return jsonify({'error': f'channel_scope חייב להיות אחד מ: {", ".join(valid_scopes)}'}), 400
            rule.channel_scope = data['channel_scope']
        if 'when_ambiguous_ask' in data:
            rule.when_ambiguous_ask = data['when_ambiguous_ask']
        if 'question_text' in data:
            rule.question_text = data['question_text']
        if 'priority' in data:
            rule.priority = data['priority']
        if 'is_active' in data:
            rule.is_active = data['is_active']
        
        db.session.commit()
        
        logger.info(f"✅ Updated routing rule id={rule_id}")
        
        return jsonify({
            'success': True,
            'rule': {
                'id': rule.id,
                'calendar_id': rule.calendar_id,
                'match_labels': rule.match_labels or [],
                'match_keywords': rule.match_keywords or [],
                'channel_scope': rule.channel_scope,
                'when_ambiguous_ask': rule.when_ambiguous_ask,
                'question_text': rule.question_text,
                'priority': rule.priority,
                'is_active': rule.is_active
            }
        })
        
    except Exception as e:
        logger.error(f"Error updating routing rule: {e}")
        db.session.rollback()
        return jsonify({'error': 'שגיאה בעדכון חוק ניתוב'}), 500

@calendar_bp.route('/routing-rules/<int:rule_id>', methods=['DELETE'])
@require_api_auth(['system_admin', 'owner', 'admin'])
@require_page_access('calendar')
def delete_routing_rule(rule_id):
    """Delete a routing rule"""
    try:
        business_id = get_business_id()
        if not business_id:
            return jsonify({'error': 'Business ID required'}), 400
        
        from server.models_sql import CalendarRoutingRule
        
        # Find rule and verify ownership
        rule = CalendarRoutingRule.query.filter(
            CalendarRoutingRule.id == rule_id,
            CalendarRoutingRule.business_id == business_id
        ).first()
        
        if not rule:
            return jsonify({'error': 'חוק ניתוב לא נמצא'}), 404
        
        # Hard delete routing rules (they can be recreated)
        db.session.delete(rule)
        db.session.commit()
        
        logger.info(f"✅ Deleted routing rule id={rule_id}")
        
        return jsonify({
            'success': True,
            'message': 'חוק הניתוב נמחק בהצלחה'
        })
        
    except Exception as e:
        logger.error(f"Error deleting routing rule: {e}")
        db.session.rollback()
        return jsonify({'error': 'שגיאה במחיקת חוק ניתוב'}), 500