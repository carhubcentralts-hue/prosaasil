import hashlib
import hmac
import secrets
import logging
import psycopg2
import os
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, current_app

logger = logging.getLogger(__name__)

login_bp = Blueprint('login', __name__)

def get_db_connection():
    """יצירת חיבור למסד הנתונים"""
    try:
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            logger.error("DATABASE_URL not found")
            return None
        conn = psycopg2.connect(database_url)
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return None

def simple_verify_password(stored_password, provided_password):
    """בדיקת סיסמה פשוטה לפיתוח"""
    # עבור פיתוח נשתמש בהשוואה פשוטה
    if stored_password.startswith('simple_hash_'):
        expected = stored_password.replace('simple_hash_', '')
        return expected == provided_password
    return False

def generate_simple_token(username, role):
    """יצירת טוקן פשוט לאימות"""
    timestamp = str(int(datetime.now().timestamp()))
    token_data = f"{username}:{role}:{timestamp}"
    token = hashlib.sha256(token_data.encode()).hexdigest()
    return token

@login_bp.route('/login', methods=['POST'])
def login():
    """API endpoint להתחברות למערכת"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'נתונים לא תקינים'}), 400
            
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return jsonify({'error': 'שם משתמש וסיסמה נדרשים'}), 400
            
        logger.info(f"Login attempt for username: {username}")
        
        # חיבור למסד הנתונים
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed")
            return jsonify({'error': 'שגיאת חיבור למסד הנתונים'}), 500
            
        cur = conn.cursor()
        
        # חיפוש המשתמש
        cur.execute("""
            SELECT id, username, password_hash, role, name, business_id 
            FROM users 
            WHERE username = %s
        """, (username,))
        
        user = cur.fetchone()
        
        if not user:
            logger.warning(f"User not found: {username}")
            return jsonify({'error': 'שם משתמש או סיסמה שגויים'}), 401
            
        user_id, user_username, password_hash, role, name, business_id = user
        
        # בדיקת סיסמה
        if not simple_verify_password(password_hash, password):
            logger.warning(f"Invalid password for user: {username}")
            return jsonify({'error': 'שם משתמש או סיסמה שגויים'}), 401
            
        # יצירת טוקן
        token = generate_simple_token(username, role)
        
        logger.info(f"Successful login for user: {username} (role: {role})")
        
        # הכנת תגובה
        response_data = {
            'token': token,
            'role': role,
            'name': name,
            'username': username,
            'user_id': user_id
        }
        
        # הוספת business_id אם רלוונטי
        if business_id:
            response_data['business_id'] = business_id
            
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({'error': 'שגיאה בהתחברות'}), 500
    finally:
        if 'conn' in locals() and conn:
            conn.close()

@login_bp.route('/logout', methods=['POST'])
def logout():
    """API endpoint ליציאה מהמערכת"""
    try:
        # כאן נוכל להוסיף לוגיקה לביטול טוקנים אם נרצה
        logger.info("User logout")
        return jsonify({'message': 'התנתקת בהצלחה'}), 200
    except Exception as e:
        logger.error(f"Logout error: {e}")
        return jsonify({'error': 'שגיאה ביציאה'}), 500

@login_bp.route('/verify-token', methods=['POST'])
def verify_token():
    """בדיקת תוקף טוקן"""
    try:
        data = request.get_json()
        token = data.get('token')
        
        if not token:
            return jsonify({'valid': False, 'error': 'חסר טוקן'}), 400
            
        # כאן נוכל להוסיף לוגיקה מתקדמת יותר לבדיקת טוקנים
        # לעת עתה נחזיר שהטוקן תקף אם הוא קיים
        return jsonify({'valid': True}), 200
        
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        return jsonify({'valid': False, 'error': 'שגיאה בבדיקת טוקן'}), 500

# פונקציה עזר ליצירת משתמשים (לטסטים או הגדרה ראשונית)
def create_default_users():
    """יצירת משתמשים ראשוניים"""
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("Cannot create default users - DB connection failed")
            return False
            
        cur = conn.cursor()
        
        # בדיקה אם כבר קיימים משתמשים
        cur.execute("SELECT COUNT(*) FROM users")
        user_count = cur.fetchone()[0]
        
        if user_count > 0:
            logger.info("Users already exist, skipping default user creation")
            return True
            
        # יצירת סיסמאות מוצפנות
        admin_password_hash = hash_password('admin123')
        business_password_hash = hash_password('biz1234')
        
        # יצירת משתמש מנהל
        cur.execute("""
            INSERT INTO users (username, password_hash, role, name)
            VALUES (%s, %s, %s, %s)
        """, ('admin', admin_password_hash, 'admin', 'מנהל ראשי'))
        
        # יצירת משתמש עסק
        cur.execute("""
            INSERT INTO users (username, password_hash, role, name, business_id)
            VALUES (%s, %s, %s, %s, %s)
        """, ('business1', business_password_hash, 'business', 'עסק לדוגמה', 1))
        
        conn.commit()
        logger.info("Default users created successfully")
        
        return True
        
    except Exception as e:
        logger.error(f"Error creating default users: {e}")
        return False
    finally:
        if 'conn' in locals() and conn:
            conn.close()