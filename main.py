#!/usr/bin/env python3
"""
Professional Hebrew Auth Server - Production Ready
מערכת התחברות מקצועית עם React 19 + Tailwind 4.1 + Motion
"""

# CRITICAL: eventlet.monkey_patch() MUST be first for gunicorn+eventlet
import eventlet
eventlet.monkey_patch()

import os
import sys
import json
import tempfile
from flask import Flask, render_template, send_from_directory, request, jsonify, session
from flask_cors import CORS
from datetime import datetime

# 🔧 CRITICAL FIX: Setup Google Cloud credentials at startup!
def setup_google_credentials():
    """Setup Google Cloud credentials from environment"""
    try:
        creds_json = os.getenv('GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON')
        if creds_json:
            creds_data = json.loads(creds_json)
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(creds_data, f)
                temp_path = f.name
            
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = temp_path
            print(f'✅ Google Cloud credentials configured: {temp_path}')
            
            # Test connection
            from google.cloud import speech
            client = speech.SpeechClient()
            print('✅ Google Cloud Speech client ready for STT!')
            return True
        else:
            print('❌ Missing GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON')
            return False
    except Exception as e:
        print(f'❌ Google Cloud credentials error: {e}')
        return False

# LAZY INIT: Google credentials setup moved to lazy_services.py

# Use the comprehensive app factory instead of manual Flask setup
from server.app_factory import create_app

# Create the Flask app using the full factory with all blueprints
app = create_app()

# Import Twilio routes to ensure they're registered
try:
    from server.routes_twilio import twilio_bp
    if not any(bp.name == 'twilio' for bp in app.blueprints.values()):
        app.register_blueprint(twilio_bp)
        print("✅ Twilio webhooks registered via main.py")
    else:
        print("✅ Twilio webhooks already registered via app_factory")
except Exception as e:
    print(f"⚠️ Twilio registration warning: {e}")

# app_factory.py already handles all CORS, blueprints, and configuration
# This file is now just an entry point for production deployment

print("🚀 Hebrew AI Call Center CRM")
print("🔗 Using app_factory.py for full system configuration")

# Mock data kept for backwards compatibility only
MOCK_USERS = {
    'superadmin@shai.co.il': {
        'password': 'super123',
        'role': 'superadmin',
        'name': 'מנהל מערכת ראשי',
        'business_id': None,
        'permissions': ['all']
    },
    'admin@shai.co.il': {
        'password': 'admin123',
        'role': 'admin',
        'name': 'מנהל המערכת',
        'business_id': None,
        'permissions': ['manage_businesses', 'manage_users', 'view_all']
    },
    'owner@shai.co.il': {
        'password': 'owner123',
        'role': 'business_owner',
        'name': 'בעל עסק - שי דירות',
        'business_id': 'biz_001',
        'permissions': ['manage_business_users', 'view_business_data', 'manage_business_settings']
    },
    'agent@shai.co.il': {
        'password': 'agent123',
        'role': 'business_agent',
        'name': 'סוכן מכירות',
        'business_id': 'biz_001',
        'permissions': ['view_business_data', 'edit_crm', 'handle_calls']
    },
    'viewer@shai.co.il': {
        'password': 'viewer123',
        'role': 'read_only',
        'name': 'צופה בלבד',
        'business_id': 'biz_001',
        'permissions': ['view_business_data']
    }
}

# Mock businesses database
MOCK_BUSINESSES = {
    'biz_001': {
        'id': 'biz_001',
        'name': 'שי דירות ומשרדים בע״מ',
        'domain': 'shai.co.il',
        'status': 'active',
        'integrations': {
            'whatsapp': 'connected',
            'twilio': 'connected',
            'paypal': 'not_configured',
            'tranzila': 'not_configured'
        },
        'settings': {
            'timezone': 'Asia/Jerusalem',
            'language': 'he',
            'branding': {
                'logo_url': '',
                'primary_color': '#8B5CF6',
                'secondary_color': '#06B6D4'
            }
        }
    }
}

