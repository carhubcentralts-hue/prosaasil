"""
Calendar API endpoints for appointments management
Handles all appointment CRUD operations with full security and role-based permissions
"""
from flask import Blueprint, request, jsonify, session, g
from datetime import datetime, timedelta
from server.models_sql import Appointment, Business, Customer, Deal, CallLog, WhatsAppMessage, User, db
from server.routes_admin import require_api_auth  # Standardized import per guidelines
from server.routes_crm import get_business_id
import json
from sqlalchemy import and_, or_, desc, asc
import pytz

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
    
    # Owner/Admin/Manager/Business/Agent filter by their business
    if user_role in ['owner', 'admin', 'manager', 'business', 'agent']:
        if business_id:
            return Appointment.business_id == business_id
        else:
            # Fallback to user's own business_id if available
            user_business = user_data.get('business_id')
            if user_business:
                return Appointment.business_id == user_business
    
    return None

@calendar_bp.route('/appointments', methods=['GET'])
@require_api_auth(['system_admin', 'owner', 'admin', 'manager', 'business', 'agent'])
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
                
                # ✅ BUILD 144: Include call summary from source call
                'call_summary': apt.call_summary,
                
                # Related data
                'business_name': None,
                'customer_name': None
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
        print(f"Error fetching appointments: {e}")
        return jsonify({'error': 'שגיאה בטעינת הפגישות'}), 500

@calendar_bp.route('/appointments', methods=['POST'])
@require_api_auth(['system_admin', 'owner', 'admin', 'manager', 'business', 'agent'])
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
            start_time = datetime.fromisoformat(data['start_time'].replace('Z', '+00:00'))
            end_time = datetime.fromisoformat(data['end_time'].replace('Z', '+00:00'))
            
            # 🔥 CRITICAL FIX: Remove timezone before saving to DB
            # DB columns are DateTime (not DateTimeTZ), so we save local Israel time without timezone
            # This prevents PostgreSQL from converting to UTC which causes 2-hour shift!
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
        appointment.call_log_id = data.get('call_log_id')
        appointment.whatsapp_message_id = data.get('whatsapp_message_id')
        appointment.title = data['title']
        appointment.description = data.get('description')
        appointment.start_time = start_time  # Now naive datetime (local Israel time)
        appointment.end_time = end_time      # Now naive datetime (local Israel time)
        appointment.location = data.get('location')
        appointment.status = data.get('status', 'scheduled')
        appointment.appointment_type = data.get('appointment_type', 'viewing')
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
        
        return jsonify({
            'success': True,
            'appointment_id': appointment.id,
            'message': 'הפגישה נוצרה בהצלחה'
        }), 201
        
    except Exception as e:
        db.session.rollback()
        print(f"Error creating appointment: {e}")
        return jsonify({'error': 'שגיאה ביצירת הפגישה'}), 500

@calendar_bp.route('/appointments/<int:appointment_id>', methods=['GET'])
@require_api_auth(['system_admin', 'owner', 'admin', 'manager', 'business', 'agent'])
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
            
            # Related data
            'business': {'id': business.id, 'name': business.name} if business else None,
            'customer': {'id': customer.id, 'name': customer.name, 'phone': customer.phone} if customer else None,
            'deal': {'id': deal.id, 'title': deal.title, 'stage': deal.stage, 'amount': deal.amount} if deal else None,
            'call_log': {'id': call_log.id, 'from_number': call_log.from_number, 'status': call_log.status} if call_log else None
        }
        
        return jsonify({'appointment': appointment_data})
        
    except Exception as e:
        print(f"Error fetching appointment {appointment_id}: {e}")
        return jsonify({'error': 'שגיאה בטעינת הפגישה'}), 500

@calendar_bp.route('/appointments/<int:appointment_id>', methods=['PUT'])
@require_api_auth(['system_admin', 'owner', 'admin', 'manager', 'business', 'agent'])
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
            'notes', 'outcome', 'follow_up_needed'
        ]
        
        for field in updatable_fields:
            if field in data:
                setattr(appointment, field, data[field])
        
        # Handle date fields
        if 'start_time' in data:
            try:
                start_time = datetime.fromisoformat(data['start_time'].replace('Z', '+00:00'))
                # 🔥 Remove timezone before saving to DB
                appointment.start_time = start_time.replace(tzinfo=None) if start_time.tzinfo else start_time
            except ValueError:
                return jsonify({'error': 'פורמט זמן התחלה לא תקין'}), 400
        
        if 'end_time' in data:
            try:
                end_time = datetime.fromisoformat(data['end_time'].replace('Z', '+00:00'))
                # 🔥 Remove timezone before saving to DB
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
        print(f"Error updating appointment {appointment_id}: {e}")
        return jsonify({'error': 'שגיאה בעדכון הפגישה'}), 500

@calendar_bp.route('/appointments/<int:appointment_id>', methods=['DELETE'])
@require_api_auth(['system_admin', 'owner', 'admin', 'manager', 'business', 'agent'])
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
        print(f"Error deleting appointment {appointment_id}: {e}")
        return jsonify({'error': 'שגיאה במחיקת הפגישה'}), 500

@calendar_bp.route('/stats', methods=['GET'])
@require_api_auth(['system_admin', 'owner', 'admin', 'manager', 'business', 'agent'])
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
        
        # Calculate stats
        stats = {
            'today': query.filter(
                db.func.date(Appointment.start_time) == today
            ).count(),
            
            'this_week': query.filter(
                db.func.date(Appointment.start_time) >= week_start
            ).count(),
            
            'this_month': query.filter(
                db.func.date(Appointment.start_time) >= month_start
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
        print(f"Error fetching calendar stats: {e}")
        return jsonify({'error': 'שגיאה בטעינת סטטיסטיקות'}), 500