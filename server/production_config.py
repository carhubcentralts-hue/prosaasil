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
    SECRET_KEY = os.getenv("JWT_SECRET", "production-secret-key-change-this")
    # ❌ WTF_CSRF_ENABLED הוסר - משתמשים רק בSeaSurf לפי ההנחיות
    
    # Database configuration - use single source of truth
    # 🔥 FIX: Use get_database_url() for consistent DB connection
    try:
        from server.database_url import get_database_url
        SQLALCHEMY_DATABASE_URI = get_database_url()
    except Exception:
        # Fallback for edge cases (e.g., during import before env is set)
        SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///./agentlocator.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,       # 🔥 Check connection health before use
        "pool_recycle": 180,          # 🔥 Recycle connections before Supabase pooler timeout
        "pool_timeout": 30,
        "pool_size": 5,
        "max_overflow": 10,
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