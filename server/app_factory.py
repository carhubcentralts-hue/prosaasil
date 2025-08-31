"""
Hebrew AI Call Center CRM - App Factory (לפי ההנחיות המדויקות)
"""
import os
from flask import Flask, jsonify, send_from_directory, send_file, current_app, request, session, g
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_sock import Sock
from simple_websocket import Server as WSServer
try:
    from flask_seasurf import SeaSurf
    from flask_wtf.csrf import CSRFProtect
    CSRF_AVAILABLE = True
except ImportError:
    print("⚠️ CSRF packages not available - using basic security")
    SeaSurf = None
    CSRFProtect = None 
    CSRF_AVAILABLE = False
from datetime import datetime, timedelta
import secrets
import hashlib

def create_app():
    """Create Flask application with React frontend (לפי ההנחיות המדויקות)"""
    
    # CRITICAL: Setup Google credentials FIRST, before any imports
    try:
        from server.bootstrap_secrets import check_secrets, ensure_google_creds_file
        ensure_google_creds_file()  # Create credentials file before TTS/STT imports
        check_secrets()  # Check all secrets
    except Exception as e:
        print(f"⚠️ Credential setup warning: {e}")
    
    app = Flask(__name__, 
                static_url_path="/static",
                static_folder=os.path.join(os.path.dirname(__file__), "..", "static"),
                template_folder=os.path.join(os.path.dirname(__file__), "templates"))
    
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
    
    # Database configuration with SSL fix
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///default.db')
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    
    # Enterprise Security Configuration
    app.config.update({
        'SECRET_KEY': os.getenv('SECRET_KEY', secrets.token_hex(32)),
        'DATABASE_URL': DATABASE_URL,
        'SQLALCHEMY_DATABASE_URI': DATABASE_URL,
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'SQLALCHEMY_ENGINE_OPTIONS': {
            'pool_pre_ping': True,
            'pool_recycle': 300,
            'connect_args': {
                'connect_timeout': 30,
                'application_name': 'AgentLocator-71'
            }
        },
        # CSRF Protection
        'CSRF_ENABLED': True,
        'CSRF_SESSION_KEY': '_csrf_token',
        'WTF_CSRF_TIME_LIMIT': 3600,  # 1 hour
        'WTF_CSRF_SSL_STRICT': False,  # Allow HTTP in development
        
        # Session Security
        'SESSION_COOKIE_SECURE': False,  # Set to True in production with HTTPS
        'SESSION_COOKIE_HTTPONLY': True,
        'SESSION_COOKIE_SAMESITE': 'Lax',
        'PERMANENT_SESSION_LIFETIME': timedelta(hours=8),  # 8 hour timeout
        'SESSION_REFRESH_EACH_REQUEST': True
    })
    
    # ProxyFix for proper URL handling behind proxy
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    
    # Enterprise Security Headers
    @app.after_request
    def add_security_headers(response):
        """Add enterprise security headers"""
        # CSP (Content Security Policy)
        csp_policy = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://unpkg.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https:; "
            "connect-src 'self' wss: ws:; "
            "frame-ancestors 'none'; "
            "object-src 'none';"
        )
        response.headers['Content-Security-Policy'] = csp_policy
        
        # Additional security headers
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        
        # Cache control for sensitive pages
        if request.endpoint and ('admin' in request.endpoint or 'biz' in request.endpoint):
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            
        return response
    
    # Session Management and Rotation
    @app.before_request
    def manage_session_security():
        """Enhanced session security management"""
        # Skip for static files, health endpoints, and React routes
        if request.endpoint in ['static', 'health', 'readyz', 'version'] or request.path in ['/', '/login', '/forgot', '/reset', '/home']:
            return
            
        # Session timeout check
        if 'al_user' in session:
            last_activity = session.get('_last_activity')
            if last_activity:
                last_time = datetime.fromisoformat(last_activity)
                if datetime.now() - last_time > timedelta(hours=8):
                    session.clear()
                    return jsonify({'error': 'Session expired'}), 401
            
            # Update last activity
            session['_last_activity'] = datetime.now().isoformat()
            
            # Session rotation (rotate session ID periodically)
            session_start = session.get('_session_start')
            if not session_start:
                session['_session_start'] = datetime.now().isoformat()
                session['_csrf_token'] = secrets.token_hex(16)
            else:
                start_time = datetime.fromisoformat(session_start)
                if datetime.now() - start_time > timedelta(hours=2):
                    # Rotate session but preserve user data
                    user_data = session.get('al_user')
                    session.clear()
                    if user_data:
                        session['al_user'] = user_data
                        session['_session_start'] = datetime.now().isoformat()
                        session['_csrf_token'] = secrets.token_hex(16)
    
    # Enterprise Security Initialization
    csrf_instance = None
    surf_instance = None
    if CSRF_AVAILABLE and CSRFProtect and SeaSurf:
        try:
            csrf_instance = CSRFProtect()
            csrf_instance.init_app(app)
            
            # SeaSurf for additional CSRF protection
            surf_instance = SeaSurf()
            surf_instance.init_app(app)
            print("🔒 Enterprise CSRF Protection enabled")
        except Exception as e:
            print(f"⚠️ CSRF setup warning: {e}")
    else:
        print("⚠️ Running with basic security (CSRF packages not available)")
    
    # CORS with security restrictions
    CORS(app, 
         origins=[
             "http://localhost:5000",
             "https://*.replit.app",
             "https://*.replit.dev"
         ],
         supports_credentials=True,
         allow_headers=["Content-Type", "Authorization", "X-CSRFToken", "HX-Request"],
         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    )
    
    # UI Blueprint registration (לפי ההנחיות) - MUST BE FIRST!
    try:
        from server.ui.routes import ui_bp
        # Removed routes_auth.py - using only auth_api.py for cleaner code
        from server.auth_api import auth_api, create_default_admin
        from server.data_api import data_api
        
        # Initialize enterprise security & audit system
        from server.security_audit import AuditLogger, SessionSecurity
        audit_logger = AuditLogger(app)
        
        @app.before_request 
        def setup_security_context():
            """Setup security context for each request"""
            # Skip React auth routes completely
            if request.path in ['/', '/login', '/forgot', '/reset', '/home']:
                return
                
            g.audit_logger = audit_logger
            g.session_security = SessionSecurity
            
            # Update session activity
            SessionSecurity.update_activity()
            
            # Check session validity for protected routes
            if request.endpoint and request.endpoint.startswith(('ui.', 'auth_api.', 'data_api.')):
                if not SessionSecurity.is_session_valid():
                    session.clear()
                    if request.headers.get('HX-Request'):
                        return '<div class="text-red-600 p-4 bg-red-50 rounded-lg">🔒 Session expired - please login again</div>', 401
        
        # Register auth system FIRST (after security middleware)
        # Using simplified auth from auth_api.py only
        
        # Session configuration for security (לפי המפרט)
        app.config.update({
            'SESSION_COOKIE_HTTPONLY': True,
            'SESSION_COOKIE_SAMESITE': 'Lax',
            'SESSION_COOKIE_SECURE': True if os.getenv('FLASK_ENV') == 'production' else False,
        })
        app.config.update({
            'SESSION_COOKIE_NAME': 'al_sess',
            'SESSION_COOKIE_HTTPONLY': True,
            'SESSION_COOKIE_SECURE': False,  # Set to True in production with HTTPS
            'SESSION_COOKIE_SAMESITE': 'Lax',
        })
        
        # Register auth blueprint - single clean system
        app.register_blueprint(auth_api)  # Auth API endpoints only
        print("✅ Auth blueprints registered")
        
        # Register new API blueprints
        from server.routes_admin import admin_bp
        from server.routes_crm import crm_bp
        from server.routes_business_management import biz_mgmt_bp
        app.register_blueprint(admin_bp)
        app.register_blueprint(crm_bp)
        app.register_blueprint(biz_mgmt_bp)
        print("✅ New API blueprints registered")
        
        app.register_blueprint(data_api)
        
        # Register UI blueprint last (after React routes are defined)
        print(f"🔧 Registering UI Blueprint: {ui_bp}")
        app.register_blueprint(ui_bp, url_prefix='')  # No prefix for admin/business routes
        print("✅ All blueprints registered")
    except Exception as e:
        print(f"❌ Blueprint registration error: {e}")
        import traceback
        traceback.print_exc()
    
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
    from server.media_ws_ai import MediaStreamHandler
    
    # CRITICAL FIX: Force Flask-Sock initialization with EventLet compatibility
    sock = Sock()
    sock.init_app(app)
    
    # Force registration in app extensions
    app.extensions['sock'] = sock
    
    # EventLet compatibility fix - ensure WebSocket is registered properly
    if hasattr(app, 'sock'):
        print("🔧 Flask-Sock already bound to app")
    else:
        # Type ignore for LSP - Flask allows dynamic attributes
        app.sock = sock  # type: ignore
        print("🔧 Flask-Sock manually bound to app")
    
    # DEPLOYMENT FIX: Ensure routes are registered before any requests
    app.before_first_request_funcs = []
    
    print(f"🔧 Flask-Sock in extensions: {'sock' in app.extensions}")
    print(f"🔧 Flask-Sock app attribute: {hasattr(app, 'sock')}")
    print(f"🔧 EventLet WebSocket mode: enabled")
    
    @sock.route('/ws/twilio-media')
    def ws_twilio_media(ws):
        """WebSocket handler - AI mode with proper TTS"""
        from server.media_ws_ai import MediaStreamHandler
        print("🚨 WEBSOCKET HANDLER CALLED - AI MODE")
        
        # Write debug immediately
        import time, os
        debug_file = "/tmp/websocket_debug.txt"
        try:
            with open(debug_file, "w") as f:
                f.write(f"WEBSOCKET_HANDLER_AI_MODE: {time.time()}\n")
                f.write(f"DEPLOYMENT: {os.getenv('REPLIT_DEPLOYMENT_ID', 'local')}\n")
                f.flush()
        except Exception as de:
            print(f"Debug write error: {de}")
        
        try:
            handler = MediaStreamHandler(ws)
            handler.run()
        except Exception as e:
            print(f"❌ WS_HANDLER_ERROR: {e}")
            try:
                with open(debug_file, "a") as f:
                    f.write(f"WS_HANDLER_ERROR: {e}\n")
                    f.flush()
            except:
                pass
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
    
    # PATCH 2: Alternative WS route with proper subprotocol handling
    @sock.route('/ws/twilio-media-alt')
    def ws_twilio_media_alt(ws):
        """Alternative WebSocket handler - FIXED AS WEBSOCKET"""
        from server.media_ws_ai import MediaStreamHandler
        import time
        print("🚨 WS_ALT_HANDLER CALLED - AI MODE (alternative endpoint)")
        
        # Write debug immediately
        with open("/tmp/websocket_debug.txt", "a") as f:
            f.write(f"WS_ALT_HANDLER_AI_MODE: {time.time()}\n")
            f.flush()
        
        try:
            print("🚨 WS_ALT: Starting MediaStreamHandler")
            handler = MediaStreamHandler(ws)
            handler.run()
        except Exception as e:
            print(f"❌ WS_ALT_ERROR: {e}")
            with open("/tmp/websocket_debug.txt", "a") as f:
                f.write(f"WS_ALT_ERROR: {e}\n")
                f.flush()
    
    print("✅ Alternative WebSocket route: /ws/twilio-media-alt (with subprotocol)")

    # רישום בלו־פרינטים - AgentLocator 71
    from server.routes_twilio import twilio_bp
    app.register_blueprint(twilio_bp)
    
    # CSRF Exemption for all Twilio webhooks (critical for phone system)
    if csrf_instance:
        try:
            # Exempt all webhook endpoints from Flask-WTF CSRF protection
            csrf_instance.exempt(twilio_bp)
            print("✅ Flask-WTF CSRF exemption applied to Twilio webhooks")
        except Exception as e:
            print(f"⚠️ Flask-WTF CSRF exemption warning: {e}")
            
    if surf_instance:
        try:
            # SeaSurf exemption - needs tuple syntax, not list
            surf_instance.exempt_urls(('/webhook/',))
            print("✅ SeaSurf exemption applied to /webhook/ prefix")
        except Exception as e:
            print(f"⚠️ SeaSurf exemption warning: {e}")
            # Alternative: Set exempt_urls directly as attribute
            try:
                surf_instance._exempt_urls = ('/webhook/',)
                print("✅ SeaSurf direct attribute exemption applied")
            except:
                print("⚠️ SeaSurf could not be configured - webhooks may be blocked")
    # WhatsApp unified registration only (no more routes_whatsapp.py)
    print("✅ WhatsApp routes removed - using unified only")
    # CRM unified moved to routes_crm.py - no separate API blueprint needed
    
    # WhatsApp Unified API (send/status/list)
    from server.api_whatsapp_unified import whatsapp_unified_bp
    app.register_blueprint(whatsapp_unified_bp)
    
    # Baileys WhatsApp bridge routes (DISABLED - cleanup)
    # try:
    #     from server.routes_whatsapp_baileys import baileys_bp
    #     app.register_blueprint(baileys_bp)
    #     print("✅ Baileys routes registered")
    # except ImportError:
    #     print("⚠️ Baileys routes not available")
    
    # Debug routes לפריסה (DISABLED - cleanup)
    # try:
    #     from server.debug_routes import debug_bp
    #     app.register_blueprint(debug_bp)
    #     print("✅ Debug routes registered")
    # except ImportError:
    #     print("⚠️ Debug routes not available")

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

    # Auth endpoints removed - handled by routes_auth.py blueprint
    
    # Static TTS file serving (לפי ההנחיות - חובה ש MP3 files יהיו 200)
    @app.route('/static/tts/<path:filename>')
    def static_tts(filename):
        """Serve static TTS files"""
        return send_from_directory(os.path.join(os.path.dirname(__file__), "..", "static", "tts"), filename)
    
    # React app assets serving - Updated for new auth app
    @app.route('/assets/<path:filename>')
    def serve_react_assets(filename):
        """Serve React build assets (JS, CSS, etc.)"""
        try:
            return send_from_directory(os.path.join(os.path.dirname(__file__), "..", "dist", "assets"), filename)
        except FileNotFoundError:
            # Fallback to old client if needed
            return send_from_directory(os.path.join(os.path.dirname(__file__), "..", "client", "dist", "assets"), filename)

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
        
    # Serve React for root and add login route
    @app.route('/')
    def serve_auth_app():
        """Serve new professional auth React app"""
        try:
            return send_file(os.path.join(os.path.dirname(__file__), "..", "dist", "index.html"))
        except FileNotFoundError:
            return """
<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <title>שי דירות ומשרדים — התחברות למערכת</title>
</head>
<body>
    <div style="text-align: center; padding: 2rem; font-family: system-ui;">
        <h1>אפליקציה לא נמצאה</h1>
        <p>אנא הפעל: cd auth-frontend && npm run build</p>
    </div>
</body>
</html>""", 500
    
    # SPA routing fallback for React app routes
    @app.route('/app')
    @app.route('/app/')
    @app.route('/app/<path:subpath>')
    def serve_react_spa(subpath=''):
        """Serve React SPA for /app/* routes"""
        try:
            return send_file(os.path.join("dist", "index.html"))
        except Exception as e:
            print(f"⚠️ React SPA serve error: {e}")
            return """<!doctype html>
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
        <h1>טוען אפליקציה...</h1>
        <p>אנא המתן לטעינת המערכת</p>
    </div>
</body>
</html>""", 200

    # Auth routes - serve the new React auth app
    @app.route('/auth')
    @app.route('/auth/')
    @app.route('/auth/<path:path>')
    @app.route('/login')
    def auth_routes(path=None):
        """All auth routes serve the new React app"""
        try:
            return send_file(os.path.join(os.path.dirname(__file__), "..", "dist", "index.html"))
        except FileNotFoundError:
            return """
<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>התחברות - מערכת CRM</title>
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
        <h1>דף התחברות</h1>
        <p>אנא המתן לטעינת המערכת...</p>
    </div>
</body>
</html>""", 200
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
    
    # Database initialization (לפי ההנחיות)
    from server.db import db
    import server.models_sql  # Import models module
    
    # Initialize SQLAlchemy with Flask app
    db.init_app(app)
    
    # Database setup
    with app.app_context():
        try:
            db.create_all()  # Create tables if they don't exist
            print("✅ Database tables created and admin user setup complete")
        except Exception as e:
            print(f"⚠️ Database setup warning: {e}")
    
    return app