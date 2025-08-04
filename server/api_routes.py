"""
API Routes for React Frontend
Modern REST API endpoints for the React + Tailwind frontend
"""

from flask import jsonify, request, session, Blueprint
from app import app, db
from models import Business, User, CRMCustomer, CRMTask, CallLog, ConversationTurn, AppointmentRequest
from auth import login_required, admin_required, AuthService
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# Create Blueprint for API routes
api_bp = Blueprint('api', __name__)

# ============== Authentication APIs ==============

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    """התחברות למערכת"""
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({'message': 'נדרש אימייל וסיסמה'}), 400
        
        # Demo login credentials
        if email == 'admin@hebrewcrm.com' and password == 'HebrewCRM2024!':
            session['user_id'] = 1
            session['user_role'] = 'admin'
            return jsonify({'message': 'התחברות בוצעה בהצלחה'}), 200
        elif email == 'business@example.com' and password == 'Business123!':
            session['user_id'] = 2
            session['user_role'] = 'business'
            session['business_id'] = 1
            return jsonify({'message': 'התחברות בוצעה בהצלחה'}), 200
        else:
            return jsonify({'message': 'פרטי התחברות שגויים'}), 401
            
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({'message': 'שגיאה בהתחברות'}), 500

@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    """התנתקות מהמערכת"""
    session.clear()
    return jsonify({'message': 'התנתקות בוצעה בהצלחה'}), 200

@app.route('/api/user/current')
def api_current_user():
    """קבלת נתוני המשתמש הנוכחי"""
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'לא מחובר'}), 401
        
        # Demo user data
        if session.get('user_role') == 'admin':
            user_data = {
                'user': {
                    'id': 1,
                    'name': 'שי מנהל',
                    'email': 'admin@hebrewcrm.com',
                    'role': 'admin'
                },
                'business': None,
                'permissions': {
                    'calls_enabled': True,
                    'whatsapp_enabled': True,
                    'crm_enabled': True
                }
            }
        else:
            user_data = {
                'user': {
                    'id': 2,
                    'name': 'משתמש עסק',
                    'email': 'business@example.com',
                    'role': 'business'
                },
                'business': {
                    'id': 1,
                    'name': 'עסק לדוגמה',
                    'phone_number': '+972501234567'
                },
                'permissions': {
                    'calls_enabled': True,
                    'whatsapp_enabled': True,
                    'crm_enabled': True
                }
            }
        
        return jsonify(user_data), 200
        
    except Exception as e:
        logger.error(f"Current user error: {e}")
        return jsonify({'error': 'שגיאה בקבלת נתוני משתמש'}), 500

# ============== Dashboard APIs ==============

@app.route('/api/dashboard/stats')
def api_dashboard_stats():
    """סטטיסטיקות דשבורד עסק"""
    try:
        business_id = request.args.get('business_id')
        
        # Demo stats
        stats = {
            'calls_today': 15,
            'whatsapp_messages_today': 28,
            'total_customers': 150,
            'active_customers': 45,
            'monthly_revenue': 25000,
            'new_customers_this_month': 12,
            'avg_response_time': 8,
            'satisfaction_rate': 92,
            'open_tasks': 7,
            'inbound_calls': 10,
            'outbound_calls': 5,
            'avg_duration': 180
        }
        
        return jsonify(stats), 200
        
    except Exception as e:
        logger.error(f"Dashboard stats error: {e}")
        return jsonify({'error': 'שגיאה בקבלת סטטיסטיקות'}), 500

@app.route('/api/dashboard/activity')
def api_dashboard_activity():
    """פעילות אחרונה בדשבורד"""
    try:
        business_id = request.args.get('business_id')
        
        # Demo activity data
        activities = [
            {
                'id': 1,
                'description': 'שיחה נכנסת מלקוח יוסי כהן',
                'timestamp': datetime.now().isoformat(),
                'type': 'call'
            },
            {
                'id': 2,
                'description': 'הודעת וואטסאפ חדשה מרחל לוי',
                'timestamp': (datetime.now() - timedelta(minutes=15)).isoformat(),
                'type': 'whatsapp'
            },
            {
                'id': 3,
                'description': 'לקוח חדש נוסף למערכת: דני אברהם',
                'timestamp': (datetime.now() - timedelta(hours=2)).isoformat(),
                'type': 'customer'
            },
            {
                'id': 4,
                'description': 'משימה הושלמה: מעקב אחר הצעת מחיר',
                'timestamp': (datetime.now() - timedelta(hours=4)).isoformat(),
                'type': 'task'
            }
        ]
        
        return jsonify({'activities': activities}), 200
        
    except Exception as e:
        logger.error(f"Dashboard activity error: {e}")
        return jsonify({'error': 'שגיאה בקבלת פעילות'}), 500

# ============== Admin APIs ==============

