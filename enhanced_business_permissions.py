"""
Enhanced Business Permissions System
מערכת הרשאות עסקיות מתקדמת עם הגנות אבטחה מלאות
"""

from functools import wraps
from flask import request, redirect, url_for, jsonify, abort
from models import Business, User
import logging

logger = logging.getLogger(__name__)

class BusinessPermissions:
    """מחלקה לניהול הרשאות עסקיות מתקדמות"""
    
    @staticmethod
    def has_calls_permission(user, business_id: int = None) -> bool:
        """בדיקת הרשאה לשיחות"""
        if not user or not user.is_active:
            return False
        
        # Admin רואה הכל
        if user.role == 'admin':
            return True
            
        # בדיקה שהמשתמש שייך לעסק ויש לו הרשאה
        if business_id:
            business = Business.query.get(business_id)
            if not business or user.business_id != business_id:
                return False
        
        return user.can_access_phone
    
    @staticmethod
    def has_whatsapp_permission(user, business_id: int = None) -> bool:
        """בדיקת הרשאה ל-WhatsApp"""
        if not user or not user.is_active:
            return False
        
        if user.role == 'admin':
            return True
            
        if business_id:
            business = Business.query.get(business_id)
            if not business or user.business_id != business_id:
                return False
        
        return user.can_access_whatsapp
    
    @staticmethod
    def has_crm_permission(user, business_id: int = None) -> bool:
        """בדיקת הרשאה ל-CRM"""
        if not user or not user.is_active:
            return False
        
        if user.role == 'admin':
            return True
            
        if business_id:
            business = Business.query.get(business_id)
            if not business or user.business_id != business_id:
                return False
        
        return user.can_access_crm
    
    @staticmethod
    def can_manage_business(user, business_id: int = None) -> bool:
        """בדיקה אם המשתמש יכול לנהל עסק"""
        if not user or not user.is_active:
            return False
        
        # רק admin יכול לנהל כל עסק
        if user.role == 'admin':
            return True
        
        # בעל עסק יכול לנהל רק את העסק שלו
        if business_id and user.business_id == business_id:
            return user.can_manage_business
            
        return False

def require_calls_permission(business_id_param: str = 'business_id'):
    """דקורטור להרשאת שיחות"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            business_id = request.view_args.get(business_id_param) if business_id_param else None
            
            if not BusinessPermissions.has_calls_permission(user, business_id):
                if request.is_json:
                    return jsonify({'error': 'אין הרשאה לגישה לשיחות'}), 403
                abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def require_whatsapp_permission(business_id_param: str = 'business_id'):
    """דקורטור להרשאת WhatsApp"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            business_id = request.view_args.get(business_id_param) if business_id_param else None
            
            if not BusinessPermissions.has_whatsapp_permission(user, business_id):
                if request.is_json:
                    return jsonify({'error': 'אין הרשאה לגישה ל-WhatsApp'}), 403
                abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def require_crm_permission(business_id_param: str = 'business_id'):
    """דקורטור להרשאת CRM"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            business_id = request.view_args.get(business_id_param) if business_id_param else None
            
            if not BusinessPermissions.has_crm_permission(user, business_id):
                if request.is_json:
                    return jsonify({'error': 'אין הרשאה לגישה ל-CRM'}), 403
                abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def require_business_management(business_id_param: str = 'business_id'):
    """דקורטור לניהול עסקים"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            business_id = request.view_args.get(business_id_param) if business_id_param else None
            
            if not BusinessPermissions.can_manage_business(user, business_id):
                if request.is_json:
                    return jsonify({'error': 'אין הרשאה לניהול עסק'}), 403
                abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def validate_business_access(user, business_id: int) -> bool:
    """אימות גישה לעסק - הגנה מפני ID spoofing"""
    if not user:
        logger.warning("Attempted business access without user")
        return False
    
    if user.role == 'admin':
        return True
    
    if user.business_id != business_id:
        logger.warning(f"User {user.id} attempted access to business {business_id} without permission")
        return False
    
    business = Business.query.get(business_id)
    if not business:
        logger.warning(f"Attempted access to non-existent business {business_id}")
        return False
    
    return True

def get_accessible_businesses(user) -> list:
    """קבלת רשימת עסקים שהמשתמש יכול לגשת אליהם"""
    if not user:
        return []
    
    if user.role == 'admin':
        return Business.query.all()
    
    if user.business_id:
        business = Business.query.get(user.business_id)
        return [business] if business else []
    
    return []

def filter_by_business_permission(query, model, user):
    """סינון שאילתא לפי הרשאות עסק"""
    if not user:
        return query.filter(model.id == -1)  # אין תוצאות
    
    if user.role == 'admin':
        return query  # רואה הכל
    
    if hasattr(model, 'business_id') and user.business_id:
        return query.filter(model.business_id == user.business_id)
    
    return query.filter(model.id == -1)  # אין תוצאות