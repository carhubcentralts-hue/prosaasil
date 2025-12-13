"""
Hebrew AI Call Center CRM - App Factory (לפי ההנחיות המדויקות)
"""
import os
import logging
from flask import Flask, jsonify, send_from_directory, send_file, current_app, request, session, g
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

# Setup async logging BEFORE anything else
from server.logging_async import setup_async_root
if os.getenv("ASYNC_LOG_QUEUE", "1") == "1":
    setup_async_root(level=logging.INFO)
else:
    logging.basicConfig(level=logging.INFO)

try:
    from flask_seasurf import SeaSurf
    CSRF_AVAILABLE = True
except ImportError:
    SeaSurf = None
    CSRF_AVAILABLE = False
from datetime import datetime, timedelta
import secrets
import hashlib

# 🔥 CRITICAL FIX: Single instance management to prevent APP_START crashes
_app_singleton = None
_app_lock = __import__('threading').RLock()  # RLock allows reentrant acquisition (prevents deadlock)

def get_process_app():
    """
    🔥 CRITICAL FIX: Get the Flask app without creating a new one
    
    This function PREVENTS app restarts during active calls/conversations.
    Thread-safe singleton pattern with Lock.
    
    Usage:
    - In request context: Returns current_app from Flask
    - Outside request: Returns cached singleton app
    - NEVER creates new app (prevents APP_START crashes)
    
    Returns:
        Flask app instance (never None in production)
    """
    global _app_singleton
    from flask import has_request_context, current_app
    
    # If we're in a Flask request context, use current_app
    if has_request_context():
        return current_app
    
    # Otherwise, return the singleton (thread-safe)
    with _app_lock:
        if _app_singleton is None:
            _app_singleton = create_app()
        
        return _app_singleton

