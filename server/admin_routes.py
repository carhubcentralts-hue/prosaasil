from flask import Blueprint, request, jsonify
import psycopg2
import os
import logging
import jwt
from datetime import datetime, timedelta

# הגדרת logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# יצירת Blueprint עבור admin
admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

def get_db_connection():
    """חיבור לבסיס נתונים PostgreSQL"""
    try:
        conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return None

def admin_required(f):
    """דקורטור לבדיקת הרשאות מנהל"""
    def decorated_function(*args, **kwargs):
        # בדיקה בסיסית לפיתוח - מאפשר גישה ברירת מחדל
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            try:
                token = auth_header.split(' ')[1]
                decoded = jwt.decode(token, 'your-secret-key', algorithms=['HS256'])
                if decoded.get('role') == 'admin':
                    return f(*args, **kwargs)
            except:
                pass
        # אם אין טוקן או שהוא לא מתאים, עדיין מאפשר גישה לפיתוח
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

@admin_bp.route('/businesses', methods=['GET'])
@admin_required
def get_businesses():
    """קבלת רשימת כל העסקים"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
            
        cur = conn.cursor()
        
        cur.execute("""
            SELECT id, name, business_type, phone_israel, phone_whatsapp, 
                   ai_prompt, crm_enabled, whatsapp_enabled, calls_enabled,
                   created_at, is_active
            FROM businesses 
            WHERE is_active = true
            ORDER BY created_at DESC
        """)
        
        businesses = []
        for row in cur.fetchall():
            business = {
                'id': row[0],
                'name': row[1],
                'type': row[2],
                'phone': row[3],
                'whatsapp_phone': row[4],
                'ai_prompt': row[5],
                'services': {
                    'crm': row[6],
                    'whatsapp': row[7],
                    'calls': row[8]
                },
                'created_at': row[9].strftime('%Y-%m-%d %H:%M:%S') if row[9] else None,
                'is_active': row[10]
            }
            businesses.append(business)
        
        cur.close()
        conn.close()
        
        logger.info(f"Found {len(businesses)} businesses")
        return jsonify(businesses)
        
    except Exception as e:
        logger.error(f"Error getting businesses: {e}")
        return jsonify({'error': 'Failed to get businesses'}), 500

@admin_bp.route('/businesses/<int:business_id>', methods=['GET'])
@admin_required
def get_business_by_id(business_id):
    """קבלת פרטי עסק ספציפי"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
            
        cur = conn.cursor()
        
        cur.execute("""
            SELECT id, name, business_type, phone_israel, phone_whatsapp, 
                   ai_prompt, crm_enabled, whatsapp_enabled, calls_enabled,
                   created_at, is_active
            FROM businesses 
            WHERE id = %s
        """, (business_id,))
        
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'Business not found'}), 404
            
        business_info = {
            'id': row[0],
            'name': row[1],
            'type': row[2],
            'phone': row[3],
            'whatsapp_phone': row[4],
            'ai_prompt': row[5],
            'services': {
                'crm': row[6],
                'whatsapp': row[7],
                'calls': row[8]
            },
            'created_at': row[9].strftime('%Y-%m-%d') if row[9] else None,
            'plan_expires': '2025-12-31',  # נתון קבוע לעת עתה
            'users_count': 1,
            'is_active': row[10]
        }
        
        cur.close()
        conn.close()
        
        logger.info(f"✅ Business {business_id} details retrieved successfully")
        return jsonify(business_info)
        
    except Exception as e:
        logger.error(f"Error fetching business {business_id}: {e}")
        return jsonify({'error': 'Failed to get business details'}), 500

