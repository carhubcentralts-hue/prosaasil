"""
Gemini API Key Provider - Simple ENV-only
Provides Gemini API key from environment variable ONLY

🎯 Purpose:
- Single source: GEMINI_API_KEY environment variable
- Clear logging without exposing keys
- No per-business complexity

🔒 Security:
- Never logs actual API keys
- Only logs availability (yes/no)
"""
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def get_gemini_api_key() -> Optional[str]:
    """
    Get Gemini API key from environment variable.
    
    Returns:
        API key string or None if not available
    
    Examples:
        >>> key = get_gemini_api_key()
        >>> if key:
        >>>     logger.info("Gemini API key available")
    """
    return os.getenv('GEMINI_API_KEY')


def is_gemini_available() -> bool:
    """
    Check if Gemini is available.
    
    Returns:
        True if GEMINI_API_KEY is set, False otherwise
    """
    return bool(get_gemini_api_key())

