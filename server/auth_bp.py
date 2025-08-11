# server/auth_bp.py
from flask import Blueprint, request, jsonify, session
import os, hmac, hashlib
from models import User, Business, db

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

def hash_password(password: str) -> str:
    """Create SHA256 hash of password"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash"""
    return hmac.compare_digest(hash_password(password), hashed)

@auth_bp.route("/login", methods=["POST"])
def login():
    """Login endpoint for both admin and business users"""
    try:
        data = request.get_json(force=True)
        email = data.get("email", "").strip().lower()
        password = data.get("password", "")
        
        if not email or not password:
            return jsonify({"success": False, "error": "נדרש אימייל וסיסמה"}), 400
        
        # Check admin credentials first
        admin_email = os.getenv("ADMIN_EMAIL", "admin@example.com")
        admin_pass = os.getenv("ADMIN_PASS", "admin123")
        
        if email == admin_email.lower() and password == admin_pass:
            session["user"] = {
                "id": "admin",
                "email": admin_email,
                "role": "admin",
                "name": "מנהל מערכת"
            }
            return jsonify({
                "success": True,
                "user": session["user"]
            })
        
        # Check business users in database
        user = User.query.filter_by(email=email).first()
        if user and verify_password(password, user.password_hash):
            business = Business.query.filter_by(id=user.business_id).first()
            session["user"] = {
                "id": user.id,
                "email": user.email,
                "role": "business",
                "name": user.name,
                "business_id": user.business_id,
                "business_name": business.name if business else "עסק לא מוגדר"
            }
            return jsonify({
                "success": True,
                "user": session["user"]
            })
        
        return jsonify({"success": False, "error": "אימייל או סיסמה שגויים"}), 401
        
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({"success": False, "error": "שגיאה בשרת"}), 500

@auth_bp.route("/me", methods=["GET"])
def me():
    """Get current user info"""
    user = session.get("user")
    if user:
        return jsonify({"success": True, "user": user})
    return jsonify({"success": False, "user": None})

@auth_bp.route("/logout", methods=["POST"])
def logout():
    """Logout endpoint"""
    session.clear()
    return jsonify({"success": True})

@auth_bp.route("/check", methods=["GET"])
def check():
    """Check if user is authenticated"""
    user = session.get("user")
    return jsonify({"authenticated": user is not None, "user": user})

def require_auth(f):
    """Decorator to require authentication"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user"):
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)
    return decorated_function

def require_admin(f):
    """Decorator to require admin role"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = session.get("user")
        if not user or user.get("role") != "admin":
            return jsonify({"error": "Admin access required"}), 403
        return f(*args, **kwargs)
    return decorated_function