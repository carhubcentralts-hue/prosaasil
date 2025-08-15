# server/auth_routes.py
from flask import Blueprint, request, jsonify, session
import hashlib

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

# Professional user database for CRM system
USERS = {
    "admin@shai.com": {
        "password_hash": hashlib.sha256("admin123".encode()).hexdigest(),
        "role": "admin",
        "name": "מנהל המערכת",
        "firstName": "מנהל",
        "lastName": "ראשי"
    },
    "admin@shai-realestate.co.il": {
        "password_hash": hashlib.sha256("admin123456".encode()).hexdigest(),
        "role": "admin", 
        "name": "מנהל ראשי",
        "firstName": "מנהל",
        "lastName": "ראשי"
    },
    "shai@shai-realestate.co.il": {
        "password_hash": hashlib.sha256("shai123".encode()).hexdigest(),
        "role": "business",
        "name": "שי כהן",
        "firstName": "שי",
        "lastName": "כהן"
    }
}

@auth_bp.route("/login", methods=["POST"])
def login():
    try:
        data = request.get_json()
        email = data.get("email", "").strip().lower()
        password = data.get("password", "")
        
        if not email or not password:
            return jsonify({"error": "Email and password required"}), 400
            
        user = USERS.get(email)
        if not user:
            return jsonify({"error": "Invalid credentials"}), 401
            
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        if password_hash != user["password_hash"]:
            return jsonify({"error": "Invalid credentials"}), 401
            
        # Set session with all required fields for frontend
        session["user"] = {
            "id": email.replace("@", "_").replace(".", "_"),
            "email": email,
            "firstName": user["firstName"],
            "lastName": user["lastName"],
            "role": user["role"],
            "businessId": None if user["role"] == "admin" else "shai_business_001",
            "isActive": True
        }
        
        return jsonify({
            "success": True,
            "user": session["user"]
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.pop("user", None)
    return jsonify({"success": True}), 200

@auth_bp.route("/me", methods=["GET"])
def me():
    user = session.get("user")
    if not user:
        return jsonify({"error": "Not authenticated"}), 401
    return jsonify(user), 200

@auth_bp.route("/check", methods=["GET"])
def check():
    """Check authentication status"""
    user = session.get("user")
    if not user:
        return jsonify({"authenticated": False}), 200
    return jsonify({"authenticated": True, "user": user}), 200