from flask import Flask, request, jsonify, session, send_from_directory
from flask_cors import CORS
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime, timedelta
import logging

# יצירת אפליקציה
app = Flask(__name__, static_folder='../client/dist', static_url_path='/')

# הגדרות אפליקציה
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_KEY_PREFIX'] = 'agentlocator:'
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False  # True בפרודקשן עם HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True

# מסד נתונים
database_url = os.getenv('DATABASE_URL', 'sqlite:///agentlocator.db')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# אתחול הרחבות
CORS(app, supports_credentials=True, origins=["http://localhost:5173", "http://0.0.0.0:5173"])
Session(app)
db = SQLAlchemy(app)

# לוגים
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# מודלים
class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='business')  # 'admin' או 'business'
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # קשר לעסק
    business = db.relationship('Business', backref=db.backref('users', lazy=True))
    
    def __init__(self, email, role='business', business_id=None, is_active=True):
        self.email = email
        self.role = role
        self.business_id = business_id
        self.is_active = is_active
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'role': self.role,
            'business_id': self.business_id,
            'business': self.business.to_dict() if self.business else None,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }

class Business(db.Model):
    __tablename__ = 'businesses'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    hebrew_name = db.Column(db.String(200), nullable=False)
    business_type = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    whatsapp = db.Column(db.String(20))
    email = db.Column(db.String(120))
    address = db.Column(db.Text)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __init__(self, name, hebrew_name=None, business_type=None, phone=None, whatsapp=None, email=None, address=None, description=None, status='active'):
        self.name = name
        self.hebrew_name = hebrew_name
        self.business_type = business_type
        self.phone = phone
        self.whatsapp = whatsapp
        self.email = email
        self.address = address
        self.description = description
        self.status = status
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'hebrew_name': self.hebrew_name,
            'business_type': self.business_type,
            'phone': self.phone,
            'whatsapp': self.whatsapp,
            'email': self.email,
            'address': self.address,
            'description': self.description,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class CallLog(db.Model):
    __tablename__ = 'call_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id'), nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    direction = db.Column(db.String(10), nullable=False)  # 'incoming' או 'outgoing'
    duration = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='completed')
    recording_url = db.Column(db.String(500))
    transcription = db.Column(db.Text)
    summary = db.Column(db.Text)
    ai_response = db.Column(db.Text)
    customer_name = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # קשר לעסק
    business = db.relationship('Business', backref=db.backref('call_logs', lazy=True))
    
    def __init__(self, business_id, phone_number, direction, duration=0, status='completed', recording_url=None, transcription=None, summary=None, ai_response=None, customer_name=None):
        self.business_id = business_id
        self.phone_number = phone_number
        self.direction = direction
        self.duration = duration
        self.status = status
        self.recording_url = recording_url
        self.transcription = transcription
        self.summary = summary
        self.ai_response = ai_response
        self.customer_name = customer_name
    
    def to_dict(self):
        return {
            'id': self.id,
            'business_id': self.business_id,
            'business': self.business.to_dict() if self.business else None,
            'phone_number': self.phone_number,
            'direction': self.direction,
            'duration': self.duration,
            'status': self.status,
            'recording_url': self.recording_url,
            'transcription': self.transcription,
            'summary': self.summary,
            'ai_response': self.ai_response,
            'customer_name': self.customer_name,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Customer(db.Model):
    __tablename__ = 'customers'
    
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    whatsapp = db.Column(db.String(20))
    notes = db.Column(db.Text)
    status = db.Column(db.String(20), default='active')
    source = db.Column(db.String(50))  # 'call', 'whatsapp', 'manual'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # קשר לעסק
    business = db.relationship('Business', backref=db.backref('customers', lazy=True))
    
    def __init__(self, business_id, name, phone=None, email=None, whatsapp=None, notes=None, status='active', source=None):
        self.business_id = business_id
        self.name = name
        self.phone = phone
        self.email = email
        self.whatsapp = whatsapp
        self.notes = notes
        self.status = status
        self.source = source
    
    def to_dict(self):
        return {
            'id': self.id,
            'business_id': self.business_id,
            'business': self.business.to_dict() if self.business else None,
            'name': self.name,
            'phone': self.phone,
            'email': self.email,
            'whatsapp': self.whatsapp,
            'notes': self.notes,
            'status': self.status,
            'source': self.source,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

# מידלוור לבדיקת הרשאות
def require_auth():
    if 'user_id' not in session:
        return jsonify({'error': 'לא מחובר למערכת', 'code': 'UNAUTHORIZED'}), 401
    return None

def require_admin():
    auth_error = require_auth()
    if auth_error:
        return auth_error
    
    user = User.query.get(session['user_id'])
    if not user or user.role != 'admin':
        return jsonify({'error': 'נדרשות הרשאות מנהל', 'code': 'FORBIDDEN'}), 403
    return None

def get_current_user():
    if 'user_id' not in session:
        return None
    return User.query.get(session['user_id'])

# נתיבי API - Authentication
@app.route('/api/auth/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        if not data or 'email' not in data or 'password' not in data:
            return jsonify({'success': False, 'error': 'נתונים חסרים'}), 400
        
        email = data['email'].strip().lower()
        password = data['password']
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password) and user.is_active:
            # עדכון זמן התחברות אחרון
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            # שמירה בסשן
            session['user_id'] = user.id
            session['user_email'] = user.email
            session['user_role'] = user.role
            session['business_id'] = user.business_id
            
            logger.info(f"התחברות מוצלחת: {email}")
            
            return jsonify({
                'success': True,
                'user': user.to_dict()
            })
        else:
            logger.warning(f"התחברות נכשלה: {email}")
            return jsonify({'success': False, 'error': 'אימייל או סיסמה שגויים'}), 401
            
    except Exception as e:
        logger.error(f"שגיאה בהתחברות: {str(e)}")
        return jsonify({'success': False, 'error': 'שגיאה בשרת'}), 500

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    try:
        user_email = session.get('user_email', 'unknown')
        session.clear()
        logger.info(f"יציאה מוצלחת: {user_email}")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"שגיאה ביציאה: {str(e)}")
        return jsonify({'success': False, 'error': 'שגיאה בשרת'}), 500

@app.route('/api/auth/me', methods=['GET'])
def get_me():
    try:
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'לא מחובר'}), 401
        
        return jsonify(current_user.to_dict())
    except Exception as e:
        logger.error(f"שגיאה בקבלת פרטי משתמש: {str(e)}")
        return jsonify({'error': 'שגיאה בשרת'}), 500

