"""
Telephony Provider Factory
Creates the appropriate telephony provider based on configuration
DEFAULTS TO TWILIO - Legacy Asterisk support removed
"""
import os
import logging
from typing import Optional
from server.telephony.provider_base import TelephonyProvider

logger = logging.getLogger(__name__)

# Global provider instance (singleton)
_provider_instance: Optional[TelephonyProvider] = None


def get_telephony_provider() -> TelephonyProvider:
    """
    Get the configured telephony provider.
    
    IMPORTANT: Defaults to Twilio.
    
    Returns:
        TelephonyProvider instance (TwilioProvider by default)
    """
    global _provider_instance
    
    # Return cached instance if available
    if _provider_instance is not None:
        return _provider_instance
    
    # Get provider type from environment
    # DEFAULT: "twilio"
    provider_type = os.getenv("TELEPHONY_PROVIDER", "twilio").lower()
    
    logger.info(f"[TELEPHONY] Initializing provider: {provider_type}")
    
    if provider_type == "twilio":
        # Production: Use Twilio
        logger.info("[TELEPHONY] ✅ Using Twilio provider (production)")
        
        # Lazy import to avoid Twilio dependency if not needed
        try:
            from server.telephony.twilio_provider import TwilioProvider
            _provider_instance = TwilioProvider()
            logger.info("[TELEPHONY] Twilio provider initialized")
        except ImportError as e:
            logger.error(f"[TELEPHONY] ❌ Failed to import TwilioProvider: {e}")
            raise RuntimeError("Failed to initialize Twilio provider")
    else:
        # Unknown provider - default to Twilio
        logger.error(f"[TELEPHONY] ❌ Unknown provider type: {provider_type}")
        logger.info("[TELEPHONY] Defaulting to Twilio")
        from server.telephony.twilio_provider import TwilioProvider
        _provider_instance = TwilioProvider()
    
    return _provider_instance


def reset_provider():
    """
    Reset the provider instance (useful for testing).
    """
    global _provider_instance
    _provider_instance = None
    logger.debug("[TELEPHONY] Provider instance reset")


def is_using_twilio() -> bool:
    """
    Check if currently using Twilio provider.
    
    Returns:
        True if using Twilio
    """
    from server.telephony.twilio_provider import TwilioProvider
    provider = get_telephony_provider()
    return isinstance(provider, TwilioProvider)

