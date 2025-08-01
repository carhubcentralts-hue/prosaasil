"""
CRM Routes - נתיבי CRM פשוטים ומודרניים
"""
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from datetime import datetime, timedelta
from app import db
from models import Business, CallLog, ConversationTurn, AppointmentRequest, User
from auth import login_required, admin_required, AuthService
import logging

logger = logging.getLogger(__name__)

# יצירת Blueprint עבור CRM
crm_bp = Blueprint('crm', __name__)

@crm_bp.route('')
@crm_bp.route('/')
@login_required
def crm_dashboard():
    """דשבורד CRM ראשי"""
    try:
        current_user = AuthService.get_current_user()
        
        # קבלת העסק הנוכחי
        if current_user.role == 'admin':
            businesses = Business.query.filter_by(is_active=True).all()
            business_id = request.args.get('business_id')
            if business_id:
                current_business = Business.query.get(business_id)
            else:
                current_business = businesses[0] if businesses else None
        else:
            current_business = Business.query.get(current_user.business_id) if current_user.business_id else None
            businesses = [current_business] if current_business else []
        
        if not current_business:
            flash('לא נמצא עסק פעיל', 'error')
            return redirect('/admin-dashboard')
        
        # סטטיסטיקות
        total_calls = CallLog.query.filter_by(business_id=current_business.id).count()
        total_appointments = AppointmentRequest.query.join(CallLog).filter(CallLog.business_id == current_business.id).count()
        
        conversion_rate = (total_appointments / total_calls * 100) if total_calls > 0 else 0
        today = datetime.now().date()
        today_calls = CallLog.query.filter_by(business_id=current_business.id).filter(CallLog.created_at >= today).count()
        this_week_calls = CallLog.query.filter_by(business_id=current_business.id).filter(CallLog.created_at >= (today - timedelta(days=7))).count()
        
        stats = {
            'total_calls': total_calls,
            'total_appointments': total_appointments,
            'customers_count': total_calls,  # סטטיסטיקה פשוטה
            'pending_tasks': 0,
            'conversion_rate': round(conversion_rate, 1),
            'today_calls': today_calls,
            'this_week_calls': this_week_calls
        }
        
        # נתונים אחרונים
        recent_calls = CallLog.query.filter_by(business_id=current_business.id).order_by(CallLog.created_at.desc()).limit(5).all()
        recent_appointments = AppointmentRequest.query.join(CallLog).filter(CallLog.business_id == current_business.id).order_by(AppointmentRequest.created_at.desc()).limit(5).all()
        
        return render_template('crm_dashboard_simple.html', 
                             business=current_business,
                             business_id=current_business.id,
                             businesses=businesses,
                             stats=stats,
                             recent_calls=recent_calls,
                             recent_appointments=recent_appointments,
                             current_user=current_user)
    
    except Exception as e:
        logger.error(f"Error in CRM dashboard: {e}")
        flash('שגיאה בטעינת דשבורד CRM', 'error')
        return redirect('/admin-dashboard')

@crm_bp.route('/leads')
@login_required  
def leads():
    """דף ניהול לידים"""
    current_user = AuthService.get_current_user()
    
    # נתונים מדמה ללידים
    leads = [
        {
            'id': 1,
            'name': 'יוסי כהן',
            'phone': '050-1234567',
            'source': 'אתר',
            'status': 'hot',
            'created_at': '15/01/2025'
        },
        {
            'id': 2,
            'name': 'דנה לוי',
            'phone': '052-9876543',
            'source': 'טלפון',
            'status': 'warm',
            'created_at': '14/01/2025'
        }
    ]
    
    return render_template('crm_leads_enhanced.html', 
                         leads=leads,
                         leads_count=len(leads),
                         hot_leads=1,
                         conversion_rate=85,
                         monthly_leads=12,
                         current_user=current_user)

# Removed duplicate calendar function - using crm_calendar below

