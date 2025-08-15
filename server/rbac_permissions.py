"""
RBAC - Role Based Access Control
Admin / Business / Agent permissions as per spec
"""
from functools import wraps
from flask import request, jsonify, session, g

# Role definitions
ADMIN_ROLE = "admin"
BUSINESS_ROLE = "business"  
AGENT_ROLE = "agent"

def get_current_user():
    """Get current user from session - mock for now"""
    # TODO: Replace with real session/JWT logic
    return {
        "id": 1,
        "role": ADMIN_ROLE,  # Mock as admin for development
        "business_id": 1,
        "name": "מנהל מערכת"
    }

def require_role(required_role):
    """Decorator to require specific role"""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = get_current_user()
            if not user:
                return jsonify({"error": "authentication required"}), 401
            
            if user["role"] != required_role and user["role"] != ADMIN_ROLE:
                return jsonify({"error": "insufficient permissions"}), 403
            
            g.current_user = user
            return fn(*args, **kwargs)
        return wrapper
    return decorator

def require_auth():
    """Basic authentication check"""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = get_current_user()
            if not user:
                return jsonify({"error": "authentication required"}), 401
            
            g.current_user = user
            return fn(*args, **kwargs)
        return wrapper
    return decorator

def scope_business_query(query):
    """Scope database query to current user's business"""
    user = get_current_user()
    if user["role"] == ADMIN_ROLE:
        return query  # Admin sees all
    
    # Business/Agent see only their business
    return query.filter_by(business_id=user["business_id"])

def can_access_business(business_id):
    """Check if user can access specific business"""
    user = get_current_user()
    return user["role"] == ADMIN_ROLE or user["business_id"] == business_id