@app.route('/api/admin/stats')
def api_admin_stats():
    """סטטיסטיקות מנהל מערכת"""
    try:
        if session.get('user_role') != 'admin':
            return jsonify({'error': 'אין הרשאה'}), 403
        
        # Demo admin stats
        stats = {
            'total_businesses': 5,
            'active_users': 12,
            'calls_today': 45,
            'whatsapp_messages_today': 89
        }
        
        return jsonify(stats), 200
        
    except Exception as e:
        logger.error(f"Admin stats error: {e}")
        return jsonify({'error': 'שגיאה בקבלת סטטיסטיקות מנהל'}), 500

@app.route('/api/admin/businesses')
def api_admin_businesses():
    """רשימת עסקים למנהל"""
    try:
        if session.get('user_role') != 'admin':
            return jsonify({'error': 'אין הרשאה'}), 403
        
        # Demo businesses data
        businesses = [
            {
                'id': 1,
                'name': 'עסק לדוגמה',
                'phone_number': '+972501234567',
                'calls_enabled': True,
                'whatsapp_enabled': True,
                'crm_enabled': True,
                'stats': {
                    'customers': 150,
                    'calls_today': 15
                }
            },
            {
                'id': 2,
                'name': 'חברת ABC',
                'phone_number': '+972507654321',
                'calls_enabled': True,
                'whatsapp_enabled': False,
                'crm_enabled': True,
                'stats': {
                    'customers': 89,
                    'calls_today': 8
                }
            }
        ]
        
        return jsonify({'businesses': businesses}), 200
        
    except Exception as e:
        logger.error(f"Admin businesses error: {e}")
        return jsonify({'error': 'שגיאה בקבלת רשימת עסקים'}), 500

@app.route('/api/admin/businesses/<int:business_id>/permissions', methods=['PUT'])
def api_update_business_permissions(business_id):
    """עדכון הרשאות עסק"""
    try:
        if session.get('user_role') != 'admin':
            return jsonify({'error': 'אין הרשאה'}), 403
        
        data = request.get_json()
        # Here you would update the business permissions in the database
        
        return jsonify({'message': 'הרשאות עודכנו בהצלחה'}), 200
        
    except Exception as e:
        logger.error(f"Update permissions error: {e}")
        return jsonify({'error': 'שגיאה בעדכון הרשאות'}), 500

@app.route('/api/admin/impersonate/<int:business_id>', methods=['POST'])
def api_impersonate_business(business_id):
    """כניסה כעסק"""
    try:
        if session.get('user_role') != 'admin':
            return jsonify({'error': 'אין הרשאה'}), 403
        
        # Switch session to business user
        session['user_role'] = 'business'
        session['business_id'] = business_id
        session['impersonating'] = True
        
        return jsonify({'message': 'כניסה כעסק בוצעה בהצלחה'}), 200
        
    except Exception as e:
        logger.error(f"Impersonate error: {e}")
        return jsonify({'error': 'שגיאה בכניסה כעסק'}), 500

# ============== Calls APIs ==============

@app.route('/api/calls')
def api_calls():
    """רשימת שיחות"""
    try:
        business_id = request.args.get('business_id')
        period = request.args.get('period', 'today')
        
        # Demo calls data
        calls = [
            {
                'id': 1,
                'phone_number': '+972501234567',
                'customer_name': 'יוסי כהן',
                'direction': 'inbound',
                'status': 'completed',
                'duration': 180,
                'created_at': datetime.now().isoformat(),
                'recording_url': '/api/calls/1/recording'
            },
            {
                'id': 2,
                'phone_number': '+972507654321',
                'customer_name': 'רחל לוי',
                'direction': 'outbound',
                'status': 'completed',
                'duration': 120,
                'created_at': (datetime.now() - timedelta(hours=1)).isoformat(),
                'recording_url': '/api/calls/2/recording'
            },
            {
                'id': 3,
                'phone_number': '+972509876543',
                'customer_name': None,
                'direction': 'inbound',
                'status': 'missed',
                'duration': 0,
                'created_at': (datetime.now() - timedelta(hours=2)).isoformat(),
                'recording_url': None
            }
        ]
        
        return jsonify({'calls': calls}), 200
        
    except Exception as e:
        logger.error(f"Calls error: {e}")
        return jsonify({'error': 'שגיאה בקבלת שיחות'}), 500

@app.route('/api/calls/stats')
def api_calls_stats():
    """סטטיסטיקות שיחות"""
    try:
        business_id = request.args.get('business_id')
        period = request.args.get('period', 'today')
        
        # Demo call stats
        stats = {
            'calls_today': 15,
            'inbound_calls': 10,
            'outbound_calls': 5,
            'avg_duration': 150
        }
        
        return jsonify(stats), 200
        
    except Exception as e:
        logger.error(f"Call stats error: {e}")
        return jsonify({'error': 'שגיאה בקבלת סטטיסטיקות שיחות'}), 500