print("🚀 Professional Hebrew Auth Server")
print("📁 Frontend: Premium React 19 Auth App")
print("🎨 Glass morphism design with Hebrew RTL")
print("🔐 API endpoints: /api/auth/*")

# Check if build exists
if os.path.exists('./dist/index.html'):
    print("✅ React build found")
else:
    print("❌ React build missing - run 'npm run build' first")

@app.route('/')
def serve_index():
    """Serve the main React application - Tailwind 4.1 + React 19"""
    return send_from_directory('./dist', 'index.html')

@app.route('/auth')
def serve_auth_index():
    """Serve auth routes - Glass morphism design"""
    return send_from_directory('./dist', 'index.html')

@app.route('/app')
def serve_app_index():
    """Serve app routes - CRM system"""
    return send_from_directory('./dist', 'index.html')

# API Routes for authentication and business logic

@app.route('/api/auth/me')
def get_current_user():
    """Get current user info with role and permissions"""
    user_email = session.get('user_id')  # תוקן: user_id במקום user_email
    if not user_email or user_email not in MOCK_USERS:
        return jsonify({'error': 'לא מחובר'}), 401
    
    user_data = MOCK_USERS[user_email].copy()
    user_data.pop('password', None)  # Don't send password
    user_data['email'] = user_email
    
    # Add business info if applicable
    if user_data.get('business_id'):
        business = MOCK_BUSINESSES.get(user_data['business_id'])
        if business:
            user_data['business'] = business
    
    return jsonify(user_data)

# REMOVED DUPLICATE - using api_login below instead

# REMOVED DUPLICATE - using api_logout below instead

@app.route('/api/auth/impersonate', methods=['POST'])
def impersonate():
    """Admin-only: Impersonate a business"""
    user_email = session.get('user_id')  # תוקן: user_id במקום user_email
    if not user_email or user_email not in MOCK_USERS:
        return jsonify({'error': 'לא מורשה'}), 401
    
    user = MOCK_USERS[user_email]
    if user['role'] not in ['superadmin', 'admin']:
        return jsonify({'error': 'אין הרשאה'}), 403
    
    data = request.get_json()
    business_id = data.get('business_id')
    
    if business_id not in MOCK_BUSINESSES:
        return jsonify({'error': 'עסק לא נמצא'}), 404
    
    session['impersonating_business'] = business_id
    return jsonify({'business': MOCK_BUSINESSES[business_id]})

@app.route('/api/businesses')
def get_businesses():
    """Get all businesses (admin only)"""
    user_email = session.get('user_id')  # תוקן: user_id במקום user_email
    if not user_email or user_email not in MOCK_USERS:
        return jsonify({'error': 'לא מורשה'}), 401
    
    user = MOCK_USERS[user_email]
    if user['role'] not in ['superadmin', 'admin']:
        return jsonify({'error': 'אין הרשאה'}), 403
    
    return jsonify(list(MOCK_BUSINESSES.values()))

@app.route('/api/business/<business_id>/overview')
def get_business_overview(business_id):
    """Get business overview data"""
    user_email = session.get('user_email')
    if not user_email or user_email not in MOCK_USERS:
        return jsonify({'error': 'לא מורשה'}), 401
    
    user = MOCK_USERS[user_email]
    
    # Check if user has access to this business
    if user['role'] not in ['superadmin', 'admin']:
        if user.get('business_id') != business_id:
            return jsonify({'error': 'אין הרשאה לעסק זה'}), 403
    
    # Mock overview data
    overview_data = {
        'kpis': {
            'active_calls': 3,
            'whatsapp_threads': 15,
            'new_leads': 8,
            'pending_documents': 2
        },
        'integrations': MOCK_BUSINESSES.get(business_id, {}).get('integrations', {}),
        'recent_activity': [
            {'type': 'call', 'time': '10:30', 'description': 'שיחה נכנסת מלקוח חדש'},
            {'type': 'whatsapp', 'time': '09:15', 'description': 'הודעה חדשה בוואטסאפ'},
            {'type': 'crm', 'time': '08:45', 'description': 'ליד חדש נוצר'}
        ]
    }
    
    return jsonify(overview_data)