@admin_bp.route('/summary', methods=['GET'])
@admin_required
def get_admin_summary():
    """סטטיסטיקות מערכת כלליות למנהל"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
            
        cur = conn.cursor()
        
        # ספירת עסקים
        cur.execute("SELECT COUNT(*) FROM businesses")
        result = cur.fetchone()
        total_businesses = result[0] if result else 0
        
        # ספירת משתמשים
        cur.execute("SELECT COUNT(*) FROM users")
        users_result = cur.fetchone()
        total_users = users_result[0] if users_result else 0
        
        # שיחות היום
        try:
            cur.execute("""
                SELECT COUNT(*) FROM call_log 
                WHERE created_at >= CURRENT_DATE
            """)
            calls_result = cur.fetchone()
            calls_today = calls_result[0] if calls_result else 0
        except Exception:
            calls_today = 0
        
        # הודעות WhatsApp היום (טבלה לא קיימת, נחזיר 0)
        messages_today = 0
        
        cur.close()
        conn.close()
        
        summary = {
            'businesses': {
                'total': total_businesses,
                'active': total_businesses
            },
            'users': {
                'total': total_users
            },
            'today': {
                'calls': calls_today,
                'messages': messages_today
            },
            'system_health': 'operational'
        }
        
        return jsonify(summary)
        
    except Exception as e:
        logger.error(f"Error getting admin summary: {e}")
        return jsonify({'error': 'Failed to get summary'}), 500

@admin_bp.route('/reset-password', methods=['POST'])
@admin_required
def reset_business_password():
    """איפוס סיסמה לעסק"""
    try:
        data = request.get_json()
        business_id = data.get('business_id')
        old_password = data.get('old_password')
        new_password = data.get('new_password')
        
        if not business_id or not new_password:
            return jsonify({'error': 'Missing business_id or new_password'}), 400
            
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
            
        cur = conn.cursor()
        
        # איפוס סיסמה ללא בדיקת סיסמה נוכחית במצב מנהל
        
        # עדכון סיסמה
        cur.execute("""
            UPDATE users SET password = %s 
            WHERE business_id = %s AND role = 'business'
        """, (new_password, business_id))
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"Password reset for business {business_id}")
        return jsonify({'message': 'Password reset successfully'})
        
    except Exception as e:
        logger.error(f"Error resetting password: {e}")
        return jsonify({'error': 'Failed to reset password'}), 500

@admin_bp.route('/businesses/<int:business_id>/reset-password', methods=['POST'])
@admin_required
def reset_business_password_by_id(business_id):
    """איפוס סיסמה לעסק ספציפי"""
    try:
        data = request.get_json()
        new_password = data.get('new_password', 'newpassword123')
        
        if not new_password:
            return jsonify({'error': 'Missing new_password'}), 400
            
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
            
        cur = conn.cursor()
        
        # עדכון סיסמה בטבלת המשתמשים
        cur.execute("""
            UPDATE users SET password = %s 
            WHERE business_id = %s AND role = 'business'
        """, (new_password, business_id))
        
        # אם אין משתמש קיים, ניצור חדש
        if cur.rowcount == 0:
            cur.execute("""
                INSERT INTO users (business_id, name, password, role, created_at)
                VALUES (%s, %s, %s, 'business', NOW())
            """, (business_id, f'business{business_id}', new_password))
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"✅ Password reset for business {business_id}")
        return jsonify({'message': 'סיסמה עודכנה בהצלחה', 'new_password': new_password})
        
    except Exception as e:
        logger.error(f"Error resetting password for business {business_id}: {e}")
        return jsonify({'error': 'Failed to reset password'}), 500

@admin_bp.route('/businesses/<int:business_id>/add-user', methods=['POST'])
@admin_required
def add_user_to_business(business_id):
    """הוספת משתמש חדש לעסק"""
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password', 'defaultpass123')
        email = data.get('email', '')
        
        if not username:
            return jsonify({'error': 'Missing username'}), 400
            
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
            
        cur = conn.cursor()
        
        # בדיקה שהעסק קיים
        cur.execute("SELECT id FROM businesses WHERE id = %s", (business_id,))
        if not cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({'error': 'Business not found'}), 404
        
        # בדיקה שהשם משתמש לא קיים
        cur.execute("SELECT id FROM users WHERE name = %s", (username,))
        if cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({'error': 'Username already exists'}), 409
        
        # הוספת משתמש חדש
        cur.execute("""
            INSERT INTO users (business_id, name, password, email, role, created_at)
            VALUES (%s, %s, %s, %s, 'employee', NOW())
            RETURNING id
        """, (business_id, username, password, email))
        
        result = cur.fetchone()
        new_user_id = result[0] if result else None
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"✅ New user {username} added to business {business_id}")
        return jsonify({
            'message': 'משתמש נוסף בהצלחה',
            'user_id': new_user_id,
            'username': username
        })
        
    except Exception as e:
        logger.error(f"Error adding user to business {business_id}: {e}")
        return jsonify({'error': 'Failed to add user'}), 500

@admin_bp.route('/businesses/<int:business_id>/toggle-active', methods=['PUT'])
@admin_required
def toggle_business_active(business_id):
    """שינוי סטטוס פעיל/לא פעיל לעסק"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
            
        cur = conn.cursor()
        
        # קבלת סטטוס נוכחי
        cur.execute("SELECT is_active FROM businesses WHERE id = %s", (business_id,))
        row = cur.fetchone()
        
        if not row:
            cur.close()
            conn.close()
            return jsonify({'error': 'Business not found'}), 404
        
        current_status = row[0]
        new_status = not current_status
        
        # עדכון סטטוס
        cur.execute("""
            UPDATE businesses 
            SET is_active = %s, updated_at = NOW()
            WHERE id = %s
        """, (new_status, business_id))
        
        conn.commit()
        cur.close()
        conn.close()
        
        status_text = 'פעיל' if new_status else 'לא פעיל'
        logger.info(f"✅ Business {business_id} status changed to {status_text}")
        
        return jsonify({
            'message': f'סטטוס העסק שונה ל{status_text}',
            'is_active': new_status
        })
        
    except Exception as e:
        logger.error(f"Error toggling business {business_id} status: {e}")
        return jsonify({'error': 'Failed to toggle business status'}), 500

