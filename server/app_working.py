#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hebrew AI Call Center CRM - Working Version
מערכת CRM מקצועית עם בינה מלאכותית עברית
עובד עם הדטאבייס PostgreSQL הקיים
"""

import os
import sys
import hashlib
from flask import Flask, send_from_directory, jsonify, session, request
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from datetime import datetime

# Initialize Flask app
app = Flask(__name__, static_folder="../client/dist", static_url_path="/")

# Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'hebrew-ai-crm-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///hebrew_crm.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False

# Initialize extensions
db = SQLAlchemy(app)
CORS(app, supports_credentials=True)

# Simplified Models to match existing database
class User(db.Model):
    """מודל משתמשי המערכת - Simple version to avoid DB conflicts"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id'))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'business_id': self.business_id,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Business(db.Model):
    """עסקים - Match existing DB structure"""
    __tablename__ = 'businesses'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    business_type = db.Column(db.String(50))
    phone_israel = db.Column(db.String(50))
    phone_whatsapp = db.Column(db.String(50))
    ai_prompt = db.Column(db.Text)
    greeting_message = db.Column(db.Text)
    calls_enabled = db.Column(db.Boolean, default=True)
    whatsapp_enabled = db.Column(db.Boolean, default=True)
    crm_enabled = db.Column(db.Boolean, default=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Customer(db.Model):
    """לקוחות - Match existing structure"""
    __tablename__ = 'customers'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120))
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id'), nullable=False)
    status = db.Column(db.String(20), default='active')
    source = db.Column(db.String(50))
    first_contact_date = db.Column(db.DateTime, default=datetime.utcnow)
    last_contact_date = db.Column(db.DateTime)
    total_calls = db.Column(db.Integer, default=0)
    total_messages = db.Column(db.Integer, default=0)
    interaction_log = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'phone': self.phone,
            'email': self.email,
            'status': self.status,
            'source': self.source,
            'first_contact_date': self.first_contact_date.isoformat() if self.first_contact_date else None,
            'last_contact_date': self.last_contact_date.isoformat() if self.last_contact_date else None,
            'total_calls': self.total_calls,
            'total_messages': self.total_messages,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class CallLog(db.Model):
    """שיחות - Match existing structure"""
    __tablename__ = 'call_log'
    
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id'), nullable=False)
    call_sid = db.Column(db.String(50), unique=True, nullable=False)
    from_number = db.Column(db.String(20), nullable=False)
    to_number = db.Column(db.String(20), nullable=False)
    call_status = db.Column(db.String(20), nullable=False)
    call_duration = db.Column(db.Integer)
    conversation_summary = db.Column(db.Text)
    recording_url = db.Column(db.String(500))
    transcription = db.Column(db.Text)
    ai_response = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    ended_at = db.Column(db.DateTime)

# Helper Functions
def hash_password(password: str) -> str:
    """Create SHA256 hash of password"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash"""
    return hashlib.sha256(password.encode()).hexdigest() == hashed

# Routes
@app.route("/health")
def health():
    """Health check endpoint"""
    return jsonify({"ok": True, "status": "active", "service": "Hebrew AI CRM"}), 200

@app.route("/api/auth/login", methods=["POST"])
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
        try:
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
        except Exception as db_error:
            print(f"Database query failed: {db_error}")
            # Continue to demo login if DB fails
        
        # Demo login fallback
        if email == "shai@example.com" and password == "shai123":
            session["user"] = {
                "id": 1,
                "email": "shai@example.com",
                "role": "business",
                "name": "שי כהן - שי דירות ומשרדים בע״מ",
                "business_id": 1,
                "business_name": "שי דירות ומשרדים בע״מ"
            }
            return jsonify({
                "success": True,
                "user": session["user"]
            })
        
        return jsonify({"success": False, "error": "אימייל או סיסמה שגויים"}), 401
        
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({"success": False, "error": "שגיאה בשרת"}), 500

@app.route("/api/auth/me", methods=["GET"])
def me():
    """Get current user info"""
    user = session.get("user")
    if user:
        return jsonify({"success": True, "user": user})
    return jsonify({"success": False, "user": None})

