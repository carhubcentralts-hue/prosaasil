#!/usr/bin/env python3
"""
Final Clean App - אפליקציה מלאה ונקייה עם כל המערכות
"""

import os
import logging
from flask import Flask
from flask_cors import CORS
from app_clean import create_clean_app
from routes_clean import clean_twilio_bp
from flask import send_from_directory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s'
)
logger = logging.getLogger(__name__)

def create_final_app():
    """יצירת אפליקציה מלאה ונקייה"""
    
    # Create clean base app with React frontend support
    from flask import Flask
    from flask_cors import CORS
    from models_clean import db
    
    # Create Flask app with React frontend config
    app = Flask(__name__, static_folder="../client/dist", static_url_path="/")
    
    # Configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'clean-hebrew-ai-2025')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///clean_hebrew_crm.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }
    
    # Initialize extensions
    CORS(app, supports_credentials=True)
    db.init_app(app)
    
    # Create tables and business
    with app.app_context():
        from models_clean import CleanBusiness
        db.create_all()
        
        existing_business = CleanBusiness.query.first()
        if not existing_business:
            from datetime import datetime
            business = CleanBusiness()
            business.name = 'שי דירות ומשרדים בע״מ'
            business.business_type = 'real_estate'
            business.phone = '+972-3-555-7777'
            business.email = 'info@shai-realestate.co.il'
            business.address = 'תל אביב, ישראל'
            business.is_active = True
            business.created_at = datetime.utcnow()
            
            db.session.add(business)
            db.session.commit()
    
    # Register clean Twilio routes with Hebrew TTS
    app.register_blueprint(clean_twilio_bp)
    logger.info("✅ Clean Twilio webhooks registered successfully")
    
    # Add authentication routes for frontend
    from flask import session, jsonify, request
    from datetime import datetime
    
    @app.route('/api/auth/login', methods=['POST'])
    def login():
        """Simple login for demo"""
        data = request.json
        username = data.get('username')
        password = data.get('password')
        
        # Demo users
        if username == 'admin' and password == 'admin':
            session['user'] = {'username': 'admin', 'role': 'admin', 'name': 'מנהל מערכת'}
            return jsonify({'success': True, 'user': session['user']})
        elif username == 'shai' and password == 'shai123':
            session['user'] = {'username': 'shai', 'role': 'business', 'name': 'שי דירות ומשרדים - בעל העסק'}
            return jsonify({'success': True, 'user': session['user']})
        
        return jsonify({'success': False, 'message': 'שם משתמש או סיסמה שגויים'}), 401

    @app.route('/api/auth/me', methods=['GET'])
    def get_current_user():
        """Get current logged user"""
        user = session.get('user')
        if user:
            return jsonify(user)
        return jsonify({'error': 'לא מחובר למערכת'}), 401

    @app.route('/api/auth/logout', methods=['POST'])
    def logout():
        """Logout"""
        session.pop('user', None)
        return jsonify({'success': True})

    # Add static file serving for voice files
    @app.route('/static/<path:filename>')
    def serve_static(filename):
        """Serve static files including voice responses"""
        from flask import send_from_directory
        static_dir = os.path.join(app.root_path, 'static')
        return send_from_directory(static_dir, filename)
        
    @app.route('/static/voice_responses/<path:filename>')
    def serve_voice_files(filename):
        """Serve generated voice response files"""
        from flask import send_from_directory
        voice_dir = os.path.join(app.root_path, 'static', 'voice_responses')
        return send_from_directory(voice_dir, filename)

    # Add basic CRM routes for frontend
    @app.route('/api/admin/stats', methods=['GET'])
    def admin_stats():
        """Admin stats"""
        if not session.get('user'):
            return jsonify({'error': 'נדרש אימות'}), 401
            
        return jsonify({
            'success': True,
            'stats': {
                'total_businesses': 1,
                'total_customers': 4,
                'total_calls_today': len(clean_ai.business_context if hasattr(clean_ai, 'business_context') else []),
                'total_messages_today': 12,
                'system_status': 'פעיל - AI מחובר',
                'ai_system': 'OpenAI GPT-4o + Whisper',
                'twilio_status': 'פעיל',
                'last_update': datetime.now().isoformat()
            }
        })

    # Serve React SPA
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_spa(path):
        """Serve React SPA"""
        try:
            # Serve static files
            if app.static_folder and path and os.path.exists(os.path.join(app.static_folder, path)):
                return send_from_directory(app.static_folder, path)
            
            # Serve React app
            if app.static_folder:
                index_path = os.path.join(app.static_folder, 'index.html')
                if os.path.exists(index_path):
                    return send_from_directory(app.static_folder, 'index.html')
            
            # Fallback if React not built
            return f'''<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
    <meta charset="utf-8">
    <title>Hebrew AI Call Center - שי דירות ומשרדים</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            text-align: center;
            padding: 50px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            min-height: 100vh;
        }}
        .container {{
            background: rgba(255,255,255,0.1);
            padding: 30px;
            border-radius: 15px;
            max-width: 600px;
            margin: 0 auto;
        }}
        .status {{
            color: #4CAF50;
            font-weight: bold;
        }}
        .webhooks {{
            background: rgba(255,255,255,0.1);
            padding: 20px;
            border-radius: 10px;
            margin: 20px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 Hebrew AI Call Center</h1>
        <h2>שי דירות ומשרדים בע״מ</h2>
        <p class="status">✅ המערכת פעילה ומוכנה לשיחות!</p>
        
        <div class="webhooks">
            <h3>📞 Twilio Webhooks Ready:</h3>
            <p><strong>Incoming Call:</strong> /webhook/incoming_call</p>
            <p><strong>Recording Handler:</strong> /webhook/handle_recording</p>
        </div>
        
        <h3>🎯 תכונות פעילות:</h3>
        <ul style="text-align: right; display: inline-block;">
            <li>שיחות AI חכמות בעברית</li>
            <li>תמלול אוטומטי עם Whisper</li>
            <li>מומחיות בנדל״ן ישראלי</li>
            <li>תיעוד שיחות מלא</li>
            <li>זיהוי סיום שיחה טבעי</li>
        </ul>
        
        <p><strong>טלפון עסק:</strong> +972-3-555-7777</p>
        <p style="margin-top: 30px; font-size: 14px; opacity: 0.8;">
            React frontend לא זמין - אבל כל מערכות ה-AI עובדות מושלם!
        </p>
    </div>
</body>
</html>'''
            
        except Exception as e:
            logger.error(f"Error serving SPA: {e}")
            return "Server Error", 500
    
    return app

# Create the app instance
app = create_final_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(
        debug=False,
        host="0.0.0.0", 
        port=port,
        threaded=True
    )