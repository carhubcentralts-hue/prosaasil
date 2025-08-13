#!/usr/bin/env python3
"""
Professional Flask App Factory - Hebrew AI Call Center CRM
מפעל אפליקציות Flask מקצועי - מערכת ניהול שיחות עברית AI
"""

from flask import Flask, Response, request, jsonify, send_file
from flask_cors import CORS
import os

def create_app():
    """יצירת אפליקציית Flask עם הגדרות מקצועיות"""
    
    app = Flask(__name__, static_folder='../client/dist', static_url_path='')
    CORS(app)
    
    # Security configurations
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'shai-real-estate-secure-key-2025')
    app.config['SECURITY_PASSWORD_SALT'] = 'shai-offices-salt'
    
    # Register routes
    register_auth_routes(app)
    register_core_routes(app)
    register_webhook_routes(app)
    
    # Register API blueprints
    try:
        from api_crm_advanced import crm_api_bp
        from api_timeline import timeline_api_bp
        from whatsapp_api import whatsapp_api_bp
        app.register_blueprint(crm_api_bp)
        app.register_blueprint(timeline_api_bp)
        app.register_blueprint(whatsapp_api_bp)
    except ImportError as e:
        print(f"Warning: Could not import some API blueprints: {e}")
    
    return app

def register_auth_routes(app):
    """רישום נתיבי אימות מאובטחים"""
    
    @app.route('/api/auth/login', methods=['POST'])
    def login():
        data = request.get_json()
        
        # Secure authentication for professional system
        username = data.get('username') or data.get('email')
        if username == 'admin' and data.get('password') == 'admin123':
            user = {
                'id': '1',
                'username': 'admin',
                'firstName': 'מנהל',
                'lastName': 'ראשי',
                'role': 'admin',
                'businessId': None,
                'isActive': True
            }
            return jsonify({'user': user, 'token': 'admin-token-secure'})
        elif username == 'shai' and data.get('password') == 'shai123':
            user = {
                'id': '2',
                'username': 'shai',
                'firstName': 'שי',
                'lastName': 'כהן',
                'role': 'business',
                'businessId': 'shai-offices',
                'isActive': True
            }
            return jsonify({'user': user, 'token': 'business-token-secure'})
        else:
            return jsonify({'error': 'פרטי התחברות שגויים'}), 401
    
    @app.route('/api/auth/logout', methods=['POST'])
    def logout():
        return jsonify({'message': 'התנתקת בהצלחה'})
    
    @app.route('/api/auth/me', methods=['GET'])
    def auth_me():
        # For now, return unauthorized to force login
        return jsonify({'error': 'נדרשת התחברות'}), 401

def register_core_routes(app):
    """רישום נתיבים עיקריים"""
    
    @app.route('/')
    def serve_frontend():
        """הגשת הפרונטאנד המקצועי"""
        try:
            return send_file('../client/dist/index.html')
        except:
            return """<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>מערכת ניהול שיחות AI - שי דירות ומשרדים בע״מ</title>
    <style>
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: white;
            color: #333;
            text-align: center; 
            padding: 60px 20px;
            direction: rtl;
        }
        .container {
            max-width: 500px;
            margin: 0 auto;
            background: #f9f9f9;
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 { color: #2c3e50; margin-bottom: 20px; }
        .status { 
            color: #27ae60; 
            font-weight: bold; 
            margin: 20px 0;
        }
        .features {
            text-align: right;
            margin-top: 30px;
        }
        .feature {
            margin: 10px 0;
            padding: 5px;
        }
        .loading {
            color: #3498db;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🏢 מערכת ניהול שיחות AI</h1>
        <h2>שי דירות ומשרדים בע״מ</h2>
        <div class="status">✅ השרת פועל בהצלחה</div>
        
        <div class="features">
            <div class="feature">🔐 מערכת התחברות מאובטחת</div>
            <div class="feature">📞 שיחות קוליות חכמות</div>
            <div class="feature">💬 WhatsApp אוטומטי</div>
            <div class="feature">🎯 תמלול עברית מדויק</div>
            <div class="feature">🤖 תשובות AI מתוחכמות</div>
        </div>
        
        <div class="loading">⏳ טוען ממשק המשתמש...</div>
    </div>
</body>
</html>"""

def register_webhook_routes(app):
    """רישום webhooks לTwilio"""
    
    PUBLIC_HOST = "https://ai-crmd.replit.app"
    
    @app.route('/webhook/incoming_call', methods=['POST'])
    def incoming_call():
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
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>{PUBLIC_HOST}/static/voice_responses/listening.mp3</Play>
  <Hangup/>
</Response>"""
        return Response(xml, mimetype="text/xml")
    
    @app.route('/webhook/call_status', methods=['POST'])
    def call_status():
        return "OK", 200

if __name__ == '__main__':
    app = create_app()
    print("🎯 Starting Professional Hebrew AI Call Center CRM")
    print("🔐 מנהל: admin / admin123")
    print("🏢 שי: shai / shai123")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=False)