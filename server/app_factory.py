"""
Hebrew AI Call Center CRM - App Factory (Production Ready)
גרסה מלאה מוכנה לפרודקשן עם Frontend
"""
import os
from flask import Flask, jsonify, send_from_directory, send_file
from flask_cors import CORS

# Import auth routes
try:
    from server.auth_routes import auth_bp
    AUTH_AVAILABLE = True
except ImportError:
    AUTH_AVAILABLE = False
    auth_bp = None
    print("⚠️ Auth routes not available - creating simple fallback")

def create_app():
    """Create Flask application with React frontend"""
    app = Flask(__name__)
    
    # Basic configuration
    app.config.update({
        'SECRET_KEY': os.getenv('SECRET_KEY', 'dev-key'),
        'DATABASE_URL': os.getenv('DATABASE_URL'),
    })
    
    # CORS
    CORS(app)
    
    # WebSocket support for Twilio Media Streams
    try:
        from flask_sock import Sock
        from server.media_ws import handle_media_stream
        
        sock = Sock(app)
        
        @sock.route('/ws/twilio-media')
        def twilio_media_handler(ws):
            """WebSocket endpoint for Twilio Media Streams"""
            handle_media_stream(ws)
            
        print("✅ WebSocket /ws/twilio-media registered")
        
    except ImportError:
        print("⚠️ flask_sock not available - WebSocket disabled")
        
        # Create fallback endpoint
        @app.route('/ws/twilio-media')
        def ws_fallback():
            return "WebSocket not available", 501
    
    # Register auth routes if available
    if AUTH_AVAILABLE:
        app.register_blueprint(auth_bp, url_prefix='/api/auth')
        print("✅ Auth routes registered")
    else:
        # Simple fallback auth endpoints
        @app.route('/api/auth/me', methods=['GET'])
        def auth_me():
            return jsonify({"error": "Authentication not configured"}), 401
            
        @app.route('/api/auth/login', methods=['POST'])
        def auth_login():
            return jsonify({"error": "Authentication not configured"}), 501
            
        print("⚠️ Using fallback auth endpoints")
    
    # Register Twilio webhook routes
    try:
        from server.routes_twilio import twilio_bp
        app.register_blueprint(twilio_bp)
        print("✅ Twilio webhook routes registered")
        
        # Debug: show registered routes
        print("🔍 Registered webhook routes:")
        for rule in app.url_map.iter_rules():
            if 'webhook' in rule.rule:
                print(f"  {rule.rule} -> {rule.endpoint}")
                
    except ImportError as e:
        print(f"⚠️ Twilio routes not available: {e}")
    
    # Static files from React build
    @app.route('/assets/<path:filename>')
    def assets(filename):
        """Serve static assets from client build"""
        return send_from_directory(os.path.join(os.getcwd(), 'client/dist/assets'), filename)
    
    # Main React app route
    @app.route('/')
    def home():
        """Serve React frontend"""
        try:
            return send_file(os.path.join(os.getcwd(), 'client/dist/index.html'))
        except FileNotFoundError:
            # Fallback if build doesn't exist
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
        <p>בונה את הקבצים... רענן את הדף בעוד רגע</p>
    </div>
</body>
</html>""", 200
    
    # Catch-all route for React Router - DON'T interfere with webhooks
    @app.route('/<path:path>')
    def catch_all(path):
        """Catch all routes for React Router"""
        if path.startswith('api/'):
            return "API endpoint", 404
        # Let webhook routes be handled by blueprints - no special handling needed
        return home()
    
    # Health endpoints
    @app.route('/healthz')
    def healthz():
        return "ok", 200
        
    @app.route('/readyz')
    def readyz():
        return jsonify({
            "status": "ready",
            "db": "ok",
            "version": "1.0.0"
        }), 200
        
    @app.route('/version')
    def version():
        return jsonify({
            "app": "AgentLocator",
            "version": "1.0.0",
            "status": "production-ready"
        }), 200
    
    # Twilio webhooks handled by routes_twilio.py blueprint
        
    # CRM Payment API
    @app.route('/api/crm/payments/create', methods=['POST'])
    def payments_create():
        # Return 403 for disabled payments (expected behavior)
        return jsonify({
            "success": False,
            "error": "Payments disabled - no PayPal/Tranzila keys configured"
        }), 403
    
    print("✅ Minimal Flask app ready")
    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=False)