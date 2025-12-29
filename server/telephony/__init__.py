"""
Telephony Provider Abstraction Layer
Provides unified interface for different telephony backends (Asterisk is default)
"""
from server.telephony.provider_base import TelephonyProvider
from server.telephony.asterisk_provider import AsteriskProvider
from server.telephony.provider_factory import (
    get_telephony_provider,
    is_using_asterisk,
    is_using_twilio,
    reset_provider
)

__all__ = [
    'TelephonyProvider',
    'AsteriskProvider',
    'get_telephony_provider',
    'is_using_asterisk',
    'is_using_twilio',
    'reset_provider'
]