# נתיבי API - CRM
@app.route('/api/crm/customers', methods=['GET'])
def get_customers():
    auth_error = require_auth()
    if auth_error:
        return auth_error
    
    try:
        current_user = get_current_user()
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 25, type=int)
        
        query = Customer.query
        
        # סינון לפי הרשאות
        if current_user and current_user.role != 'admin':
            query = query.filter_by(business_id=current_user.business_id)
        
        # Pagination
        customers = query.paginate(
            page=page, per_page=limit, error_out=False
        )
        
        return jsonify({
            'customers': [customer.to_dict() for customer in customers.items],
            'total': customers.total,
            'pages': customers.pages,
            'current_page': page,
            'per_page': limit
        })
        
    except Exception as e:
        logger.error(f"שגיאה בקבלת לקוחות: {str(e)}")
        return jsonify({'error': 'שגיאה בשרת'}), 500

# נתיבי API - Calls  
@app.route('/api/calls', methods=['GET'])
def get_calls():
    auth_error = require_auth()
    if auth_error:
        return auth_error
    
    try:
        current_user = get_current_user()
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 25, type=int)
        
        query = CallLog.query
        
        # סינון לפי הרשאות
        if current_user and current_user.role != 'admin':
            query = query.filter_by(business_id=current_user.business_id)
        
        # סדר לפי תאריך יצירה - החדשים ראשון
        query = query.order_by(CallLog.created_at.desc())
        
        # Pagination
        calls = query.paginate(
            page=page, per_page=limit, error_out=False
        )
        
        return jsonify({
            'calls': [call.to_dict() for call in calls.items],
            'total': calls.total,
            'pages': calls.pages,
            'current_page': page,
            'per_page': limit
        })
        
    except Exception as e:
        logger.error(f"שגיאה בקבלת שיחות: {str(e)}")
        return jsonify({'error': 'שגיאה בשרת'}), 500

