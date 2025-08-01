"""
Business Permissions System - מערכת הרשאות מתקדמת לפי עסק
"""
import enum
from functools import wraps
from datetime import datetime
from flask import request, jsonify, session, redirect, url_for, flash
from app import db
from models import Business, User
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class BusinessPermission(enum.Enum):
    """הרשאות עסקיות"""
    PHONE_CALLS = "phone_calls"        # הרשאה לקבל שיחות טלפון
    WHATSAPP = "whatsapp"              # הרשאה ל-WhatsApp Business
    CRM = "crm"                        # הרשאה למערכת CRM
    ADMIN_PANEL = "admin_panel"        # הרשאה לפאנל ניהול
    ANALYTICS = "analytics"            # הרשאה לאנליטיקה
    APPOINTMENTS = "appointments"       # הרשאה לניהול תורים

class BusinessPermissionChecker:
    """בודק הרשאות עסקיות"""
    
    @staticmethod
    def has_permission(business_id: int, permission: BusinessPermission) -> bool:
        """בדיקה האם לעסק יש הרשאה מסוימת"""
        try:
            business = Business.query.get(business_id)
            if not business:
                return False
            
            # בדיקת הרשאות לפי העסק
            if permission == BusinessPermission.PHONE_CALLS:
                return getattr(business, 'phone_permissions', True)
            elif permission == BusinessPermission.WHATSAPP:
                return getattr(business, 'whatsapp_permissions', True)
            elif permission == BusinessPermission.CRM:
                return getattr(business, 'crm_permissions', True)
            elif permission == BusinessPermission.ADMIN_PANEL:
                return getattr(business, 'admin_permissions', False)
            elif permission == BusinessPermission.ANALYTICS:
                return getattr(business, 'analytics_permissions', True)
            elif permission == BusinessPermission.APPOINTMENTS:
                return getattr(business, 'appointments_permissions', True)
            
            return False
        except Exception as e:
            logger.error(f"Error checking permission {permission} for business {business_id}: {e}")
            return False
    
    @staticmethod
    def get_user_business_access(user_id: int) -> list:
        """קבלת רשימת עסקים שהמשתמש יכול לגשת אליהם"""
        try:
            user = User.query.get(user_id)
            
            if not user:
                return []
            
            # אדמין רואה הכל
            if user.role == 'admin':
                return Business.query.filter_by(is_active=True).all()
            
            # משתמש עסקי רואה רק את העסק שלו
            elif user.role == 'business':
                business = Business.query.filter_by(username=user.username).first()
                return [business] if business else []
            
            return []
        except Exception as e:
            logger.error(f"Error getting business access for user {user_id}: {e}")
            return []

class SecurityLimiter:
    """מגביל ניסיונות התחברות וביטחון"""
    
    login_attempts = {}  # זמני - במציאות צריך Redis או DB
    
    @classmethod
    def is_ip_blocked(cls, ip_address: str) -> bool:
        """בדיקה האם IP חסום"""
        if ip_address not in cls.login_attempts:
            return False
        
        attempts = cls.login_attempts[ip_address]
        return attempts.get('count', 0) >= 3
    
    @classmethod
    def record_failed_login(cls, ip_address: str):
        """רישום ניסיון התחברות כושל"""
        if ip_address not in cls.login_attempts:
            cls.login_attempts[ip_address] = {'count': 0, 'last_attempt': None}
        
        cls.login_attempts[ip_address]['count'] += 1
        cls.login_attempts[ip_address]['last_attempt'] = datetime.now()
        
        logger.warning(f"Failed login attempt from IP: {ip_address}, total attempts: {cls.login_attempts[ip_address]['count']}")
    
    @classmethod
    def reset_attempts(cls, ip_address: str):
        """איפוס ניסיונות עבור IP"""
        if ip_address in cls.login_attempts:
            del cls.login_attempts[ip_address]

# דקורטורים להגנה על נתיבים

