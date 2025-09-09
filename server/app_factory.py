"""
Hebrew AI Call Center CRM - App Factory (לפי ההנחיות המדויקות)
"""
import os
from flask import Flask, jsonify, send_from_directory, send_file, current_app, request, session, g
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix
# NO Flask-Sock - using EventLet WebSocketWSGI in wsgi.py composite
try:
    from flask_seasurf import SeaSurf
    CSRF_AVAILABLE = True
except ImportError:
    print("⚠️ CSRF packages not available - using basic security")
    SeaSurf = None
    CSRF_AVAILABLE = False
from datetime import datetime, timedelta
import secrets
import hashlib

def create_app():
    """Create Flask application with React frontend (לפי ההנחיות המדויקות)"""
    
    # GOOGLE TTS CREDENTIALS SETUP
    # Handle both file path and JSON string credentials
    import json, tempfile
    gcp_creds = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', '')
    if gcp_creds and gcp_creds.startswith('{'):
        # If it's a JSON string, create a temporary file
        try:
            creds_data = json.loads(gcp_creds)
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(creds_data, f)
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = f.name
            print("🔧 GCP credentials converted from JSON to file")
        except Exception as e:
            print(f"⚠️ GCP credentials error: {e}")
    else:
        print("🔧 GCP credentials loaded from file path")
    
    app = Flask(__name__, 
                static_folder=os.path.join(os.path.dirname(__file__), "..", "dist"),
                static_url_path="",
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
    
    # Session Management and Rotation - with auth exemptions
    @app.before_request
    def manage_session_security():
        """Enhanced session security management"""
        # Skip for static files, health endpoints, React routes, and auth endpoints  
        auth_paths = ['/api/auth/login', '/api/auth/logout', '/api/auth/me', 
                     '/api/admin/businesses', '/api/admin/impersonate/exit', '/api/ui/login']
        # Add COMPLETE impersonation bypass - NUCLEAR OPTION
        impersonate_paths = ['/api/admin/businesses/', '/impersonate', '/api/admin/impersonate/']
        # NUCLEAR: Skip ANY PATH containing 'impersonate'
        is_impersonate_path = (('/impersonate' in request.path) or 
                              (request.path.startswith('/api/admin/businesses/') and request.path.endswith('/impersonate')))
        if (request.endpoint in ['static', 'health', 'readyz', 'version'] or 
            request.path in ['/', '/login', '/forgot', '/reset', '/home'] or
            any(request.path.startswith(p) for p in auth_paths) or is_impersonate_path or
            any(p in request.path for p in impersonate_paths)):
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
            
            # Session rotation (rotate session ID periodically) - FIXED: More conservative
            session_start = session.get('_session_start')
            if not session_start:
                session['_session_start'] = datetime.now().isoformat()
                session['_csrf_token'] = secrets.token_hex(16)
            else:
                start_time = datetime.fromisoformat(session_start)
                # FIXED: Increase rotation period from 2 to 24 hours and preserve session data better
                if datetime.now() - start_time > timedelta(hours=24):
                    # Rotate session but preserve ALL user data
                    user_data = session.get('al_user')
                    tenant_id = session.get('tenant_id')
                    token = session.get('token')
                    impersonating = session.get('impersonating', False)
                    
                    session.clear()
                    
                    # Restore all user session data
                    if user_data:
                        session['al_user'] = user_data
                        session['tenant_id'] = tenant_id
                        session['token'] = token
                        session['impersonating'] = impersonating
                        session['_session_start'] = datetime.now().isoformat()
                        session['_csrf_token'] = secrets.token_hex(16)
    
    # CSRF Protection - Single SeaSurf instance
    from server.extensions import csrf
    
    app.config.update({
        'SESSION_COOKIE_SECURE': False,   # preview
        'SESSION_COOKIE_SAMESITE': 'Lax',
        'SESSION_COOKIE_PATH': '/',
        'SEASURF_COOKIE_NAME': 'XSRF-TOKEN',
        'SEASURF_HEADER': 'X-CSRFToken',
    })
    
    csrf.init_app(app)  # ← פעם אחת בלבד
    print("🔒 SeaSurf CSRF Protection enabled")
    
    # CORS with security restrictions - FIXED for session cookies
    CORS(app, 
         origins=[
             "http://localhost:5000",
             "https://*.replit.app", 
             "https://*.replit.dev",
             "*"  # Allow all origins for development
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
            # Skip React auth routes and auth API endpoints
            auth_paths = ['/api/auth/login', '/api/auth/logout', '/api/auth/me',
                         '/api/admin/businesses', '/api/admin/impersonate/exit']
            # Also exempt specific impersonate endpoints dynamically  
            is_impersonate_path = (request.path.startswith('/api/admin/businesses/') and 
                                  request.path.endswith('/impersonate'))
            if (request.path in ['/', '/login', '/forgot', '/reset', '/home'] or
                any(request.path.startswith(p) for p in auth_paths) or is_impersonate_path):
                return
                
            g.audit_logger = audit_logger
            g.session_security = SessionSecurity
            
            # Update session activity
            SessionSecurity.update_activity()
            
            # Check session validity for protected routes - EXCLUDE auth endpoints from validation
            if request.endpoint and request.endpoint.startswith(('ui.', 'data_api.')):
                if not SessionSecurity.is_session_valid():
                    session.clear()
                    if request.headers.get('HX-Request'):
                        return '<div class="text-red-600 p-4 bg-red-50 rounded-lg">🔒 Session expired - please login again</div>', 401
        
        # Register auth system FIRST (after security middleware)
        # Using simplified auth from auth_api.py only
        
        # Session configuration for Preview (HTTP) mode - FIXED for better persistence
        app.config.update({
            'SESSION_COOKIE_NAME': 'al_sess',
            'SESSION_COOKIE_HTTPONLY': False,  # Allow JS access for debugging
            'SESSION_COOKIE_SECURE': False,   # HTTP mode (Replit doesn't use HTTPS in preview)
            'SESSION_COOKIE_SAMESITE': 'Lax',  # FIXED: Lax instead of None for better refresh support
            'SESSION_COOKIE_PATH': '/',
            'SESSION_COOKIE_DOMAIN': None,    # Let browser decide
            'SESSION_COOKIE_MAX_AGE': 28800,  # 8 hours in seconds (same as PERMANENT_SESSION_LIFETIME)
        })
        
        # Register auth blueprint - single clean system
        app.register_blueprint(auth_api)  # Auth API endpoints only
        print("✅ Auth blueprints registered")
        
        # Register new API blueprints
        from server.routes_admin import admin_bp
        from server.routes_crm import crm_bp
        from server.routes_business_management import biz_mgmt_bp
        from server.routes_twilio import twilio_bp
        from server.routes_calendar import calendar_bp
        app.register_blueprint(admin_bp)
        app.register_blueprint(crm_bp)
        app.register_blueprint(biz_mgmt_bp)
        app.register_blueprint(twilio_bp)
        app.register_blueprint(calendar_bp)
        print("✅ New API blueprints registered")
        print("✅ Twilio webhooks registered")
        
        # Register API Adapter Blueprint - Frontend Compatibility Layer
        from server.api_adapter import api_adapter_bp
        app.register_blueprint(api_adapter_bp)
        print("✅ API Adapter blueprint registered")
        
        # Health endpoints - MUST be registered
        from server.health_endpoints import health_bp
        app.register_blueprint(health_bp)
        print("✅ Health endpoints registered")
        
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
    
    # DISABLE Flask-Sock when using EventLet Composite WSGI to prevent conflicts
    # Flask-Sock route registration completely skipped to avoid protocol errors
    if False:  # Disabled to prevent conflict with EventLet WSGI
        from flask_sock import Sock
        sock = Sock(app)
        
        @sock.route('/ws/twilio-media')
        def websocket_fallback(ws):
            """REAL WebSocket FALLBACK route with Flask-Sock if Composite WSGI fails"""
            print("🔄 Flask-Sock WebSocket FALLBACK activated!", flush=True)
            
            try:
                print("✅ Flask-Sock WebSocket connection established", flush=True)
                
                # Import and use MediaStreamHandler
                from server.media_ws_ai import MediaStreamHandler
                handler = MediaStreamHandler(ws)
                handler.run()
                
            except Exception as e:
                print(f"❌ WebSocket fallback error: {e}", flush=True)
                import traceback
                traceback.print_exc()
            
        print("🔧 Flask-Sock WebSocket DISABLED - using EventLet Composite WSGI exclusively")
        
    # EventLet Composite WSGI handles WebSocket exclusively  
    print("🔧 WebSocket: EventLet Composite WSGI + Flask WebSocket fallback")
    
    # IMMEDIATE DEBUG: Test if routes register at all
    print("🔧 REGISTERING TEST ROUTES...")
    
    # NO WebSocket routes in Flask - handled by Composite WSGI in wsgi.py
    # WebSocket צריך להיות ברמת WSGI לפני Flask
    print("🔧 WebSocket routes removed from Flask - handled by wsgi.py composite")
    
    print("🔧 TEST ROUTE REGISTERED")
    
    # WebSocket routes handled by EventLet WebSocketWSGI in wsgi.py
    print("🔧 WebSocket routes handled by EventLet WebSocketWSGI in wsgi.py")
    print("📞 /ws/twilio-media → EventLet WebSocketWSGI with audio.twilio.com")
    
    # DEBUG: Test route to verify which version is running
    @app.route('/test-websocket-version')
    def test_websocket_version():
        """Test route to verify WebSocket integration is active"""
        return jsonify({
            'websocket_integration': 'EventLet_WebSocketWSGI_composite + Flask-Sock_fallback',
            'route': '/ws/twilio-media',
            'method': 'eventlet_websocket_wsgi + flask_sock_fallback',
            'worker_type': 'eventlet',
            'fallback_available': True,
            'real_websocket': True,
            'timestamp': int(time.time())
        })
    
    print("✅ WebSocket test route added: /test-websocket-version")
    
    # CRITICAL DEBUG: Print all registered routes
    print("🔍 ALL REGISTERED ROUTES:")
    for rule in app.url_map.iter_rules():
        print(f"  {rule.methods} {rule.rule}")
    print("🔍 Route registration complete")
    
    print("🔧 WebSocket routes removed from Flask - handled by wsgi.py composite")
    print("✅ Health routes handled by health_endpoints.py blueprint")
    
    # CRITICAL DEBUG: Add test route directly in app_factory for production
    @app.route('/debug-factory-http', methods=['GET', 'POST'])
    def debug_factory_http():
        """Test route in app_factory.py for production debugging"""
        import time
        
        print("🚨 APP_FACTORY HTTP HANDLER CALLED!", flush=True)
        
        # Immediate debug
        with open("/tmp/factory_http_debug.txt", "w") as f:
            f.write(f"FACTORY_HTTP_CALLED: {time.time()}\n")
            f.write(f"METHOD: {request.method}\n")
            f.write(f"HEADERS: {dict(request.headers)}\n")
            f.flush()
        
        return jsonify({
            'status': 'app_factory.py HTTP handler works!',
            'timestamp': time.time(),
            'method': request.method,
            'production': True
        })
    
    # תיקון /healthz ישירות כפי שצריך
    @app.route('/healthz', methods=['GET'])
    def healthz_app_factory():
        """Direct healthz route - WORKING VERSION"""
        return "ok", 200
    
    @app.route('/healthz-direct', methods=['GET'])
    def healthz_direct():
        """Direct healthz route for debugging"""
        return "ok", 200
    
    print("✅ Factory debug route registered: /debug-factory-http")
    print("✅ /healthz route added directly to app_factory")
    print("🆘 Emergency healthz-direct route added")
    
    # All Flask-Sock references completely removed

    # רישום בלו־פרינטים - AgentLocator 71
    # Twilio blueprint already registered above with other API blueprints
    
    # Note: Using @csrf.exempt decorators instead of exempt_urls for cleaner approach
    # WhatsApp unified registration only (no more routes_whatsapp.py)
    print("✅ WhatsApp routes removed - using unified only")
    
    # Enhanced 400 error handler for debugging CSRF issues
    @app.errorhandler(400)
    def bad_request_handler(e):
        """Enhanced 400 error handler for better debugging"""
        return jsonify({
            "error": "bad_request", 
            "debug_info": {
                "hint": "Check Content-Type and JSON schema",
                "content_type": request.headers.get("Content-Type"),
                "is_json": request.is_json,
                "method": request.method,
                "path": request.path,
                "csrf_token_missing": "CSRF token is missing" in str(e) or "Bad Request" in str(e)
            }
        }), 400
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

    # Version endpoint moved to health_endpoints.py to avoid duplicates

    # Auth endpoints removed - handled by routes_auth.py blueprint
    
    # Static TTS file serving (לפי ההנחיות - חובה ש MP3 files יהיו 200)
    @app.route('/static/tts/<path:filename>')
    def static_tts(filename):
        """Serve static TTS files"""
        return send_from_directory(os.path.join(os.path.dirname(__file__), "..", "static", "tts"), filename)
    

    # Health endpoints moved below to prevent duplicates
        
    # Simple SPA routes (temporary fix - replacing spa_bp)
    @app.route('/')
    @app.route('/app')
    @app.route('/app/')
    @app.route('/app/<path:subpath>')
    def serve_spa(subpath=''):
        """Simple SPA serving - serves our BUILD 18"""
        from pathlib import Path
        from flask import send_file
        DIST = Path(__file__).resolve().parents[1] / "dist"
        return send_file(DIST / "index.html")
    
    # Assets route
    @app.route('/assets/<path:filename>')
    def serve_assets(filename):
        """Serve assets with correct MIME types"""
        from pathlib import Path
        from flask import send_from_directory, make_response
        DIST = Path(__file__).resolve().parents[1] / "dist"
        resp = make_response(send_from_directory(DIST / "assets", filename))
        if filename.endswith('.js'):
            resp.headers['Content-Type'] = 'application/javascript'
        elif filename.endswith('.css'):
            resp.headers['Content-Type'] = 'text/css'
        return resp
    
    # Database initialization (לפי ההנחיות)
    from server.db import db
    import server.models_sql  # Import models module
    
    # Initialize SQLAlchemy with Flask app
    db.init_app(app)
    
    # Apply database migrations on boot (prevents 500 errors)
    try:
        with app.app_context():
            from server.db_migrate import apply_migrations
            apply_migrations()
            print("✅ Database migrations applied successfully")
    except Exception as e:
        print(f"⚠️ Database migration error: {e}")
        # Continue startup - don't crash on migration failures
    
    # Health endpoints removed - using health_endpoints.py blueprint only
    
    # DISABLE warmup temporarily to isolate boot issue
    # from server.services.lazy_services import warmup_services_async
    # warmup_services_async()
    print("🔧 Warmup disabled for debugging")
    
    # SPA blueprint disabled temporarily - using direct routes
    # from server.spa_static import spa_bp
    # app.register_blueprint(spa_bp)
    print("✅ Simple SPA routes registered (no blueprint)")
    
    return app