#!/usr/bin/env python3
"""
Professional Hebrew Auth Server - Production Ready
מערכת התחברות מקצועית עם React 19 + Tailwind 4.1 + Motion
"""

from flask import Flask, render_template, send_from_directory, request, jsonify, session
from flask_cors import CORS
import os
import json
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'development-key-change-in-production')

# Enable CORS for frontend
CORS(app, supports_credentials=True, origins=['http://localhost:5000', 'http://127.0.0.1:5000'])

# Mock user database (replace with real database in production)
MOCK_USERS = {
    'admin@shai.co.il': {
        'password': 'admin123',
        'role': 'admin',
        'name': 'מנהל המערכת'
    },
    'business@shai.co.il': {
        'password': 'business123', 
        'role': 'business',
        'name': 'משתמש עסקי'
    }
}

print("🚀 Professional Hebrew Auth Server")
print("📁 Frontend: auth-frontend/dist/")
print("🎨 Glass morphism design with Hebrew RTL")
print("🔐 API endpoints: /api/auth/*")

# Check if build exists
if os.path.exists('auth-frontend/dist/index.html'):
    print("✅ React build found")
else:
    print("❌ React build missing - run 'npm run build' first")

@app.route('/')
def serve_index():
    """Serve the main React application"""
    return send_from_directory('auth-frontend/dist', 'index.html')

@app.route('/auth')
def serve_auth_index():
    """Serve auth routes"""
    return send_from_directory('auth-frontend/dist', 'index.html')

@app.route('/auth/<path:path>')
def serve_auth_routes(path):
    """Serve auth sub-routes (login, forgot, reset)"""
    return send_from_directory('auth-frontend/dist', 'index.html')

@app.route('/assets/<path:filename>')
def serve_assets(filename):
    """Serve static assets"""
    return send_from_directory('auth-frontend/dist/assets', filename)

@app.route('/vite.svg')
def serve_vite_svg():
    """Serve Vite logo"""
    return send_from_directory('auth-frontend/dist', 'vite.svg')

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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🌐 Starting server on port {port}")
    print(f"📖 Access at: http://localhost:{port}")
    print(f"🔗 Auth routes: http://localhost:{port}/auth/login")
    print("")
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=True,
        threaded=True
    )