"""
Authentication helpers for UI
Session management and role decorators
"""
from flask import session, request, redirect, url_for, g, current_app
from functools import wraps

def load_current_user():
    """Load current user from session before each request"""
    g.user = session.get('user')
    g.token = session.get('token')

def require_roles(*roles):
    """Decorator to require specific roles"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not g.user:
                return redirect(url_for('ui.login'))
            
            user_role = g.user.get('role')
            if user_role not in roles:
                return redirect(url_for('ui.login'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def require_login(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not g.user:
            return redirect(url_for('ui.login'))
        return f(*args, **kwargs)
    return decorated_function