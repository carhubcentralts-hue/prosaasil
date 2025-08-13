#!/usr/bin/env python3
"""
Hebrew AI Call Center CRM - Professional Login System
"""
from flask import Flask, Response, request, send_from_directory, send_file
from flask_cors import CORS
import os

# Create Flask app
app = Flask(__name__, static_folder='client/dist', static_url_path='')
CORS(app)

# Simple in-line Flask routes to avoid import issues
def setup_routes(app):
    @app.route('/api/auth/login', methods=['POST'])
    def login():
        from flask import request, jsonify
        data = request.get_json()
        
        # Simple hardcoded auth for demo
        if data.get('email') == 'admin@shai-realestate.co.il' and data.get('password') == 'admin123456':
            user = {
                'id': '1',
                'email': 'admin@shai-realestate.co.il',
                'firstName': 'מנהל',
                'lastName': 'ראשי',
                'role': 'admin',
                'businessId': None,
                'isActive': True
            }
            return jsonify({'user': user, 'token': 'admin-token'})
        elif data.get('email') == 'manager@shai-realestate.co.il' and data.get('password') == 'business123456':
            user = {
                'id': '2',
                'email': 'manager@shai-realestate.co.il',
                'firstName': 'שי',
                'lastName': 'כהן',
                'role': 'business',
                'businessId': 'shai-offices',
                'isActive': True
            }
            return jsonify({'user': user, 'token': 'business-token'})
        else:
            return jsonify({'error': 'אימייל או סיסמא שגויים'}), 401
    
    @app.route('/api/auth/logout', methods=['POST'])
    def logout():
        from flask import jsonify
        return jsonify({'message': 'התנתקת בהצלחה'})
    
    @app.route('/api/auth/me', methods=['GET'])
    def auth_me():
        from flask import jsonify
        # For demo, return empty (not authenticated)
        return jsonify({'error': 'לא מחובר'}), 401
    
    # Keep existing webhook routes
    @app.route('/webhook/incoming_call', methods=['POST'])
    def incoming_call():
        from flask import Response
        PUBLIC_HOST = "https://ai-crmd.replit.app"
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>{PUBLIC_HOST}/static/voice_responses/greeting.mp3</Play>
  <Pause length="1"/>
  <Record action="/webhook/handle_recording"
          method="POST"
          maxLength="30"
          timeout="5"
          finishOnKey="*"
          transcribe="false"/>
</Response>"""
        return Response(xml, mimetype="text/xml")
    
    @app.route('/webhook/handle_recording', methods=['POST'])
    def handle_recording():
        from flask import Response
        PUBLIC_HOST = "https://ai-crmd.replit.app"
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>{PUBLIC_HOST}/static/voice_responses/listening.mp3</Play>
  <Hangup/>
</Response>"""
        return Response(xml, mimetype="text/xml")
    
    @app.route('/webhook/call_status', methods=['POST'])
    def call_status():
        return "OK", 200

print("🎯 Starting Hebrew AI Call Center with Professional Login System")

@app.route('/')
def serve_frontend():
    """Serve the React frontend"""
    try:
        return send_file('client/dist/index.html')
    except:
        return """<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>מערכת ניהול שיחות עברית AI</title>
    <style>
        body { 
            font-family: Arial, sans-serif; 
            text-align: center; 
            padding: 50px; 
            direction: rtl;
            background: white;
        }
    </style>
</head>
<body>
    <h1>מערכת ניהול שיחות עברית AI</h1>
    <p>מערכת התחברות מקצועית - שי דירות ומשרדים בע״מ</p>
    <p>הקוד נטען... אנא המתן</p>
</body>
</html>"""

# Catch-all route for SPA
@app.route('/<path:path>')
def serve_spa(path):
    """Serve SPA for all routes"""
    if path.startswith('api/') or path.startswith('webhook/') or path.startswith('static/'):
        # Let API routes handle themselves
        return Response('Not Found', 404)
    
    try:
        return send_file('client/dist/index.html')
    except:
        return serve_frontend()

if __name__ == '__main__':
    # Set up all routes
    setup_routes(app)
    
    print("✅ Professional Login System Ready")
    print("🔐 Admin: admin@shai-realestate.co.il / admin123456")
    print("🏢 Business: manager@shai-realestate.co.il / business123456")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=False)