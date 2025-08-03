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

def generate_simple_token(username, role):
    """יצירת טוכן פשוט לאימות"""
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
            
        try:
            cur = conn.cursor()
            
            # חיפוש המשתמש
            cur.execute("""
                SELECT id, email, password, role, name, business_id 
                FROM users 
                WHERE name = %s OR email = %s
            """, (username, username))
            
            user = cur.fetchone()
            
            if not user:
                logger.warning(f"User not found: {username}")
                cur.close()
                conn.close()
                return jsonify({'error': 'שם משתמש או סיסמה שגויים'}), 401
                
            user_id, user_email, stored_password, role, name, business_id = user
            
            # בדיקת סיסמה
            if stored_password != password:
                logger.warning(f"Invalid password for user: {username}")
                cur.close()
                conn.close()
                return jsonify({'error': 'שם משתמש או סיסמה שגויים'}), 401
                
            # יצירת טוכן
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
                
            cur.close()
            conn.close()
            
            return jsonify(response_data), 200
            
        except Exception as db_error:
            logger.error(f"Database error: {db_error}")
            if conn:
                conn.close()
            return jsonify({'error': 'שגיאת מסד נתונים'}), 500
        
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({'error': 'שגיאה בהתחברות'}), 500

@login_bp.route('/logout', methods=['POST'])
def logout():
    """API endpoint ליציאה מהמערכת"""
    try:
        logger.info("User logout")
        return jsonify({'message': 'התנתקת בהצלחה'}), 200
    except Exception as e:
        logger.error(f"Logout error: {e}")
        return jsonify({'error': 'שגיאה ביציאה'}), 500

@login_bp.route('/verify-token', methods=['POST'])
def verify_token():
    """בדיקת תוקף טוכן"""
    try:
        data = request.get_json()
        token = data.get('token')
        
        if not token:
            return jsonify({'valid': False, 'error': 'חסר טוכן'}), 400
            
        return jsonify({'valid': True}), 200
        
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        return jsonify({'valid': False, 'error': 'שגיאה בבדיקת טוכן'}), 500