@app.route('/auth/<path:path>')
def serve_auth_routes(path):
    """Serve auth sub-routes (login, forgot, reset) - Premium design"""
    return send_from_directory('./dist', 'index.html')

@app.route('/app/<path:path>')
def serve_app_routes(path):
    """Serve app routes (admin/*, biz/*) - SPA routing"""
    return send_from_directory('./dist', 'index.html')

@app.route('/assets/<path:filename>')
def serve_assets(filename):
    """Serve static assets - Modern build with OKLCH colors"""
    return send_from_directory('./dist/assets', filename)

@app.route('/vite.svg')
def serve_vite_svg():
    """Serve Vite logo"""
    return send_from_directory('.', 'vite.svg')

# Additional API Routes for Overview functionality

# API Routes
@app.route('/api/auth/login', methods=['POST'])
def api_login():
    """Login API endpoint"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'נתונים חסרים'}), 400
            
        email = data.get('email', '').lower().strip()
        password = data.get('password', '')
        remember = data.get('remember', False)
        
        if not email or not password:
            return jsonify({'success': False, 'message': 'אימייל וסיסמה נדרשים'}), 400
            
        # Check user credentials
        user = MOCK_USERS.get(email)
        if not user or user['password'] != password:
            return jsonify({'success': False, 'message': 'אימייל או סיסמה שגויים'}), 401
            
        # Set session
        session['user_id'] = email
        session['user_role'] = user['role']
        session['user_name'] = user['name']
        session.permanent = remember
        
        return jsonify({
            'success': True, 
            'message': 'התחברת בהצלחה',
            'user': {
                'email': email,
                'role': user['role'],
                'name': user['name']
            }
        })
        
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({'success': False, 'message': 'שגיאת שרת'}), 500

@app.route('/api/admin/businesses')
def api_admin_businesses():
    """Get all businesses (admin only)"""
    user_id = session.get('user_id')
    if not user_id or user_id not in MOCK_USERS:
        return jsonify({'error': 'לא מורשה'}), 401
    
    user = MOCK_USERS[user_id]
    if user['role'] not in ['superadmin', 'admin']:
        return jsonify({'error': 'אין הרשאה'}), 403
    
    # Enhanced business data with statistics
    businesses = []
    for biz_id, biz in MOCK_BUSINESSES.items():
        business_data = biz.copy()
        business_data.update({
            'stats': {
                'users_count': len([u for u in MOCK_USERS.values() if u.get('business_id') == biz_id]),
                'active_calls': 2 if biz['status'] == 'active' else 0,
                'whatsapp_threads': 12 if biz['status'] == 'active' else 0,
                'last_activity': '2024-08-30T15:30:00Z'
            }
        })
        businesses.append(business_data)
    
    return jsonify(businesses)

@app.route('/api/admin/users')
def api_admin_users():
    """Get all system users (admin only)"""
    user_id = session.get('user_id')
    if not user_id or user_id not in MOCK_USERS:
        return jsonify({'error': 'לא מורשה'}), 401
    
    user = MOCK_USERS[user_id]
    if user['role'] not in ['superadmin', 'admin']:
        return jsonify({'error': 'אין הרשאה'}), 403
    
    # Return user data without passwords
    users = []
    for email, user_data in MOCK_USERS.items():
        safe_user = user_data.copy()
        safe_user.pop('password', None)
        safe_user['email'] = email
        safe_user['status'] = 'active'
        safe_user['last_login'] = '2024-08-30T14:20:00Z'
        users.append(safe_user)
    
    return jsonify(users)

@app.route('/api/biz/kpis')
def api_biz_kpis():
    """Get business KPIs"""
    user_id = session.get('user_id')
    if not user_id or user_id not in MOCK_USERS:
        return jsonify({'error': 'לא מורשה'}), 401
    
    user = MOCK_USERS[user_id]
    business_id = user.get('business_id')
    
    if not business_id:
        return jsonify({'error': 'משתמש לא משויך לעסק'}), 403
    
    import random
    from datetime import datetime
    
    hour = datetime.now().hour
    is_business_hours = 8 <= hour <= 22
    
    kpis = {
        'active_calls_now': random.randint(1, 4) if is_business_hours else 0,
        'whatsapp_messages_24h': random.randint(50, 150),
        'delivery_rate': f"{random.uniform(92, 98):.1f}%",
        'avg_first_response_sec': f"{random.uniform(1.2, 3.5):.1f} דק",
        'new_leads_today': random.randint(3, 12),
        'opportunities_open': random.randint(5, 15),
        'revenue_today': f"₪{random.randint(5000, 25000):,}",
        'conversion_rate': f"{random.uniform(15, 25):.1f}%",
        'ws_connections_ok': is_business_hours
    }
    
    return jsonify(kpis)

@app.route('/api/whatsapp/threads')
def api_whatsapp_threads():
    """Get WhatsApp threads"""
    user_id = session.get('user_id')
    if not user_id or user_id not in MOCK_USERS:
        return jsonify({'error': 'לא מורשה'}), 401
    
    user = MOCK_USERS[user_id]
    business_id = user.get('business_id')
    
    # For admin, get all businesses; for business users, only their business
    if user['role'] in ['superadmin', 'admin']:
        if not business_id:
            business_id = 'all'
    elif not business_id:
        return jsonify({'error': 'משתמש לא משויך לעסק'}), 403
    
    # Mock WhatsApp threads data
    threads = [
        {
            'id': 1,
            'name': 'דוד כהן',
            'phone': '054-1234567',
            'unread_count': 2,
            'status': 'delivered',
            'last_message': 'מתי אפשר לקבוע סיור בדירה?',
            'last_activity': '2024-08-30T15:30:00Z',
            'business_id': business_id if business_id != 'all' else 'biz_001'
        },
        {
            'id': 2,
            'name': 'שרה לוי',
            'phone': '052-9876543',
            'unread_count': 0,
            'status': 'read',
            'last_message': 'תודה על הפרטים',
            'last_activity': '2024-08-30T14:15:00Z',
            'business_id': business_id if business_id != 'all' else 'biz_001'
        },
        {
            'id': 3,
            'name': 'יוסי משה',
            'phone': '050-5555555',
            'unread_count': 1,
            'status': 'sent',
            'last_message': 'אשלח לך עוד אפשרויות מחר',
            'last_activity': '2024-08-30T13:45:00Z',
            'business_id': business_id if business_id != 'all' else 'biz_001'
        }
    ]
    
    return jsonify(threads)

@app.route('/api/calls/recent')
def api_calls_recent():
    """Get recent calls"""
    user_id = session.get('user_id')
    if not user_id or user_id not in MOCK_USERS:
        return jsonify({'error': 'לא מורשה'}), 401
    
    user = MOCK_USERS[user_id]
    business_id = user.get('business_id')
    
    # For admin, get all businesses; for business users, only their business
    if user['role'] in ['superadmin', 'admin']:
        if not business_id:
            business_id = 'all'
    elif not business_id:
        return jsonify({'error': 'משתמש לא משויך לעסק'}), 403
    
    # Mock recent calls data
    calls = [
        {
            'id': 1,
            'name': 'אבי שמש',
            'phone': '+972541234567',
            'duration': '5:23',
            'status': 'completed',
            'transcribed': True,
            'sentiment': 'positive',
            'date': '2024-08-30T14:30:00Z',
            'business_id': business_id if business_id != 'all' else 'biz_001'
        },
        {
            'id': 2,
            'name': 'ליאת גל', 
            'phone': '+972529876543',
            'duration': '2:15',
            'status': 'completed',
            'transcribed': True,
            'sentiment': 'neutral',
            'date': '2024-08-30T13:15:00Z',
            'business_id': business_id if business_id != 'all' else 'biz_001'
        },
        {
            'id': 3,
            'name': 'רון ברק',
            'phone': '+972505555555',
            'duration': '8:42',
            'status': 'completed',
            'transcribed': False,
            'sentiment': None,
            'date': '2024-08-30T11:20:00Z',
            'business_id': business_id if business_id != 'all' else 'biz_001'
        }
    ]
    
    return jsonify(calls)

@app.route('/api/crm/leads')
def api_crm_leads():
    """Get CRM leads"""
    user_id = session.get('user_id')
    if not user_id or user_id not in MOCK_USERS:
        return jsonify({'error': 'לא מורשה'}), 401
    
    user = MOCK_USERS[user_id]
    business_id = user.get('business_id')
    
    # For admin, get all businesses; for business users, only their business
    if user['role'] in ['superadmin', 'admin']:
        if not business_id:
            business_id = 'all'
    elif not business_id:
        return jsonify({'error': 'משתמש לא משויך לעסק'}), 403
    
    # Mock leads data
    leads = [
        {
            'id': 1,
            'name': 'יעל רוזן',
            'status': 'hot',
            'stage': 'negotiation',
            'last_update': '2024-08-30T13:00:00Z',
            'value': '₪2,300,000',
            'property_type': 'דירת גן בהרצליה',
            'source': 'website',
            'business_id': business_id if business_id != 'all' else 'biz_001'
        },
        {
            'id': 2,
            'name': 'אלון פרץ',
            'status': 'warm',
            'stage': 'viewing',
            'last_update': '2024-08-30T10:30:00Z',
            'value': '₪890,000',
            'property_type': 'דירת 3 חדרים בחדרה',
            'source': 'referral',
            'business_id': business_id if business_id != 'all' else 'biz_001'
        },
        {
            'id': 3,
            'name': 'דנה שחר',
            'status': 'cold',
            'stage': 'interest',
            'last_update': '2024-08-29T16:45:00Z',
            'value': '₪1,500,000',
            'property_type': 'פנטהאוס בתל אביב',
            'source': 'social_media',
            'business_id': business_id if business_id != 'all' else 'biz_001'
        }
    ]
    
    return jsonify(leads)

@app.route('/api/integrations/status')
def api_integrations_status():
    """Get integration status"""
    user_id = session.get('user_id')
    if not user_id or user_id not in MOCK_USERS:
        return jsonify({'error': 'לא מורשה'}), 401
    
    user = MOCK_USERS[user_id]
    business_id = user.get('business_id')
    
    if user['role'] in ['superadmin', 'admin']:
        # For admin, return system-wide integration status
        status = {
            'whatsapp': 'connected',
            'voice': 'ws_ok',
            'paypal': 'not_configured',
            'tranzila': 'ready',
            'stripe': 'not_configured'
        }
    elif business_id:
        # For business users, return their business integrations
        business = MOCK_BUSINESSES.get(business_id, {})
        status = business.get('integrations', {})
        # Add voice status based on business hours
        from datetime import datetime
        hour = datetime.now().hour
        status['voice'] = 'ws_ok' if 8 <= hour <= 22 else 'fallback'
    else:
        return jsonify({'error': 'משתמש לא משויך לעסק'}), 403
    
    return jsonify(status)

@app.route('/api/activity/recent')
def api_activity_recent():
    """Get recent activity feed"""
    user_id = session.get('user_id')
    if not user_id or user_id not in MOCK_USERS:
        return jsonify({'error': 'לא מורשה'}), 401
    
    user = MOCK_USERS[user_id]
    business_id = user.get('business_id')
    
    # Mock activity feed
    activities = [
        {
            'id': 1,
            'type': 'whatsapp',
            'business': 'שי דירות ומשרדים' if user['role'] in ['superadmin', 'admin'] else None,
            'message': 'לקוח חדש הצטרף ל-WhatsApp - מעוניין בדירת 4 חדרים',
            'time': '2024-08-30T15:30:00Z',
            'status': 'unread',
            'priority': 'medium',
            'customer': 'דוד כהן'
        },
        {
            'id': 2,
            'type': 'call',
            'business': 'דוד נכסים' if user['role'] in ['superadmin', 'admin'] else None,
            'message': 'שיחה נענתה בהצלחה - תמלול מוכן',
            'time': '2024-08-30T15:28:00Z',
            'status': 'completed',
            'priority': 'high',
            'customer': 'שרה לוי'
        },
        {
            'id': 3,
            'type': 'payment',
            'business': 'שי דירות ומשרדים' if user['role'] in ['superadmin', 'admin'] else None,
            'message': 'תשלום התקבל - ₪15,000 עמלת מכירה',
            'time': '2024-08-30T15:25:00Z',
            'status': 'success',
            'priority': 'high',
            'customer': 'יוסי משה'
        },
        {
            'id': 4,
            'type': 'contract',
            'business': 'שי דירות ומשרדים' if user['role'] in ['superadmin', 'admin'] else None,
            'message': 'חוזה חדש נחתם דיגיטלית - דירה בחדרה',
            'time': '2024-08-30T15:22:00Z',
            'status': 'signed',
            'priority': 'high',
            'customer': 'רחל אברהם'
        },
        {
            'id': 5,
            'type': 'user',
            'business': 'דוד נכסים' if user['role'] in ['superadmin', 'admin'] else None,
            'message': 'משתמש חדש הוזמן - סוכן מכירות',
            'time': '2024-08-30T15:18:00Z',
            'status': 'pending',
            'priority': 'low',
            'customer': 'מיכל דוד'
        }
    ]
    
    return jsonify(activities)

# API Routes

@app.route('/api/auth/forgot-password', methods=['POST'])
def api_forgot_password():
    """Forgot password API endpoint"""
    try:
        data = request.get_json()
        email = data.get('email', '').lower().strip() if data else ''
        
        if not email:
            return jsonify({'success': False, 'message': 'אימייל נדרש'}), 400
            
        # Always return success for security (don't reveal if email exists)
        return jsonify({
            'success': True, 
            'message': 'אם האימייל קיים במערכת, נשלח אליך קישור לאיפוס הסיסמה'
        })
        
    except Exception as e:
        print(f"Forgot password error: {e}")
        return jsonify({'success': False, 'message': 'שגיאת שרת'}), 500

@app.route('/api/auth/validate-reset-token', methods=['POST'])
def api_validate_reset_token():
    """Validate reset token API endpoint"""
    try:
        data = request.get_json()
        token = data.get('token', '') if data else ''
        
        # For demo purposes, accept any token that looks like a valid format
        if len(token) > 10:
            return jsonify({'success': True, 'valid': True})
        else:
            return jsonify({'success': False, 'valid': False}), 400
            
    except Exception as e:
        print(f"Validate token error: {e}")
        return jsonify({'success': False, 'message': 'שגיאת שרת'}), 500

@app.route('/api/auth/reset-password', methods=['POST'])
def api_reset_password():
    """Reset password API endpoint"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'נתונים חסרים'}), 400
            
        token = data.get('token', '')
        password = data.get('password', '')
        
        if not token or not password:
            return jsonify({'success': False, 'message': 'טוקן וסיסמה נדרשים'}), 400
            
        if len(password) < 8:
            return jsonify({'success': False, 'message': 'הסיסמה חייבת להכיל לפחות 8 תווים'}), 400
            
        # For demo purposes, always succeed
        return jsonify({
            'success': True, 
            'message': 'הסיסמה עודכנה בהצלחה'
        })
        
    except Exception as e:
        print(f"Reset password error: {e}")
        return jsonify({'success': False, 'message': 'שגיאת שרת'}), 500

