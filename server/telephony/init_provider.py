"""
Telephony Provider Initialization
Ensures Twilio provider is loaded and logs configuration on startup
"""
import os
import logging

logger = logging.getLogger(__name__)


def initialize_telephony_provider():
    """
    Initialize telephony provider on application startup.
    
    In Twilio-only mode, the system uses routes_twilio.py directly
    for all Twilio integration. This function just logs the configuration.
    """
    # Get provider type from environment
    provider_env = os.getenv("TELEPHONY_PROVIDER", "twilio").lower()
    
    logger.info("=" * 60)
    logger.info("TELEPHONY PROVIDER INITIALIZATION")
    logger.info("=" * 60)
    
    # Log provider info
    if provider_env == "twilio":
        logger.info("✅ [TELEPHONY] TWILIO PROVIDER ACTIVE (PRODUCTION)")
        logger.info("   Integration: routes_twilio.py")
        logger.info(f"   Account SID: {os.getenv('TWILIO_ACCOUNT_SID', 'not set')[:20]}...")
    else:
        logger.warning("⚠️ [TELEPHONY] UNKNOWN PROVIDER ACTIVE")
        logger.warning(f"   Environment: TELEPHONY_PROVIDER={provider_env}")
        logger.warning("   Defaulting to Twilio")
    
    logger.info("=" * 60)
    
    return None


def validate_twilio_configuration():
    """
    Validate Twilio configuration is present.
    
    Logs warnings if required environment variables are missing.
    """
    required_vars = {
        "TWILIO_ACCOUNT_SID": os.getenv("TWILIO_ACCOUNT_SID"),
        "TWILIO_AUTH_TOKEN": os.getenv("TWILIO_AUTH_TOKEN"),
    }
    
    missing = []
    for var_name, var_value in required_vars.items():
        if not var_value:
            missing.append(var_name)
    
    if missing:
        logger.warning("[TELEPHONY] ⚠️ Missing Twilio configuration:")
        for var in missing:
            logger.warning(f"   - {var}")
        logger.warning("   Please set these environment variables")
    else:
        logger.info("[TELEPHONY] ✅ Twilio configuration validated")


