from flask import Blueprint, request, jsonify
import psycopg2
import os
import logging
from datetime import datetime

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
        # כרגע מאפשרים גישה לכולם לצורך פיתוח
        # בהמשך נוסיף בדיקת JWT ותפקידים
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
                   created_at
            FROM businesses 
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
                'created_at': row[9].strftime('%Y-%m-%d %H:%M:%S') if row[9] else None
            }
            businesses.append(business)
        
        cur.close()
        conn.close()
        
        logger.info(f"Found {len(businesses)} businesses")
        return jsonify(businesses)
        
    except Exception as e:
        logger.error(f"Error fetching businesses: {e}")
        return jsonify({'error': 'Failed to fetch businesses'}), 500

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
        
        # עדכון services
        services = data.get('services', {})
        
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
            services.get('crm', False),
            services.get('whatsapp', False),
            services.get('calls', False)
        ))
        
        business_id = cur.fetchone()[0]
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
        
        # עדכון services
        services = data.get('services', {})
        
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
            services.get('crm', False),
            services.get('whatsapp', False),
            services.get('calls', False),
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

@admin_bp.route('/businesses/<int:business_id>', methods=['DELETE'])
@admin_required
def delete_business(business_id):
    """מחיקת עסק"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
            
        cur = conn.cursor()
        
        # קבלת שם העסק לפני המחיקה
        cur.execute("SELECT name FROM businesses WHERE id = %s", (business_id,))
        result = cur.fetchone()
        if not result:
            return jsonify({'error': 'Business not found'}), 404
            
        business_name = result[0]
        
        # מחיקת העסק
        cur.execute("DELETE FROM businesses WHERE id = %s", (business_id,))
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"✅ Business deleted: {business_name} (ID: {business_id})")
        
        return jsonify({'message': 'Business deleted successfully'})
    
    except Exception as e:
        logger.error(f"Error deleting business: {e}")
        return jsonify({'error': 'Failed to delete business'}), 500

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
        total_businesses = cur.fetchone()[0]
        
        # עסקים פעילים (לפחות שירות אחד פעיל)
        cur.execute("""
            SELECT COUNT(*) FROM businesses 
            WHERE crm_enabled = true OR whatsapp_enabled = true OR calls_enabled = true
        """)
        active_businesses = cur.fetchone()[0]
        
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