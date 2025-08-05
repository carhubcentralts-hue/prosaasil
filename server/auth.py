"""
Authentication system for AI Call Center
מערכת אימות מתקדמת למוקד שיחות AI
"""
from functools import wraps
from flask import session, redirect, url_for, request, flash
from werkzeug.security import check_password_hash, generate_password_hash
from app import db
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Dictionary to track login attempts per IP/username
login_attempts = {}

class AuthService:
    """שירות אימות משתמשים"""
    
    @staticmethod
    def create_admin_user(username: str, password: str, email: str) -> bool:
        """יצירת משתמש מנהל"""
        try:
            from models import User
            
            # בדיקה אם המשתמש קיים
            existing_user = User.query.filter_by(username=username).first()
            if existing_user:
                return False
            
            # יצירת משתמש חדש
            user = User(
                username=username,
                email=email,
                password_hash=generate_password_hash(password),
                role='admin',
                is_active=True
            )
            
            db.session.add(user)
            db.session.commit()
            
            logger.info(f"Admin user created: {username}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create admin user: {e}")
            db.session.rollback()
            return False
    
    @staticmethod
    def create_business_user(username: str, password: str, email: str, business_id: int, 
                           can_access_phone: bool = True, can_access_whatsapp: bool = True) -> bool:
        """יצירת משתמש עסק עם הרשאות ספציפיות"""
        try:
            from models import User
            
            existing_user = User.query.filter_by(username=username).first()
            if existing_user:
                return False
            
            user = User(
                username=username,
                email=email,
                password_hash=generate_password_hash(password),
                role='business',
                business_id=business_id,
                is_active=True,
                can_access_phone=can_access_phone,
                can_access_whatsapp=can_access_whatsapp,
                can_manage_business=False  # רק המנהל יכול לנהל עסקים
            )
            
            db.session.add(user)
            db.session.commit()
            
            logger.info(f"Business user created: {username} for business {business_id} "
                       f"(Phone: {can_access_phone}, WhatsApp: {can_access_whatsapp})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create business user: {e}")
            db.session.rollback()
            return False
    
    @staticmethod
    def authenticate_user(username: str, password: str, client_ip: str = ""):
        """אימות משתמש עם הגבלת ניסיונות"""
        try:
            # בדיקת הגבלת ניסיונות
            attempt_key = f"{client_ip}:{username}" if client_ip else username
            current_time = datetime.now()
            
            if attempt_key in login_attempts:
                attempts, last_attempt = login_attempts[attempt_key]
                # אם עברה דקה - אפס ניסיונות
                if (current_time - last_attempt).seconds > 60:
                    del login_attempts[attempt_key]
                # אם יש יותר מ-3 ניסיונות בדקה האחרונה
                elif attempts >= 3:
                    logger.warning(f"Too many login attempts for {username} from {client_ip}")
                    return None
            
            from models import User
            user = User.query.filter_by(username=username, is_active=True).first()
            
            if user and check_password_hash(user.password_hash, password):
                # ניקוי ניסיונות לא מוצלחים
                if attempt_key in login_attempts:
                    del login_attempts[attempt_key]
                
                # עדכון זמן התחברות אחרון
                user.last_login = datetime.utcnow()
                db.session.commit()
                
                # שמירה ב-session
                from flask import session
                session['user_id'] = user.id
                session['username'] = user.username
                session.permanent = True
                
                logger.info(f"User authenticated: {username} from {client_ip}")
                return user
            else:
                # רישום ניסיון כושל
                if attempt_key not in login_attempts:
                    login_attempts[attempt_key] = [1, current_time]
                else:
                    attempts, _ = login_attempts[attempt_key]
                    login_attempts[attempt_key] = [attempts + 1, current_time]
                
                logger.warning(f"Authentication failed for: {username} from {client_ip}")
                return None
                
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return None
    
    @staticmethod
    def get_current_user():
        """קבלת המשתמש הנוכחי"""
        try:
            user_id = session.get('user_id')
            if not user_id:
                return None
            
            from models import User
            return User.query.get(user_id)
            
        except Exception as e:
            logger.error(f"Error getting current user: {e}")
            return None
    
    @staticmethod
    def logout_user():
        """יציאה מהמערכת"""
        try:
            username = session.get('username', 'Unknown')
            session.clear()
            logger.info(f"User logged out: {username}")
            return True
            
        except Exception as e:
            logger.error(f"Logout error: {e}")
            return False

def login_required(f):
    """דקורטור שמחייב התחברות - DISABLED FOR DIRECT ACCESS"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Skip authentication completely - direct access allowed
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """דקורטור שמחייב הרשאות מנהל"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        current_user = AuthService.get_current_user()
        if not current_user or current_user.role != 'admin':
            flash('נדרשות הרשאות מנהל', 'error')
            return redirect(url_for('index'))
        
        return f(*args, **kwargs)
    return decorated_function

def business_required(f):
    """דקורטור שמחייב הרשאות עסק"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        current_user = AuthService.get_current_user()
        if not current_user or current_user.role not in ['admin', 'business']:
            flash('נדרשות הרשאות עסק', 'error')
            return redirect(url_for('index'))
        
        return f(*args, **kwargs)
    return decorated_function

def check_business_access(resource_business_id: int) -> bool:
    """Task 5: Check if current user can access specific business data"""
    current_user = AuthService.get_current_user() 
    if not current_user:
        return False
    
    # Admin can access all businesses
    if current_user.role == 'admin':
        return True
    
    # Business users can only access their own business
    if current_user.role == 'business':
        has_access = current_user.business_id == resource_business_id
        logger.info(f"🔐 Business access check: user {current_user.username} business_id={current_user.business_id} vs resource_business_id={resource_business_id} -> {has_access}")
        return has_access
    
    return False