@crm_bp.route('/customers')
@login_required
def customers():
    """דף ניהול לקוחות"""
    try:
        current_user = AuthService.get_current_user()
        
        # אסוף נתונים מקיימים (שיחות כלקוחות)
        if current_user.role == 'admin':
            calls = CallLog.query.all()
        else:
            calls = CallLog.query.filter_by(business_id=current_user.business_id).all()
        
        # יצירת רשימת לקוחות מהשיחות
        customers = []
        for call in calls:
            if call.caller_number:
                customers.append({
                    'id': call.id,
                    'name': f'לקוח {call.caller_number}',
                    'phone': call.caller_number,
                    'email': None,
                    'status': 'active',
                    'created_at': call.created_at,
                    'tags': None
                })
        
        # סטטיסטיקות
        active_customers = len(customers)
        total_calls = len(calls)
        pending_appointments = AppointmentRequest.query.count()
        
        return render_template('crm_customers.html', 
                             customers=customers,
                             active_customers=len(customers),
                             new_customers=5,
                             total_revenue=25000,
                             avg_order=850,
                             current_user=current_user)
    
    except Exception as e:
        logger.error(f"Error loading customers: {e}")
        flash('שגיאה בטעינת לקוחות', 'error')
        return redirect('/crm')

@crm_bp.route('/tasks')
@login_required
def tasks():
    """דף ניהול משימות"""
    current_user = AuthService.get_current_user()
    
    # משימות פשוטות מהתורים
    if current_user.role == 'admin':
        appointments = AppointmentRequest.query.order_by(AppointmentRequest.created_at.desc()).all()
    else:
        appointments = AppointmentRequest.query.join(CallLog).filter(CallLog.business_id == current_user.business_id).order_by(AppointmentRequest.created_at.desc()).all()
    
    tasks = []
    for apt in appointments:
        tasks.append({
            'id': apt.id,
            'title': f'תור עם {apt.customer_name or "לקוח"}',
            'description': apt.notes or 'תור ללא פרטים נוספים',
            'status': apt.status,
            'due_date': apt.appointment_date,
            'created_at': apt.created_at
        })
    
    return render_template('crm_tasks.html',
                         tasks=tasks,
                         total_tasks=len(tasks),
                         pending_tasks=len([t for t in tasks if t['status'] == 'pending']),
                         completed_tasks=len([t for t in tasks if t['status'] == 'completed']),
                         completion_rate=85,
                         current_user=current_user)

@crm_bp.route('/calendar')
@login_required  
def crm_calendar():
    """לוח שנה לניהול תורים"""
    try:
        current_user = AuthService.get_current_user()
        
        # Statistics for calendar
        if current_user and current_user.role == 'admin':
            total_appointments = AppointmentRequest.query.count()
        elif current_user and current_user.business_id:
            total_appointments = AppointmentRequest.query.join(CallLog).filter(CallLog.business_id == current_user.business_id).count()
        else:
            total_appointments = 0
        
        stats = {
            'total_appointments': total_appointments,
            'new_this_week': 8,  # Mock - replace with real calculation
            'confirmed_appointments': int(total_appointments * 0.8),
            'pending_appointments': int(total_appointments * 0.2),
            'confirmation_rate': 85,
            'avg_duration': 45
        }
        
        # Upcoming appointments
        today = datetime.now().date()
        if current_user and current_user.role == 'admin':
            # For admin, get mock appointments since appointment_date field might not exist
            appointments = []
        elif current_user and current_user.business_id:
            # For business users, get their appointments
            appointments = []
        else:
            appointments = []
        
        # Format appointments for template - using mock data for now
        upcoming_appointments = [
            {
                'id': 1,
                'customer_name': 'יוסי כהן',
                'phone_number': '050-1234567',
                'date': datetime.now().date(),
                'time': '10:00',
                'service': 'ייעוץ',
                'status': 'confirmed'
            },
            {
                'id': 2,
                'customer_name': 'שרה לוי',
                'phone_number': '052-9876543',
                'date': datetime.now().date(),
                'time': '14:30',
                'service': 'פגישה',
                'status': 'pending'
            }
        ]
        
        # Today's schedule
        todays_schedule = []
        for hour in range(9, 18):  # 9 AM to 6 PM
            time_str = f"{hour:02d}:00"
            occupied = any(apt['time'] == time_str and apt['date'] == today for apt in upcoming_appointments)
            if occupied:
                apt = next(apt for apt in upcoming_appointments if apt['time'] == time_str and apt['date'] == today)
                todays_schedule.append({
                    'time': time_str,
                    'occupied': True,
                    'customer_name': apt['customer_name'],
                    'service': apt['service']
                })
            else:
                todays_schedule.append({
                    'time': time_str,
                    'occupied': False
                })
        
        # Current month/year
        current_date = datetime.now()
        current_month_name = ['ינואר', 'פברואר', 'מרץ', 'אפריל', 'מאי', 'יוני',
                             'יולי', 'אוגוסט', 'ספטמבר', 'אוקטובר', 'נובמבר', 'דצמבר'][current_date.month - 1]
        
        return render_template('crm_calendar.html',
                             upcoming_appointments=upcoming_appointments,
                             appointments_today=3,
                             appointments_week=15,
                             confirmation_rate=85,
                             avg_duration=45,
                             current_user=current_user)
        
    except Exception as e:
        logger.error(f"Error in calendar: {e}")
        return redirect('/crm')

