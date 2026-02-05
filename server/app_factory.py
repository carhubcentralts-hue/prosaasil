"""
Hebrew AI Call Center CRM - App Factory (לפי ההנחיות המדויקות)
"""
import os
import logging
import threading
from flask import Flask, jsonify, send_from_directory, send_file, current_app, request, session, g
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

# 🔥 CRITICAL: Setup centralized logging BEFORE any imports
# This configures LOG_LEVEL environment variable for production-safe logging
if os.getenv('MIGRATION_MODE') != '1':
    try:
        from server.logging_config import configure_logging
        configure_logging()
    except ImportError:
        # Fallback to basic logging if logging_config is not available
        logging.basicConfig(
            level=logging.getLevelName(os.getenv('LOG_LEVEL', 'INFO').upper()),
            format='[%(asctime)s] %(levelname)-8s [%(name)s] %(message)s'
        )
else:
    # Migration mode - use standard logging to avoid dependencies
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')

try:
    from flask_seasurf import SeaSurf
    CSRF_AVAILABLE = True
except ImportError:
    SeaSurf = None
    CSRF_AVAILABLE = False
from datetime import datetime, timedelta
import secrets
import hashlib

# Module-level logger
logger = logging.getLogger(__name__)

# 🔥 CRITICAL FIX: Single instance management to prevent APP_START crashes
_app_singleton = None
_app_lock = __import__('threading').RLock()  # RLock allows reentrant acquisition (prevents deadlock)

# 🔥 CRITICAL: Global migrations completion event
# Used by health check to ensure migrations complete before returning 200 OK
_migrations_complete = threading.Event()

# 🔥 CRITICAL: Global DB readiness flag and lock
# Set to True only after actual DB connectivity and schema validation
_db_ready = False
_db_ready_lock = threading.Lock()

def ensure_db_ready(app, max_retries=10, retry_delay=2.0):
    """
    🔥 CRITICAL: Ensure database is actually ready for use
    
    This validates:
    1. Database connection works (SELECT 1)
    2. Alembic version table exists (migrations have been applied)
    3. Can query basic tables
    
    Args:
        app: Flask application instance (required for app_context)
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds
    
    Returns True if DB is ready, False otherwise.
    Does NOT raise exceptions - logs and returns status.
    """
    global _db_ready
    
    # Fast path: Check if already ready (no lock needed for read)
    if _db_ready:
        return True  # Already validated
    
    # Use lock to prevent race conditions when setting _db_ready
    with _db_ready_lock:
        # Double-check pattern: Another thread might have set it while we waited for lock
        if _db_ready:
            return True
        
        import time
        from server.db import db
        from sqlalchemy import text
        
        for attempt in range(max_retries):
            try:
                # 🔥 CRITICAL: Wrap all DB operations in app context to avoid
                # "Working outside of application context" error
                with app.app_context():
                    # Test 1: Basic connectivity
                    db.session.execute(text('SELECT 1'))
                    
                    # Test 2: Alembic version table exists (migrations ran)
                    result = db.session.execute(text(
                        "SELECT 1 FROM information_schema.tables "
                        "WHERE table_schema = current_schema() "
                        "AND table_name = :table_name"
                    ), {"table_name": "alembic_version"})
                    if not result.fetchone():
                        logger.warning(f"⏳ Alembic table not found (attempt {attempt + 1}/{max_retries})")
                        db.session.rollback()
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay)
                            continue
                        return False
                    
                    # Test 3: Can query business table (core schema exists)
                    result = db.session.execute(text(
                        "SELECT 1 FROM information_schema.tables "
                        "WHERE table_schema = current_schema() "
                        "AND table_name = :table_name"
                    ), {"table_name": "business"})
                    if not result.fetchone():
                        logger.warning(f"⏳ Business table not found (attempt {attempt + 1}/{max_retries})")
                        db.session.rollback()
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay)
                            continue
                        return False
                    
                    # Test 4: Check critical columns exist (like lead_tabs_config)
                    # This prevents queries from failing with UndefinedColumn error
                    result = db.session.execute(text(
                        "SELECT 1 FROM information_schema.columns "
                        "WHERE table_schema = current_schema() "
                        "AND table_name = :table_name "
                        "AND column_name = :column_name"
                    ), {"table_name": "business", "column_name": "lead_tabs_config"})
                    if not result.fetchone():
                        error_msg = "❌ Critical column 'business.lead_tabs_config' not found"
                        logger.error(error_msg)
                        logger.error("   Migrations need to run! Set RUN_MIGRATIONS=1 or run migrations manually")
                        
                        # 🔥 FAIL FAST in production - don't start the API if schema is missing
                        is_production = (
                            os.getenv('FLASK_ENV') == 'production' or 
                            os.getenv('PRODUCTION', '0') in ('1', 'true', 'True')
                        )
                        if is_production:
                            logger.error("   🚨 PRODUCTION MODE: Cannot start with missing schema!")
                            db.session.rollback()
                            raise RuntimeError(
                                "Critical database schema missing: business.lead_tabs_config column not found. "
                                "Run migrations before starting the API service."
                            )
                        else:
                            logger.warning("   ⚠️ DEV MODE: System will attempt to continue but queries may fail")
                    
                    db.session.rollback()  # Clean up
                    
                    # All checks passed - set flag (already inside lock)
                    _db_ready = True
                    logger.info("✅ Database ready - connectivity and schema validated")
                    return True
                
            except Exception as e:
                logger.warning(f"⏳ DB not ready (attempt {attempt + 1}/{max_retries}): {str(e)[:100]}")
                try:
                    with app.app_context():
                        db.session.rollback()
                except Exception:
                    pass
                
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    logger.error(f"❌ Database not ready after {max_retries} attempts")
                    return False
        
        return False

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

