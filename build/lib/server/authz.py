# server/authz.py
from functools import wraps
from flask import session, jsonify

def auth_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user"):
            return jsonify({"error": "unauthorized"}), 401
        return fn(*args, **kwargs)
    return wrapper

def roles_required(*roles):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = session.get("user")
            if not user:
                return jsonify({"error":"unauthorized"}), 401
            if "role" not in user or user["role"] not in roles:
                return jsonify({"error":"forbidden"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return deco