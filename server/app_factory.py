"""
Hebrew AI Call Center CRM - App Factory (לפי ההנחיות המדויקות)
"""
import os
from flask import Flask, jsonify, send_from_directory, send_file, current_app, request
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_sock import Sock

def create_app():
    """Create Flask application with React frontend (לפי ההנחיות המדויקות)"""
    app = Flask(__name__, static_url_path="/static",
                static_folder=os.path.join(os.path.dirname(__file__), "..", "static"))
    
    # Basic configuration
    app.config.update({
        'SECRET_KEY': os.getenv('SECRET_KEY', 'dev-key'),
        'DATABASE_URL': os.getenv('DATABASE_URL'),
    })
    
    # ProxyFix for proper URL handling behind proxy (לפי ההנחיות)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    
    # CORS
    CORS(app)
    
    # 8) לוגים שמראים הכל (לפי ההנחיות המדויקות)
    @app.before_request
    def _req_log():
        current_app.logger.info("REQ", extra={"path": request.path, "method": request.method})

    @app.after_request
    def _res_log(resp):
        current_app.logger.info("RES", extra={"path": request.path, "status": resp.status_code})
        return resp
    
    # 2) Flask-Sock רישום נכון + שני נתיבי WS (לפי ההנחיות המדויקות)
    try:
        # Try direct initialization first
        sock = Sock(app)
        if "sock" not in app.extensions:
            # If that fails, try init_app method
            sock = Sock()
            sock.init_app(app)
        
        # Verify registration
        if "sock" not in app.extensions:
            raise Exception("Flask-Sock failed to register")
            
        from server.media_ws import MediaStreamHandler
        @sock.route("/ws/twilio-media")
        def ws_a(ws): MediaStreamHandler(ws).run()
        @sock.route("/ws/twilio-media/")   # ← גם עם סלאש למנוע Redirect/404 בהנדשייק
        def ws_b(ws): MediaStreamHandler(ws).run()
        
        print("✅ Flask-Sock registered successfully")
        
    except Exception as e:
        print(f"❌ Flask-Sock registration failed: {e}")
        # Continue without WebSocket for now
        print("⚠️ Continuing without WebSocket support")

    # רישום בלו־פרינטים
    from server.routes_twilio import twilio_bp
    app.register_blueprint(twilio_bp)
    from server.routes_whatsapp import register_whatsapp_routes
    register_whatsapp_routes(app)  # ← פעם אחת בלבד

    # Simple auth endpoints (fallback)
    @app.route('/api/auth/me', methods=['GET'])
    def auth_me():
        return jsonify({"error": "Authentication not configured"}), 401
        
    @app.route('/api/auth/login', methods=['POST'])
    def auth_login():
        return jsonify({"error": "Authentication not configured"}), 501
    
    # Static TTS file serving (לפי ההנחיות - חובה ש MP3 files יהיו 200)
    @app.route('/static/tts/<path:filename>')
    def static_tts(filename):
        """Serve static TTS files"""
        return send_from_directory(os.path.join(os.path.dirname(__file__), "..", "static", "tts"), filename)
    
    # React frontend routes
    @app.route('/assets/<path:filename>')
    def assets(filename):
        """Serve static assets from client build"""
        return send_from_directory(os.path.join(os.getcwd(), 'client/dist/assets'), filename)
    
    @app.route('/')
    def home():
        """Serve React frontend"""
        try:
            return send_file(os.path.join(os.getcwd(), 'client/dist/index.html'))
        except FileNotFoundError:
            return """
<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>מערכת CRM - שי דירות ומשרדים</title>
    <style>
        body { font-family: Assistant, sans-serif; direction: rtl; 
               background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
               min-height: 100vh; display: flex; align-items: center; 
               justify-content: center; color: white; }
        .container { text-align: center; padding: 2rem; 
                    background: rgba(255,255,255,0.1); border-radius: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>מערכת CRM לשיחות בעברית</h1>
        <p>השרת פועל - מערכת מוכנה לשיחות</p>
    </div>
</body>
</html>""", 200
    
    return app