# נתיבי API - Businesses (מנהלים בלבד)
@app.route('/api/admin/businesses', methods=['GET'])
def get_businesses():
    admin_error = require_admin()
    if admin_error:
        return admin_error
    
    try:
        businesses = Business.query.all()
        return jsonify({
            'businesses': [business.to_dict() for business in businesses]
        })
    except Exception as e:
        logger.error(f"שגיאה בקבלת עסקים: {str(e)}")
        return jsonify({'error': 'שגיאה בשרת'}), 500

# נתיב בריאות
@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        'ok': True,
        'service': 'AgentLocator API',
        'version': '1.0.0',
        'timestamp': datetime.utcnow().isoformat()
    })

# הגשת React App
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_spa(path):
    if app.static_folder and path and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    if app.static_folder:
        return send_from_directory(app.static_folder, 'index.html')
    return 'Static files not configured', 404

# יצירת הטבלאות ונתונים ראשוניים
def init_database():
    """יצירת הטבלאות ונתוני דמו"""
    try:
        db.create_all()
        
        # בדיקה אם יש כבר נתונים
        if User.query.first():
            logger.info("הנתונים כבר קיימים במסד הנתונים")
            return
        
        # יצירת עסק דמו
        business = Business(
            name='Shai Real Estate & Offices Ltd.',
            hebrew_name='שי דירות ומשרדים בע״מ',
            business_type='נדל"ן ותיווך',
            phone='+972-3-555-7777',
            whatsapp='+1-555-123-4567',
            email='info@shai-realestate.co.il',
            description='חברת תיווך נדל"ן מקצועית המתמחה בדירות ומשרדים',
            status='active'
        )
        db.session.add(business)
        db.session.flush()  # כדי לקבל ID
        
        # יצירת משתמש מנהל
        admin_user = User(
            email='admin@example.com',
            role='admin',
            is_active=True
        )
        admin_user.set_password('admin123')
        db.session.add(admin_user)
        
        # יצירת משתמש עסק
        business_user = User(
            email='shai@example.com',
            role='business',
            business_id=business.id,
            is_active=True
        )
        business_user.set_password('shai123')
        db.session.add(business_user)
        
        # יצירת נתוני דמו - לקוחות
        customers_data = [
            {'name': 'יוסי כהן', 'phone': '+972-50-123-4567', 'source': 'call'},
            {'name': 'רחל לוי', 'phone': '+972-54-987-6543', 'source': 'whatsapp'},
            {'name': 'דוד ישראל', 'phone': '+972-52-456-7890', 'source': 'manual'},
        ]
        
        for customer_data in customers_data:
            customer = Customer(
                business_id=business.id,
                name=customer_data['name'],
                phone=customer_data['phone'],
                source=customer_data['source'],
                status='active'
            )
            db.session.add(customer)
        
        # יצירת נתוני דמו - שיחות
        for i in range(5):
            call = CallLog(
                business_id=business.id,
                phone_number=f'+972-50-{1234567+i}',
                direction='incoming',
                duration=120 + i * 30,
                status='completed',
                transcription=f'תמלול שיחה מספר {i+1} - לקוח מעוניין בדירת 3 חדרים באזור המרכז',
                summary=f'סיכום שיחה {i+1}: פנייה לגבי דירה',
                customer_name=f'לקוח {i+1}'
            )
            db.session.add(call)
        
        db.session.commit()
        logger.info("נתוני הדמו נוצרו בהצלחה")
        logger.info("פרטי התחברות:")
        logger.info("מנהל: admin@example.com / admin123")
        logger.info("עסק: shai@example.com / shai123")
        
    except Exception as e:
        logger.error(f"שגיאה ביצירת מסד הנתונים: {str(e)}")
        db.session.rollback()

if __name__ == '__main__':
    init_database()
    port = int(os.getenv('PORT', 5000))
    debug_mode = os.getenv('FLASK_ENV') == 'development'
    
    logger.info(f"מפעיל שרת AgentLocator על פורט {port}")
    app.run(host='0.0.0.0', port=port, debug=debug_mode)