def create_minimal_app():
    """
    Create minimal Flask app for migrations - NO background threads, NO warmup, NO eventlet
    
    This is used ONLY for database migrations to avoid hanging.
    """
    app = Flask(__name__)
    
    # 🔥 FIX: Single source of truth for database URL
    # Use unified function that prioritizes DATABASE_URL, falls back to DB_POSTGRESDB_*
    # 🔥 CRITICAL: Use POOLER connection for API/Worker traffic (not direct)
    from server.database_url import get_database_url
    DATABASE_URL = get_database_url(connection_type="pooler")
    
    app.config.update({
        'SECRET_KEY': os.getenv('SECRET_KEY', secrets.token_hex(32)),
        'DATABASE_URL': DATABASE_URL,
        'SQLALCHEMY_DATABASE_URI': DATABASE_URL,
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'SQLALCHEMY_ENGINE_OPTIONS': {
            'pool_pre_ping': True,
            'pool_recycle': 300,
            'poolclass': __import__('sqlalchemy.pool', fromlist=['NullPool']).NullPool,
            'connect_args': {
                'connect_timeout': 5,  # 🔥 DNS FIX: Shorter timeout for faster failover
                'application_name': 'AgentLocator-Migrations',
                'options': '-c statement_timeout=30000',
                # 🔥 DNS FIX: TCP keepalive to detect dead connections
                'keepalives': 1,
                'keepalives_idle': 30,
                'keepalives_interval': 10,
                'keepalives_count': 5
            }
        }
    })
    
    # Initialize SQLAlchemy with minimal app
    from server.db import db
    import server.models_sql  # Import models module
    db.init_app(app)
    
    return app

