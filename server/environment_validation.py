"""
Environment Validation - Production Ready Setup
אימות משתני סביבה - הגדרת פרודקשן מוכנה
"""
import os
import logging
import sys
from typing import List, Dict, Any
from sqlalchemy import text

logger = logging.getLogger(__name__)

# Critical columns that MUST exist for the system to function
CRITICAL_COLUMNS = {
    'call_log': [
        'recording_mode',  # Required for recording tracking
        'recording_sid',   # Required for recording callbacks
        'audio_bytes_len', # Required for post-call pipeline
        'audio_duration_sec', # Required for post-call pipeline
        'transcript_source', # Required for post-call pipeline
        'stream_started_at', # Required for cost tracking
        'stream_ended_at',   # Required for cost tracking
        'recording_count',   # Required for cost tracking
    ],
    'leads': [
        'gender',  # Required for lead queries and call lookups
    ],
    'business': [
        'voice_id',  # Required for per-business voice selection in Realtime API
    ],
}

def validate_production_environment() -> Dict[str, Any]:
    """
    Validate all required environment variables for production
    אימות כל משתני הסביבה הנדרשים לפרודקשן
    """
    
    # Core required variables
    required_core = [
        "PUBLIC_HOST",
        "TWILIO_ACCOUNT_SID", 
        "TWILIO_AUTH_TOKEN"
    ]
    
    # WhatsApp provider specific
    whatsapp_provider = os.getenv("WHATSAPP_PROVIDER", "baileys").lower()
    required_whatsapp = []
    
    if whatsapp_provider == "twilio":
        required_whatsapp = ["TWILIO_WHATSAPP_NUMBER"]
    
    # Optional but recommended
    recommended = [
        "OPENAI_API_KEY",
        "GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON",
        "DATABASE_URL"
    ]
    
    # Check required variables
    missing_core = []
    missing_whatsapp = []
    missing_recommended = []
    
    for var in required_core:
        if not os.getenv(var):
            missing_core.append(var)
    
    for var in required_whatsapp:
        if not os.getenv(var):
            missing_whatsapp.append(var)
    
    for var in recommended:
        if not os.getenv(var):
            missing_recommended.append(var)
    
    # Calculate readiness
    total_missing = len(missing_core) + len(missing_whatsapp)
    is_production_ready = total_missing == 0
    
    result = {
        "production_ready": is_production_ready,
        "whatsapp_provider": whatsapp_provider,
        "missing": {
            "core": missing_core,
            "whatsapp": missing_whatsapp,
            "recommended": missing_recommended
        },
        "configured": {
            "core": [var for var in required_core if os.getenv(var)],
            "whatsapp": [var for var in required_whatsapp if os.getenv(var)],
            "recommended": [var for var in recommended if os.getenv(var)]
        }
    }
    
    # Log results
    if is_production_ready:
        logger.info("✅ Environment validation passed - production ready")
    else:
        logger.warning(f"⚠️ Environment validation failed - missing: {total_missing} variables")
        if missing_core:
            logger.error(f"Missing CORE variables: {missing_core}")
        if missing_whatsapp:
            logger.error(f"Missing WhatsApp variables: {missing_whatsapp}")
    
    return result

def require_environment_variables(required_vars: List[str]) -> None:
    """
    Require specific environment variables or raise error
    דרישת משתני סביבה ספציפיים או העלאת שגיאה
    """
    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
    
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}. "
            f"Configure these in Replit Secrets or .env file."
        )

def get_public_url(path: str = "") -> str:
    """
    Get absolute public URL for webhooks
    קבלת URL ציבורי מוחלט לוובהוקים
    """
    host = os.getenv("PUBLIC_HOST", "").rstrip("/")
    
    if not host:
        raise RuntimeError(
            "PUBLIC_HOST not configured. Set this in Replit Secrets to your deployed domain."
        )
    
    if path:
        path = "/" + path.lstrip("/")
    
    return host + path

def log_environment_status():
    """Log current environment configuration status"""
    validation = validate_production_environment()
    
    logger.info("🔧 Environment Configuration Status:")
    logger.info(f"   Provider: {validation['whatsapp_provider']}")
    logger.info(f"   Production Ready: {validation['production_ready']}")
    
    if validation["configured"]["core"]:
        logger.info(f"   ✅ Core: {', '.join(validation['configured']['core'])}")
    
    if validation["configured"]["whatsapp"]:
        logger.info(f"   ✅ WhatsApp: {', '.join(validation['configured']['whatsapp'])}")
    
    if validation["configured"]["recommended"]:
        logger.info(f"   ✅ Recommended: {', '.join(validation['configured']['recommended'])}")
    
    if validation["missing"]["core"]:
        logger.warning(f"   ❌ Missing Core: {', '.join(validation['missing']['core'])}")
    
    if validation["missing"]["whatsapp"]:
        logger.warning(f"   ❌ Missing WhatsApp: {', '.join(validation['missing']['whatsapp'])}")
    
    if validation["missing"]["recommended"]:
        logger.info(f"   ⚠️ Missing Recommended: {', '.join(validation['missing']['recommended'])}")

def check_column_exists(engine, table_name, column_name):
    """Check if column exists in table"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_schema = 'public' 
                  AND table_name = :table_name 
                  AND column_name = :column_name
            """), {"table_name": table_name, "column_name": column_name})
            return result.fetchone() is not None
    except Exception as e:
        logger.warning(f"Error checking if column {column_name} exists in {table_name}: {e}")
        return False

def validate_database_schema(db):
    """
    Validate that all critical columns exist in the database.
    If any are missing, fail immediately with a clear error message.
    
    This prevents the system from starting in a broken state and cascading errors.
    """
    engine = db.engine
    missing_columns = []
    
    logger.info("🔍 Validating database schema...")
    
    for table_name, columns in CRITICAL_COLUMNS.items():
        for column_name in columns:
            if not check_column_exists(engine, table_name, column_name):
                missing_columns.append(f"{table_name}.{column_name}")
                logger.error(f"❌ Missing critical column: {table_name}.{column_name}")
    
    if missing_columns:
        error_msg = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                      ❌ DATABASE SCHEMA VALIDATION FAILED ❌                 ║
╚══════════════════════════════════════════════════════════════════════════════╝

The following critical columns are MISSING from the database:

{chr(10).join(f'  • {col}' for col in missing_columns)}

This will cause PostgreSQL errors throughout the system, affecting:
  - Recording callbacks (REC_CB)
  - Call status webhooks
  - Stream ended webhooks
  - API endpoints (calls_in_range, calls_last7d, etc.)
  - Background tasks (offline_stt, finalize_in_background)

🛠️  TO FIX THIS ISSUE:

1. Run database migrations to add missing columns:
   
   python -m server.db_migrate
   
   OR in production with Flask app:
   
   from server.db_migrate import apply_migrations
   with app.app_context():
       apply_migrations()

2. Restart the application

⚠️  The application will NOT START until this is fixed.

╔══════════════════════════════════════════════════════════════════════════════╗
║                         PREVENTING SERVER STARTUP                            ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
        logger.critical(error_msg)
        # Print to stderr directly instead of using logger with file argument
        print(error_msg, file=sys.stderr, flush=True)
        sys.exit(1)
    
    logger.info("✅ Database schema validation passed - all critical columns exist")
    return True


if __name__ == "__main__":
    # Quick validation test
    validation = validate_production_environment()
    log_environment_status()
    
    if validation["production_ready"]:
        logger.info("✅ Environment is production ready!")
    else:
        logger.error("❌ Environment needs configuration before production deployment")
        logger.info(f"Missing: {validation['missing']}")