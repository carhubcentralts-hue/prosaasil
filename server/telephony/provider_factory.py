"""
Telephony Provider Factory - Legacy compatibility layer
In Twilio-only mode, the system uses routes_twilio.py directly
This module is kept for backward compatibility but is not actively used
"""
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Global provider instance (singleton)
_provider_instance: Optional[object] = None


def get_telephony_provider():
    """
    Get the configured telephony provider.
    
    Note: In Twilio-only mode, this returns None as the system
    uses routes_twilio.py directly for Twilio integration.
    
    Returns:
        None (legacy compatibility)
    """
    global _provider_instance
    
    if _provider_instance is not None:
        return _provider_instance
    
    # Get provider type from environment
    provider_type = os.getenv("TELEPHONY_PROVIDER", "twilio").lower()
    
    logger.info(f"[TELEPHONY] Provider type: {provider_type}")
    
    if provider_type == "twilio":
        # Twilio integration is handled by routes_twilio.py directly
        logger.info("[TELEPHONY] ✅ Using Twilio (via routes_twilio.py)")
        _provider_instance = None  # No abstraction needed
    else:
        logger.warning(f"[TELEPHONY] ⚠️ Unknown provider: {provider_type}, defaulting to Twilio")
        _provider_instance = None
    
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
        Always True in Twilio-only mode
    """
    return True


