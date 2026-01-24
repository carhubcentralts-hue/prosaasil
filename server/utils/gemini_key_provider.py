"""
Gemini API Key Provider - Single Source of Truth
Provides consistent Gemini API key retrieval across all services

🎯 Purpose:
- Eliminate confusion between preview and live call API key sources
- Support per-business Gemini keys (future) with env fallback
- Provide clear logging without exposing keys

🔒 Security:
- Never logs actual API keys
- Only logs source (db/env) and business_id
"""
import os
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def get_gemini_api_key(business_id: Optional[int] = None) -> Tuple[Optional[str], str]:
    """
    Get Gemini API key with business-specific fallback.
    
    Args:
        business_id: Optional business ID for per-business API keys (future feature)
    
    Returns:
        Tuple of (api_key, source) where source is "db", "env", or "none"
    
    Examples:
        >>> key, source = get_gemini_api_key(123)
        >>> if key:
        >>>     logger.info(f"Using Gemini key from {source}")
    """
    # Future: Check for per-business API key in database
    # For now, this is a placeholder for when we implement per-business keys
    if business_id:
        # TODO: Query BusinessSettings for gemini_api_key field
        # business_key = db.session.query(BusinessSettings.gemini_api_key).filter_by(tenant_id=business_id).scalar()
        # if business_key:
        #     logger.info(f"[GEMINI_KEY] Using business-specific key for business_id={business_id}")
        #     return business_key, "db"
        pass
    
    # Fallback to environment variable
    env_key = os.getenv('GEMINI_API_KEY')
    if env_key:
        source = "env"
        if business_id:
            logger.info(f"[GEMINI_KEY] Using env key (source=env) for business={business_id}")
        return env_key, source
    
    # No key available
    if business_id:
        logger.warning(f"[GEMINI_KEY] No Gemini key available for business={business_id}")
    return None, "none"


def is_gemini_available(business_id: Optional[int] = None) -> bool:
    """
    Check if Gemini is available for a business.
    
    Args:
        business_id: Optional business ID
    
    Returns:
        True if Gemini API key is available, False otherwise
    """
    key, _ = get_gemini_api_key(business_id)
    return key is not None
