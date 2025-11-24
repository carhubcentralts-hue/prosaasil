# server/authz.py
"""
Authorization helpers for role-based access control
BUILD 124: Updated to support new role structure (system_admin, owner, admin, agent)
"""
from functools import wraps
from flask import session, jsonify

def auth_required(fn):
    """Require authentication - user must be logged in"""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user"):
            return jsonify({"error": "unauthorized"}), 401
        return fn(*args, **kwargs)
    return wrapper

def roles_required(*roles):
    """
    Require specific roles
    
    Supported roles (BUILD 124):
    - system_admin: Global access to all businesses
    - owner: Full control of their business
    - admin: Limited business access
    - agent: CRM/calls only
    - business: Legacy role (kept for backward compatibility)
    - manager: Legacy role (kept for backward compatibility)
    """
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = session.get("user")
            if not user:
                return jsonify({"error":"unauthorized"}), 401
            if "role" not in user or user["role"] not in roles:
                return jsonify({"error":"forbidden", "message": f"Requires one of: {', '.join(roles)}, got: {user.get('role')}"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return deco

def owner_or_admin_required(fn):
    """Require owner, admin, or system_admin role"""
    return roles_required('system_admin', 'owner', 'admin')(fn)

def system_admin_required(fn):
    """Require system_admin role only"""
    return roles_required('system_admin')(fn)