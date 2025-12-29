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
    
    This function:
    1. Loads the provider (defaults to Twilio)
    2. Logs the active provider
    3. Validates configuration
    """
    from server.telephony import get_telephony_provider, is_using_twilio
    
    # Get provider type from environment
    provider_env = os.getenv("TELEPHONY_PROVIDER", "twilio").lower()
    
    logger.info("=" * 60)
    logger.info("TELEPHONY PROVIDER INITIALIZATION")
    logger.info("=" * 60)
    
    # Initialize provider
    try:
        provider = get_telephony_provider()
        
        if is_using_twilio():
            logger.info("✅ [TELEPHONY] TWILIO PROVIDER ACTIVE (PRODUCTION)")
            logger.info(f"   Account SID: {os.getenv('TWILIO_ACCOUNT_SID', 'not set')[:20]}...")
        else:
            logger.warning("⚠️ [TELEPHONY] UNKNOWN PROVIDER ACTIVE")
            logger.warning(f"   Environment: TELEPHONY_PROVIDER={provider_env}")
        
        logger.info("=" * 60)
        
        return provider
        
    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"❌ [TELEPHONY] FAILED TO INITIALIZE PROVIDER: {e}")
        logger.error("=" * 60)
        raise


def validate_twilio_configuration():
    """
    Validate Twilio configuration is present.
    
    Logs warnings if required environment variables are missing.
    """
    from server.telephony import is_using_twilio
    
    if not is_using_twilio():
        logger.debug("[TELEPHONY] Skipping Twilio validation (not using Twilio)")
        return
    
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

