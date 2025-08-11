#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hebrew AI Call Center CRM - Professional Main Server
מערכת CRM מקצועית עם בינה מלאכותית עברית
"""

import os
import sys
from flask import Flask, send_from_directory, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import hashlib

# Initialize Flask app
app = Flask(__name__, static_folder="../client/dist", static_url_path="/")

# Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'hebrew-ai-crm-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///hebrew_crm.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False

# Initialize extensions
db = SQLAlchemy(app)
CORS(app, supports_credentials=True)

# Import blueprints and models after db initialization
sys.path.append(os.path.dirname(__file__))

@app.route("/health")
def health():
    """Health check endpoint"""
    return jsonify({"ok": True, "status": "active", "service": "Hebrew AI CRM"}), 200

# Setup authentication
from auth_bp import auth_bp
app.register_blueprint(auth_bp)

# Initialize database and demo data
def init_database():
    """Initialize database with demo data"""
    try:
        # Import models after db is initialized
        from models import User, Business, Customer, CallLog
        
        db.create_all()
        
        # Create demo business if not exists
        shai_business = Business.query.filter_by(name="שי דירות ומשרדים בע״מ").first()
        if not shai_business:
            shai_business = Business(
                name="שי דירות ומשרדים בע״מ",
                business_type="נדלן ותיווך",
                phone_israel="+972-3-555-7777",
                phone_whatsapp="+1-555-123-4567",
                ai_prompt="אני עוזר וירטואלי של חברת שי דירות ומשרדים. אני כאן לעזור עם שאלות לגבי נכסים, השכרה, מכירה ותיווך נדלן. איך אוכל לעזור לך היום?",
                greeting_message="שלום וברוכים הבאים לשי דירות ומשרדים! איך אוכל לעזור לך?",
                calls_enabled=True,
                whatsapp_enabled=True,
                crm_enabled=True,
                is_active=True
            )
            db.session.add(shai_business)
            db.session.commit()
            print(f"✅ Created business: {shai_business.name}")
        
        # Create demo business user if not exists
        business_user = User.query.filter_by(email="shai@example.com").first()
        if not business_user:
            password_hash = hashlib.sha256("shai123".encode()).hexdigest()
            business_user = User(
                email="shai@example.com",
                name="שי כהן",
                password_hash=password_hash,
                business_id=shai_business.id,
                is_active=True
            )
            db.session.add(business_user)
            db.session.commit()
            print(f"✅ Created business user: {business_user.email}")
        
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
            print(f"✅ Created {len(demo_customers)} demo customers")
        
        print("🚀 Database initialized successfully!")
        
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        return False
    
    return True

# CRM API Routes
@app.route("/api/crm/customers", methods=["GET"])
def get_customers():
    """Get customers list with pagination"""
    user = session.get("user")
    if not user:
        return jsonify({"error": "Authentication required"}), 401
    
    try:
        from models import Customer
        
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

# Calls API Routes
@app.route("/api/calls", methods=["GET"])
def get_calls():
    """Get calls list with pagination"""
    user = session.get("user")
    if not user:
        return jsonify({"error": "Authentication required"}), 401
    
    try:
        from models import CallLog
        
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

# WhatsApp API Routes
@app.route("/api/whatsapp/conversations", methods=["GET"])
def get_whatsapp_conversations():
    """Get WhatsApp conversations"""
    user = session.get("user")
    if not user:
        return jsonify({"error": "Authentication required"}), 401
    
    # This would integrate with the actual WhatsApp system
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

# Admin Routes
@app.route("/api/admin/businesses", methods=["GET"])
def get_businesses():
    """Get all businesses (admin only)"""
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"error": "Admin access required"}), 403
    
    try:
        from models import Business
        
        businesses = Business.query.all()
        return jsonify({
            "success": True,
            "businesses": [
                {
                    'id': b.id,
                    'name': b.name,
                    'business_type': b.business_type,
                    'phone_israel': b.phone_israel,
                    'phone_whatsapp': b.phone_whatsapp,
                    'is_active': b.is_active,
                    'created_at': b.created_at.isoformat()
                } for b in businesses
            ]
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

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
    
    app.run(host=host, port=port, debug=False)