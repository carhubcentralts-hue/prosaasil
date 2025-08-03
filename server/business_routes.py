from flask import Blueprint, request, jsonify
import psycopg2
import os
import logging
from datetime import datetime

# הגדרת logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# יצירת Blueprint עבור business
business_bp = Blueprint('business', __name__, url_prefix='/api/business')

def get_db_connection():
    """חיבור לבסיס נתונים PostgreSQL"""
    try:
        conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return None

def business_required(f):
    """דקורטור לבדיקת הרשאות עסק"""
    def decorated_function(*args, **kwargs):
        # כרגע מאפשרים גישה לכולם לצורך פיתוח
        # בהמשך נוסיף בדיקת JWT ותפקידים
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

@business_bp.route('/info', methods=['GET'])
@business_required
def get_business_info():
    """קבלת פרטי העסק הנוכחי"""
    try:
        # בהמשך נשלוף מה-JWT, כרגע נחזיר עסק ID 1
        business_id = request.args.get('business_id', 1)
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
            
        cur = conn.cursor()
        
        cur.execute("""
            SELECT id, name, business_type, phone_israel, phone_whatsapp, 
                   ai_prompt, crm_enabled, whatsapp_enabled, calls_enabled,
                   created_at
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
            'users_count': 1
        }
        
        cur.close()
        conn.close()
        
        return jsonify(business_info)
        
    except Exception as e:
        logger.error(f"Error getting business info: {e}")
        return jsonify({'error': 'Failed to get business info'}), 500

@business_bp.route('/services', methods=['GET'])
@business_required  
def get_business_services():
    """קבלת השירותים הפעילים לעסק"""
    try:
        business_id = request.args.get('business_id', 1)
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
            
        cur = conn.cursor()
        
        cur.execute("""
            SELECT crm_enabled, whatsapp_enabled, calls_enabled
            FROM businesses 
            WHERE id = %s
        """, (business_id,))
        
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'Business not found'}), 404
            
        services = {
            'crm': row[0],
            'whatsapp': row[1], 
            'calls': row[2]
        }
        
        cur.close()
        conn.close()
        
        return jsonify(services)
        
    except Exception as e:
        logger.error(f"Error getting business services: {e}")
        return jsonify({'error': 'Failed to get services'}), 500

@business_bp.route('/users', methods=['GET'])
@business_required
def get_business_users():
    """קבלת משתמשי העסק"""
    try:
        business_id = request.args.get('business_id', 1)
        
        # נתונים קבועים לעת עתה
        users = [
            {
                'id': 1,
                'name': 'משתמש עסק',
                'role': 'business',
                'last_login': '2025-08-03T10:00:00Z',
                'status': 'active'
            }
        ]
        
        return jsonify(users)
        
    except Exception as e:
        logger.error(f"Error getting business users: {e}")
        return jsonify({'error': 'Failed to get users'}), 500

@business_bp.route('/change-password', methods=['POST'])
@business_required
def change_password():
    """שינוי סיסמה עבור העסק"""
    try:
        data = request.get_json()
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        
        if not current_password or not new_password:
            return jsonify({'error': 'Missing passwords'}), 400
            
        # כרגע נחזיר הצלחה - בהמשך נוסיף אימות אמיתי
        logger.info("Password change requested")
        return jsonify({'message': 'Password changed successfully'})
        
    except Exception as e:
        logger.error(f"Error changing password: {e}")
        return jsonify({'error': 'Failed to change password'}), 500