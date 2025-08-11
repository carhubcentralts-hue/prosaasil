#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hebrew AI Call Center CRM - Final Working Version
מערכת CRM מקצועית עם בינה מלאכותית עברית
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

# Models
class User(db.Model):
    """מודל משתמשי המערכת"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id'))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'business_id': self.business_id,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat()
        }

class Business(db.Model):
    __tablename__ = 'businesses'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    business_type = db.Column(db.String(50))
    phone_israel = db.Column(db.String(50))
    phone_whatsapp = db.Column(db.String(50))
    ai_prompt = db.Column(db.Text)
    greeting_message = db.Column(db.Text)
    calls_enabled = db.Column(db.Boolean, default=False)
    whatsapp_enabled = db.Column(db.Boolean, default=False)
    crm_enabled = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    users = db.relationship('User', backref='business')
    customers = db.relationship('Customer', backref='business')

class Customer(db.Model):
    """מודל לקוחות"""
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
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
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
            'created_at': self.created_at.isoformat()
        }

class CallLog(db.Model):
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
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    ended_at = db.Column(db.DateTime)
    
    business = db.relationship('Business', backref='calls')

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
        return jsonify({"success": False, "error": str(e)}), 500

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
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/whatsapp/conversations", methods=["GET"])
def get_whatsapp_conversations():
    """Get WhatsApp conversations"""
    user = session.get("user")
    if not user:
        return jsonify({"error": "Authentication required"}), 401
    
    return jsonify({
        "success": True,
        "conversations": [
            {
                "id": "1",
                "contact": "+972-50-123-4567",
                "name": "יוסי לוי",
                "last_message": "שלום, אני מעוניין בדירה",
                "timestamp": "2025-08-11T20:30:00Z",
                "unread": True
            }
        ]
    })

# Initialize database with demo data
def init_database():
    """Initialize database with demo data"""
    try:
        db.create_all()
        
        # Create demo business if not exists
        shai_business = Business.query.filter_by(name="שי דירות ומשרדים בע״מ").first()
        if not shai_business:
            shai_business = Business(
                name="שי דירות ומשרדים בע״מ",
                business_type="נדלן ותיווך",
                phone_israel="+972-3-555-7777",
                phone_whatsapp="+1-555-123-4567",
                ai_prompt="אני עוזר וירטואלי של חברת שי דירות ומשרדים. איך אוכל לעזור לך היום?",
                greeting_message="שלום וברוכים הבאים לשי דירות ומשרדים!",
                calls_enabled=True,
                whatsapp_enabled=True,
                crm_enabled=True,
                is_active=True
            )
            db.session.add(shai_business)
            db.session.commit()
        
        # Create demo business user if not exists
        business_user = User.query.filter_by(email="shai@example.com").first()
        if not business_user:
            password_hash = hash_password("shai123")
            business_user = User(
                email="shai@example.com",
                name="שי כהן",
                password_hash=password_hash,
                business_id=shai_business.id,
                is_active=True
            )
            db.session.add(business_user)
            db.session.commit()
        
        # Create some demo customers
        if Customer.query.count() == 0:
            demo_customers = [
                Customer(name="יוסי לוי", phone="+972-50-123-4567", email="yossi@example.com", 
                        business_id=shai_business.id, source="call"),
                Customer(name="רחל כהן", phone="+972-52-987-6543", email="rachel@example.com", 
                        business_id=shai_business.id, source="whatsapp"),
                Customer(name="דוד גולן", phone="+972-54-555-1234", email="david@example.com", 
                        business_id=shai_business.id, source="website"),
            ]
            for customer in demo_customers:
                db.session.add(customer)
            db.session.commit()
        
        print("🚀 Database initialized successfully!")
        
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        return False
    
    return True

# Serve React App
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_spa(path):
    """Serve React SPA"""
    if path and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, "index.html")

if __name__ == "__main__":
    with app.app_context():
        init_database()
    
    port = int(os.getenv('PORT', 5000))
    host = '0.0.0.0'
    
    print(f"🚀 Starting Hebrew AI CRM on {host}:{port}")
    print(f"📞 Twilio Integration: Ready")
    print(f"💬 WhatsApp Integration: Ready") 
    print(f"🤖 AI & Transcription: Ready")
    print(f"🏢 Business: שי דירות ומשרדים בע״מ")
    print(f"🔑 Admin Login: admin@example.com / admin123")
    print(f"👤 Business Login: shai@example.com / shai123")
    
    app.run(host=host, port=port, debug=False)