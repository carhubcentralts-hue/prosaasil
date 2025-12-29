"""
Telephony Provider Initialization
Ensures Asterisk provider is loaded and logs configuration on startup
"""
import os
import logging

logger = logging.getLogger(__name__)


def initialize_telephony_provider():
    """
    Initialize telephony provider on application startup.
    
    This function:
    1. Loads the provider (defaults to Asterisk)
    2. Logs the active provider
    3. Validates configuration
    4. Warns if Twilio is being used (legacy)
    """
    from server.telephony import get_telephony_provider, is_using_asterisk
    
    # Get provider type from environment
    provider_env = os.getenv("TELEPHONY_PROVIDER", "asterisk").lower()
    
    logger.info("=" * 60)
    logger.info("TELEPHONY PROVIDER INITIALIZATION")
    logger.info("=" * 60)
    
    # Initialize provider
    try:
        provider = get_telephony_provider()
        
        if is_using_asterisk():
            logger.info("✅ [TELEPHONY] ASTERISK PROVIDER ACTIVE (PRODUCTION)")
            logger.info(f"   ARI URL: {os.getenv('ASTERISK_ARI_URL', 'not set')}")
            logger.info(f"   ARI User: {os.getenv('ASTERISK_ARI_USER', 'not set')}")
            logger.info(f"   SIP Trunk: {os.getenv('ASTERISK_SIP_TRUNK', 'not set')}")
        else:
            logger.warning("⚠️ [TELEPHONY] TWILIO PROVIDER ACTIVE (LEGACY FALLBACK)")
            logger.warning("   This should only be used for emergency rollback")
            logger.warning("   Please migrate to Asterisk as soon as possible")
            logger.warning(f"   Environment: TELEPHONY_PROVIDER={provider_env}")
        
        logger.info("=" * 60)
        
        return provider
        
    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"❌ [TELEPHONY] FAILED TO INITIALIZE PROVIDER: {e}")
        logger.error("=" * 60)
        raise


def validate_asterisk_configuration():
    """
    Validate Asterisk configuration is present.
    
    Logs warnings if required environment variables are missing.
    """
    from server.telephony import is_using_asterisk
    
    if not is_using_asterisk():
        logger.debug("[TELEPHONY] Skipping Asterisk validation (not using Asterisk)")
        return
    
    required_vars = {
        "ASTERISK_ARI_URL": os.getenv("ASTERISK_ARI_URL"),
        "ASTERISK_ARI_USER": os.getenv("ASTERISK_ARI_USER"),
        "ASTERISK_ARI_PASSWORD": os.getenv("ASTERISK_ARI_PASSWORD"),
        "ASTERISK_SIP_TRUNK": os.getenv("ASTERISK_SIP_TRUNK"),
    }
    
    missing = []
    for var_name, var_value in required_vars.items():
        if not var_value:
            missing.append(var_name)
    
    if missing:
        logger.warning("[TELEPHONY] ⚠️ Missing Asterisk configuration:")
        for var in missing:
            logger.warning(f"   - {var}")
        logger.warning("   Please set these environment variables")
    else:
        logger.info("[TELEPHONY] ✅ Asterisk configuration validated")
