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
    
    # GOOGLE TTS CREDENTIALS SETUP - FIXED: Use permanent file
    # Handle both file path and JSON string credentials
    import json
    gcp_creds = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', '')
    if gcp_creds and gcp_creds.startswith('{'):
        # If it's a JSON string, create a PERMANENT file
        try:
            creds_data = json.loads(gcp_creds)
            credentials_path = '/tmp/gcp_credentials.json'
            with open(credentials_path, 'w') as f:
                json.dump(creds_data, f)
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
            print(f"🔧 GCP credentials converted from JSON to file: {credentials_path}")
        except Exception as e:
            print(f"⚠️ GCP credentials error: {e}")
    else:
        print(f"🔧 GCP credentials loaded from file path: {gcp_creds[:50]}...")
    
    app = Flask(__name__, 
                static_folder=os.path.join(os.path.dirname(__file__), "..", "client", "dist"),
                static_url_path="",
                template_folder=os.path.join(os.path.dirname(__file__), "templates"))
    
    # הדגל השחור - לוג זיהוי לקוד ישן/חדש (שלב 7)
    import time, subprocess
    
    # נתיב FE_DIST שהשרת משרת
    FE_DIST_PATH = os.path.join(os.path.dirname(__file__), "..", "client", "dist")
    print(f"🔧 FE_DIST={FE_DIST_PATH}")
    
    # Git SHA קצר
    try:
        git_sha = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], 
                                        cwd=os.path.dirname(__file__), 
                                        stderr=subprocess.DEVNULL).decode().strip()
    except:
        git_sha = "dev"
    print(f"🔧 APP_SHA={git_sha}")
    
    version_info = {
        "build": 87,
        "sha": git_sha,
        "fe": "client/dist",
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "app": "AgentLocator-Complete",
        "commit": os.getenv("GIT_COMMIT", git_sha),
        "startup_ts": int(time.time())
    }
    print(f"🚩 APP_START {version_info}")
    
    # Database configuration with SSL fix
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///default.db')
    
    # ✅ PRODUCTION SAFETY CHECK - No SQLite in production!
    IS_PRODUCTION = os.getenv('REPLIT_DEPLOYMENT') == '1' or os.getenv('RAILWAY_ENVIRONMENT') == 'production'
    if IS_PRODUCTION and DATABASE_URL.startswith('sqlite'):
        raise RuntimeError("❌ FATAL: SQLite is not allowed in production! Set DATABASE_URL secret.")
    
    # Log database driver (without password)
    db_driver = DATABASE_URL.split(':')[0] if DATABASE_URL else 'none'
    print(f"🔧 DB_DRIVER: {db_driver}", flush=True)
    
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
            # Fix for Eventlet + SQLAlchemy lock issue
            'poolclass': __import__('sqlalchemy.pool', fromlist=['NullPool']).NullPool,
            'connect_args': {
                'connect_timeout': 30,
                'application_name': 'AgentLocator-71'
            }
        },
        # Session configuration
        'SESSION_COOKIE_HTTPONLY': True,
        'PERMANENT_SESSION_LIFETIME': timedelta(hours=8),
        'SESSION_REFRESH_EACH_REQUEST': True
    })
    
    # 1) Flask bootstrap אחיד לשתי הסביבות (Preview/Prod) - לפי ההנחיות המדויקות
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    app.config.update(PREFERRED_URL_SCHEME='https')

    IS_PREVIEW = (
        'picard.replit.dev' in os.getenv('REPLIT_URL', '') or
        os.getenv('PREVIEW_MODE') == '1'
    )

    # Consolidated Cookie policy - מתוקן לפי הarchitect (תמיד HttpOnly=True!)
    if IS_PREVIEW:
        app.config.update(
            SESSION_COOKIE_SAMESITE='None',  # None לPreview לפי ההנחיות
            SESSION_COOKIE_SECURE=True,      # True לPreview לפי ההנחיות  
            SESSION_COOKIE_HTTPONLY=True,    # ✅ אבטחה - תמיד HttpOnly=True (לפי architect)
            REMEMBER_COOKIE_SAMESITE='None',
            REMEMBER_COOKIE_SECURE=True,
            REMEMBER_COOKIE_HTTPONLY=True,   # ✅ גם remember cookie מאובטח
        )
    else:
        app.config.update(
            SESSION_COOKIE_SAMESITE='Lax',   # Lax לProduction לפי ההנחיות
            SESSION_COOKIE_SECURE=True,      # True לProduction לפי ההנחיות
            SESSION_COOKIE_HTTPONLY=True,    # ✅ Secure in production (לפי architect)
            REMEMBER_COOKIE_SAMESITE='Lax',
            REMEMBER_COOKIE_SECURE=True,
            REMEMBER_COOKIE_HTTPONLY=True,   # ✅ גם remember cookie מאובטח
        )

    # SeaSurf – מקור יחיד
    app.config.update(
        SEASURF_COOKIE_NAME='XSRF-TOKEN',
        SEASURF_HEADER='X-CSRFToken',
    )
    
    # Initialize SeaSurf
    from server.extensions import csrf
    csrf.init_app(app)
    
    # שגיאות JSON ברורות (שלא תראה Error {} ריק) - REMOVED DUPLICATES
    
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
    
