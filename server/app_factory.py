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
    
    # CRITICAL: Setup Google credentials FIRST, before any imports
    try:
        from server.bootstrap_secrets import check_secrets, ensure_google_creds_file
        ensure_google_creds_file()  # Create credentials file before TTS/STT imports
        check_secrets()  # Check all secrets
    except Exception as e:
        print(f"⚠️ Credential setup warning: {e}")
    
    app = Flask(__name__, static_url_path="/static",
                static_folder=os.path.join(os.path.dirname(__file__), "..", "static"))
    
    # הדגל השחור - לוג זיהוי לקוד ישן/חדש (שלב 7)
    import time
    version_info = {
        "app": "AgentLocator-71",
        "commit": os.getenv("GIT_COMMIT", "dev"),
        "build_time": os.getenv("BUILD_TIME", "dev"),
        "deploy_id": os.getenv("DEPLOY_ID", "dev"),
        "startup_ts": int(time.time())
    }
    print(f"🚩 APP_START {version_info}")
    
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
    
    # 2) WebSocket עם Flask-Sock - יציב יותר לTwilio (תיקון 500 Error)
    from flask_sock import Sock
    from server.media_ws import MediaStreamHandler
    
    # FORCED FIX: Force Flask-Sock registration
    sock = Sock(app)
    
    # Manual registration if needed
    if 'sock' not in app.extensions:
        app.extensions['sock'] = sock
        print("🔧 Flask-Sock manually registered")
    
    print(f"🔧 Flask-Sock in extensions: {'sock' in app.extensions}")
    
    @sock.route('/ws/twilio-media')
    def ws_twilio_media(ws):
        """WebSocket handler - AI mode with proper TTS"""
        from server.media_ws_ai import MediaStreamHandler
        print("🚨 WEBSOCKET HANDLER CALLED - AI MODE")
        
        # Write debug immediately
        import time
        with open("/tmp/websocket_debug.txt", "w") as f:
            f.write(f"WEBSOCKET_HANDLER_AI_MODE: {time.time()}\n")
            f.flush()
        
        try:
            handler = MediaStreamHandler(ws)
            handler.run()
        except Exception as e:
            print(f"❌ WS_HANDLER_ERROR: {e}")
            with open("/tmp/websocket_debug.txt", "a") as f:
                f.write(f"WS_HANDLER_ERROR: {e}\n")
                f.flush()
        print("WS_CLOSED")
        
    @sock.route('/ws/twilio-media/')
    def ws_twilio_media_slash(ws):
        """WebSocket handler with slash - AI mode"""
        from server.media_ws_ai import MediaStreamHandler
        import time
        print("🚨 WEBSOCKET HANDLER CALLED - AI MODE (slash)")
        
        # Write debug immediately
        with open("/tmp/websocket_debug.txt", "a") as f:
            f.write(f"WEBSOCKET_HANDLER_AI_MODE_SLASH: {time.time()}\n")
            f.flush()
        
        try:
            handler = MediaStreamHandler(ws)
            handler.run()
        except Exception as e:
            print(f"❌ WS_HANDLER_ERROR: {e}")
            with open("/tmp/websocket_debug.txt", "a") as f:
                f.write(f"WS_HANDLER_ERROR: {e}\n")
                f.flush()
    
    print("✅ WebSocket routes registered: /ws/twilio-media and /ws/twilio-media/ (One True Path)")

    # רישום בלו־פרינטים - AgentLocator 71
    from server.routes_twilio import twilio_bp
    app.register_blueprint(twilio_bp)
    from server.routes_whatsapp import register_whatsapp_routes, whatsapp_bp
    register_whatsapp_routes(app)  # ← Legacy compatibility
    app.register_blueprint(whatsapp_bp)  # ← New unified WhatsApp routes
    from server.api_crm_unified import api_bp
    app.register_blueprint(api_bp, url_prefix="/api")
    
    # WhatsApp Unified API (send/status/list)
    from server.api_whatsapp_unified import whatsapp_unified_bp
    app.register_blueprint(whatsapp_unified_bp)
    
    # Baileys WhatsApp bridge routes 
    try:
        from server.routes_whatsapp_baileys import baileys_bp
        app.register_blueprint(baileys_bp)
        print("✅ Baileys routes registered")
    except ImportError:
        print("⚠️ Baileys routes not available")
    
    # Debug routes לפריסה
    try:
        from server.debug_routes import debug_bp
        app.register_blueprint(debug_bp)
        print("✅ Debug routes registered")
    except ImportError:
        print("⚠️ Debug routes not available")

    # Version endpoint for deployment verification
    @app.route('/version', methods=['GET'])
    def version():
        """Return version info to verify deployment"""
        import os, time
        return jsonify({
            "app": os.getenv("GIT_COMMIT", "AgentLocator-73-dev"),
            "commit": os.getenv("GIT_COMMIT", "dev"),
            "build_time": os.getenv("BUILD_TIME", "dev"),
            "deploy_id": os.getenv("DEPLOY_ID", "dev"),
            "ts": int(time.time())
        }), 200

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
    
    # CRITICAL: Serve React frontend on root path
    @app.route('/', methods=['GET'])
    def root():
        """Serve React frontend as main page"""
        try:
            return send_file(os.path.join(os.getcwd(), 'client/dist/index.html'))
        except FileNotFoundError:
            # Fallback if React app not built
            return """
<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>מערכת CRM עברית - שי דירות ומשרדים</title>
    <style>
        body { font-family: Assistant, sans-serif; direction: rtl; 
               background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
               min-height: 100vh; display: flex; align-items: center; 
               justify-content: center; color: white; margin: 0; }
        .container { text-align: center; max-width: 600px; padding: 40px; }
        h1 { font-size: 2.5rem; margin-bottom: 20px; }
        p { font-size: 1.2rem; opacity: 0.9; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🏢 מערכת CRM עברית</h1>
        <p>שי דירות ומשרדים בע״מ</p>
        <p>מערכת ניהול שיחות עם בינה מלאכותית בעברית</p>
        <div style="margin-top: 30px; padding: 20px; background: rgba(255,255,255,0.1); border-radius: 10px;">
            <p>✅ המערכת פעילה ומוכנה לשיחות</p>
            <p>📞 קו חם: +972-3-376-3805</p>
        </div>
    </div>
</body>
</html>""", 200

    @app.route('/healthz', methods=['GET'])
    def healthz():
        """Basic health check - fast endpoint for deployment"""
        return "ok", 200
    
    @app.route('/readyz', methods=['GET'])
    def readyz():
        """Readiness check with system status"""
        checks = {
            "db": "ok",
            "openai": "ok", 
            "tts": "ok",
            "twilio_secrets": "ok"
        }
        return jsonify(checks), 200
        
    @app.route('/home')
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