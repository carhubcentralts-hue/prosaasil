#!/usr/bin/env python3
"""
Professional auth server for Hebrew AI Call Center CRM
Serves React auth frontend with proper API integration
"""

from flask import Flask, send_from_directory, send_file, jsonify, request
import os

app = Flask(__name__)

# Serve React build from auth-frontend/dist
@app.route('/auth')
@app.route('/auth/')
@app.route('/auth/<path:path>')
def serve_auth(path=None):
    """Serve React auth app"""
    return send_file('auth-frontend/dist/index.html')

@app.route('/auth/assets/<path:filename>')
def serve_auth_assets(filename):
    """Serve React auth assets"""
    return send_from_directory('auth-frontend/dist/assets', filename)

# API endpoints for auth
@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    """Handle login requests"""
    data = request.get_json()
    email = data.get('email', '')
    password = data.get('password', '')
    
    # Basic validation for demo
    if not email or not password:
        return jsonify({'error': 'נא למלא את כל השדות'}), 400
    
    # Mock authentication - replace with real auth
    if email == "admin@shai.co.il" and password == "admin123":
        return jsonify({
            'user': {'role': 'admin', 'email': email},
            'message': 'התחברות הצליחה'
        })
    elif email == "business@shai.co.il" and password == "business123":
        return jsonify({
            'user': {'role': 'business', 'email': email},
            'message': 'התחברות הצליחה'
        })
    else:
        return jsonify({'error': 'שם משתמש או סיסמה שגויים'}), 401

@app.route('/api/auth/forgot', methods=['POST'])
def auth_forgot():
    """Handle forgot password requests"""
    data = request.get_json()
    email = data.get('email', '')
    
    if not email:
        return jsonify({'error': 'נא הזן כתובת אימייל'}), 400
    
    # Always return success for security
    return jsonify({'message': 'אם האימייל קיים, נשלח קישור איפוס'})

@app.route('/api/auth/reset', methods=['POST'])
def auth_reset():
    """Handle password reset"""
    data = request.get_json()
    token = data.get('token', '')
    password = data.get('password', '')
    
    if not token or not password:
        return jsonify({'error': 'נתונים חסרים'}), 400
    
    if len(password) < 8:
        return jsonify({'error': 'הסיסמה חייבת להכיל לפחות 8 תווים'}), 400
    
    return jsonify({'message': 'הסיסמה עודכנה בהצלחה'})

# Health check
@app.route('/api/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok', 
        'message': 'Professional Hebrew Auth Server',
        'version': '1.0.0'
    })

# Redirect root to auth
@app.route('/')
def root():
    return send_file('auth-frontend/dist/index.html')

if __name__ == '__main__':
    print("🚀 Professional Hebrew Auth Server")
    print("📁 Frontend: auth-frontend/dist/")
    print("🎨 Glass morphism design with Hebrew RTL")
    print("🔐 API endpoints: /api/auth/*")
    
    # Check if build exists
    if os.path.exists('auth-frontend/dist/index.html'):
        print("✅ React build found")
    else:
        print("❌ React build not found - run: cd auth-frontend && npm run build")
        
    app.run(host='0.0.0.0', port=5000, debug=True)