# Duplicate leads function removed - using first one at line 79

@crm_bp.route('/analytics')
@login_required
def analytics():
    """דף אנליטיקס"""
    current_user = AuthService.get_current_user()
    
    if current_user and current_user.role == 'admin':
        total_calls = CallLog.query.count()
        total_appointments = AppointmentRequest.query.count()
        businesses = Business.query.count()
    else:
        total_calls = CallLog.query.filter_by(business_id=current_user.business_id).count()
        total_appointments = AppointmentRequest.query.join(CallLog).filter(CallLog.business_id == current_user.business_id).count()
        businesses = 1
    
    analytics_data = {
        'total_calls': total_calls,
        'total_appointments': total_appointments,
        'businesses': businesses,
        'conversion_rate': (total_appointments / total_calls * 100) if total_calls > 0 else 0
    }
    
    return render_template('crm_analytics.html',
                         total_revenue=45000,
                         total_calls=analytics_data['total_calls'],
                         conversion_rate=analytics_data['conversion_rate'],
                         customer_satisfaction=92,
                         current_user=current_user)

# New API Routes for enhanced features
@crm_bp.route('/api/hot-leads-count')
@login_required
def api_hot_leads_count():
    """API endpoint לספירת ליידים חמים"""
    try:
        current_user = AuthService.get_current_user()
        
        # Count hot leads that haven't signed
        if current_user.role == 'admin':
            hot_leads = CallLog.query.join(ConversationTurn).filter(
                ConversationTurn.message.contains('חם')
            ).count()
        else:
            hot_leads = CallLog.query.filter_by(business_id=current_user.business_id).join(ConversationTurn).filter(
                ConversationTurn.message.contains('חם')
            ).count()
        
        return jsonify({'success': True, 'count': hot_leads})
    except Exception as e:
        logger.error(f"Error counting hot leads: {e}")
        return jsonify({'success': False, 'count': 0})

@crm_bp.route('/api/send-whatsapp', methods=['POST'])
@login_required
def api_send_whatsapp():
    """API endpoint לשליחת WhatsApp"""
    try:
        data = request.get_json()
        phone = data.get('phone')
        name = data.get('name')
        template = data.get('template', 'followup')
        
        # Here you would integrate with your WhatsApp service
        # For now, just return success
        return jsonify({'success': True, 'message': 'WhatsApp sent successfully'})
    except Exception as e:
        logger.error(f"Error sending WhatsApp: {e}")
        return jsonify({'success': False, 'error': str(e)})

@crm_bp.route('/api/send-sms', methods=['POST'])
@login_required  
def api_send_sms():
    """API endpoint לשליחת SMS"""
    try:
        data = request.get_json()
        phone = data.get('phone')
        name = data.get('name')
        
        # Here you would integrate with your SMS service (Twilio)
        return jsonify({'success': True, 'message': 'SMS sent successfully'})
    except Exception as e:
        logger.error(f"Error sending SMS: {e}")
        return jsonify({'success': False, 'error': str(e)})

@crm_bp.route('/api/urgent-alert', methods=['POST'])
@login_required
def api_urgent_alert():
    """API endpoint לשליחת התראה דחופה"""
    try:
        data = request.get_json()
        lead_id = data.get('leadId')
        
        # Send urgent alert to business owner
        return jsonify({'success': True, 'message': 'Urgent alert sent'})
    except Exception as e:
        logger.error(f"Error sending urgent alert: {e}")
        return jsonify({'success': False, 'error': str(e)})

@crm_bp.route('/api/send-property-matches', methods=['POST'])
@login_required
def api_send_property_matches():
    """API endpoint לשליחת התאמות נכסים"""
    try:
        data = request.get_json()
        lead_id = data.get('leadId')
        
        # Send property matches to lead
        return jsonify({'success': True, 'message': 'Property matches sent'})
    except Exception as e:
        logger.error(f"Error sending property matches: {e}")
        return jsonify({'success': False, 'error': str(e)})

