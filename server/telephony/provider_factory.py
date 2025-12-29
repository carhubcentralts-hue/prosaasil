"""
Telephony Provider Factory
Creates the appropriate telephony provider based on configuration
DEFAULTS TO ASTERISK - Twilio is legacy fallback only
"""
import os
import logging
from typing import Optional
from server.telephony.provider_base import TelephonyProvider
from server.telephony.asterisk_provider import AsteriskProvider

logger = logging.getLogger(__name__)

# Global provider instance (singleton)
_provider_instance: Optional[TelephonyProvider] = None


def get_telephony_provider() -> TelephonyProvider:
    """
    Get the configured telephony provider.
    
    IMPORTANT: Defaults to Asterisk.
    Twilio is only used if explicitly set via TELEPHONY_PROVIDER=twilio (legacy fallback).
    
    Returns:
        TelephonyProvider instance (AsteriskProvider by default)
    """
    global _provider_instance
    
    # Return cached instance if available
    if _provider_instance is not None:
        return _provider_instance
    
    # Get provider type from environment
    # DEFAULT: "asterisk" - Twilio is legacy only
    provider_type = os.getenv("TELEPHONY_PROVIDER", "asterisk").lower()
    
    logger.info(f"[TELEPHONY] Initializing provider: {provider_type}")
    
    if provider_type == "asterisk":
        # Production: Use Asterisk
        _provider_instance = AsteriskProvider()
        logger.info("[TELEPHONY] ✅ Using Asterisk provider (production)")
        
    elif provider_type == "twilio":
        # Legacy fallback: Use Twilio (only if explicitly set)
        logger.warning("[TELEPHONY] ⚠️ Using Twilio provider (LEGACY - should migrate to Asterisk)")
        
        # Lazy import to avoid Twilio dependency if not needed
        try:
            from server.telephony.twilio_provider import TwilioProvider
            _provider_instance = TwilioProvider()
            logger.info("[TELEPHONY] Twilio provider initialized (legacy mode)")
        except ImportError as e:
            logger.error(f"[TELEPHONY] ❌ Failed to import TwilioProvider: {e}")
            logger.error("[TELEPHONY] Falling back to Asterisk")
            _provider_instance = AsteriskProvider()
    else:
        # Unknown provider - default to Asterisk
        logger.error(f"[TELEPHONY] ❌ Unknown provider type: {provider_type}")
        logger.info("[TELEPHONY] Defaulting to Asterisk")
        _provider_instance = AsteriskProvider()
    
    return _provider_instance


def reset_provider():
    """
    Reset the provider instance (useful for testing).
    """
    global _provider_instance
    _provider_instance = None
    logger.debug("[TELEPHONY] Provider instance reset")


def is_using_asterisk() -> bool:
    """
    Check if currently using Asterisk provider.
    
    Returns:
        True if using Asterisk, False otherwise
    """
    provider = get_telephony_provider()
    return isinstance(provider, AsteriskProvider)


def is_using_twilio() -> bool:
    """
    Check if currently using Twilio provider (legacy).
    
    Returns:
        True if using Twilio, False otherwise
    """
    return not is_using_asterisk()
