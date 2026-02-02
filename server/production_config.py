"""
Production configuration for Hebrew AI Call Center CRM
Production-ready environment setup
"""
import os
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class ProductionConfig:
    """Production configuration settings"""
    
    # Basic Flask settings
    # 🔒 SECURITY: No fallback for SECRET_KEY - must be provided via SECRET_KEY env var
    # This is used for Flask session signing and CSRF protection
    # Note: Will be None if not set - validation in init_production_config() will catch this
    SECRET_KEY = os.getenv("SECRET_KEY")
    # ❌ WTF_CSRF_ENABLED הוסר - משתמשים רק בSeaSurf לפי ההנחיות
    
    # Database configuration - use single source of truth
    # 🔥 FIX: Use get_database_url() for consistent DB connection
    # 🔥 CRITICAL: Use POOLER connection for API traffic (not direct)
    try:
        from server.database_url import get_database_url
        SQLALCHEMY_DATABASE_URI = get_database_url(connection_type="pooler")
    except Exception:
        # Fallback for edge cases (e.g., during import before env is set)
        SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///./agentlocator.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 🔥 PERFORMANCE: Connection pool configuration (Claude performance fix)
    # Increased from 5 to 10 for better concurrency under load
    # Configurable via environment variables for different deployment scenarios
    # Note: When using Supabase Pooler, these settings apply to the pooler connection
    # The pooler itself handles the actual connections to PostgreSQL
    
    # Parse pool configuration with error handling
    try:
        pool_size = int(os.getenv("DB_POOL_SIZE", "10"))
        if pool_size < 1:
            logger.warning(f"Invalid DB_POOL_SIZE={pool_size}, using default 10")
            pool_size = 10
    except (ValueError, TypeError):
        logger.warning(f"Invalid DB_POOL_SIZE={os.getenv('DB_POOL_SIZE')}, using default 10")
        pool_size = 10
    
    try:
        max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "10"))
        if max_overflow < 0:
            logger.warning(f"Invalid DB_MAX_OVERFLOW={max_overflow}, using default 10")
            max_overflow = 10
    except (ValueError, TypeError):
        logger.warning(f"Invalid DB_MAX_OVERFLOW={os.getenv('DB_MAX_OVERFLOW')}, using default 10")
        max_overflow = 10
    
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,       # 🔥 Check connection health before use
        "pool_recycle": 180,          # 🔥 Recycle connections before Supabase pooler timeout
        "pool_timeout": 30,
        "pool_size": pool_size,
        "max_overflow": max_overflow,
    }
    
    # Session configuration
    SESSION_TYPE = "filesystem"
    SESSION_PERMANENT = False
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    
    # Security headers
    SEND_FILE_MAX_AGE_DEFAULT = 31536000  # 1 year cache for static files
    
    # CORS configuration
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
    
    # Rate limiting
    RATELIMIT_STORAGE_URL = "memory://"
    RATELIMIT_DEFAULT = "1000 per hour"
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    # Feature flags
    TESTING = False
    DEBUG = False

def init_production_config(app):
    """Initialize production configuration"""
    app.config.from_object(ProductionConfig)
    
    # 🔒 SECURITY: Validate SECRET_KEY in production mode
    # Note: Accepts PRODUCTION='1', 'true', or 'True' (consistent with app_factory.py)
    is_production = os.getenv('PRODUCTION', '0') in ('1', 'true', 'True')
    if is_production and not app.config.get('SECRET_KEY'):
        raise RuntimeError(
            "PRODUCTION=1 requires SECRET_KEY environment variable. "
            "Generate with: python3 -c \"import secrets; print(secrets.token_hex(32))\""
        )
    
    # Environment validation
    required_vars = [
        "PUBLIC_HOST",
        "TWILIO_ACCOUNT_SID", 
        "TWILIO_AUTH_TOKEN",
        "WHATSAPP_PROVIDER"
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.warning(f"⚠️ Warning: Missing environment variables: {', '.join(missing_vars)}")
    else:
        logger.info("✅ All required environment variables present")
    
    return app