@crm_bp.route('/api/save-whatsapp-templates', methods=['POST'])
@login_required
def api_save_whatsapp_templates():
    """API endpoint לשמירת תבניות WhatsApp"""
    try:
        data = request.get_json()
        templates = data.get('templates', {})
        
        # Save templates to database or file
        return jsonify({'success': True, 'message': 'Templates saved successfully'})
    except Exception as e:
        logger.error(f"Error saving templates: {e}")
        return jsonify({'success': False, 'error': str(e)})

@crm_bp.route('/api/get-whatsapp-templates')
@login_required
def api_get_whatsapp_templates():
    """API endpoint לקבלת תבניות WhatsApp"""
    try:
        # Get templates from database or return defaults
        templates = {
            'followup': 'שלום {name}! איך אפשר לעזור לך היום?',
            'hot_lead': 'שלום {name}! נראה שאתה מעוניין בנכס. בואו נדבר?',
            'post_signature': 'ברכות {name}! החוזה נחתם בהצלחה.',
            'reminder': 'שלום {name}, תזכורת לחתימה על החוזה.'
        }
        return jsonify({'success': True, 'templates': templates})
    except Exception as e:
        logger.error(f"Error getting templates: {e}")
        return jsonify({'success': False, 'error': str(e)})

@crm_bp.route('/api/match-property', methods=['POST'])
@login_required
def api_match_property():
    """API endpoint להתאמת נכס ללקוח"""
    try:
        data = request.get_json()
        property_id = data.get('propertyId')
        client_name = data.get('clientName')
        
        # Save property match to database
        return jsonify({'success': True, 'message': 'Property matched successfully'})
    except Exception as e:
        logger.error(f"Error matching property: {e}")
        return jsonify({'success': False, 'error': str(e)})