def create_app():
    """Create Flask application with React frontend (לפי ההנחיות המדויקות)"""
    
    # Check if we're in migration mode - skip all heavy initialization
    if os.getenv('MIGRATION_MODE') == '1':
        logger.info("🔧 MIGRATION_MODE detected - creating minimal app")
        return create_minimal_app()
    
    # 🔒 P1: Determine production mode for security features
    is_production_mode = os.getenv('PRODUCTION', '0') in ('1', 'true', 'True')
    
    # 🔒 P1: SECRET_KEY Fail-Fast in Production
    secret_key = os.getenv('SECRET_KEY')
    if is_production_mode and not secret_key:
        raise RuntimeError(
            "PRODUCTION=1 requires SECRET_KEY environment variable. "
            "Generate with: python3 -c \"import secrets; print(secrets.token_hex(32))\""
        )
    if not secret_key:
        secret_key = secrets.token_hex(32)
        logger.warning("⚠️ Development mode: Using generated SECRET_KEY (not persistent)")
    
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
    # 🔥 CRITICAL FIX: Use unified DATABASE_URL validation
    # This prevents confusing DNS errors from invalid database URLs
    from server.database_validation import validate_database_url
    validate_database_url()
    
    # 🔥 FIX: Single source of truth for database URL
    # Use unified function that prioritizes DATABASE_URL, falls back to DB_POSTGRESDB_*
    # 🔥 CRITICAL: Use POOLER connection for API/Worker traffic (not direct)
    from server.database_url import get_database_url
    DATABASE_URL = get_database_url(connection_type="pooler")
    
    # Enterprise Security Configuration
    app.config.update({
        'SECRET_KEY': secret_key,
        'DATABASE_URL': DATABASE_URL,
        'SQLALCHEMY_DATABASE_URI': DATABASE_URL,
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'SQLALCHEMY_ENGINE_OPTIONS': {
            'pool_pre_ping': True,  # ✅ DB RESILIENCE: Verify connections before use (prevents stale connections)
            'pool_recycle': 180,    # 🔥 FIX: Recycle connections after 3 min (before Supabase pooler timeout)
            # Fix for Eventlet + SQLAlchemy lock issue
            'poolclass': __import__('sqlalchemy.pool', fromlist=['NullPool']).NullPool,
            'connect_args': {
                'connect_timeout': 5,  # 🔥 DNS FIX: Shorter timeout for faster failover
                'application_name': 'AgentLocator-71',
                # ✅ DB RESILIENCE: Add statement timeout to prevent hanging queries
                'options': '-c statement_timeout=30000',  # 30 seconds max per statement
                # 🔥 DNS FIX: TCP keepalive to detect dead connections
                'keepalives': 1,
                'keepalives_idle': 30,
                'keepalives_interval': 10,
                'keepalives_count': 5
            }
        },
        # Session configuration
        'SESSION_COOKIE_HTTPONLY': True,
        'PERMANENT_SESSION_LIFETIME': timedelta(hours=8),
        'SESSION_REFRESH_EACH_REQUEST': True
    })
    
    # ✅ DB RESILIENCE: Log pool configuration for troubleshooting
    logger.info(f"[DB_POOL] pool_pre_ping=True pool_recycle=60s (forced refresh)")  # QA: Fixed log to match actual value
    
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
    
    # P3 Security: Enforce secure cookies in production
    is_production = os.getenv('PRODUCTION', '0') == '1'
    if is_production and not cookie_secure:
        logger.error("❌ SECURITY: PRODUCTION=1 requires COOKIE_SECURE=true (HTTPS only)")
        logger.error("Set COOKIE_SECURE=false only for development/testing")
        raise ValueError("Production mode requires secure cookies (HTTPS)")
    
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
    
    # P3 Security: Log session configuration
    session_lifetime = app.config.get('PERMANENT_SESSION_LIFETIME', timedelta(hours=8))
    if isinstance(session_lifetime, timedelta):
        session_hours = session_lifetime.total_seconds() / 3600
    else:
        session_hours = session_lifetime / 3600 if session_lifetime else 8
    
    logger.info(f"[SESSION] Secure={cookie_secure}, HttpOnly=True, SameSite={cookie_samesite}, Lifetime={session_hours}h")
    
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
        
        # Check if this is a PDF viewing endpoint that needs iframe support
        is_pdf_endpoint = (
            request.endpoint and 
            (request.endpoint.endswith('.stream_contract_pdf') or 
             request.endpoint.endswith('.get_contract_pdf_url'))
        )
        
        # CSP (Content Security Policy) - Strict but functional
        # For PDF endpoints, allow same-origin framing
        if is_pdf_endpoint:
            csp_policy = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://unpkg.com; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com data:; "
                "img-src 'self' data: blob: https:; "
                "connect-src 'self' wss: ws: https://fonts.googleapis.com https://fonts.gstatic.com; "
                "frame-ancestors 'self'; "  # Allow same-origin framing for PDFs
                "object-src 'none'; "
                "base-uri 'self'; "
                "form-action 'self';"
            )
        else:
            csp_policy = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://unpkg.com; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com data:; "
                "img-src 'self' data: blob: https:; "
                "connect-src 'self' wss: ws: https://fonts.googleapis.com https://fonts.gstatic.com; "
                "frame-ancestors 'none'; "
                "object-src 'none'; "
                "base-uri 'self'; "
                "form-action 'self';"
            )
        response.headers['Content-Security-Policy'] = csp_policy
        
        # HSTS - Strict Transport Security (force HTTPS)
        # Only add in production (when using HTTPS)
        if cookie_secure:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        
        # Additional security headers
        # For PDF endpoints, allow same-origin framing
        if is_pdf_endpoint:
            response.headers['X-Frame-Options'] = 'SAMEORIGIN'  # Allow same-origin framing for PDFs
        else:
            response.headers['X-Frame-Options'] = 'DENY'
            
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=(), payment=()'
        
        # Cross-Origin headers for additional security
        response.headers['Cross-Origin-Opener-Policy'] = 'same-origin'
        response.headers['Cross-Origin-Resource-Policy'] = 'same-origin'
        
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
    
    # 🔒 P1: CORS with Production Lockdown
    # In production: Only allow explicitly configured origins
    # In development: Allow localhost and replit for easier development
    if is_production_mode:
        # Production: Strict CORS - only explicit allowed origins
        cors_origins = []
        
        # Add PUBLIC_BASE_URL if configured
        public_url = os.getenv('PUBLIC_BASE_URL', '').strip()
        if public_url:
            cors_origins.append(public_url)
            logger.info(f"[CORS] Production: Added PUBLIC_BASE_URL: {public_url}")
        
        # Add FRONTEND_URL if configured
        frontend_url = os.getenv('FRONTEND_URL', '').strip()
        if frontend_url and frontend_url not in cors_origins:
            cors_origins.append(frontend_url)
            logger.info(f"[CORS] Production: Added FRONTEND_URL: {frontend_url}")
        
        # Add external origins from CORS_ALLOWED_ORIGINS
        external_origins = os.getenv("CORS_ALLOWED_ORIGINS", "").strip()
        if external_origins:
            for origin in external_origins.split(","):
                origin = origin.strip()
                if origin and origin not in cors_origins:
                    cors_origins.append(origin)
                    logger.info(f"[CORS] Production: Added external origin: {origin}")
        
        # Remove duplicates and empty strings
        cors_origins = [o for o in set(cors_origins) if o]
        
        # 🔒 P1: Fail-fast if no origins configured in production
        # This prevents silent failures where CORS would block all requests
        if not cors_origins:
            logger.error("🚨 CRITICAL: CORS enabled with credentials but no origins configured!")
            logger.error("   Set PUBLIC_BASE_URL and/or CORS_ALLOWED_ORIGINS in production")
            raise RuntimeError(
                "Production requires CORS origins when using credentials. "
                "Set PUBLIC_BASE_URL or CORS_ALLOWED_ORIGINS environment variables."
            )
    else:
        # Development: Allow localhost and replit patterns for easier development
        cors_origins = [
            "http://localhost:5000",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:8080",
            r"^https://[\w-]+\.replit\.app$",    # Regex pattern for *.replit.app
            r"^https://[\w-]+\.replit\.dev$"     # Regex pattern for *.replit.dev
        ]
        
        # Add external origins from environment variable in dev too
        external_origins = os.getenv("CORS_ALLOWED_ORIGINS", "").strip()
        if external_origins:
            for origin in external_origins.split(","):
                origin = origin.strip()
                if origin:
                    cors_origins.append(origin)
                    logger.info(f"[CORS] Development: Added external origin: {origin}")
    
    # 🔒 P1: CORS Configuration with Credentials
    # When supports_credentials=True (required for cookies/sessions):
    # - MUST have explicit origins (cannot use '*')
    # - Origins must match exactly (no wildcards in origin strings, only regex patterns)
    # - Browser enforces strict origin matching
    
    CORS(app, 
         origins=cors_origins,
         supports_credentials=True,  # Required for session cookies
         allow_headers=["Content-Type", "Authorization", "X-CSRFToken", "HX-Request"],
         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    )
    
    logger.info(f"[CORS] Configured with {len(cors_origins)} allowed origin(s)")
    if is_production_mode:
        safe_origins = [o for o in cors_origins if not o.startswith('r"')]
        logger.info(f"[CORS] Production mode: {', '.join(safe_origins)}")
    
    # ⚡ CRITICAL FIX: Register essential API blueprints FIRST (before all other blueprints)
    # This ensures dashboard, business, notifications, etc. work even if other blueprints fail
    # If these fail to register, app CRASHES (fail-fast) instead of running without API
    try:
        # Health endpoints - MUST be registered FIRST for monitoring
        from server.health_endpoints import health_bp
        app.register_blueprint(health_bp)
        app.logger.info("✅ Health endpoints registered")
        
        # API Adapter - Dashboard, stats, activity endpoints
        from server.api_adapter import api_adapter_bp
        app.register_blueprint(api_adapter_bp)
        app.logger.info("✅ API Adapter blueprint registered (dashboard endpoints)")
        
        # Admin endpoints - /api/admin/businesses, etc.
        from server.routes_admin import admin_bp
        app.register_blueprint(admin_bp)
        app.logger.info("✅ Admin blueprint registered")
        
        # Business management - /api/business/current, settings, FAQs
        from server.routes_business_management import biz_mgmt_bp
        app.register_blueprint(biz_mgmt_bp)
        app.logger.info("✅ Business management blueprint registered")
        
        # Leads - /api/leads, /api/notifications
        from server.routes_leads import leads_bp
        app.register_blueprint(leads_bp)
        app.logger.info("✅ Leads blueprint registered")
        
        # Search - /api/search
        from server.routes_search import search_api
        app.register_blueprint(search_api)
        app.logger.info("✅ Search blueprint registered")
        
        # CRM - /api/crm/threads
        from server.routes_crm import crm_bp
        app.register_blueprint(crm_bp)
        app.logger.info("✅ CRM blueprint registered")
        
        # Status management - /api/statuses
        from server.routes_status_management import status_management_bp
        app.register_blueprint(status_management_bp)
        app.logger.info("✅ Status management blueprint registered")
        
        # WhatsApp - /api/whatsapp/*
        from server.routes_whatsapp import whatsapp_bp, internal_whatsapp_bp
        app.register_blueprint(whatsapp_bp)
        app.register_blueprint(internal_whatsapp_bp)
        app.logger.info("✅ WhatsApp blueprints registered")
        
        # Scheduled WhatsApp Messages - /api/scheduled-messages/*
        from server.routes_scheduled_messages import scheduled_messages_bp
        app.register_blueprint(scheduled_messages_bp)
        app.logger.info("✅ Scheduled Messages blueprint registered")
        
        # Job Health and Monitoring - /api/jobs/*
        from server.routes_jobs import jobs_bp
        app.register_blueprint(jobs_bp)
        app.logger.info("✅ Job Health and Monitoring blueprint registered")
        
        # Webhook Secret Management - /api/business/settings/webhook-secret
        from server.routes_webhook_secret import webhook_secret_bp
        app.register_blueprint(webhook_secret_bp)
        app.logger.info("✅ Webhook Secret Management blueprint registered")
        
        # Webhook Leads Ingestion - /api/leads/webhooks and /api/webhooks/leads
        from server.routes_webhook_leads import webhook_leads_bp
        app.register_blueprint(webhook_leads_bp)
        app.logger.info("✅ Webhook Leads Ingestion blueprint registered")
        
        # Email System - /api/email/*
        from server.email_api import email_bp
        app.register_blueprint(email_bp)
        app.logger.info("✅ Email System blueprint registered")
        
        # Attachments System - /api/attachments/*
        from server.routes_attachments import attachments_bp
        app.register_blueprint(attachments_bp)
        app.logger.info("✅ Attachments System blueprint registered")
        
        # Assets Library (מאגר) - /api/assets/*
        from server.routes_assets import assets_bp
        app.register_blueprint(assets_bp)
        app.logger.info("✅ Assets Library blueprint registered")
        
        # Gmail Receipts System - /api/gmail/* and /api/receipts/*
        from server.routes_receipts import gmail_oauth_bp, receipts_bp
        app.register_blueprint(gmail_oauth_bp)
        app.register_blueprint(receipts_bp)
        app.logger.info("✅ Gmail Receipts System blueprints registered")
        
        # Contracts System - /api/contracts/*
        from server.routes_contracts import contracts_bp
        app.register_blueprint(contracts_bp)
        app.logger.info("✅ Contracts System blueprint registered")
        
        # Push Notifications - /api/push/*
        from server.routes_push import push_bp
        app.register_blueprint(push_bp)
        app.logger.info("✅ Push Notifications blueprint registered")
        
        # Recording Management - /api/recordings/*
        from server.routes_recordings import recordings_bp
        app.register_blueprint(recordings_bp)
        app.logger.info("✅ Recording Management blueprint registered")
        
    except Exception as e:
        app.logger.error(f"❌ CRITICAL: Failed to register essential API blueprints: {e}")
        import traceback
        traceback.print_exc()
        # Re-raise to prevent app from starting with broken API
        raise RuntimeError(f"Essential API blueprints failed to register: {e}")
    
    # UI Blueprint registration (לפי ההנחיות)
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
        
        # AI Topics Management Blueprint - Topic classification system
        from server.routes_ai_topics import ai_topics_bp
        app.register_blueprint(ai_topics_bp)
        
        # AI System Settings Blueprint - Voice Library and TTS Preview
        from server.routes_ai_system import ai_system_bp
        app.register_blueprint(ai_system_bp)
        
        # Live Call Blueprint - Browser-based voice chat (Web App only)
        # 🔥 This is the ONLY voice test interface - uses saved Business settings
        from server.routes_live_call import live_call_bp
        app.register_blueprint(live_call_bp)
        
        # Prompt Builder Blueprint - AI-powered prompt generation
        from server.routes_prompt_builder import prompt_builder_bp
        app.register_blueprint(prompt_builder_bp)
        
        # Smart Prompt Generator v2 - Structured template-based generation
        from server.routes_smart_prompt_generator import smart_prompt_bp
        app.register_blueprint(smart_prompt_bp)
        
        # Prompt Builder Chat - Natural conversational prompt generation
        from server.routes_prompt_builder_chat import prompt_builder_chat_bp
        app.register_blueprint(prompt_builder_chat_bp)
        
        # Note: Status Management Blueprint now registered earlier (before line 356)
        
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
        
        # Context API - user permissions and enabled pages
        from server.routes_context import context_bp
        app.register_blueprint(context_bp)
        
        # ⚡ NOTE: Critical API blueprints (admin, business, leads, search, crm, status, whatsapp, health, api_adapter)
        # are now registered EARLIER in a separate try-except block (before line 356)
        # This ensures they load even if other blueprints fail
        
        # ⚡ CRITICAL: Register Twilio and Calendar blueprints (MUST succeed for calls to work)
        # If these fail to register, app CRASHES (fail-fast) instead of running without call handling
        try:
            from server.routes_twilio import twilio_bp
            app.register_blueprint(twilio_bp)
            app.logger.info("✅ Twilio blueprint registered (call webhooks active)")
        except Exception as e:
            app.logger.error(f"❌ [BOOT][FATAL] Failed to import/register Twilio blueprint: {e}")
            import traceback
            traceback.print_exc()
            raise RuntimeError(f"Critical blueprint 'routes_twilio' failed to register: {e}")
        
        try:
            from server.routes_calendar import calendar_bp
            app.register_blueprint(calendar_bp)
            app.logger.info("✅ Calendar blueprint registered")
        except Exception as e:
            app.logger.error(f"❌ [BOOT][FATAL] Failed to import/register Calendar blueprint: {e}")
            import traceback
            traceback.print_exc()
            raise RuntimeError(f"Critical blueprint 'routes_calendar' failed to register: {e}")
        
        # Register appointment automations blueprint
        try:
            from server.routes_appointment_automations import appointment_automations_bp
            app.register_blueprint(appointment_automations_bp)
            app.logger.info("✅ Appointment automations blueprint registered")
        except Exception as e:
            app.logger.warning(f"⚠️ Failed to register appointment automations blueprint: {e}")
            # Don't fail app startup if automation blueprint fails
        
        # Register additional API blueprints
        from server.routes_user_management import user_mgmt_api
        app.register_blueprint(user_mgmt_api)
        
        # Calls API for recordings and transcripts
        from server.routes_calls import calls_bp
        app.register_blueprint(calls_bp)
        
        # BUILD 174: Outbound Calls API
        from server.routes_outbound import outbound_bp
        app.register_blueprint(outbound_bp)
        
        # Projects API for Outbound Calls
        from server.routes_projects import projects_bp
        app.register_blueprint(projects_bp)
        
        # Register receipts and contracts endpoints
        from server.routes_receipts_contracts import receipts_contracts_bp
        app.register_blueprint(receipts_contracts_bp)
        
        # Note: WhatsApp blueprints now registered earlier (before line 356)
        
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
        
        # Note: API Adapter and Health blueprints now registered earlier (before line 356)
        
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
            # 🔥 FIX: Only log REALLY slow API requests (>3s) to reduce spam
            # Per user: "SLOW_API: להשאיר WARN רק אם באמת איטי (למשל > 3s), לא 1.3s"
            if duration > 3.0 and request.path.startswith('/api/'):
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
    
    # 🔒 P1: Determine production mode for security features
    is_production_mode = os.getenv('PRODUCTION', '0') in ('1', 'true', 'True')
    
    # Database initialization (לפי ההנחיות)
    from server.db import db
    import server.models_sql  # Import models module
    
    # Initialize SQLAlchemy with Flask app
    db.init_app(app)
    
    # 🔒 CRITICAL: Cleanup stuck jobs and runs on startup to prevent blocking
    # Must run AFTER db.init_app() and in app context to avoid SQLAlchemy errors
    # This prevents "Flask app is not registered with this SQLAlchemy instance" error
    # Only run in API service, not in worker service (to prevent duplicate cleanup)
    service_role = os.getenv('SERVICE_ROLE', 'api').lower()
    if service_role != 'worker':
        try:
            logger.info(f"[STARTUP] Running outbound cleanup on startup (service_role={service_role})...")
            with app.app_context():
                from server.routes_outbound import cleanup_stuck_dialing_jobs, cleanup_stuck_runs
                cleanup_stuck_dialing_jobs()
                cleanup_stuck_runs(on_startup=True)  # Pass on_startup=True to mark ALL running runs as failed
                
                # Also clean up Redis locks for stuck runs
                try:
                    import redis
                    REDIS_URL = os.getenv('REDIS_URL')
                    if REDIS_URL:
                        # Note: cleanup_expired_slots() is per-business and requires business_id
                        # We can't enumerate all businesses here without additional DB queries
                        # The per-business cleanup will happen when each business starts a new run
                        # Just log that Redis is available for cleanup
                        logger.info("[STARTUP] Redis available - per-business slot cleanup will occur on demand")
                    else:
                        logger.warning("[STARTUP] REDIS_URL not set, skipping Redis cleanup")
                except Exception as redis_err:
                    logger.warning(f"[STARTUP] Redis cleanup warning: {redis_err}")
                    
            logger.info("[STARTUP] ✅ Outbound cleanup complete")
        except Exception as e:
            logger.error(f"[STARTUP] ⚠️ Cleanup failed: {e}")
            import traceback
            logger.error(f"[STARTUP] Traceback: {traceback.format_exc()}")
    else:
        logger.info(f"[STARTUP] Skipping outbound cleanup (service_role={service_role}, worker services don't need cleanup)")
    
    # 🔒 P1: Rate Limiting for Security
    # Initialize rate limiter with Redis for distributed limiting
    if is_production_mode:
        try:
            from server.rate_limiter import init_rate_limiter
            limiter = init_rate_limiter(app)
            app.extensions['limiter'] = limiter
            logger.info("✅ Rate limiting initialized (Redis-backed)")
        except Exception as e:
            logger.warning(f"⚠️ Rate limiter initialization failed: {e}")
    else:
        logger.info("ℹ️  Development mode - Rate limiting skipped")
    
    # 🔥 CRITICAL: Validate R2 storage configuration in production
    # This validation runs at startup to fail-fast if R2 is not properly configured
    if is_production_mode:
        try:
            logger.info("🔒 Production mode detected - validating R2 storage configuration...")
            
            # Validate storage driver is set to R2
            storage_driver = os.getenv('ATTACHMENT_STORAGE_DRIVER', 'local').lower()
            if storage_driver != 'r2':
                logger.error("🚨 CRITICAL: PRODUCTION=1 but ATTACHMENT_STORAGE_DRIVER is not 'r2'")
                logger.error(f"   Current value: ATTACHMENT_STORAGE_DRIVER={storage_driver}")
                logger.error("   Required: ATTACHMENT_STORAGE_DRIVER=r2")
                raise RuntimeError(
                    "Production mode requires ATTACHMENT_STORAGE_DRIVER=r2. "
                    "Update your .env file and restart."
                )
            
            # Validate all R2 environment variables are set
            required_r2_vars = {
                'R2_ACCOUNT_ID': os.getenv('R2_ACCOUNT_ID'),
                'R2_BUCKET_NAME': os.getenv('R2_BUCKET_NAME'),
                'R2_ACCESS_KEY_ID': os.getenv('R2_ACCESS_KEY_ID'),
                'R2_SECRET_ACCESS_KEY': os.getenv('R2_SECRET_ACCESS_KEY'),
                'ATTACHMENT_SECRET': os.getenv('ATTACHMENT_SECRET')
            }
            
            missing_vars = [var for var, value in required_r2_vars.items() if not value]
            
            if missing_vars:
                logger.error("🚨 CRITICAL: Missing required R2 environment variables:")
                for var in missing_vars:
                    logger.error(f"   ❌ {var} = Not set")
                logger.error("Set these environment variables in your .env file and restart.")
                raise RuntimeError(
                    f"Production mode requires complete R2 configuration. "
                    f"Missing: {', '.join(missing_vars)}. "
                    "See .env.r2.example for configuration details."
                )
            
            # Validate ATTACHMENT_SECRET is not the default
            attachment_secret = os.getenv('ATTACHMENT_SECRET', '')
            if attachment_secret == 'CHANGE_ME_TO_RANDOM_SECRET_KEY_IN_PRODUCTION' or \
               attachment_secret == 'change-me-in-production':
                logger.error("🚨 CRITICAL: ATTACHMENT_SECRET is still set to default value")
                logger.error("   Generate a secure secret with: python3 -c \"import secrets; print(secrets.token_urlsafe(32))\"")
                raise RuntimeError(
                    "Production mode requires a secure ATTACHMENT_SECRET. "
                    "Change it from the default value."
                )
            
            # Try to initialize storage provider to verify R2 connection
            logger.info("   Validating R2 connection...")
            from server.services.storage import get_attachment_storage
            storage = get_attachment_storage()
            
            logger.info(f"   ✅ Storage provider initialized: {type(storage).__name__}")
            logger.info("✅ R2 storage configuration validated successfully")
            
        except Exception as e:
            logger.error(f"🚨 FATAL: R2 storage validation failed: {e}")
            logger.error("   Application cannot start in production mode without proper R2 configuration.")
            logger.error("   See .env.r2.example for configuration details.")
            raise
    else:
        logger.info("ℹ️  Development mode - R2 validation skipped (local storage allowed)")
    
    # ⚡ DEPLOYMENT FIX: Run heavy initialization in background
    # This prevents deployment timeout while still ensuring DB is ready
    # SKIP if in migration mode to prevent hanging
    if os.getenv('MIGRATION_MODE') != '1':
        def _background_initialization():
            """Run migrations and initialization after server is listening"""
            global _migrations_complete
            import time
            time.sleep(0.5)  # Let server bind to port first
            
            # 🔥 CRITICAL: Workers must NEVER run migrations
            # Migrations should only run in API service, not in workers
            service_role = os.getenv('SERVICE_ROLE', '').lower()
            # 🔥 FIX: Check actual PRODUCTION flag, not RUN_MIGRATIONS_ON_START
            is_production = os.getenv('PRODUCTION', '0') in ('1', 'true', 'True')
            
            # Skip migrations entirely if this is a worker
            if service_role == 'worker':
                logger.info("=" * 80)
                logger.info("🚫 WORKER MODE: Skipping migrations and initialization")
                logger.info("   Workers use existing schema - migrations run only in API")
                logger.info("=" * 80)
                # Signal migrations complete so worker can proceed
                _migrations_complete.set()
                return
            
            # 🔥 FIX: Always run migrations in API mode (production or dev)
            # The apply_migrations() function itself checks RUN_MIGRATIONS env var
            if is_production or True:  # Always attempt migrations
                try:
                    with app.app_context():
                        from server.db_migrate import apply_migrations
                        migrations_result = apply_migrations()
                        
                        # 🔥 NEW: Handle 'skip' return value gracefully
                        if migrations_result == 'skip':
                            # Migrations were skipped (lock timeout or disabled) - this is SAFE
                            # Another container is running migrations or migrations are disabled
                            logger.info("=" * 80)
                            logger.info("✅ MIGRATIONS SKIPPED: Lock timeout or disabled")
                            logger.info("   This is safe - migrations will run in designated container")
                            logger.info("=" * 80)
                            _migrations_complete.set()
                            return
                        
                        # 🔒 CRITICAL: Validate database schema after migrations
                        # This ensures all critical columns exist and prevents cascading errors
                        from server.environment_validation import validate_database_schema
                        from server.db import db
                        validate_database_schema(db)
                        
                        # 🔥 CRITICAL FIX: Signal that migrations are complete
                        # This prevents warmup from running before migrations finish
                        # Uses global _migrations_complete event (module-level)
                        _migrations_complete.set()
                        logger.info("🔒 Migrations complete - warmup can now proceed")
                        
                        # Migrate legacy admin roles to system_admin
                        try:
                            from server.scripts.migrate_admin_roles import migrate_admin_roles
                            migrate_admin_roles()
                        except Exception:
                            pass
                        
                except Exception as e:
                    # 🔥 CRITICAL: DO NOT proceed if migrations fail with real errors
                    # But if migrations were skipped gracefully, that's OK
                    logger.error(f"❌ MIGRATION ERROR: {e}")
                    
                    # Check if this was a skip (not a real failure)
                    if "skip" in str(e).lower() or "lock" in str(e).lower():
                        logger.warning("⚠️ Migrations were skipped (lock timeout or disabled)")
                        logger.warning("   System will continue - migrations run in designated container")
                        _migrations_complete.set()
                        return
                    
                    # Real migration failure - don't start the system
                    logger.error("System cannot start with failed migrations")
                    # Signal migrations complete but re-raise to stop startup
                    _migrations_complete.set()
                    raise RuntimeError(f"Migration failed - cannot proceed: {e}") from e
            else:
                # Development mode - use migrations (NOT db.create_all())
                # 🔥 CRITICAL: All schema changes must go through migrations
                # This prevents drift between dev and prod schemas
                # 🔥 CRITICAL: Workers must NEVER run migrations, even in dev mode
                try:
                    with app.app_context():
                        # Run migrations even in dev mode to ensure schema consistency
                        # (but only if not a worker - double-check for safety)
                        if service_role != 'worker':
                            logger.info("🔧 Running migrations in development mode...")
                            from server.db_migrate import apply_migrations
                            migrations_result = apply_migrations()
                            
                            # 🔥 NEW: Handle 'skip' return value
                            if migrations_result == 'skip':
                                logger.info("✅ Dev mode: Migrations skipped (disabled or lock timeout)")
                                _migrations_complete.set()
                            else:
                                # 🔥 CRITICAL FIX: Signal migrations complete in dev mode too
                                _migrations_complete.set()
                                logger.info("🔒 Dev mode DB setup complete - warmup can now proceed")
                        else:
                            logger.info("🚫 Worker in dev mode - skipping migrations")
                            _migrations_complete.set()
                except Exception as e:
                    # Even on failure, allow warmup to proceed in dev mode
                    logger.warning(f"⚠️ Dev mode migrations failed: {e}")
                    _migrations_complete.set()
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
        
        # 🔥 REMOVED THREADING: Background initialization now runs synchronously
        # Migrations must complete before app starts - no threading needed
        # This prevents race conditions and ensures DB is ready
        _background_initialization()
        
        # Preload services after startup to avoid cold start
        from server.services.lazy_services import warmup_services_async, start_periodic_warmup
        warmup_services_async()
        start_periodic_warmup()
        
        # 🔥 Google clients warmup - Only if Google services are NOT disabled
        # This prevents 403 errors from Google TTS when DISABLE_GOOGLE=true
        if os.getenv("DISABLE_GOOGLE", "false").lower() != "true":
            try:
                from server.services.providers.google_clients import warmup_google_clients
                warmup_google_clients()
            except Exception as e:
                logger.warning(f"⚠️ Google clients warmup failed (non-critical): {e}")
        else:
            logger.info("⚠️ Google services disabled (DISABLE_GOOGLE=true) - skipping Google TTS warmup")
    

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
    # SKIP if in migration mode
    if os.getenv('MIGRATION_MODE') != '1':
        # 🔥 TTS Warmup - Optional, can be disabled
        # This doesn't query DB and can be skipped for faster startup
        if os.getenv("DISABLE_TTS_WARMUP") != "true":
            try:
                from server.services.gcp_tts_live import maybe_warmup
                maybe_warmup()
            except Exception as e:
                logger.warning(f"TTS warmup failed (non-critical): {e}")
                pass
        else:
            logger.info("⚠️ TTS warmup disabled by DISABLE_TTS_WARMUP environment variable")
        
        # 🔥 Agent Warmup - Queries DB, must wait for migrations
        # This is separate from TTS warmup and cannot be completely bypassed
        try:
            from server.agent_tools.agent_factory import warmup_all_agents
            
            def warmup_with_context():
                # 🔥 CRITICAL: Wait for migrations AND validate actual DB readiness
                # Agent warmup queries the database (Business.query), so schema MUST be ready
                # This prevents "InFailedSqlTransaction" errors when warmup queries fail
                # due to missing columns (e.g., business.company_id)
                import time
                
                # Use global _migrations_complete event
                global _migrations_complete
                
                # Step 1: Wait up to 60 seconds for migrations signal
                logger.info("🔥 Agent warmup waiting for migrations signal...")
                migrations_ready = _migrations_complete.wait(timeout=60.0)
                
                if not migrations_ready:
                    logger.error("❌ Agent warmup timeout waiting for migrations signal")
                    
                    # Check multiple environment variables to detect production mode
                    is_production = (
                        os.getenv("ENV") == "production" or
                        os.getenv("FLASK_ENV") == "production" or
                        os.getenv("PRODUCTION", "0") in ("1", "true", "True")
                    )
                    
                    if not is_production:
                        # In development, still raise to catch issues early
                        raise RuntimeError("Agent warmup timeout waiting for migrations")
                    
                    # In production, don't crash but try DB validation anyway
                    logger.warning("⚠️ Migration signal timeout in production - validating DB directly")
                else:
                    logger.info("✅ Migrations signal received")
                
                # Step 2: Actually validate DB readiness (not just signal)
                # This is CRITICAL - signal alone is not enough
                logger.info("🔥 Validating actual database readiness...")
                if not ensure_db_ready(app, max_retries=10, retry_delay=2.0):
                    logger.error("❌ Database not ready after validation")
                    
                    # Check if production
                    is_production = (
                        os.getenv("ENV") == "production" or
                        os.getenv("FLASK_ENV") == "production" or
                        os.getenv("PRODUCTION", "0") in ("1", "true", "True")
                    )
                    
                    if is_production:
                        logger.warning("⚠️ Skipping agent warmup in production - DB not ready")
                        logger.warning("⚠️ Note: First requests will be slower until DB is ready")
                        return
                    else:
                        raise RuntimeError("Database not ready for agent warmup")
                
                logger.info("✅ Database ready - starting agent warmup")
                
                # Additional 1 second delay for DB connection pool to settle
                time.sleep(1.0)
                
                with app.app_context():
                    try:
                        warmup_all_agents()
                        logger.info("✅ Agent warmup completed successfully")
                    except Exception as e:
                        # Agent warmup has built-in retry logic, so failures here are expected
                        logger.warning(f"Agent warmup failed (will retry on first request): {e}")
                        pass
            
            # 🔥 REMOVED THREADING: Agent warmup moved to RQ worker job
            # Use: enqueue_job('low', warmup_agents_job) in worker
            # Or rely on lazy initialization (warmup on first request)
            logger.info("⚠️ Agent warmup disabled - using lazy initialization or worker job")
        except Exception as e:
            logger.warning(f"Failed to start agent warmup thread: {e}")
            pass
        
        # ====================================================================
        # Background Schedulers and Workers
        # ====================================================================
        # 🔥 CRITICAL: Service role enforcement for clean separation
        # SERVICE_ROLE can be 'api', 'worker', 'scheduler', 'calls', or 'all' (default)
        # - api: Only HTTP endpoints, enqueues jobs
        # - calls: Only HTTP endpoints + WebSocket for calls
        # - worker: Only processes jobs from queues
        # - scheduler: Only runs scheduler loop to enqueue periodic jobs
        # - all: Both API and worker (for development/small deployments)
        SERVICE_ROLE = os.getenv('SERVICE_ROLE', 'all').lower()
        ENABLE_SCHEDULERS = os.getenv('ENABLE_SCHEDULERS', 'false').lower() == 'true'
        
        if SERVICE_ROLE not in ['api', 'worker', 'scheduler', 'calls', 'all']:
            logger.warning(f"⚠️ Invalid SERVICE_ROLE '{SERVICE_ROLE}', defaulting to 'all'")
            SERVICE_ROLE = 'all'
        
        logger.info(f"🔧 [CONFIG] SERVICE_ROLE={SERVICE_ROLE}, ENABLE_SCHEDULERS={ENABLE_SCHEDULERS}")
        
        # 🔥 CRITICAL: Never start schedulers or threads in api/calls/scheduler mode
        if SERVICE_ROLE in ['api', 'calls', 'scheduler']:
            if ENABLE_SCHEDULERS:
                logger.warning(f"⚠️ [BACKGROUND] Schedulers IGNORED for SERVICE_ROLE={SERVICE_ROLE}")
                logger.warning("   Background threads are PROHIBITED in api/calls/scheduler mode")
                ENABLE_SCHEDULERS = False
            logger.info(f"✅ [BACKGROUND] Background threads DISABLED for service: {SERVICE_ROLE}")
        elif ENABLE_SCHEDULERS and SERVICE_ROLE in ['worker', 'all']:
            logger.warning(f"⚠️ [DEPRECATED] ENABLE_SCHEDULERS is deprecated for SERVICE_ROLE={SERVICE_ROLE}")
            logger.warning("   Use separate scheduler service (SERVICE_ROLE=scheduler) instead")
            logger.info(f"   Schedulers requested but should be handled by scheduler service")
        else:
            logger.info(f"✅ [BACKGROUND] Schedulers DISABLED for service: {SERVICE_ROLE}")
            logger.info("   To enable schedulers, deploy scheduler service with SERVICE_ROLE=scheduler")
        
        # 🔥 REMOVED THREADING: All background tasks now run as scheduled RQ jobs
        # These deprecation notices help developers understand the new architecture
        logger.info("✅ [ARCHITECTURE] All background tasks moved to RQ jobs:")
        logger.info("   - Recording cleanup → cleanup_old_recordings_job (scheduled)")
        logger.info("   - WhatsApp sessions → whatsapp_sessions_cleanup_job (scheduled)")
        logger.info("   - Recording transcription → recording_job (enqueued)")
        logger.info("   - Reminder notifications → reminders_tick_job (scheduled)")
        logger.info("   - Webhook processing → webhook_process_job (enqueued)")
        logger.info("   - Push notifications → push_send_job (enqueued)")
        logger.info("   Scheduler service handles periodic job enqueuing with Redis locks")
    
    # ✅ GUARDRAIL: Route map audit at startup (prevent 404/405 errors)
    # Log all auth routes to verify they're registered correctly
    if os.getenv('MIGRATION_MODE') != '1':
        logger.info("🔍 [STARTUP] Auth route audit:")
        auth_routes_found = False
        for rule in app.url_map.iter_rules():
            if 'auth' in rule.rule.lower():
                methods = sorted([m for m in rule.methods if m not in ["HEAD", "OPTIONS"]])
                logger.info(f"   ✅ {rule.rule} → methods={methods} endpoint={rule.endpoint}")
                auth_routes_found = True
                
                # Verify critical auth endpoints
                if rule.rule == '/api/auth/csrf' and 'GET' not in methods:
                    logger.error(f"   ❌ CRITICAL: /api/auth/csrf missing GET method!")
                if rule.rule == '/api/auth/me' and 'GET' not in methods:
                    logger.error(f"   ❌ CRITICAL: /api/auth/me missing GET method!")
                if rule.rule == '/api/auth/login' and 'POST' not in methods:
                    logger.error(f"   ❌ CRITICAL: /api/auth/login missing POST method!")
        
        if not auth_routes_found:
            logger.error("   ❌ CRITICAL: No auth routes found! Blueprint might not be registered.")
    
    # Set singleton so future calls to get_process_app() reuse this instance
    global _app_singleton
    with _app_lock:
        if _app_singleton is None:
            _app_singleton = app
    
    return app