"""
Enterprise Security & Audit System
מערכת אבטחה ומעקב אנטרפרייז מתקדמת
"""
import os
import json
import hashlib
from datetime import datetime, timedelta
from flask import session, request, g, jsonify
from functools import wraps

class AuditLogger:
    """Professional audit logging system"""
    
    def __init__(self, app=None):
        self.app = app
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize audit logging"""
        app.audit_logger = self
        
    def log_action(self, action_type, resource, resource_id=None, details=None, user_id=None, business_id=None):
        """Log audit action with full context"""
        try:
            user = session.get('al_user', {})
            
            audit_entry = {
                'timestamp': datetime.now().isoformat(),
                'action_type': action_type,  # CREATE, UPDATE, DELETE, VIEW, IMPERSONATE
                'resource': resource,        # tenant, user, contact, invoice, contract
                'resource_id': resource_id,
                'user_id': user_id or user.get('id'),
                'user_email': user.get('email'),
                'user_role': user.get('role'),
                'business_id': business_id or user.get('business_id'),
                'ip_address': request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr),
                'user_agent': request.headers.get('User-Agent', ''),
                'endpoint': request.endpoint,
                'method': request.method,
                'details': details or {},
            }
            
            # Add payload hash for integrity
            payload_str = json.dumps(audit_entry, sort_keys=True, ensure_ascii=False)
            audit_entry['payload_hash'] = hashlib.sha256(payload_str.encode()).hexdigest()[:16]
            
            # Log to file (in production, send to proper logging service)
            log_file = os.path.join(os.path.dirname(__file__), '..', 'logs', 'audit.log')
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(audit_entry, ensure_ascii=False) + '\n')
                
            print(f"📋 AUDIT: {action_type} {resource} by {user.get('email', 'unknown')}")
            
        except Exception as e:
            print(f"❌ Audit logging error: {e}")

def audit_action(action_type, resource):
    """Decorator for audit logging"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                # Get resource ID from kwargs, args, or request
                resource_id = kwargs.get('id') or request.form.get('id') or request.args.get('id')
                
                # Execute the function first
                result = f(*args, **kwargs)
                
                # Log successful action
                if hasattr(g, 'audit_logger'):
                    g.audit_logger.log_action(action_type, resource, resource_id)
                
                return result
            except Exception as e:
                # Log failed action
                if hasattr(g, 'audit_logger'):
                    g.audit_logger.log_action(f"{action_type}_FAILED", resource, None, {'error': str(e)})
                raise
                
        return decorated_function
    return decorator

# REMOVED require_csrf_token - using SeaSurf only for CSRF protection per guidelines

class SessionSecurity:
    """Advanced session security management"""
    
    @staticmethod
    def rotate_session():
        """Rotate session ID while preserving user data"""
        if 'al_user' in session:
            user_data = dict(session['al_user'])
            session.clear()
            session['al_user'] = user_data
            session['_session_start'] = datetime.now().isoformat()
            # SeaSurf handles CSRF tokens - no manual _csrf_token needed
    
    @staticmethod
    def is_session_valid():
        """Check if current session is valid"""
        if 'al_user' not in session:
            return False
            
        last_activity = session.get('_last_activity')
        if last_activity:
            last_time = datetime.fromisoformat(last_activity)
            if datetime.now() - last_time > timedelta(hours=8):
                return False
                
        return True
    
    @staticmethod 
    def update_activity():
        """Update session activity timestamp"""
        if 'al_user' in session:
            session['_last_activity'] = datetime.now().isoformat()

def password_strength_check(password):
    """Enterprise password policy validation"""
    if not password or len(password) < 8:
        return False, "סיסמה חייבת להכיל לפחות 8 תווים"
        
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)
    
    if not (has_upper and has_lower and has_digit and has_special):
        return False, "סיסמה חייבת להכיל אותיות גדולות, קטנות, ספרה ותו מיוחד"
    
    return True, "סיסמה תקינה"

# Global audit logger instance
audit_logger = AuditLogger()