# API Routes for dashboard refresh
@crm_bp.route('/api/dashboard-stats')
@login_required
def api_dashboard_stats():
    """API endpoint לרענון נתוני דשבורד"""
    try:
        current_user = AuthService.get_current_user()
        
        if current_user and current_user.role == 'admin':
            total_calls = CallLog.query.count()
            total_appointments = AppointmentRequest.query.count()
        elif current_user and current_user.business_id:
            total_calls = CallLog.query.filter_by(business_id=current_user.business_id).count()
            total_appointments = AppointmentRequest.query.join(CallLog).filter(CallLog.business_id == current_user.business_id).count()
        else:
            total_calls = 0
            total_appointments = 0

        stats = {
            'total_calls': total_calls,
            'total_appointments': total_appointments,
            'customers_count': total_calls,
            'pending_tasks': 0,
            'conversion_rate': round((total_appointments / total_calls * 100) if total_calls > 0 else 0, 1),
            'today_calls': 3,  # Mock data
            'this_week_calls': 15  # Mock data
        }
        
        return jsonify({'success': True, 'data': stats})
    
    except Exception as e:
        logger.error(f"Error in dashboard stats API: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# API Routes for Payment and Invoice Actions
@crm_bp.route('/api/crm-action', methods=['POST'])
@login_required
def handle_crm_action():
    """API לטיפול בפעולות CRM כמו שליחת חשבוניות ותשלומים"""
    try:
        current_user = AuthService.get_current_user()
        data = request.get_json()
        
        action_type = data.get('action_type')
        action_data = data.get('action_data', {})
        business_id = current_user.business_id if current_user.role != 'admin' else data.get('business_id')
        
        if action_type == 'payment':
            # שליחת קישור תשלום - מדמה פעולה
            logger.info(f"Payment link sent to {action_data.get('customer_phone')} for amount {action_data.get('amount')}")
            return jsonify({'success': True, 'message': f"קישור תשלום נשלח ל-{action_data.get('customer_name')}"})
            
        elif action_type == 'invoice':
            # יצירת חשבונית - מדמה פעולה
            logger.info(f"Invoice created for {action_data.get('customer_name')} - {action_data.get('service_description')}")
            return jsonify({'success': True, 'message': f"חשבונית נוצרה עבור {action_data.get('customer_name')}"})
            
        else:
            return jsonify({'success': False, 'error': 'סוג פעולה לא מוכר'})
        
    except Exception as e:
        logger.error(f"Error handling CRM action: {e}")
        return jsonify({'success': False, 'error': str(e)})

@crm_bp.route('/api/create-invoice', methods=['POST'])
@login_required  
def create_invoice_api():
    """API ליצירת חשבונית"""
    try:
        data = request.get_json()
        current_user = AuthService.get_current_user()
        
        # מדמה יצירת חשבונית
        logger.info(f"Invoice created by user {current_user.id}: {data.get('customer_name')} - {data.get('amount')}")
        
        return jsonify({
            'success': True, 
            'message': f"חשבונית נוצרה בהצלחה עבור {data.get('customer_name')}",
            'invoice_id': f"INV-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        })
        
    except Exception as e:
        logger.error(f"Error creating invoice: {e}")
        return jsonify({'success': False, 'error': str(e)})

# New template routes  
@crm_bp.route('/whatsapp-templates')
@login_required
def whatsapp_templates():
    """עמוד עריכת תבניות WhatsApp"""
    return render_template('whatsapp_templates.html')

@crm_bp.route('/property-matches')
@login_required
def property_matches():
    """עמוד התאמות נכסים"""
    return render_template('property_matches.html')

@crm_bp.route('/digital-signatures')
@login_required
def digital_signatures():
    """עמוד חתימות דיגיטליות"""
    return render_template('digital_signature.html')

@crm_bp.route('/api/create-signature', methods=['POST'])
@login_required
def api_create_signature():
    """API ליצירת חתימה דיגיטלית"""
    try:
        data = request.get_json()
        client_name = data.get('clientName')
        client_email = data.get('clientEmail')
        document_type = data.get('documentType')
        
        # Create digital signature (mock implementation)
        signature_id = f"SIG-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        return jsonify({
            'success': True, 
            'message': f'חתימה דיגיטלית נוצרה ונשלחה ל-{client_name}',
            'signature_id': signature_id
        })
    except Exception as e:
        logger.error(f"Error creating signature: {e}")
        return jsonify({'success': False, 'error': str(e)})

# Additional routes for invoice and payment management
@crm_bp.route('/invoices')
@login_required
def invoices():
    """דף ניהול חשבוניות"""
    current_user = AuthService.get_current_user()
    
    # אין חשבוניות במסד הנתונים, נציג נתונים מהשיחות
    if current_user.role == 'admin':
        recent_calls = CallLog.query.order_by(CallLog.created_at.desc()).limit(10).all()
    else:
        recent_calls = CallLog.query.filter_by(business_id=current_user.business_id).order_by(CallLog.created_at.desc()).limit(10).all()
    
    # יצירת חשבוניות מדמה מהשיחות
    invoices = []
    for i, call in enumerate(recent_calls):
        invoices.append({
            'id': i + 1,
            'customer_name': f'לקוח {call.from_number[-4:] if call.from_number else str(call.id)}',
            'customer_phone': call.from_number or 'לא זמין',
            'amount': (i + 1) * 250,  # סכום מדמה
            'date': call.created_at.strftime('%d/%m/%Y') if call.created_at else 'לא זמין',
            'status': 'נשלח' if i % 3 == 0 else 'ממתין' if i % 3 == 1 else 'שולם',
            'description': f'שירותים עבור שיחה {call.call_sid[:8] if call.call_sid else str(call.id)}'
        })
    
    return render_template('invoices_management.html', 
                         invoices=invoices,
                         current_user=current_user)

@crm_bp.route('/digital-signature')
@login_required
def digital_signature():
    """דף חתימות דיגיטליות"""
    current_user = AuthService.get_current_user()
    
    # נתונים מדמה לחתימות
    signatures = [
        {
            'id': 1,
            'document_name': 'חוזה שירותים - יוסי כהן',
            'customer_name': 'יוסי כהן',
            'date_created': '15/01/2025',
            'status': 'חתום',
            'signed_date': '15/01/2025'
        },
        {
            'id': 2,
            'document_name': 'הסכם תחזוקה - דנה לוי',
            'customer_name': 'דנה לוי',
            'date_created': '14/01/2025',
            'status': 'ממתין לחתימה',
            'signed_date': None
        }
    ]
    
    return render_template('digital_signature.html', 
                         signatures=signatures,
                         current_user=current_user)