# הוסרה כפילות של _dbg_csrf

    # Session Management and Rotation - with auth exemptions
    @app.before_request
    def manage_session_security():
        """Enhanced session security management"""
        # Skip for static files, health endpoints, React routes, and auth endpoints  
        auth_paths = ['/api/auth/login', '/api/auth/logout', '/api/auth/me', '/api/auth/csrf', '/api/ui/login']
        if (request.endpoint in ['static', 'health', 'readyz', 'version'] or 
            request.path in ['/', '/login', '/forgot', '/reset', '/home'] or
            any(request.path.startswith(p) for p in auth_paths)):
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
                # SeaSurf handles CSRF - no manual _csrf_token needed
            else:
                start_time = datetime.fromisoformat(session_start)
                # FIXED: Increase rotation period from 2 to 24 hours and preserve session data better
                if datetime.now() - start_time > timedelta(hours=24):
                    # Rotate session but preserve ALL user data
                    user_data = session.get('al_user')
                    impersonated_tenant_id = session.get('impersonated_tenant_id')  # Fixed key per guidelines
                    token = session.get('token')
                    impersonating = session.get('impersonating', False)
                    
                    session.clear()
                    
                    # Restore all user session data
                    if user_data:
                        session['al_user'] = user_data
                        session['impersonated_tenant_id'] = impersonated_tenant_id  # Fixed key per guidelines
                        session['token'] = token
                        session['impersonating'] = impersonating
                        session['_session_start'] = datetime.now().isoformat()
                        # SeaSurf handles CSRF - no manual _csrf_token needed
    
    # CSRF כבר מוגדר למעלה - הסרת כפילות
    
    # CORS with security restrictions - SECURE: regex patterns work in Flask-CORS
    cors_origins = [
        "http://localhost:5000",
        r"^https://[\w-]+\.replit\.app$",    # Regex pattern for *.replit.app
        r"^https://[\w-]+\.replit\.dev$"     # Regex pattern for *.replit.dev
    ]
    # Only add specific preview origins in Preview mode
    if IS_PREVIEW:
        cors_origins.extend([
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:8080"          # Common dev server ports
        ])  # Specific preview origins only
    
    CORS(app, 
         origins=cors_origins,
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
        
        # AI Prompt Management Blueprint - לפי ההנחיות
        from server.routes_ai_prompt import ai_prompt_bp
        app.register_blueprint(ai_prompt_bp)
        
        # Status Management Blueprint - Custom Lead Statuses
        from server.routes_status_management import status_management_bp
        app.register_blueprint(status_management_bp)
        
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
        
        # Session name and path (cookie security already configured above)
        app.config.update({
            'SESSION_COOKIE_NAME': 'al_sess',
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
        from server.routes_leads import leads_bp
        app.register_blueprint(admin_bp)
        app.register_blueprint(crm_bp)
        app.register_blueprint(biz_mgmt_bp)
        app.register_blueprint(twilio_bp)
        app.register_blueprint(calendar_bp)
        app.register_blueprint(leads_bp)
        
        # Calls API for recordings and transcripts
        from server.routes_calls import calls_bp
        app.register_blueprint(calls_bp)
        
        # Register receipts and contracts endpoints
        from server.routes_receipts_contracts import receipts_contracts_bp
        app.register_blueprint(receipts_contracts_bp)
        
        # WhatsApp Canonical API (replaces all other WhatsApp routes)
        from server.routes_whatsapp import whatsapp_bp
        app.register_blueprint(whatsapp_bp)
        
        # WhatsApp Webhook endpoints for Baileys service
        from server.routes_webhook import webhook_bp
        app.register_blueprint(webhook_bp)
        
        # Customer Intelligence API
        from server.routes_intelligence import intelligence_bp
        app.register_blueprint(intelligence_bp)
        
        # Admin Channels API - Multi-tenant routing management
        from server.routes_admin_channels import admin_channels_bp
        app.register_blueprint(admin_channels_bp)
        
        # CSRF exemptions לroutes WhatsApp - only GET routes for security
        try:
            csrf.exempt(app.view_functions.get('whatsapp.status'))  # GET - safe
            csrf.exempt(app.view_functions.get('whatsapp.qr'))      # GET - safe  
            # POST start NOT exempt for security - requires CSRF token
            app.logger.info("WhatsApp CSRF exemptions applied (GET only)")
        except Exception as e:
            app.logger.warning(f"WhatsApp CSRF exemption issue: {e}")
        
        app.logger.info("New API blueprints registered")
        app.logger.info("Twilio webhooks registered")
        
        # Register API Adapter Blueprint - Frontend Compatibility Layer
        from server.api_adapter import api_adapter_bp
        app.register_blueprint(api_adapter_bp)
        app.logger.info("API Adapter blueprint registered")
        
        # Health endpoints - MUST be registered
        from server.health_endpoints import health_bp
        app.register_blueprint(health_bp)
        app.logger.info("Health endpoints registered")
        
        # data_api removed - כפילות
        
        # Register UI blueprint last (after React routes are defined)
        app.logger.info(f"Registering UI Blueprint: {ui_bp}")
        app.register_blueprint(ui_bp, url_prefix='')  # No prefix for admin/business routes
        
        # CSRF exemption for login after blueprint registration
        from server.ui.routes import api_login
        csrf.exempt(api_login)
        app.logger.info("CSRF exemption added for login")
        
        app.logger.info("All blueprints registered")
    except Exception as e:
        app.logger.error(f"Blueprint registration error: {e}")
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
        
    # WebSocket routes handled by ASGI layer (asgi.py with Starlette)
    # Flask app doesn't handle WebSocket - delegated to ASGI wrapper
    print("🔧 WebSocket: Handled by ASGI layer (Starlette WebSocket)")
    print("📞 /ws/twilio-media → ASGI WebSocket (asgi.py)")
    
    # DEBUG: Test route to verify which version is running
    @app.route('/test-websocket-version')
    def test_websocket_version():
        """Test route to verify WebSocket integration is active"""
        # Check if running under ASGI or standalone
        server_type = 'uvicorn_asgi' if os.getenv('ASGI_SERVER') else 'standalone'
        
        return jsonify({
            'build': 70,
            'websocket_integration': 'Starlette_ASGI_WebSocket',
            'route': '/ws/twilio-media',
            'method': 'asgi_starlette_websocket',
            'worker_type': server_type,
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
    
    # Health endpoints handled by health_endpoints.py blueprint
    
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
    
    # WhatsApp Unified API - REPLACED by canonical routes_whatsapp.py
    
    # Baileys worker integration - DISABLED for clean setup
    # External Baileys service runs on port 3300 via start_system_stable.sh
    
    # WhatsApp Baileys Proxy Routes - REPLACED by canonical routes_whatsapp.py
    # from server.routes_baileys_proxy import bp_wa
    # app.register_blueprint(bp_wa)
    
    # Legacy WhatsApp Proxy Routes - REPLACED by canonical routes_whatsapp.py
    # from server.routes_whatsapp import wa_bp
    # app.register_blueprint(wa_bp)
    
    # Route registration verification
    wa_routes = [rule for rule in app.url_map.iter_rules() if str(rule).startswith('/wa/')]
    wa_proxy_routes = [rule for rule in app.url_map.iter_rules() if str(rule).startswith('/api/wa-proxy')]
    print(f"✅ Baileys proxy routes: {len(wa_routes)} /wa/* endpoints")
    print(f"✅ Legacy proxy routes: {len(wa_proxy_routes)} /api/wa-proxy/* endpoints")
    
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
        
    # SPA serving - לפי ההנחיות המדויקות  
    from pathlib import Path
    from flask import send_from_directory, abort
    FE_DIST = Path(__file__).resolve().parents[1] / "client" / "dist"
    
    # הדפסה פעם אחת בהפעלה
    try:
        mtime = FE_DIST.stat().st_mtime
        print(f"FE_DIST = {FE_DIST} mtime = {mtime}")
    except Exception as e:
        print(f"⚠️ FE_DIST error: {e}")
    
    @app.route('/assets/<path:filename>')
    def assets(filename): 
        return send_from_directory(FE_DIST/'assets', filename)

    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def spa(path):
        # אל תיתן לנתיבי /api, /webhook, /static, /wa להגיע לכאן
        if path.startswith(('api','webhook','static','assets','wa')):
            abort(404)
        resp = send_from_directory(FE_DIST, 'index.html')
        resp.cache_control.no_store = True
        return resp
    
    # DEBUG endpoint removed - no longer needed
    
    # Database initialization (לפי ההנחיות)
    from server.db import db
    import server.models_sql  # Import models module
    
    # Initialize SQLAlchemy with Flask app
    db.init_app(app)
    
    # CRITICAL FIX: Run migrations FIRST, then initialization
    # Order matters: tables must exist before we can initialize data
    if os.getenv('RUN_MIGRATIONS_ON_START', '0') == '1':
        try:
            with app.app_context():
                from server.db_migrate import apply_migrations
                apply_migrations()
                print("✅ Database migrations applied successfully")
                
                # Create default admin user if none exists
                from server.auth_api import create_default_admin
                create_default_admin()
                
                # 🚀 AUTO-INITIALIZATION for production deployments (runs AFTER migrations)
                # This ensures the system is ready to use out-of-the-box
                from server.init_database import initialize_production_database
                initialization_success = initialize_production_database()
                if initialization_success:
                    print("✅ Production database initialized successfully")
                else:
                    print("⚠️ Database initialization had issues but continuing...")
        except Exception as e:
            print(f"⚠️ Database migration/initialization error: {e}")
            import traceback
            traceback.print_exc()
            # Continue startup - don't crash on migration failures
    else:
        print("🔧 Database migrations skipped (set RUN_MIGRATIONS_ON_START=1 to enable)")
        print("🔧 Server will start immediately without blocking on DB operations")
    
    # Health endpoints removed - using health_endpoints.py blueprint only
    
    # DISABLE warmup temporarily to isolate boot issue
    # from server.services.lazy_services import warmup_services_async
    # warmup_services_async()
    print("🔧 Warmup disabled for debugging")
    
    # דיבוג זמני CSRF (מוחקים אחרי שזה עובד) 
    @app.before_request
    def _dbg_csrf():
        if request.path.endswith('/prompt') or request.path.endswith('/impersonate'):
            print('CSRF-DBG',
                  'cookie=', request.cookies.get('XSRF-TOKEN'),
                  'header=', request.headers.get('X-CSRFToken'),
                  'ct=', request.headers.get('Content-Type'))

    # ✅ ERROR HANDLERS - JSON responses instead of Error {}
    @app.errorhandler(400)
    def handle_bad_request(e):
        return jsonify({"error": "bad_request", "message": str(e)}), 400
    
    @app.errorhandler(401) 
    def handle_unauthorized(e):
        return jsonify({"error": "unauthorized", "message": "Authentication required"}), 401
    
    # REMOVED generic 403 handler - let auth decorators return detailed responses
    # Note: flask_seasurf doesn't export CSRFError, CSRF validation errors 
    # are handled by the framework's built-in error handling
    
    @app.errorhandler(404)
    def handle_not_found(e):
        # ✅ Only return JSON for API routes, let SPA handle everything else
        if request.path.startswith('/api/') or request.path.startswith('/webhook/'):
            return jsonify({"error": "not_found", "message": "Resource not found"}), 404
        # For non-API routes, serve the React app
        try:
            static_folder = app.static_folder or os.path.join(os.path.dirname(__file__), "..", "client", "dist")
            return send_from_directory(static_folder, 'index.html')
        except:
            return jsonify({"error": "not_found", "message": "Resource not found"}), 404
    
    @app.errorhandler(409)
    def handle_conflict(e):
        return jsonify({"error": "conflict", "message": str(e)}), 409
    
    @app.errorhandler(500)
    def handle_server_error(e):
        return jsonify({"error": "server_error", "message": "Internal server error"}), 500
    
    # Version endpoint handled by health_endpoints.py blueprint
    
    # POST-STARTUP DATABASE OPERATIONS ENDPOINT
    @app.route('/api/admin/run-migrations', methods=['POST'])
    def run_migrations_endpoint():
        """Run database migrations after startup (non-blocking alternative)"""
        try:
            from server.db_migrate import apply_migrations
            from server.auth_api import create_default_admin
            
            with app.app_context():
                apply_migrations()
                create_default_admin()
                
            return jsonify({
                'success': True,
                'message': 'Database migrations and admin creation completed successfully'
            }), 200
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    # הדפסת רשימת נתיבים לדיבוג
    print("\n=== URL MAP ===")
    for r in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
        if any(keyword in r.rule for keyword in ['/api/', '/prompt', '/impersonate', '/csrf', '/auth']):
            print(f"  {r.methods} {r.rule} -> {r.endpoint}")
    print("================")
    
    # SPA blueprint disabled temporarily - using direct routes
    # from server.spa_static import spa_bp
    # app.register_blueprint(spa_bp)
    print("✅ Simple SPA routes registered (no blueprint)")
    
    return app