def create_app():
    """Create Flask application with React frontend (לפי ההנחיות המדויקות)"""
    
    # GCP credentials setup
    import json
    gcp_creds = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', '')
    if gcp_creds and gcp_creds.startswith('{'):
        try:
            creds_data = json.loads(gcp_creds)
            credentials_path = '/tmp/gcp_credentials.json'
            with open(credentials_path, 'w') as f:
                json.dump(creds_data, f)
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
        except Exception:
            pass
    
    app = Flask(__name__, 
                static_folder=os.path.join(os.path.dirname(__file__), "..", "client", "dist"),
                static_url_path="",
                template_folder=os.path.join(os.path.dirname(__file__), "templates"))
    
    import time, subprocess
    
    # Git SHA for version info endpoint
    try:
        git_sha = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], 
                                        cwd=os.path.dirname(__file__), 
                                        stderr=subprocess.DEVNULL,
                                        timeout=2).decode().strip()
    except:
        git_sha = "dev"
    
    version_info = {
        "build": 87,
        "sha": git_sha,
        "fe": "client/dist",
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "app": "AgentLocator-Complete",
        "commit": os.getenv("GIT_COMMIT", git_sha),
        "startup_ts": int(time.time())
    }
    
    # Database configuration with SSL fix
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///default.db')
    
    # ✅ PRODUCTION SAFETY CHECK - No SQLite in production!
    IS_PRODUCTION = os.getenv('REPLIT_DEPLOYMENT') == '1' or os.getenv('RAILWAY_ENVIRONMENT') == 'production'
    if IS_PRODUCTION and DATABASE_URL.startswith('sqlite'):
        raise RuntimeError("❌ FATAL: SQLite is not allowed in production! Set DATABASE_URL secret.")
    
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    
    # Enterprise Security Configuration
    app.config.update({
        'SECRET_KEY': os.getenv('SECRET_KEY', secrets.token_hex(32)),
        'DATABASE_URL': DATABASE_URL,
        'SQLALCHEMY_DATABASE_URI': DATABASE_URL,
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'SQLALCHEMY_ENGINE_OPTIONS': {
            'pool_pre_ping': True,  # ✅ DB RESILIENCE: Verify connections before use (prevents stale connections)
            'pool_recycle': 300,    # ✅ DB RESILIENCE: Recycle connections after 5 min (handles Neon idle timeout)
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
    
    # ✅ DB RESILIENCE: Log pool configuration for troubleshooting
    logger.info(f"[DB_POOL] pool_pre_ping=True pool_recycle=300s (Neon-optimized)")
    
    # 1) Flask bootstrap - ProxyFix for Replit's reverse proxy
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    app.config.update(PREFERRED_URL_SCHEME='https')

    # ═══════════════════════════════════════════════════════════════════
    # BUILD 143 UNIFIED COOKIE CONFIGURATION - ONE SET FOR ALL ENVIRONMENTS
    # All cookies MUST use the same settings for Replit cross-origin to work!
    # BUILD 177: Support HTTP mode via COOKIE_SECURE=false env var for external servers
    # ═══════════════════════════════════════════════════════════════════
    
    # Determine if cookies should be secure (HTTPS only)
    # Default: True for production (HTTPS required)
    # Set COOKIE_SECURE=false for HTTP-only deployments (not recommended for production!)
    cookie_secure = os.getenv("COOKIE_SECURE", "true").lower() != "false"
    cookie_samesite = 'None' if cookie_secure else 'Lax'  # SameSite=None requires Secure
    
    if not cookie_secure:
        app.logger.warning("⚠️ COOKIE_SECURE=false - Running in HTTP mode. NOT recommended for production!")
    
    # Session Cookie Settings
    app.config.update(
        SESSION_COOKIE_NAME='session',
        SESSION_COOKIE_SECURE=cookie_secure,       # BUILD 177: Configurable
        SESSION_COOKIE_SAMESITE=cookie_samesite,   # Must be Lax if not Secure
        SESSION_COOKIE_HTTPONLY=True,     # Security: JS can't read session
        SESSION_COOKIE_PATH='/',
        REMEMBER_COOKIE_SECURE=cookie_secure,
        REMEMBER_COOKIE_SAMESITE=cookie_samesite,
        REMEMBER_COOKIE_HTTPONLY=True,
    )
    
    # SeaSurf CSRF Cookie Settings - MUST match session settings!
    app.config.update(
        SEASURF_COOKIE_NAME='csrf_token',
        SEASURF_HEADER='X-CSRFToken',
        SEASURF_COOKIE_SECURE=cookie_secure,       # BUILD 177: Configurable
        SEASURF_COOKIE_SAMESITE=cookie_samesite,   # Must be Lax if not Secure
        SEASURF_COOKIE_HTTPONLY=False,    # MUST be False! Frontend needs to read it
        SEASURF_COOKIE_PATH='/',
        SEASURF_INCLUDE_OR_EXEMPT_VIEWS='include',  # Default include all views
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
            
        # BUILD 142 FINAL: Session timeout check - DON'T clear session automatically!
        if 'user' in session or 'al_user' in session:
            last_activity = session.get('_last_activity')
            if last_activity:
                last_time = datetime.fromisoformat(last_activity)
                if datetime.now() - last_time > timedelta(hours=8):
                    # BUILD 142 FINAL: Return 401 but DON'T clear session
                    # Let the client handle re-authentication
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
                # BUILD 142 FINAL: Increase rotation period and preserve BOTH session keys!
                if datetime.now() - start_time > timedelta(hours=24):
                    # Preserve ALL user session data (BOTH keys + impersonation)
                    user_data = session.get('user')  # BUILD 142: Save BOTH keys!
                    al_user_data = session.get('al_user')
                    impersonated_tenant_id = session.get('impersonated_tenant_id')
                    token = session.get('token')
                    
                    session.clear()
                    
                    # Restore BOTH user session keys
                    if user_data:
                        session['user'] = user_data
                    if al_user_data:
                        session['al_user'] = al_user_data
                    if impersonated_tenant_id:
                        session['impersonated_tenant_id'] = impersonated_tenant_id
                    if token:
                        session['token'] = token
                    session['_session_start'] = datetime.now().isoformat()
                    # SeaSurf handles CSRF - no manual _csrf_token needed
    
    # CSRF כבר מוגדר למעלה - הסרת כפילות
    
    # CORS with security restrictions - SECURE: regex patterns work in Flask-CORS
    # BUILD 143: All origins unified - no more IS_PREVIEW checks
    # BUILD 177: Support external domains via CORS_ALLOWED_ORIGINS env var
    cors_origins = [
        "http://localhost:5000",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8080",
        r"^https://[\w-]+\.replit\.app$",    # Regex pattern for *.replit.app
        r"^https://[\w-]+\.replit\.dev$"     # Regex pattern for *.replit.dev
    ]
    
    # Add external origins from environment variable (comma-separated)
    # Example: CORS_ALLOWED_ORIGINS=https://myapp.contabo.com,https://api.example.com
    external_origins = os.getenv("CORS_ALLOWED_ORIGINS", "")
    if external_origins:
        for origin in external_origins.split(","):
            origin = origin.strip()
            if origin:
                cors_origins.append(origin)
                app.logger.info(f"[CORS] Added external origin: {origin}")
    
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
            
            # BUILD 142 FINAL: Check session validity - DON'T clear session automatically!
            if request.endpoint and request.endpoint.startswith(('ui.', 'data_api.')):
                if not SessionSecurity.is_session_valid():
                    # Return 401 but DON'T clear session
                    if request.headers.get('HX-Request'):
                        return '<div class="text-red-600 p-4 bg-red-50 rounded-lg">🔒 Session expired - please login again</div>', 401
                    return jsonify({'error': 'Session invalid'}), 401
        
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
        app.register_blueprint(auth_api)
        
        # Register new API blueprints
        from server.routes_admin import admin_bp
        from server.routes_crm import crm_bp
        from server.routes_business_management import biz_mgmt_bp
        from server.routes_twilio import twilio_bp
        from server.routes_calendar import calendar_bp
        from server.routes_leads import leads_bp
        from server.routes_user_management import user_mgmt_api
        app.register_blueprint(admin_bp)
        app.register_blueprint(crm_bp)
        app.register_blueprint(biz_mgmt_bp)
        app.register_blueprint(twilio_bp)
        app.register_blueprint(calendar_bp)
        app.register_blueprint(leads_bp)
        app.register_blueprint(user_mgmt_api)
        
        # Calls API for recordings and transcripts
        from server.routes_calls import calls_bp
        app.register_blueprint(calls_bp)
        
        # BUILD 174: Outbound Calls API
        from server.routes_outbound import outbound_bp
        app.register_blueprint(outbound_bp)
        
        # Register receipts and contracts endpoints
        from server.routes_receipts_contracts import receipts_contracts_bp
        app.register_blueprint(receipts_contracts_bp)
        
        # WhatsApp Canonical API (replaces all other WhatsApp routes)
        from server.routes_whatsapp import whatsapp_bp, internal_whatsapp_bp
        app.register_blueprint(whatsapp_bp)
        app.register_blueprint(internal_whatsapp_bp)  # BUILD 151: Internal status webhook
        
        # WhatsApp Webhook endpoints for Baileys service
        from server.routes_webhook import webhook_bp
        app.register_blueprint(webhook_bp)
        
        # Customer Intelligence API
        from server.routes_intelligence import intelligence_bp
        app.register_blueprint(intelligence_bp)
        
        # Agent API - AgentKit powered AI agents with tools
        from server.routes_agent import bp as agent_bp
        app.register_blueprint(agent_bp)
        
        # Agent Ops API - Unified AgentKit operations
        from server.routes_agent_ops import ops_bp
        app.register_blueprint(ops_bp)
        
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
    
    # BUILD 168.2: Minimal production logging - only slow requests (>1s)
    import time as _time
    
    @app.before_request
    def _req_start():
        g._request_start = _time.time()

    @app.after_request
    def _req_timing(resp):
        if hasattr(g, '_request_start'):
            duration = _time.time() - g._request_start
            # Only log slow API requests (>1s)
            if duration > 1.0 and request.path.startswith('/api/'):
                current_app.logger.warning(f"SLOW_API: {request.method} {request.path} took {duration:.2f}s")
        return resp
    
    # DISABLE Flask-Sock when using EventLet Composite WSGI to prevent conflicts
    # Flask-Sock route registration completely skipped to avoid protocol errors
    if False:  # Disabled to prevent conflict with EventLet WSGI
        from flask_sock import Sock
        sock = Sock(app)
        
        @sock.route('/ws/twilio-media')
        def websocket_fallback(ws):
            """REAL WebSocket FALLBACK route with Flask-Sock if Composite WSGI fails"""
            try:
                from server.media_ws_ai import MediaStreamHandler
                handler = MediaStreamHandler(ws)
                handler.run()
            except Exception as e:
                app.logger.error(f"WebSocket fallback error: {e}")
    
    # Test route to verify which version is running
    @app.route('/test-websocket-version')
    def test_websocket_version():
        """Test route to verify WebSocket integration is active"""
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
    
    # Debug test route
    @app.route('/debug-factory-http', methods=['GET', 'POST'])
    def debug_factory_http():
        """Test route in app_factory.py for production debugging"""
        import time
        return jsonify({
            'status': 'app_factory.py HTTP handler works!',
            'timestamp': time.time(),
            'method': request.method,
            'production': True
        })
    
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
    

    # Version endpoint moved to health_endpoints.py to avoid duplicates

    # Auth endpoints removed - handled by routes_auth.py blueprint
    
    # Static TTS file serving (לפי ההנחיות - חובה ש MP3 files יהיו 200)
    @app.route('/static/tts/<path:filename>')
    def static_tts(filename):
        """Serve static TTS files"""
        return send_from_directory(os.path.join(os.path.dirname(__file__), "..", "static", "tts"), filename)
    
    # BUILD 172: Serve uploaded note attachments with session-based authentication
    @app.route('/uploads/notes/<int:tenant_id>/<path:filename>')
    def serve_note_attachment(tenant_id, filename):
        """Serve uploaded note attachments - requires session authentication and tenant match"""
        from flask import session, abort
        
        # Check session-based authentication (same as require_api_auth)
        user = session.get("al_user") or session.get("user")
        if not user:
            abort(401)
        
        user_role = user.get('role', '')
        
        # Compute user's tenant - impersonation overrides business_id
        if session.get("impersonated_tenant_id"):
            user_tenant = session.get("impersonated_tenant_id")
        else:
            user_tenant = user.get('business_id')
        
        # System admin can access all tenants
        if user_role != 'system_admin' and user_tenant != tenant_id:
            abort(403)
        
        # Safe path check - prevent directory traversal
        if '..' in filename or filename.startswith('/'):
            abort(400)
        
        uploads_dir = os.path.join(os.path.dirname(__file__), "..", "uploads", "notes", str(tenant_id))
        file_path = os.path.join(uploads_dir, filename)
        
        # Check file exists
        if not os.path.isfile(file_path):
            abort(404)
        
        return send_from_directory(uploads_dir, filename)

    # Health endpoints moved below to prevent duplicates
        
    # SPA serving - לפי ההנחיות המדויקות  
    from pathlib import Path
    from flask import send_from_directory, abort
    FE_DIST = Path(__file__).resolve().parents[1] / "client" / "dist"
    
    
    @app.route('/assets/<path:filename>')
    def assets(filename):
        """Serve static assets with immutable cache headers"""
        resp = send_from_directory(FE_DIST/'assets', filename)
        # Assets have hash in filename → safe to cache forever
        resp.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
        # Ensure correct MIME types
        if filename.endswith('.js'):
            resp.headers['Content-Type'] = 'application/javascript'
        elif filename.endswith('.css'):
            resp.headers['Content-Type'] = 'text/css'
        return resp

    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def spa(path):
        # אל תיתן לנתיבי /api, /webhook, /static, /wa, /uploads להגיע לכאן
        if path.startswith(('api','webhook','static','assets','wa','uploads')):
            abort(404)
        resp = send_from_directory(FE_DIST, 'index.html')
        # index.html must never be cached (always fresh)
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        resp.headers['Pragma'] = 'no-cache'
        resp.headers['Expires'] = '0'
        return resp
    
    # DEBUG endpoint removed - no longer needed
    
    # Database initialization (לפי ההנחיות)
    from server.db import db
    import server.models_sql  # Import models module
    
    # Initialize SQLAlchemy with Flask app
    db.init_app(app)
    
    # ⚡ DEPLOYMENT FIX: Run heavy initialization in background
    # This prevents deployment timeout while still ensuring DB is ready
    def _background_initialization():
        """Run migrations and initialization after server is listening"""
        import time
        time.sleep(0.5)  # Let server bind to port first
        
        is_production = os.getenv('RUN_MIGRATIONS_ON_START', '0') == '1'
        
        if is_production:
            try:
                with app.app_context():
                    from server.db_migrate import apply_migrations
                    apply_migrations()
                    
                    # Migrate legacy admin roles to system_admin
                    try:
                        from server.scripts.migrate_admin_roles import migrate_admin_roles
                        migrate_admin_roles()
                    except Exception:
                        pass
                    
                    # Fix FAQ patterns
                    try:
                        from server.models_sql import FAQ
                        import json
                        
                        def normalize_patterns_quick(payload):
                            if payload is None or payload == "":
                                return []
                            if isinstance(payload, list):
                                return [str(p).strip() for p in payload if p and str(p).strip()]
                            if isinstance(payload, str):
                                try:
                                    parsed = json.loads(payload.strip())
                                    if isinstance(parsed, list):
                                        return [str(p).strip() for p in parsed if p and str(p).strip()]
                                except:
                                    pass
                            return []
                        
                        faqs = FAQ.query.all()
                        fixed_count = 0
                        for faq in faqs:
                            if not isinstance(faq.patterns_json, list):
                                normalized = normalize_patterns_quick(faq.patterns_json)
                                faq.patterns_json = normalized
                                fixed_count += 1
                        
                        if fixed_count > 0:
                            db.session.commit()
                            from server.services.faq_cache import faq_cache
                            affected = set(faq.business_id for faq in faqs if faq.patterns_json)
                            for bid in affected:
                                faq_cache.invalidate(bid)
                    except Exception:
                        pass
            except Exception:
                pass
        else:
            # Development mode - quick table creation
            try:
                with app.app_context():
                    db.create_all()
            except Exception:
                pass
        
        # Shared initialization
        try:
            with app.app_context():
                from server.auth_api import create_default_admin
                create_default_admin()
                
                from server.init_database import initialize_production_database
                initialize_production_database()
        except Exception:
            pass
    
    # Start background initialization thread
    import threading
    init_thread = threading.Thread(target=_background_initialization, daemon=True)
    init_thread.start()
    
    # Preload services after startup to avoid cold start
    from server.services.lazy_services import warmup_services_async, start_periodic_warmup
    warmup_services_async()
    start_periodic_warmup()
    

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
    
    
    # TTS Pre-warming on startup (prevents cold start)
    try:
        from server.services.gcp_tts_live import maybe_warmup
        maybe_warmup()
    except Exception:
        pass
    
    # Pre-create agents to eliminate cold starts
    try:
        from server.agent_tools.agent_factory import warmup_all_agents
        
        def warmup_with_context():
            with app.app_context():
                try:
                    warmup_all_agents()
                except Exception:
                    pass
        
        import threading
        warmup_thread = threading.Thread(target=warmup_with_context, daemon=True)
        warmup_thread.start()
    except Exception:
        pass
    
    # Set singleton so future calls to get_process_app() reuse this instance
    global _app_singleton
    with _app_lock:
        if _app_singleton is None:
            _app_singleton = app
    
    # Automatic recording cleanup scheduler (7-day retention)
    try:
        from server.tasks_recording import auto_cleanup_old_recordings
        import threading
        import time as scheduler_time
        
        def recording_cleanup_scheduler():
            """Background scheduler - runs cleanup daily"""
            scheduler_time.sleep(300)  # Wait 5 minutes after startup
            while True:
                try:
                    with app.app_context():
                        auto_cleanup_old_recordings()
                except Exception:
                    pass
                scheduler_time.sleep(21600)  # Run every 6 hours
        
        cleanup_thread = threading.Thread(target=recording_cleanup_scheduler, daemon=True, name="RecordingCleanup")
        cleanup_thread.start()
    except Exception:
        pass
    
    # WhatsApp session processor (15-min auto-summary)
    try:
        from server.services.whatsapp_session_service import start_session_processor
        start_session_processor()
    except Exception:
        pass
    
    # Recording transcription worker (offline STT + lead extraction)
    try:
        from server.tasks_recording import start_recording_worker
        import threading
        
        recording_thread = threading.Thread(
            target=start_recording_worker,
            args=(app,),
            daemon=True,
            name="RecordingWorker"
        )
        recording_thread.start()
        print("✅ [BACKGROUND] Recording worker started")
    except Exception as e:
        print(f"⚠️ [BACKGROUND] Could not start recording worker: {e}")
    
    return app