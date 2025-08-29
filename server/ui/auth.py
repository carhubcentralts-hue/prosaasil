"""
Authentication helpers for UI
Session management and role decorators
"""
from flask import session, request, redirect, url_for, g, current_app
from functools import wraps

def load_current_user():
    """Load current user from session before each request"""
    # Check new auth system first
    g.user = session.get('al_user') or session.get('user')
    g.token = session.get('al_token') or session.get('token')
    
    # Debug logging
    if request.path.startswith('/app/'):
        print(f"🔍 AUTH CHECK for {request.path}:")
        print(f"   Session keys: {list(session.keys())}")
        print(f"   g.user: {g.user}")
        print(f"   al_user in session: {'al_user' in session}")
        if 'al_user' in session:
            print(f"   al_user value: {session['al_user']}")
    
    return g.user

def require_roles(*roles):
    """Decorator to require specific roles"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not g.user:
                return redirect("/login")
            
            user_role = g.user.get('role')
            if user_role not in roles:
                return redirect("/login")
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def require_login(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not g.user:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function