"""
Hebrew AI Call Center CRM - App Factory (Production Ready)
גרסה מלאה מוכנה לפרודקשן עם Frontend
"""
import os
from flask import Flask, jsonify, send_from_directory, send_file, current_app
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
    
    # ProxyFix for proper URL handling behind proxy
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    
    # CORS
    CORS(app)
    
    # COMPREHENSIVE LOGGING FOR WATCHDOG SYSTEM
    @app.before_request
    def _req_log():
        from flask import request
        print(f"🔥 REQ: {request.method} {request.path} from {request.remote_addr}")
        current_app.logger.info("REQ", extra={"path": request.path, "method": request.method})
        if 'webhook' in request.path:
            print(f"📞 WEBHOOK: {request.method} {request.path} - TWILIO CALLING!")
            # Force webhook detection file
            with open('/tmp/webhook_detected.log', 'w') as f:
                f.write(f"{request.method} {request.path} at {request.remote_addr}\n")

    @app.after_request
    def _res_log(resp):
        from flask import request
        print(f"✅ RES: {request.path} -> {resp.status_code}")
        current_app.logger.info("RES", extra={"path": request.path, "status": resp.status_code})
        return resp
    
    # RAW WEBSOCKET support for Twilio Media Streams - PRODUCTION READY
    try:
        from flask_sock import Sock
        from server.media_ws import handle_media_stream
        
        # Initialize Flask-Sock with app (RAW WebSocket, not Socket.IO!)
        sock = Sock(app)  # Direct initialization
        
        @sock.route('/ws/twilio-media')
        def twilio_media_handler(ws):
            """RAW WebSocket endpoint for Twilio Media Streams - NO Socket.IO!"""
            print("🔗 RAW WEBSOCKET CONNECTION RECEIVED!", flush=True)
            print(f"🔍 WebSocket client: {ws.environ.get('REMOTE_ADDR', 'unknown')}", flush=True)
            try:
                handle_media_stream(ws)
            except Exception as e:
                print(f"❌ WebSocket handler error: {e}")
        
        # Add trailing slash version to prevent 31920 redirects 
        @sock.route('/ws/twilio-media/')
        def twilio_media_handler_slash(ws):
            """RAW WebSocket endpoint with trailing slash - prevents redirects"""
            print("🔗 RAW WEBSOCKET CONNECTION (/) RECEIVED!", flush=True)
            try:
                handle_media_stream(ws)
            except Exception as e:
                print(f"❌ WebSocket handler (/) error: {e}")
                
        # Add HTTP fallback route to help debug
        @app.route('/ws/twilio-media')
        def ws_debug():
            return "This is a WebSocket endpoint. Use WebSocket protocol to connect.", 426
            
        print("✅ RAW WebSocket /ws/twilio-media registered (both variants)")
        print("🔍 WebSocket URL: wss://ai-crmd.replit.app/ws/twilio-media")
        
    except ImportError as e:
        print(f"⚠️ flask_sock not available - WebSocket disabled: {e}")
        
        # Create fallback endpoint
        @app.route('/ws/twilio-media')
        def ws_fallback():
            return "WebSocket not available - flask-sock missing", 501
            
    except Exception as e:
        print(f"❌ WebSocket registration failed: {e}")
        
        # Create fallback endpoint  
        @app.route('/ws/twilio-media')
        def ws_fallback_error():
            return f"WebSocket error: {str(e)}", 501
    
    # Register auth routes if available
    if AUTH_AVAILABLE and auth_bp is not None:
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
        if twilio_bp is not None:
            app.register_blueprint(twilio_bp)
            print("✅ Twilio webhook routes registered")
            
            # Test database connection for call recording
            print("🔄 Testing database for call recording...")
            import psycopg2
            import datetime
            try:
                conn = psycopg2.connect(os.getenv('DATABASE_URL'))
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM call_log")
                result = cur.fetchone()
                call_count = result[0] if result else 0
                cur.close()
                conn.close()
                print(f"✅ Database ready - {call_count} existing calls")
                
                # Apply database recording patch
                try:
                    from database_fix import apply_patch
                    if apply_patch():
                        print("✅ DATABASE RECORDING PATCH APPLIED TO SERVER")
                    else:
                        print("❌ DATABASE PATCH FAILED")
                except Exception as patch_err:
                    print(f"❌ Patch import failed: {patch_err}")
                    
            except Exception as db_err:
                print(f"❌ Database test failed: {db_err}")
        else:
            print("⚠️ Twilio blueprint is None")
        
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
    
    # Catch-all route for React Router - DON'T interfere with webhooks or WebSocket
    @app.route('/<path:path>')
    def catch_all(path):
        """Catch all routes for React Router"""
        if path.startswith('api/'):
            return "API endpoint", 404
        if path.startswith('webhook/'):
            return "Webhook handled by blueprint", 404
        if path.startswith('ws/'):
            return "WebSocket handled separately", 404
        # Let other routes be handled by React Router
        return home()
    
    # Health endpoints
    @app.route('/healthz')
    def healthz():
        return "ok", 200
        
    @app.route('/readyz')
    def readyz():
        """Enhanced health check - shows secret availability for debugging"""
        try:
            import psycopg2
            conn = psycopg2.connect(os.getenv('DATABASE_URL'))
            conn.close()
            db_status = "ok"
        except Exception as e:
            db_status = f"error: {str(e)}"
        
        # Check critical secrets for Watchdog system
        secrets = {
            'twilio_sid': "ok" if os.getenv('TWILIO_ACCOUNT_SID') else "missing", 
            'twilio_token': "ok" if os.getenv('TWILIO_AUTH_TOKEN') else "missing",
            'openai': "ok" if os.getenv('OPENAI_API_KEY') else "missing",
            'gcp_tts': "ok" if os.getenv('GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON') else "missing"
        }
        
        watchdog_enabled = secrets['twilio_sid'] == 'ok' and secrets['twilio_token'] == 'ok'
        
        return jsonify({
            "status": "ready",
            "version": "4.0.0-RAW-WEBSOCKET-TWILIO-COMPATIBLE",
            "timestamp": "2025-08-19-23:45-NO-SOCKETIO-PURE-WEBSOCKET",
            "db": db_status,
            "secrets": secrets,
            "watchdog": "enabled" if watchdog_enabled else "disabled - missing Twilio credentials",
            "deployment_verification": "NEW_CODE_WITH_WATCHDOG_DEPLOYED"
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
    
    # Serve static files for TTS audio
    @app.route('/static/tts/<filename>')
    def serve_tts_file(filename):
        """Serve TTS audio files"""
        import os
        tts_dir = os.path.join(os.getcwd(), 'static', 'tts')
        return send_from_directory(tts_dir, filename)
    
    print("✅ Static TTS file serving configured")
    print("✅ Minimal Flask app ready")
    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=False)