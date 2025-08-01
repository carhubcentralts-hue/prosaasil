"""
Business Security and Access Control
בקרת גישה ואבטחה עסקית מתקדמת
"""
import logging
from functools import wraps
from flask import request, jsonify, flash, redirect, url_for
from auth import AuthService

logger = logging.getLogger(__name__)

class BusinessSecurity:
    """מחלקה לניהול אבטחה ובקרת גישה עסקית"""
    
    @staticmethod
    def validate_business_access(user, business_id):
        """וולידציה שמשתמש יכול לגשת לעסק מסוים"""
        if not user:
            logger.warning("Business access validation failed - no user")
            return False
            
        # מנהל יכול לגשת לכל עסק
        if user.role == 'admin':
            return True
            
        # משתמש עסק יכול לגשת רק לעסק שלו
        if user.role == 'business' and user.business_id == int(business_id):
            return True
            
        logger.warning(f"User {user.username} tried to access business {business_id} without permission")
        return False
    
    @staticmethod
    def validate_crm_access(user):
        """וולידציה שמשתמש יכול לגשת ל-CRM"""
        if not user:
            return False
            
        # מנהל תמיד יכול לגשת
        if user.role == 'admin':
            return True
            
        # משתמש עסק - בדיקת הרשאות CRM
        if user.role == 'business' and user.business_id:
            try:
                from permissions import PermissionManager
                return PermissionManager.check_service_permission(user.business_id, 'crm')
            except Exception as e:
                logger.error(f"Error checking CRM permissions: {e}")
                return False
                
        return False
    
    @staticmethod
    def filter_data_by_business(query, user, business_id_field='business_id'):
        """סינון נתונים לפי עסק - מניעת cross-business access"""
        if not user:
            return query.filter(False)  # לא מחזיר כלום
            
        # מנהל רואה הכל
        if user.role == 'admin':
            return query
            
        # משתמש עסק רואה רק את הנתונים שלו
        if user.role == 'business' and user.business_id:
            return query.filter(getattr(query.column_descriptions[0]['type'], business_id_field) == user.business_id)
            
        # במקרה של משתמש לא מזוהה
        return query.filter(False)

def business_required(f):
    """דקורטור שמחייב הרשאות עסק או מנהל"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        current_user = AuthService.get_current_user()
        
        if not current_user:
            flash('נדרשת התחברות למערכת', 'warning')
            return redirect(url_for('login'))
            
        if current_user.role not in ['admin', 'business']:
            flash('אין לך הרשאה לגשת לאזור זה', 'error')
            return redirect(url_for('index'))
            
        return f(*args, **kwargs)
    return decorated_function

def validate_business_route_access(f):
    """דקורטור לוולידציה של גישה לנתיבי עסק"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        current_user = AuthService.get_current_user()
        business_id = kwargs.get('business_id') or request.view_args.get('business_id')
        
        if not BusinessSecurity.validate_business_access(current_user, business_id):
            if request.is_json:
                return jsonify({'error': 'אין הרשאה לגשת לעסק זה'}), 403
            else:
                flash('אין לך הרשאה לגשת לעסק זה', 'error')
                return redirect(url_for('index'))
                
        return f(*args, **kwargs)
    return decorated_function

def crm_access_required(f):
    """דקורטור שמחייב הרשאות CRM"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        current_user = AuthService.get_current_user()
        
        if not BusinessSecurity.validate_crm_access(current_user):
            if request.is_json:
                return jsonify({'error': 'אין הרשאה לגשת למערכת CRM'}), 403
            else:
                flash('אין לך הרשאה לגשת למערכת CRM', 'error')
                return redirect(url_for('index'))
                
        return f(*args, **kwargs)
    return decorated_function

class DataValidator:
    """וולידטור נתונים למניעת זיוף ו-injection"""
    
    @staticmethod
    def validate_whatsapp_message(message_data):
        """וולידציה של הודעת WhatsApp"""
        if not message_data or not isinstance(message_data, dict):
            return False
            
        # בדיקת שדות חובה
        required_fields = ['From', 'Body']
        for field in required_fields:
            if field not in message_data:
                logger.warning(f"Missing required field in WhatsApp message: {field}")
                return False
                
        # בדיקת תוכן ההודעה
        body = message_data.get('Body', '').strip()
        if not body or len(body) == 0:
            logger.warning("Empty WhatsApp message body")
            return False
            
        # בדיקת אורך מקסימלי
        if len(body) > 4096:  # הגבלת אורך
            logger.warning(f"WhatsApp message too long: {len(body)} chars")
            return False
            
        return True
    
    @staticmethod
    def sanitize_phone_number(phone_number):
        """ניקוי וולידציה של מספר טלפון"""
        if not phone_number:
            return None
            
        # הסרת תווים לא רלוונטיים
        cleaned = ''.join(filter(str.isdigit, phone_number))
        
        # בדיקת אורך הגיוני
        if len(cleaned) < 10 or len(cleaned) > 15:
            return None
            
        return f"+{cleaned}" if not cleaned.startswith('+') else cleaned
    
    @staticmethod
    def generate_unique_message_sid():
        """יצירת MessageSid ייחודי עם UUID"""
        import uuid
        return f"WA{uuid.uuid4().hex[:24]}"