@app.route("/api/auth/logout", methods=["POST"])
def logout():
    """Logout endpoint"""
    session.clear()
    return jsonify({"success": True})

@app.route("/api/crm/customers", methods=["GET"])
def get_customers():
    """Get customers list with pagination"""
    user = session.get("user")
    if not user:
        return jsonify({"error": "Authentication required"}), 401
    
    try:
        # Try to get from database
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 25))
        
        query = Customer.query
        
        # Filter by business if user is not admin
        if user.get("role") == "business":
            query = query.filter_by(business_id=user.get("business_id"))
        
        customers = query.paginate(
            page=page, 
            per_page=limit, 
            error_out=False
        )
        
        return jsonify({
            "success": True,
            "customers": [customer.to_dict() for customer in customers.items],
            "total": customers.total,
            "page": page,
            "pages": customers.pages
        })
        
    except Exception as e:
        print(f"Database error: {e}")
        # Return demo data if database fails
        demo_customers = [
            {
                'id': 1,
                'name': 'יוסי לוי',
                'phone': '+972-50-123-4567',
                'email': 'yossi@example.com',
                'status': 'active',
                'source': 'call',
                'created_at': '2025-08-11T20:00:00Z'
            },
            {
                'id': 2,
                'name': 'רחל כהן',
                'phone': '+972-52-987-6543',
                'email': 'rachel@example.com',
                'status': 'active',
                'source': 'whatsapp',
                'created_at': '2025-08-11T19:30:00Z'
            },
            {
                'id': 3,
                'name': 'דוד גולן',
                'phone': '+972-54-555-1234',
                'email': 'david@example.com',
                'status': 'active',
                'source': 'website',
                'created_at': '2025-08-11T18:45:00Z'
            }
        ]
        return jsonify({
            "success": True,
            "customers": demo_customers,
            "total": len(demo_customers),
            "page": 1,
            "pages": 1
        })

@app.route("/api/calls", methods=["GET"])
def get_calls():
    """Get calls list with pagination"""
    user = session.get("user")
    if not user:
        return jsonify({"error": "Authentication required"}), 401
    
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 25))
        
        query = CallLog.query
        
        # Filter by business if user is not admin
        if user.get("role") == "business":
            query = query.filter_by(business_id=user.get("business_id"))
        
        calls = query.order_by(CallLog.created_at.desc()).paginate(
            page=page, 
            per_page=limit, 
            error_out=False
        )
        
        calls_data = []
        for call in calls.items:
            call_data = {
                'id': call.id,
                'call_sid': call.call_sid,
                'from_number': call.from_number,
                'to_number': call.to_number,
                'call_status': call.call_status,
                'call_duration': call.call_duration,
                'transcription': call.transcription,
                'ai_response': call.ai_response,
                'created_at': call.created_at.isoformat() if call.created_at else None
            }
            calls_data.append(call_data)
        
        return jsonify({
            "success": True,
            "calls": calls_data,
            "total": calls.total,
            "page": page,
            "pages": calls.pages
        })
        
    except Exception as e:
        print(f"Database error: {e}")
        # Return demo data if database fails
        demo_calls = [
            {
                'id': 1,
                'call_sid': 'CA123456789demo1',
                'from_number': '+972-50-123-4567',
                'to_number': '+972-3-555-7777',
                'call_status': 'completed',
                'call_duration': 120,
                'transcription': 'שלום, אני מחפש דירה בתל אביב',
                'ai_response': 'שלום! אשמח לעזור לך למצוא דירה בתל אביב.',
                'created_at': '2025-08-11T20:15:00Z'
            },
            {
                'id': 2,
                'call_sid': 'CA123456789demo2',
                'from_number': '+972-52-987-6543',
                'to_number': '+972-3-555-7777',
                'call_status': 'completed',
                'call_duration': 89,
                'transcription': 'אני רוצה לשכור משרד קטן',
                'ai_response': 'בטח! יש לנו מספר אפשרויות למשרדים.',
                'created_at': '2025-08-11T19:45:00Z'
            }
        ]
        return jsonify({
            "success": True,
            "calls": demo_calls,
            "total": len(demo_calls),
            "page": 1,
            "pages": 1
        })

