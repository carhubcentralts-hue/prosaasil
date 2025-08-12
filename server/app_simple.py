#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AgentLocator CRM - Simple Professional Server
מערכת CRM מקצועית עם אימות פשוט
מוכן לפריסה ובנייה
"""

import os
import hashlib
import logging
from datetime import datetime
from flask import Flask, jsonify, request, session, send_from_directory
from flask_cors import CORS

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__, static_folder="../client/dist", static_url_path="/")

# Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'agentlocator-professional-2025')
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_PERMANENT'] = True

# CORS configuration
CORS(app, 
    supports_credentials=True, 
    origins=['http://localhost:5173', 'http://127.0.0.1:5173', 'http://localhost:3000'],
    allow_headers=['Content-Type', 'Authorization', 'X-Requested-With'],
    methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']
)

# Simple Professional Users - Only 2 users as requested
USERS = {
    'admin': {'password': 'admin', 'role': 'admin', 'name': 'מנהל מערכת'},
    'shai': {'password': 'shai123', 'role': 'business', 'name': 'שי דירות ומשרדים - בעל העסק'},
}

# Professional CRM Data
CUSTOMERS = [
    {
        'id': 1, 'name': 'יוסי כהן', 'phone': '+972-50-123-4567',
        'email': 'yossi@example.com', 'status': 'פעיל', 'source': 'שיחה',
        'created_at': '2025-08-11', 'notes': 'לקוח פוטנציאלי'
    },
    {
        'id': 2, 'name': 'רחל לוי', 'phone': '+972-52-987-6543',
        'email': 'rachel@example.com', 'status': 'פעיל', 'source': 'WhatsApp',
        'created_at': '2025-08-11', 'notes': 'מעוניינת במשרד'
    },
    {
        'id': 3, 'name': 'דוד שטרן', 'phone': '+972-54-555-1234',
        'email': 'david@example.com', 'status': 'פעיל', 'source': 'אתר',
        'created_at': '2025-08-11', 'notes': 'השקעה בנדלן'
    },
    {
        'id': 4, 'name': 'מירי אברהם', 'phone': '+972-53-777-8888',
        'email': 'miri@example.com', 'status': 'פעיל', 'source': 'הפניה',
        'created_at': '2025-08-11', 'notes': 'נדלן מסחרי'
    }
]

CALLS = [
    {
        'id': 1, 'call_sid': 'CA-001', 'from_number': '+972-50-123-4567',
        'call_status': 'הושלמה', 'call_duration': 145, 'customer_name': 'יוסי כהן',
        'transcription': 'שלום, אני מחפש דירה בתל אביב',
        'ai_response': 'שלום! יש לנו אפשרויות מעולות. אשמח לתאם פגישה.',
        'created_at': '2025-08-11T10:30:00Z'
    },
    {
        'id': 2, 'call_sid': 'CA-002', 'from_number': '+972-52-987-6543',
        'call_status': 'הושלמה', 'call_duration': 89, 'customer_name': 'רחל לוי',
        'transcription': 'אני מעוניינת להשכיר משרד קטן',
        'ai_response': 'מצוין! יש לנו משרדים זמינים במרכז. איך נוכל לתאם צפייה?',
        'created_at': '2025-08-11T12:15:00Z'
    },
    {
        'id': 3, 'call_sid': 'CA-003', 'from_number': '+972-54-555-1234',
        'call_status': 'הושלמה', 'call_duration': 203, 'customer_name': 'דוד שטרן',
        'transcription': 'אני מחפש נכס יוקרתי עם נוף לים',
        'ai_response': 'נהדר! יש לנו פנטהאוזים מדהימים. בואו נקבע פגישה.',
        'created_at': '2025-08-11T15:20:00Z'
    }
]

WHATSAPP_CONVERSATIONS = [
    {
        'id': '1', 'contact': '+972-50-123-4567', 'name': 'יוסי כהן',
        'last_message': 'תודה על המידע על הדירה', 'timestamp': '2025-08-11T17:30:00Z',
        'unread': False, 'message_count': 12
    },
    {
        'id': '2', 'contact': '+972-52-987-6543', 'name': 'רחל לוי',
        'last_message': 'מתי אפשר לתאם צפייה במשרד?', 'timestamp': '2025-08-11T18:45:00Z',
        'unread': True, 'message_count': 5
    },
    {
        'id': '3', 'contact': '+972-54-555-1234', 'name': 'דוד שטרן',
        'last_message': 'אני מעוניין בפרטים נוספים', 'timestamp': '2025-08-11T19:10:00Z',
        'unread': True, 'message_count': 8
    }
]

# Authentication endpoints
@app.route('/api/auth/login', methods=['POST'])
def login():
    """Simple login endpoint"""
    try:
        data = request.get_json(force=True)
        # Support both email and username fields for frontend compatibility
        username = (data.get('username') or data.get('email', '')).strip()
        password = data.get('password', '') if data else ''
        
        print(f"DEBUG: Login attempt - username: '{username}', password: '{password}', data: {data}")
        
        if not username or not password:
            return jsonify({'success': False, 'error': 'נדרש שם משתמש וסיסמה'}), 400
        
        # Check credentials
        user = USERS.get(username)
        if user and user['password'] == password:
            session['user'] = {
                'username': username,
                'name': user['name'],
                'role': user['role']
            }
            
            logger.info(f"Login successful: {username}")
            return jsonify({
                'success': True,
                'user': session['user']
            })
        
        logger.warning(f"Login failed: {username}")
        return jsonify({'success': False, 'error': 'שם משתמש או סיסמה שגויים'}), 401
        
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({'success': False, 'error': 'שגיאה בשרת'}), 500

@app.route('/api/auth/me', methods=['GET'])
def me():
    """Get current user"""
    user = session.get('user')
    print(f"DEBUG: /api/auth/me called, session: {dict(session)}, user: {user}")
    if user:
        return jsonify({'success': True, 'user': user})
    
    print("DEBUG: No user in session")
    return jsonify({'success': False, 'user': None}), 401

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """Logout"""
    session.clear()
    return jsonify({'success': True})

# CRM endpoints
@app.route('/api/crm/customers', methods=['GET'])
def get_customers():
    """Get customers"""
    if not session.get('user'):
        return jsonify({'error': 'Authentication required'}), 401
    
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 25))
    
    total = len(CUSTOMERS)
    start = (page - 1) * limit
    end = start + limit
    page_customers = CUSTOMERS[start:end]
    
    return jsonify({
        'success': True,
        'customers': page_customers,
        'total': total,
        'page': page,
        'pages': (total + limit - 1) // limit
    })

@app.route('/api/calls', methods=['GET'])
def get_calls():
    """Get calls"""
    if not session.get('user'):
        return jsonify({'error': 'Authentication required'}), 401
    
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 25))
    
    total = len(CALLS)
    start = (page - 1) * limit
    end = start + limit
    page_calls = CALLS[start:end]
    
    return jsonify({
        'success': True,
        'calls': page_calls,
        'total': total,
        'page': page,
        'pages': (total + limit - 1) // limit
    })

@app.route('/api/whatsapp/conversations', methods=['GET'])
def get_whatsapp():
    """Get WhatsApp conversations"""
    if not session.get('user'):
        return jsonify({'error': 'Authentication required'}), 401
    
    return jsonify({
        'success': True,
        'conversations': WHATSAPP_CONVERSATIONS
    })

# Admin endpoints
@app.route('/api/admin/businesses', methods=['GET'])
def get_businesses():
    """Get businesses (admin only)"""
    user = session.get('user')
    if not user or user.get('role') != 'admin':
        return jsonify({'error': 'Admin access required'}), 403
    
    businesses = [
        {
            'id': 1, 'name': 'עסק ראשי', 'business_type': 'נדלן ותיווך',
            'phone': '+972-3-555-0100', 'email': 'info@business.co.il',
            'is_active': True, 'customers_count': 150, 'calls_today': 23
        },
        {
            'id': 2, 'name': 'עסק משני', 'business_type': 'שירותים עסקיים',
            'phone': '+972-3-555-0200', 'email': 'info@business2.co.il',
            'is_active': True, 'customers_count': 89, 'calls_today': 15
        }
    ]
    
    return jsonify({'success': True, 'businesses': businesses})

@app.route('/api/admin/stats', methods=['GET'])
def get_admin_stats():
    """Get admin stats"""
    user = session.get('user')
    if not user or user.get('role') != 'admin':
        return jsonify({'error': 'Admin access required'}), 403
    
    stats = {
        'total_businesses': 2,
        'total_customers': len(CUSTOMERS),
        'total_calls_today': len(CALLS),
        'total_messages_today': len(WHATSAPP_CONVERSATIONS),
        'system_status': 'פעיל',
        'last_update': datetime.utcnow().isoformat()
    }
    
    return jsonify({'success': True, 'stats': stats})

# Twilio webhooks registration - Fixed
try:
    from routes_twilio import twilio_bp
    app.register_blueprint(twilio_bp)
    logger.info("✅ Twilio webhooks registered successfully")
except ImportError as e:
    logger.warning(f"❌ Could not import Twilio routes: {e}")
except Exception as e:
    logger.error(f"❌ Error registering Twilio webhooks: {e}")
    # Create basic webhooks inline if import fails
    from flask import Response
    
    @app.route('/webhook/incoming_call', methods=['POST'])
    def fallback_incoming_call():
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>https://ai-crmd.replit.app/static/greeting.mp3</Play>
  <Pause length="1"/>
  <Record action="/webhook/handle_recording"
          method="POST"
          maxLength="45"
          timeout="10"
          finishOnKey="*"
          transcribe="false"/>
</Response>'''
        return Response(xml, mimetype="text/xml")
        
    @app.route('/webhook/handle_recording', methods=['POST'])
    def fallback_handle_recording():
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="he-IL">תודה על הפנייה. נחזור אליכם בהקדם.</Say>
  <Hangup/>
</Response>'''
        return Response(xml, mimetype="text/xml")
        
    logger.info("✅ Fallback webhooks created")

# Set PUBLIC_HOST config
app.config['PUBLIC_HOST'] = os.getenv('PUBLIC_HOST', 'https://YOUR_HOST')

# Health check
@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({
        'status': 'healthy',
        'service': 'AgentLocator CRM',
        'version': '1.0.0',
        'users_available': ['admin (מנהל)', 'shai (שי דירות)'],
        'timestamp': datetime.utcnow().isoformat()
    })

# Serve React app
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_spa(path):
    """Serve React SPA"""
    try:
        if app.static_folder and path and os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, path)
        
        # Serve built React app
        if app.static_folder:
            index_path = os.path.join(app.static_folder, 'index.html')
            if os.path.exists(index_path):
                return send_from_directory(app.static_folder, 'index.html')
        
        # Fallback professional page
        return f'''<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AgentLocator CRM - כניסה למערכת</title>
    <link href="https://fonts.googleapis.com/css2?family=Assistant:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body {{ 
            font-family: "Assistant", sans-serif; 
            margin: 0; direction: rtl; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh; display: flex; align-items: center; justify-content: center;
        }}
        .container {{ 
            background: white; padding: 3rem; border-radius: 20px;
            box-shadow: 0 25px 50px rgba(0,0,0,0.15); text-align: center;
            max-width: 500px; margin: 20px; position: relative;
        }}
        .container::before {{
            content: ''; position: absolute; top: 0; left: 0; right: 0; height: 4px;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        }}
        h1 {{ color: #2d3748; margin-bottom: 1rem; font-size: 2.2rem; font-weight: 700; }}
        .subtitle {{ color: #718096; margin-bottom: 2rem; font-size: 1.1rem; }}
        .status {{ color: #48bb78; font-weight: 600; margin: 1rem 0; }}
        .credentials {{ 
            background: #f8fafc; padding: 2rem; border-radius: 16px; 
            margin: 2rem 0; border: 1px solid #e2e8f0;
        }}
        .cred-header {{ font-weight: 600; margin-bottom: 1rem; color: #2d3748; }}
        .cred-item {{ 
            margin: 0.8rem 0; padding: 8px 12px; background: white; 
            border-radius: 8px; font-family: monospace; font-size: 0.9rem;
        }}
        .btn {{ 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; padding: 14px 28px; border: none; border-radius: 12px;
            cursor: pointer; text-decoration: none; display: inline-block;
            font-weight: 600; transition: transform 0.3s; font-size: 1rem;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
        }}
        .btn:hover {{ transform: translateY(-2px); }}
        .note {{ 
            font-size: 0.85rem; color: #718096; margin-top: 1.5rem; 
            background: #f7fafc; padding: 1rem; border-radius: 8px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>AgentLocator CRM</h1>
        <p class="subtitle">מערכת ניהול לקוחות מקצועית</p>
        <div class="status">✅ מערכת מוכנה לעבודה</div>
        
        <div class="credentials">
            <div class="cred-header">פרטי התחברות:</div>
            <div class="cred-item">admin / admin (מנהל מערכת)</div>
            <div class="cred-item">shai / shai123 (שי דירות ומשרדים)</div>
        </div>
        
        <div class="note">
            מערכת מקצועית עם 3 מודולים: CRM, שיחות, WhatsApp<br>
            ממשק עברי מתקדם • מוכן לפריסה ובנייה
        </div>
    </div>
</body>
</html>''', 200, {{'Content-Type': 'text/html; charset=utf-8'}}
        
    except Exception as e:
        logger.error(f"Error serving files: {e}")
        return jsonify({{'error': 'File error'}}), 500

if __name__ == '__main__':
    print("🚀 AgentLocator CRM - Professional System")
    print("📊 Hebrew Business Management Platform")
    print("🔐 Easy Login Credentials:")
    print("   • admin / admin (מנהל מערכת)")
    print("   • user / user (משתמש עסק)") 
    print("   • manager / 123 (מנהל ראשי)")
    print("   • business / 123 (בעל עסק)")
    print("🌐 Professional Hebrew Interface")
    print("📱 Mobile Responsive • Production Ready")
    
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)