def admin_required(f):
    """דקורטור שדורש הרשאות אדמין"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from auth import AuthService
        current_user = AuthService.get_current_user()
        
        if not current_user or current_user.role != 'admin':
            flash('נדרשת הרשאת מנהל לגישה לעמוד זה', 'error')
            return redirect(url_for('login'))
        
        return f(*args, **kwargs)
    return decorated_function

def business_required(f):
    """דקורטור שדורש הרשאות עסקיות"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from auth import AuthService
        current_user = AuthService.get_current_user()
        
        if not current_user:
            flash('נדרשת התחברות', 'error')
            return redirect(url_for('login'))
        
        if current_user.role not in ['admin', 'business']:
            flash('נדרשת הרשאת עסק לגישה לעמוד זה', 'error')
            return redirect(url_for('login'))
        
        return f(*args, **kwargs)
    return decorated_function

def permission_required(permission: BusinessPermission):
    """דקורטור שדורש הרשאה ספציפית"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from auth import AuthService
            current_user = AuthService.get_current_user()
            
            if not current_user:
                return jsonify({'error': 'נדרשת התחברות'}), 401
            
            # אדמין עובר הכל
            if current_user.role == 'admin':
                return f(*args, **kwargs)
            
            # בדיקת הרשאה לעסק
            business = Business.query.filter_by(username=current_user.username).first()
            if not business:
                return jsonify({'error': 'עסק לא נמצא'}), 404
            
            if not BusinessPermissionChecker.has_permission(business.id, permission):
                return jsonify({'error': f'אין הרשאה ל{permission.value}'}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def rate_limit(max_requests: int = 100, window_minutes: int = 60):
    """הגבלת קצב בקשות"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            ip_address = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
            
            # בדיקה אם IP חסום
            if SecurityLimiter.is_ip_blocked(ip_address):
                return jsonify({'error': 'IP חסום זמנית בגלל יותר מדי ניסיונות'}), 429
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def cross_business_protection(f):
    """הגנה מפני גישה בין עסקים"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from auth import AuthService
        current_user = AuthService.get_current_user()
        
        if not current_user:
            return jsonify({'error': 'נדרשת התחברות'}), 401
        
        # אדמין עובר הכל
        if current_user.role == 'admin':
            return f(*args, **kwargs)
        
        # בדיקת business_id בפרמטרים
        business_id = kwargs.get('business_id') or request.args.get('business_id') or request.form.get('business_id')
        
        if business_id:
            user_business = Business.query.filter_by(username=current_user.username).first()
            if not user_business or str(user_business.id) != str(business_id):
                logger.warning(f"Cross-business access attempt: user {current_user.username} tried to access business {business_id}")
                return jsonify({'error': 'אין הרשאה לגשת לעסק זה'}), 403
        
        return f(*args, **kwargs)
    return decorated_function

# פונקציות עזר

def get_current_business() -> Optional[Business]:
    """קבלת העסק הנוכחי של המשתמש"""
    from auth import AuthService
    current_user = AuthService.get_current_user()
    
    if not current_user:
        return None
    
    if current_user.role == 'business':
        return Business.query.filter_by(username=current_user.username).first()
    
    return None

def log_security_event(event_type: str, details: str, user_id: Optional[int] = None):
    """רישום אירוע ביטחוני"""
    ip_address = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
    user_agent = request.headers.get('User-Agent', '')
    
    logger.warning(f"Security Event: {event_type} | IP: {ip_address} | User: {user_id} | Details: {details} | UserAgent: {user_agent}")

def update_business_permissions(business_id: int, permissions: dict) -> bool:
    """עדכון הרשאות עסק"""
    try:
        business = Business.query.get(business_id)
        if not business:
            return False
        
        # עדכון הרשאות
        if 'phone_permissions' in permissions:
            business.phone_permissions = permissions['phone_permissions']
        if 'whatsapp_permissions' in permissions:
            business.whatsapp_permissions = permissions['whatsapp_permissions']
        if 'crm_permissions' in permissions:
            business.crm_permissions = permissions['crm_permissions']
        if 'admin_permissions' in permissions:
            business.admin_permissions = permissions['admin_permissions']
        if 'analytics_permissions' in permissions:
            business.analytics_permissions = permissions['analytics_permissions']
        if 'appointments_permissions' in permissions:
            business.appointments_permissions = permissions['appointments_permissions']
        
        db.session.commit()
        logger.info(f"Updated permissions for business {business_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error updating business permissions: {e}")
        db.session.rollback()
        return False