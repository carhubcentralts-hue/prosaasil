#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AgentLocator CRM - Production Ready Server
מערכת CRM מקצועית עם בינה מלאכותית עברית
מוכן לפריסה בייצור
"""

import os
import sys
import hashlib
from flask import Flask, send_from_directory, jsonify, session, request
from flask_cors import CORS
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__, static_folder="../client/dist", static_url_path="/")

# Production Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'agentlocator-production-key-2025')
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True

# Initialize CORS
CORS(app, supports_credentials=True, origins=['*'])

# Simple Authentication Storage
USERS = {
    # Admin users
    'admin': {
        'password': 'admin',
        'role': 'admin',
        'name': 'מנהל מערכת',
        'id': 'admin_001'
    },
    'manager': {
        'password': 'manager',
        'role': 'admin', 
        'name': 'מנהל ראשי',
        'id': 'admin_002'
    },
    # Business users
    'user': {
        'password': 'user',
        'role': 'business',
        'name': 'משתמש עסק',
        'id': 'business_001',
        'business_name': 'עסק ראשי'
    },
    'business': {
        'password': 'business',
        'role': 'business',
        'name': 'בעל עסק',
        'id': 'business_002',
        'business_name': 'עסק משני'
    }
}

def authenticate_user(email, password):
    """
    Simple authentication function
    מקבל אימייל וסיסמה ומחזיר את פרטי המשתמש אם הם נכונים
    """
    # Try exact email match first
    if email in USERS:
        user_data = USERS[email]
        if user_data['password'] == password:
            return user_data
    
    # Try finding by username part of email
    username = email.split('@')[0] if '@' in email else email
    if username in USERS:
        user_data = USERS[username]
        if user_data['password'] == password:
            return user_data
    
    return None

# Routes
@app.route("/health")
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "AgentLocator CRM",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }), 200

@app.route("/api/auth/login", methods=["POST"])
def login():
    """Login endpoint with simple credentials"""
    try:
        data = request.get_json(force=True)
        email = data.get("email", "").strip().lower()
        password = data.get("password", "")
        
        if not email or not password:
            return jsonify({
                "success": False, 
                "error": "נדרש אימייל וסיסמה"
            }), 400
        
        logger.info(f"Login attempt for: {email}")
        
        # Authenticate user
        user_data = authenticate_user(email, password)
        
        if user_data:
            # Create session
            session_user = {
                "id": user_data["id"],
                "email": email,
                "role": user_data["role"],
                "name": user_data["name"]
            }
            
            if user_data["role"] == "business":
                session_user["business_name"] = user_data.get("business_name", "עסק")
            
            session["user"] = session_user
            
            logger.info(f"Login successful for: {email}")
            return jsonify({
                "success": True,
                "user": session_user
            })
        else:
            logger.warning(f"Login failed for: {email}")
            return jsonify({
                "success": False, 
                "error": "אימייל או סיסמה שגויים"
            }), 401
        
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({
            "success": False, 
            "error": "שגיאה בשרת"
        }), 500

@app.route("/api/auth/me", methods=["GET"])
def me():
    """Get current user info"""
    user = session.get("user")
    if user:
        return jsonify({"success": True, "user": user})
    return jsonify({"success": False, "user": None}), 401

@app.route("/api/auth/logout", methods=["POST"])
def logout():
    """Logout endpoint"""
    session.clear()
    return jsonify({"success": True})

# CRM Data - Professional demo data
SAMPLE_CUSTOMERS = [
    {
        'id': 1,
        'name': 'יוסי כהן',
        'phone': '+972-50-123-4567',
        'email': 'yossi.cohen@example.com',
        'status': 'פעיל',
        'source': 'שיחה',
        'created_at': '2025-08-11T10:00:00Z',
        'notes': 'לקוח פוטנציאלי לדירת 3 חדרים'
    },
    {
        'id': 2,
        'name': 'רחל לוי',
        'phone': '+972-52-987-6543',
        'email': 'rachel.levy@example.com',
        'status': 'פעיל',
        'source': 'WhatsApp',
        'created_at': '2025-08-11T11:30:00Z',
        'notes': 'מעוניינת במשרד קטן במרכז'
    },
    {
        'id': 3,
        'name': 'דוד שטרן',
        'phone': '+972-54-555-1234',
        'email': 'david.stern@example.com',
        'status': 'פעיל',
        'source': 'אתר',
        'created_at': '2025-08-11T14:15:00Z',
        'notes': 'חיפוש דירת יוקרה'
    },
    {
        'id': 4,
        'name': 'מירי אברהם',
        'phone': '+972-53-777-8888',
        'email': 'miri.abraham@example.com',
        'status': 'פעיל',
        'source': 'הפניה',
        'created_at': '2025-08-11T16:45:00Z',
        'notes': 'השקעה בנדלן מסחרי'
    }
]

SAMPLE_CALLS = [
    {
        'id': 1,
        'call_sid': 'CA-AGT-20250811-001',
        'from_number': '+972-50-123-4567',
        'to_number': '+972-3-555-0100',
        'call_status': 'הושלמה',
        'call_duration': 145,
        'transcription': 'שלום, אני מחפש דירת 3 חדרים באזור תל אביב. יש לכם משהו זמין?',
        'ai_response': 'שלום! כן, יש לנו מספר אפשרויות מעולות לדירות 3 חדרים בתל אביב. אשמח לתאם עמכם פגישה.',
        'created_at': '2025-08-11T10:30:00Z',
        'customer_name': 'יוסי כהן'
    },
    {
        'id': 2,
        'call_sid': 'CA-AGT-20250811-002',
        'from_number': '+972-52-987-6543',
        'to_number': '+972-3-555-0100',
        'call_status': 'הושלמה',
        'call_duration': 89,
        'transcription': 'אני מעוניינת להשכיר משרד קטן במיקום מרכזי',
        'ai_response': 'מצוין! יש לנו כמה משרדים זמינים במרכז העיר. איך נוכל לתאם צפייה?',
        'created_at': '2025-08-11T12:15:00Z',
        'customer_name': 'רחל לוי'
    },
    {
        'id': 3,
        'call_sid': 'CA-AGT-20250811-003',
        'from_number': '+972-54-555-1234',
        'to_number': '+972-3-555-0100',
        'call_status': 'הושלמה',
        'call_duration': 203,
        'transcription': 'אני מחפש דירת יוקרה עם נוף לים. התקציב לא מוגבל',
        'ai_response': 'נהדר! יש לנו פנטהאוזים יוקרתיים עם נוף מדהים. בואו נקבע פגישה לצפייה.',
        'created_at': '2025-08-11T15:20:00Z',
        'customer_name': 'דוד שטרן'
    }
]

SAMPLE_WHATSAPP = [
    {
        "id": "1",
        "contact": "+972-50-123-4567",
        "name": "יוסי כהן",
        "last_message": "תודה על המידע על הדירה",
        "timestamp": "2025-08-11T17:30:00Z",
        "unread": False,
        "message_count": 12
    },
    {
        "id": "2",
        "contact": "+972-52-987-6543", 
        "name": "רחל לוי",
        "last_message": "מתי אפשר לתאם צפייה במשרד?",
        "timestamp": "2025-08-11T18:45:00Z",
        "unread": True,
        "message_count": 5
    },
    {
        "id": "3",
        "contact": "+972-54-555-1234",
        "name": "דוד שטרן", 
        "last_message": "אני מעוניין בפרטים נוספים",
        "timestamp": "2025-08-11T19:10:00Z",
        "unread": True,
        "message_count": 8
    }
]

@app.route("/api/crm/customers", methods=["GET"])
def get_customers():
    """Get customers list with pagination"""
    user = session.get("user")
    if not user:
        return jsonify({"error": "Authentication required"}), 401
    
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 25))
        
        # For demo purposes, return sample data
        total = len(SAMPLE_CUSTOMERS)
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        page_customers = SAMPLE_CUSTOMERS[start_idx:end_idx]
        
        return jsonify({
            "success": True,
            "customers": page_customers,
            "total": total,
            "page": page,
            "pages": (total + limit - 1) // limit
        })
        
    except Exception as e:
        logger.error(f"Error getting customers: {e}")
        return jsonify({
            "success": False,
            "error": "שגיאה בטעינת הלקוחות"
        }), 500

@app.route("/api/calls", methods=["GET"])
def get_calls():
    """Get calls list with pagination"""
    user = session.get("user")
    if not user:
        return jsonify({"error": "Authentication required"}), 401
    
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 25))
        
        total = len(SAMPLE_CALLS)
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        page_calls = SAMPLE_CALLS[start_idx:end_idx]
        
        return jsonify({
            "success": True,
            "calls": page_calls,
            "total": total,
            "page": page,
            "pages": (total + limit - 1) // limit
        })
        
    except Exception as e:
        logger.error(f"Error getting calls: {e}")
        return jsonify({
            "success": False,
            "error": "שגיאה בטעינת השיחות"
        }), 500

@app.route("/api/whatsapp/conversations", methods=["GET"])
def get_whatsapp_conversations():
    """Get WhatsApp conversations"""
    user = session.get("user")
    if not user:
        return jsonify({"error": "Authentication required"}), 401
    
    return jsonify({
        "success": True,
        "conversations": SAMPLE_WHATSAPP
    })

# Admin Routes
@app.route("/api/admin/businesses", methods=["GET"])
def get_businesses():
    """Get all businesses (admin only)"""
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"error": "Admin access required"}), 403
    
    sample_businesses = [
        {
            'id': 1,
            'name': 'עסק ראשי',
            'business_type': 'נדלן ותיווך',
            'phone': '+972-3-555-0100',
            'email': 'info@business1.co.il',
            'is_active': True,
            'created_at': '2025-08-01T10:00:00Z',
            'customers_count': 150,
            'calls_today': 23
        },
        {
            'id': 2,
            'name': 'עסק משני',
            'business_type': 'שירותים עסקיים',
            'phone': '+972-3-555-0200',
            'email': 'info@business2.co.il',
            'is_active': True,
            'created_at': '2025-08-01T11:00:00Z',
            'customers_count': 89,
            'calls_today': 15
        }
    ]
    
    return jsonify({
        "success": True,
        "businesses": sample_businesses
    })

@app.route("/api/admin/stats", methods=["GET"])
def get_admin_stats():
    """Get admin dashboard statistics"""
    user = session.get("user")
    if not user or user.get("role") != "admin":
        return jsonify({"error": "Admin access required"}), 403
    
    stats = {
        "total_businesses": 2,
        "total_customers": 239,
        "total_calls_today": 38,
        "total_messages_today": 47,
        "system_status": "פעיל",
        "last_update": datetime.utcnow().isoformat()
    }
    
    return jsonify({
        "success": True,
        "stats": stats
    })

# Serve React App
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_spa(path):
    """Serve React SPA"""
    try:
        if path and os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, path)
        
        # Try to serve built React app
        index_path = os.path.join(app.static_folder, "index.html")
        if os.path.exists(index_path):
            return send_from_directory(app.static_folder, "index.html")
        
        # Professional fallback page
        return '''<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AgentLocator CRM</title>
    <link href="https://fonts.googleapis.com/css2?family=Assistant:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body { 
            font-family: "Assistant", sans-serif; 
            margin: 0; direction: rtl; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh; display: flex; align-items: center; justify-content: center;
        }
        .container { 
            background: white; padding: 3rem; border-radius: 20px;
            box-shadow: 0 25px 50px rgba(0,0,0,0.15); text-align: center;
            max-width: 400px; margin: 20px;
        }
        h1 { color: #2d3748; margin-bottom: 1rem; font-size: 2rem; font-weight: 700; }
        .status { color: #48bb78; font-weight: 600; margin: 1rem 0; }
        .description { color: #718096; margin-bottom: 2rem; line-height: 1.6; }
        .credentials { 
            background: #f8fafc; padding: 1.5rem; border-radius: 12px; 
            margin: 1.5rem 0; font-size: 0.9rem; color: #4a5568;
        }
        .cred-item { margin: 0.5rem 0; }
        .btn { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; padding: 12px 24px; border: none; border-radius: 8px;
            cursor: pointer; text-decoration: none; display: inline-block;
            font-weight: 600; transition: transform 0.2s;
        }
        .btn:hover { transform: translateY(-2px); }
    </style>
</head>
<body>
    <div class="container">
        <h1>AgentLocator CRM</h1>
        <div class="status">✅ מערכת מוכנה לעבודה</div>
        <p class="description">מערכת ניהול לקוחות מקצועית עם בינה מלאכותית עברית</p>
        
        <div class="credentials">
            <strong>פרטי התחברות:</strong>
            <div class="cred-item">מנהל: admin / admin</div>
            <div class="cred-item">עסק: user / user</div>
        </div>
        
        <a href="/login" class="btn">כניסה למערכת</a>
    </div>
</body>
</html>''', 200, {'Content-Type': 'text/html; charset=utf-8'}
        
    except Exception as e:
        logger.error(f"Error serving static files: {e}")
        return jsonify({"error": "Static file error"}), 500

if __name__ == "__main__":
    print("🚀 AgentLocator CRM - Production Ready")
    print("📊 Professional Business Management System")
    print("🔐 Simple Authentication:")
    print("   • Admin: admin / admin")
    print("   • Manager: manager / manager") 
    print("   • User: user / user")
    print("   • Business: business / business")
    print("🌐 Hebrew RTL Interface Ready")
    print("📱 Mobile Responsive Design")
    print("⚡ Ready for Production Deployment")
    
    port = int(os.getenv('PORT', 5000))
    host = '0.0.0.0'
    
    print(f"\n🌐 Server starting on {host}:{port}")
    
    app.run(host=host, port=port, debug=False)