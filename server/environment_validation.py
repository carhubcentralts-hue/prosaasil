"""
Environment Validation - Production Ready Setup
אימות משתני סביבה - הגדרת פרודקשן מוכנה
"""
import os
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

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
        "GOOGLE_TTS_SA_JSON",
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

if __name__ == "__main__":
    # Quick validation test
    validation = validate_production_environment()
    log_environment_status()
    
    if validation["production_ready"]:
        print("✅ Environment is production ready!")
    else:
        print("❌ Environment needs configuration before production deployment")
        print(f"Missing: {validation['missing']}")