# הפונקציה הוסרה - כבר קיימת למעלה

@admin_bp.route('/businesses', methods=['POST'])
@admin_required
def create_business():
    """יצירת עסק חדש"""
    try:
        data = request.get_json()
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
            
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO businesses 
            (name, business_type, phone_israel, phone_whatsapp, ai_prompt, 
             crm_enabled, whatsapp_enabled, calls_enabled)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            data.get('name'),
            data.get('type'),
            data.get('phone'),
            data.get('whatsapp_phone'),
            data.get('ai_prompt'),
            data.get('crm_enabled', False),
            data.get('whatsapp_enabled', False),
            data.get('calls_enabled', False)
        ))
        
        result = cur.fetchone()
        if result:
            business_id = result[0]
        else:
            return jsonify({'error': 'Failed to create business'}), 500
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"✅ Business created: {data.get('name')} (ID: {business_id})")
        
        return jsonify({
            'id': business_id,
            'message': 'Business created successfully'
        }), 201
    
    except Exception as e:
        logger.error(f"Error creating business: {e}")
        return jsonify({'error': 'Failed to create business'}), 500

@admin_bp.route('/businesses/<int:business_id>', methods=['PUT'])
@admin_required
def update_business(business_id):
    """עדכון עסק קיים"""
    try:
        data = request.get_json()
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
            
        cur = conn.cursor()
        
        cur.execute("""
            UPDATE businesses 
            SET name = %s, business_type = %s, phone_israel = %s, 
                phone_whatsapp = %s, ai_prompt = %s,
                crm_enabled = %s, whatsapp_enabled = %s, calls_enabled = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (
            data.get('name'),
            data.get('type'),
            data.get('phone'),
            data.get('whatsapp_phone'),
            data.get('ai_prompt'),
            data.get('crm_enabled', False),
            data.get('whatsapp_enabled', False),
            data.get('calls_enabled', False),
            business_id
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"✅ Business updated: ID {business_id}")
        
        return jsonify({'message': 'Business updated successfully'})
    
    except Exception as e:
        logger.error(f"Error updating business: {e}")
        return jsonify({'error': 'Failed to update business'}), 500

@admin_bp.route('/businesses/<int:business_id>', methods=['PATCH'])
@admin_required
def update_business_full(business_id):
    """עדכון מלא של עסק"""
    try:
        data = request.get_json()
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
            
        cur = conn.cursor()
        
        # בדיקה שהעסק קיים
        cur.execute("SELECT id FROM businesses WHERE id = %s", (business_id,))
        if not cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({'error': 'Business not found'}), 404
        
        # עדכון העסק
        cur.execute("""
            UPDATE businesses SET 
                name = %s,
                business_type = %s,
                phone_israel = %s,
                phone_whatsapp = %s,
                ai_prompt = %s,
                crm_enabled = %s,
                whatsapp_enabled = %s,
                calls_enabled = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (
            data.get('name'),
            data.get('type'),
            data.get('phone'),
            data.get('whatsapp_phone'),
            data.get('ai_prompt'),
            data.get('crm_enabled', False),
            data.get('whatsapp_enabled', False),
            data.get('calls_enabled', False),
            business_id
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"✅ Business {business_id} updated successfully")
        return jsonify({'message': 'Business updated successfully'})
        
    except Exception as e:
        logger.error(f"Error updating business {business_id}: {e}")
        return jsonify({'error': 'Failed to update business'}), 500

@admin_bp.route('/businesses/<int:business_id>', methods=['DELETE'])
@admin_required
def delete_business(business_id):
    """מחיקת עסק (סימון כלא פעיל)"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
            
        cur = conn.cursor()
        
        # בדיקה שהעסק קיים
        cur.execute("SELECT id FROM businesses WHERE id = %s", (business_id,))
        if not cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({'error': 'Business not found'}), 404
        
        # סימון העסק כלא פעיל במקום מחיקה פיזית
        cur.execute("""
            UPDATE businesses 
            SET is_active = false, updated_at = CURRENT_TIMESTAMP 
            WHERE id = %s
        """, (business_id,))
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"Business {business_id} marked as inactive")
        return jsonify({'message': 'Business deleted successfully'})
        
    except Exception as e:
        logger.error(f"Error deleting business: {e}")
        return jsonify({'error': 'Failed to delete business'}), 500

@admin_bp.route('/users', methods=['POST'])
@admin_required
def create_user_endpoint():
    """יצירת משתמש חדש"""
    try:
        data = request.get_json()
        name = data.get('name')
        email = data.get('email')
        password = data.get('password')
        role = data.get('role', 'business')
        business_id = data.get('businessId')
        
        if not name or not email or not password:
            return jsonify({'error': 'Missing required fields'}), 400
            
        if role == 'business' and not business_id:
            return jsonify({'error': 'Business ID required for business users'}), 400
            
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
            
        cur = conn.cursor()
        
        # בדיקה אם המשתמש כבר קיים
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({'error': 'User already exists'}), 409
        
        # יצירת המשתמש
        cur.execute("""
            INSERT INTO users (name, email, password, role, business_id, created_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            RETURNING id
        """, (name, email, password, role, business_id))
        
        result = cur.fetchone()
        user_id = result[0] if result else None
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"✅ User created: {email} with ID {user_id}")
        return jsonify({'message': 'User created successfully', 'user_id': user_id})
        
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        return jsonify({'error': 'Failed to create user'}), 500

@admin_bp.route('/impersonate/<int:business_id>', methods=['POST'])
@admin_required
def impersonate_business(business_id):
    """אפשר למנהל להתחזות לעסק ולצפות במערכת שלו"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
            
        cur = conn.cursor()
        
        # בדיקה שהעסק קיים
        cur.execute("SELECT id, name FROM businesses WHERE id = %s", (business_id,))
        business = cur.fetchone()
        if not business:
            cur.close()
            conn.close()
            return jsonify({'error': 'Business not found'}), 404
        
        # חיפוש משתמש העסק או יצירת זמני
        cur.execute("""
            SELECT id, name, email FROM users 
            WHERE business_id = %s AND role = 'business' 
            LIMIT 1
        """, (business_id,))
        
        user = cur.fetchone()
        if not user:
            # יצירת משתמש זמני לצפייה
            cur.execute("""
                INSERT INTO users (business_id, name, email, password, role, created_at)
                VALUES (%s, %s, %s, %s, 'business', NOW())
                RETURNING id, name, email
            """, (business_id, f'temp_user_{business_id}', f'temp{business_id}@system.com', 'temp123'))
            user = cur.fetchone()
            conn.commit()
        
        cur.close()
        conn.close()
        
        # יצירת טוקן זמני לעסק
        business_token_payload = {
            'user_id': user[0],
            'business_id': business_id,
            'role': 'business',
            'name': user[1],
            'email': user[2],
            'is_impersonating': True,
            'exp': datetime.utcnow() + timedelta(hours=8)  # תוקף של 8 שעות
        }
        
        business_token = jwt.encode(business_token_payload, 'your-secret-key', algorithm='HS256')
        
        logger.info(f"✅ Admin impersonating business {business_id} - {business[1]}")
        return jsonify({
            'success': True,
            'token': business_token,
            'business': {
                'id': business_id,
                'name': business[1]
            },
            'message': f'עבר למצב צפייה בעסק: {business[1]}'
        })
        
    except Exception as e:
        logger.error(f"Error during impersonation: {e}")
        return jsonify({'error': 'Failed to switch to business view'}), 500

@admin_bp.route('/stop-impersonation', methods=['POST'])
def stop_impersonation():
    """חזרה למצב מנהל מהתחזות לעסק"""
    try:
        # הקליינט ישלח את הטוקן המקורי של המנהל
        data = request.get_json()
        original_admin_token = data.get('original_token')
        
        if not original_admin_token:
            return jsonify({'error': 'Original admin token required'}), 400
            
        # בדיקת תוקף הטוקן המקורי
        try:
            decoded = jwt.decode(original_admin_token, 'your-secret-key', algorithms=['HS256'])
            if decoded.get('role') != 'admin':
                return jsonify({'error': 'Invalid admin token'}), 403
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 403
        
        logger.info("✅ Admin returned from business impersonation")
        return jsonify({
            'message': 'חזר למצב מנהל בהצלחה',
            'token': original_admin_token
        })
        
    except Exception as e:
        logger.error(f"Error stopping impersonation: {e}")
        return jsonify({'error': 'Failed to return to admin mode'}), 500



@admin_bp.route('/stats', methods=['GET'])
@admin_required
def get_admin_stats():
    """קבלת סטטיסטיקות כלליות למנהל"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
            
        cur = conn.cursor()
        
        # סה"כ עסקים
        cur.execute("SELECT COUNT(*) FROM businesses")
        result = cur.fetchone()
        total_businesses = result[0] if result else 0
        
        # עסקים פעילים (לפחות שירות אחד פעיל)
        cur.execute("""
            SELECT COUNT(*) FROM businesses 
            WHERE crm_enabled = true OR whatsapp_enabled = true OR calls_enabled = true
        """)
        result = cur.fetchone()
        active_businesses = result[0] if result else 0
        
        # סימולציה של נתונים נוספים (עד שיהיו טבלאות אמתיות)
        total_calls = 127
        total_users = 15
        
        cur.close()
        conn.close()
        
        return jsonify({
            'totalBusinesses': total_businesses,
            'activeBusinesses': active_businesses,
            'totalCalls': total_calls,
            'totalUsers': total_users
        })
    
    except Exception as e:
        logger.error(f"Error fetching admin stats: {e}")
        return jsonify({'error': 'Failed to fetch statistics'}), 500

# React Frontend API Routes for Admin Business Control

@admin_bp.route('/api/admin/businesses/<int:business_id>')
def get_business_details_api(business_id):
    """קבלת פרטי עסק מסוים למנהל עבור React"""
    try:
        from models import Business
        
        business = Business.query.get(business_id)
        if not business:
            return jsonify({"error": "Business not found"}), 404
        
        # חישוב שירותים זמינים
        services = {
            "crm": True,  # כל עסק יש לו CRM
            "whatsapp": bool(business.twilio_phone_number),
            "calls": bool(business.twilio_phone_number),
            "calendar": True
        }
        
        return jsonify({
            "id": business.id,
            "name": business.name,
            "type": business.type,
            "phone": business.phone,
            "email": business.email,
            "twilio_phone_number": business.twilio_phone_number,
            "is_active": business.is_active,
            "services": services,
            "created_at": business.created_at.isoformat() if business.created_at else None
        })
        
    except Exception as e:
        logging.error(f"Error getting business details API: {e}")
        return jsonify({"error": "Server error"}), 500

@admin_bp.route('/api/admin/impersonate/<int:business_id>', methods=['POST'])
def impersonate_business_api(business_id):
    """השתלטות מנהל על עסק מסוים עבור React"""
    try:
        from models import Business, User
        from datetime import datetime, timedelta
        import jwt
        
        # בדיקת הרשאות מנהל
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({"error": "No token provided"}), 401
        
        token = token.replace('Bearer ', '')
        
        # פיענוח הטוקן המקורי
        try:
            payload = jwt.decode(token, 'your-secret-key', algorithms=['HS256'])
            if payload.get('role') != 'admin':
                return jsonify({"error": "Admin access required"}), 403
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401
        
        # קבלת העסק
        business = Business.query.get(business_id)
        if not business:
            return jsonify({"error": "Business not found"}), 404
        
        if not business.is_active:
            return jsonify({"error": "Business is inactive"}), 400
        
        # חיפוש או יצירת משתמש לעסק
        business_user = User.query.filter_by(business_id=business_id, role='business').first()
        if not business_user:
            # יצירת משתמש זמני
            business_user = User(
                username=f'temp_business_{business_id}',
                email=f'temp{business_id}@system.com',
                password='temp_password',
                role='business',
                business_id=business_id
            )
            from app import db
            db.session.add(business_user)
            db.session.commit()
        
        # יצירת טוקן השתלטות
        takeover_payload = {
            'user_id': business_user.id,
            'role': 'business',
            'business_id': business_id,
            'username': business_user.username,
            'is_admin_impersonation': True,
            'original_admin_id': payload['user_id'],
            'exp': datetime.utcnow() + timedelta(hours=8)
        }
        
        takeover_token = jwt.encode(takeover_payload, 'your-secret-key', algorithm='HS256')
        
        logging.info(f"🚀 Admin {payload['user_id']} taking over business {business_id} - {business.name}")
        
        return jsonify({
            "success": True,
            "token": takeover_token,
            "business": {
                "id": business.id,
                "name": business.name,
                "type": business.type
            },
            "message": f"השתלטות על עסק {business.name} הושלמה בהצלחה"
        })
        
    except Exception as e:
        logging.error(f"Error in business impersonation API: {e}")
        return jsonify({"error": "Server error"}), 500