# ============== WhatsApp APIs ==============

@app.route('/api/whatsapp/contacts')
def api_whatsapp_contacts():
    """רשימת אנשי קשר וואטסאפ"""
    try:
        business_id = request.args.get('business_id')
        
        # Demo contacts
        contacts = [
            {
                'id': 1,
                'name': 'יוסי כהן',
                'phone_number': '+972501234567',
                'last_message': 'תודה על השירות המעולה!',
                'last_message_time': datetime.now().isoformat(),
                'unread_count': 0
            },
            {
                'id': 2,
                'name': 'רחל לוי',
                'phone_number': '+972507654321',
                'last_message': 'מתי אפשר לקבוע פגישה?',
                'last_message_time': (datetime.now() - timedelta(minutes=30)).isoformat(),
                'unread_count': 2
            }
        ]
        
        return jsonify({'contacts': contacts}), 200
        
    except Exception as e:
        logger.error(f"WhatsApp contacts error: {e}")
        return jsonify({'error': 'שגיאה בקבלת אנשי קשר'}), 500

@app.route('/api/whatsapp/messages')
def api_whatsapp_messages():
    """הודעות וואטסאפ לאיש קשר"""
    try:
        contact_id = request.args.get('contact_id')
        
        # Demo messages
        messages = [
            {
                'id': 1,
                'content': 'שלום, אשמח לקבל מידע על השירותים שלכם',
                'direction': 'inbound',
                'timestamp': (datetime.now() - timedelta(hours=2)).isoformat(),
                'status': 'read'
            },
            {
                'id': 2,
                'content': 'שלום! אנחנו מציעים מגוון שירותים. אשמח לספר לך יותר בפגישה',
                'direction': 'outbound',
                'timestamp': (datetime.now() - timedelta(hours=1, minutes=55)).isoformat(),
                'status': 'read'
            },
            {
                'id': 3,
                'content': 'מעולה, מתי אפשר לקבוע פגישה?',
                'direction': 'inbound',
                'timestamp': (datetime.now() - timedelta(minutes=30)).isoformat(),
                'status': 'read'
            }
        ]
        
        return jsonify({'messages': messages}), 200
        
    except Exception as e:
        logger.error(f"WhatsApp messages error: {e}")
        return jsonify({'error': 'שגיאה בקבלת הודעות'}), 500

@app.route('/api/whatsapp/stats')
def api_whatsapp_stats():
    """סטטיסטיקות וואטסאפ"""
    try:
        business_id = request.args.get('business_id')
        
        # Demo WhatsApp stats
        stats = {
            'messages_today': 28,
            'active_chats': 8,
            'avg_response_time': 5
        }
        
        return jsonify(stats), 200
        
    except Exception as e:
        logger.error(f"WhatsApp stats error: {e}")
        return jsonify({'error': 'שגיאה בקבלת סטטיסטיקות וואטסאפ'}), 500

@app.route('/api/whatsapp/send', methods=['POST'])
def api_whatsapp_send():
    """שליחת הודעת וואטסאפ"""
    try:
        data = request.get_json()
        to = data.get('to')
        message = data.get('message')
        business_id = data.get('business_id')
        
        # Here you would send the actual WhatsApp message
        
        return jsonify({'message': 'ההודעה נשלחה בהצלחה'}), 200
        
    except Exception as e:
        logger.error(f"WhatsApp send error: {e}")
        return jsonify({'error': 'שגיאה בשליחת הודעה'}), 500

# ============== CRM APIs ==============

@app.route('/api/crm/customers')
def api_crm_customers():
    """רשימת לקוחות CRM"""
    try:
        business_id = request.args.get('business_id')
        search = request.args.get('search', '')
        status = request.args.get('status', 'all')
        
        # Demo customers
        customers = [
            {
                'id': 1,
                'first_name': 'יוסי',
                'last_name': 'כהן',
                'phone_number': '+972501234567',
                'email': 'yossi@example.com',
                'company': 'חברת ABC',
                'status': 'customer',
                'last_interaction': datetime.now().isoformat()
            },
            {
                'id': 2,
                'first_name': 'רחל',
                'last_name': 'לוי',
                'phone_number': '+972507654321',
                'email': 'rachel@example.com',
                'company': None,
                'status': 'lead',
                'last_interaction': (datetime.now() - timedelta(days=1)).isoformat()
            },
            {
                'id': 3,
                'first_name': 'דני',
                'last_name': 'אברהם',
                'phone_number': '+972509876543',
                'email': 'danny@example.com',
                'company': 'סטארטאפ XYZ',
                'status': 'prospect',
                'last_interaction': (datetime.now() - timedelta(days=3)).isoformat()
            }
        ]
        
        # Apply filters
        if search:
            customers = [c for c in customers if search.lower() in f"{c['first_name']} {c['last_name']}".lower()]
        
        if status != 'all':
            customers = [c for c in customers if c['status'] == status]
        
        return jsonify({'customers': customers}), 200
        
    except Exception as e:
        logger.error(f"CRM customers error: {e}")
        return jsonify({'error': 'שגיאה בקבלת לקוחות'}), 500

