"""
Production configuration for Hebrew AI Call Center CRM
Production-ready environment setup
"""
import os
from datetime import timedelta

class ProductionConfig:
    """Production configuration settings"""
    
    # Basic Flask settings
    SECRET_KEY = os.getenv("JWT_SECRET", "production-secret-key-change-this")
    # ❌ WTF_CSRF_ENABLED הוסר - משתמשים רק בSeaSurf לפי ההנחיות
    
    # Database configuration
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///./agentlocator.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
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
        print(f"⚠️ Warning: Missing environment variables: {', '.join(missing_vars)}")
    else:
        print("✅ All required environment variables present")
    
    return app