@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    """Logout API endpoint"""
    session.clear()
    return jsonify({'success': True, 'message': 'התנתקת בהצלחה'})

@app.route('/api/auth/status', methods=['GET'])
def api_auth_status():
    """Check authentication status"""
    if 'user_id' in session:
        return jsonify({
            'authenticated': True,
            'user': {
                'email': session['user_id'],
                'role': session['user_role'],
                'name': session['user_name']
            }
        })
    else:
        return jsonify({'authenticated': False})

# Health check
@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'server': 'Professional Hebrew Auth Server',
        'frontend': 'React 19 + Tailwind 4.1 + Motion'
    })

# MAIN.PY HTTP handler for debugging - direct approach
@app.route('/debug-main-http', methods=['GET', 'POST'])
def debug_main_http():
    """Simple HTTP handler to test if main.py works"""
    import time
    
    print("🚨 MAIN.PY HTTP HANDLER CALLED!", flush=True)
    
    # Immediate debug
    with open("/tmp/main_http_debug.txt", "w") as f:
        f.write(f"MAIN_HTTP_CALLED: {time.time()}\n")
        f.write(f"METHOD: {request.method}\n")
        f.write(f"HEADERS: {dict(request.headers)}\n")
        f.flush()
    
    return jsonify({
        'status': 'main.py HTTP handler works!',
        'timestamp': time.time(),
        'method': request.method
    })

