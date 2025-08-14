# server/auth_routes.py
from flask import Blueprint, request, jsonify, session
import hashlib

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

# Professional user database for שי דירות ומשרדים בע״מ
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
            
        # Set session
        session["user"] = {
            "email": email,
            "role": user["role"],
            "name": user["name"]
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
    return jsonify({"user": user}), 200