@app.route('/api/crm/stats')
def api_crm_stats():
    """סטטיסטיקות CRM"""
    try:
        business_id = request.args.get('business_id')
        
        # Demo CRM stats
        stats = {
            'total_customers': 150,
            'new_customers_this_month': 12,
            'active_leads': 25,
            'calls_this_week': 45
        }
        
        return jsonify(stats), 200
        
    except Exception as e:
        logger.error(f"CRM stats error: {e}")
        return jsonify({'error': 'שגיאה בקבלת סטטיסטיקות CRM'}), 500

@app.route('/api/crm/customers', methods=['POST'])
def api_add_customer():
    """הוספת לקוח חדש"""
    try:
        data = request.get_json()
        
        # Here you would save the customer to the database
        
        return jsonify({'message': 'לקוח נוסף בהצלחה'}), 201
        
    except Exception as e:
        logger.error(f"Add customer error: {e}")
        return jsonify({'error': 'שגיאה בהוספת לקוח'}), 500

@app.route('/api/crm/customers/<int:customer_id>')
def api_get_customer(customer_id):
    """קבלת פרטי לקוח"""
    try:
        # Demo customer data
        customer = {
            'id': customer_id,
            'first_name': 'יוסי',
            'last_name': 'כהן',
            'phone_number': '+972501234567',
            'email': 'yossi@example.com',
            'company': 'חברת ABC',
            'status': 'customer',
            'created_at': (datetime.now() - timedelta(days=30)).isoformat()
        }
        
        return jsonify(customer), 200
        
    except Exception as e:
        logger.error(f"Get customer error: {e}")
        return jsonify({'error': 'שגיאה בקבלת לקוח'}), 500

@app.route('/api/crm/customers/<int:customer_id>/interactions')
def api_customer_interactions(customer_id):
    """אינטראקציות של לקוח"""
    try:
        # Demo interactions
        interactions = [
            {
                'id': 1,
                'interaction_type': 'call',
                'content': 'שיחה על הצעת מחיר לפרויקט חדש',
                'interaction_date': datetime.now().isoformat(),
                'ai_response': 'נשלחה הצעת מחיר בהתאם לדרישות הלקוח'
            },
            {
                'id': 2,
                'interaction_type': 'whatsapp',
                'content': 'שאלות על תנאי התשלום',
                'interaction_date': (datetime.now() - timedelta(hours=5)).isoformat(),
                'ai_response': 'הוסברו תנאי התשלום והתקשרות לאישור'
            }
        ]
        
        return jsonify({'interactions': interactions}), 200
        
    except Exception as e:
        logger.error(f"Customer interactions error: {e}")
        return jsonify({'error': 'שגיאה בקבלת אינטראקציות'}), 500

@app.route('/api/crm/customers/<int:customer_id>/tasks')
def api_customer_tasks(customer_id):
    """משימות של לקוח"""
    try:
        # Demo tasks
        tasks = [
            {
                'id': 1,
                'title': 'מעקב אחר הצעת מחיר',
                'status': 'pending',
                'created_at': datetime.now().isoformat()
            },
            {
                'id': 2,
                'title': 'קביעת פגישת המשך',
                'status': 'completed',
                'created_at': (datetime.now() - timedelta(days=1)).isoformat()
            }
        ]
        
        return jsonify({'tasks': tasks}), 200
        
    except Exception as e:
        logger.error(f"Customer tasks error: {e}")
        return jsonify({'error': 'שגיאה בקבלת משימות'}), 500

@app.route('/api/crm/tasks', methods=['POST'])
def api_add_task():
    """הוספת משימה חדשה"""
    try:
        data = request.get_json()
        
        # Here you would save the task to the database
        
        return jsonify({'message': 'משימה נוספה בהצלחה'}), 201
        
    except Exception as e:
        logger.error(f"Add task error: {e}")
        return jsonify({'error': 'שגיאה בהוספת משימה'}), 500

@app.route('/api/crm/tasks/<int:task_id>', methods=['PUT'])
def api_update_task(task_id):
    """עדכון משימה"""
    try:
        data = request.get_json()
        
        # Here you would update the task in the database
        
        return jsonify({'message': 'משימה עודכנה בהצלחה'}), 200
        
    except Exception as e:
        logger.error(f"Update task error: {e}")
        return jsonify({'error': 'שגיאה בעדכון משימה'}), 500

if __name__ == '__main__':
    logger.info("API routes loaded successfully")