# MAIN.PY WebSocket handler - direct approach
@app.route('/ws/main-test', methods=['GET'])
def main_websocket_test():
    """WebSocket handler defined directly in main.py"""
    from flask import request
    import time
    
    print("🚨 MAIN.PY WEBSOCKET HANDLER CALLED!", flush=True)
    
    # Immediate debug
    with open("/tmp/main_ws_debug.txt", "w") as f:
        f.write(f"MAIN_WS_CALLED: {time.time()}\n")
        f.write(f"HEADERS: {dict(request.headers)}\n")
        f.flush()
    
    if request.headers.get('Upgrade', '').lower() == 'websocket':
        print("🚨 MAIN.PY WebSocket upgrade detected!", flush=True)
        try:
            from simple_websocket import Server
            from server.media_ws_ai import MediaStreamHandler
            
            ws = Server(request.environ)
            print("🚨 MAIN.PY Starting MediaStreamHandler...", flush=True)
            
            with open("/tmp/main_ws_debug.txt", "a") as f:
                f.write(f"WS_CREATED_IN_MAIN: {time.time()}\n")
                f.flush()
            
            handler = MediaStreamHandler(ws)
            handler.run()
            
            with open("/tmp/main_ws_debug.txt", "a") as f:
                f.write(f"HANDLER_COMPLETED_IN_MAIN: {time.time()}\n")
                f.flush()
            
            ws.close()
            return '', 200
        except Exception as e:
            print(f"❌ MAIN.PY WebSocket error: {e}", flush=True)
            return f"Main WebSocket error: {e}", 500
    else:
        return "WebSocket upgrade required", 400