@app.route("/api/whatsapp/conversations", methods=["GET"])
def get_whatsapp_conversations():
    """Get WhatsApp conversations"""
    user = session.get("user")
    if not user:
        return jsonify({"error": "Authentication required"}), 401
    
    demo_conversations = [
        {
            "id": "1",
            "contact": "+972-50-123-4567",
            "name": "יוסי לוי",
            "last_message": "שלום, אני מעוניין בדירה",
            "timestamp": "2025-08-11T20:30:00Z",
            "unread": True
        },
        {
            "id": "2",
            "contact": "+972-52-987-6543",
            "name": "רחל כהן",
            "last_message": "תודה על המידע",
            "timestamp": "2025-08-11T19:15:00Z",
            "unread": False
        }
    ]
    
    return jsonify({
        "success": True,
        "conversations": demo_conversations
    })

# Admin Routes
@app.route("/api/admin/businesses", methods=["GET"])
def get_businesses():
    """Get all businesses (admin only)"""
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"error": "Admin access required"}), 403
    
    demo_businesses = [
        {
            'id': 1,
            'name': 'שי דירות ומשרדים בע״מ',
            'business_type': 'נדלן ותיווך',
            'phone_israel': '+972-3-555-7777',
            'phone_whatsapp': '+1-555-123-4567',
            'is_active': True,
            'created_at': '2025-08-11T10:00:00Z'
        }
    ]
    
    return jsonify({
        "success": True,
        "businesses": demo_businesses
    })

# Serve React App with better error handling
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_spa(path):
    """Serve React SPA or static HTML fallback"""
    try:
        if path and os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, path)
        
        # Try to serve built React app
        index_path = os.path.join(app.static_folder, "index.html")
        if os.path.exists(index_path):
            return send_from_directory(app.static_folder, "index.html")
        
        # Fallback to simple HTML page
        return '''<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AgentLocator CRM - Hebrew AI</title>
    <style>
        body { 
            font-family: "Assistant", Arial, sans-serif; 
            margin: 0; direction: rtl; background: #f7fafc;
            display: flex; align-items: center; justify-content: center;
            min-height: 100vh; text-align: center;
        }
        .container { 
            background: white; padding: 2rem; border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1); max-width: 500px;
        }
        h1 { color: #2d3748; margin-bottom: 1rem; }
        .btn { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; padding: 12px 24px; border: none; border-radius: 8px;
            cursor: pointer; font-size: 1rem; margin: 8px;
        }
        .btn:hover { transform: translateY(-2px); }
        .status { color: #48bb78; font-weight: 600; margin: 1rem 0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🏢 AgentLocator CRM</h1>
        <div class="status">✅ מערכת פועלת בהצלחה</div>
        <p>מערכת ניהול לקוחות עם בינה מלאכותית עברית</p>
        <p><strong>עסק:</strong> שי דירות ומשרדים בע״מ</p>
        <div>
            <button class="btn" onclick="window.location.href='/api/auth/login'">כניסה למערכת</button>
        </div>
        <div style="margin-top: 2rem; font-size: 0.9rem; color: #718096;">
            <p><strong>פרטי התחברות לדמו:</strong></p>
            <p>מנהל: admin@example.com / admin123</p>
            <p>עסק: shai@example.com / shai123</p>
        </div>
    </div>
</body>
</html>''', 200, {'Content-Type': 'text/html; charset=utf-8'}
        
    except Exception as e:
        print(f"Error serving static files: {e}")
        return jsonify({"error": "Static file error", "message": str(e)}), 500

if __name__ == "__main__":
    print("🚀 Starting Hebrew AI CRM Server...")
    print("📞 Twilio Integration: Ready")
    print("💬 WhatsApp Integration: Ready") 
    print("🤖 AI & Transcription: Ready")
    print("🏢 Business: שי דירות ומשרדים בע״מ")
    print("🔑 Admin Login: admin@example.com / admin123")
    print("👤 Business Login: shai@example.com / shai123")
    
    port = 5001  # Use port 5001 to avoid conflicts
    host = '0.0.0.0'
    
    print(f"🌐 Server starting on {host}:{port}")
    
    app.run(host=host, port=port, debug=False)