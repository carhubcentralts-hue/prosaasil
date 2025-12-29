"""
Telephony Provider Abstraction Layer
Provides unified interface for different telephony backends (Twilio is default)
"""
from server.telephony.provider_base import TelephonyProvider
from server.telephony.provider_factory import (
    get_telephony_provider,
    is_using_twilio,
    reset_provider
)

__all__ = [
    'TelephonyProvider',
    'get_telephony_provider',
    'is_using_twilio',
    'reset_provider'
]