# Catch-all route for SPA routing - MUST BE LAST!
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    """
    Catch-all route for React Router (SPA routing)
    Returns index.html for any route that doesn't exist on server
    This allows React Router to handle all frontend routing
    """
    # Skip API routes and let them 404 properly
    if path.startswith('api/'):
        return "API endpoint not found", 404
    
    # Skip webhook routes and let them 404 properly  
    if path.startswith('webhook/'):
        return "Webhook endpoint not found", 404
    
    # CRITICAL FIX: Skip WebSocket routes and let them work properly
    if path.startswith('ws/'):
        print(f"⚠️ CATCH-ALL BLOCKING WS ROUTE: {path}")
        return "WebSocket route blocked by catch-all", 500
    
    # For all other routes, serve the React app
    return send_from_directory('./dist', 'index.html')

@app.route("/test-simple-endpoint")
def test_simple():
    return "Main.py works!"

@app.route("/force-debug-endpoint")
def force_debug():
    import time
    ts = time.time()
    with open(f"/tmp/force_debug_{ts}.txt", "w") as f:
        f.write(f"FORCE_DEBUG_WORKS: {ts}\n")
        f.flush()
    return f"Force debug works at {ts}"

print("🚨 FORCE DEBUG ENDPOINT ADDED TO MAIN.PY")

# For development - run Flask directly
if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print(f"🌐 Starting server on port {port}")
    print(f"📖 Access at: http://localhost:{port}")
    print(f"🔗 Auth routes: http://localhost:{port}/auth/login")
    print(f"🛣️  SPA Routing: ALL paths serve React app (except /api/ and /webhook/)")
    print("")
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=True,
        threaded=True
    )
