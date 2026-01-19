"""
URL Builder Utility - Public URLs for external access

✅ FIX (Problem 3): Always use PUBLIC_BASE_URL instead of localhost
This ensures links sent externally (emails, WhatsApp, contracts) use the correct domain.

Usage:
    from server.utils.url_builder import public_url
    
    # Contract signing link
    sign_url = public_url(f"/contracts/sign/{token}")
    # → https://prosaas.pro/contracts/sign/abc123
    
    # Email unsubscribe link
    unsub_url = public_url(f"/unsubscribe/{token}")
    # → https://prosaas.pro/unsubscribe/def456
"""

import os
import logging

logger = logging.getLogger(__name__)

def public_url(path: str) -> str:
    """
    Build a public URL for external access (NOT localhost!)
    
    ✅ FIX: Uses PUBLIC_BASE_URL env var (REQUIRED in production)
    Fallback to request context only in development.
    
    Args:
        path: Path to append (e.g., "/contracts/sign/token123")
        
    Returns:
        Full public URL (e.g., "https://prosaas.pro/contracts/sign/token123")
        
    Example:
        >>> os.environ['PUBLIC_BASE_URL'] = 'https://prosaas.pro'
        >>> public_url('/contracts/sign/abc')
        'https://prosaas.pro/contracts/sign/abc'
    """
    # ✅ PRIMARY: Use PUBLIC_BASE_URL from environment
    base = os.getenv('PUBLIC_BASE_URL', '').strip().rstrip('/')
    
    if not base:
        # ⚠️ FALLBACK: Try to get from Flask request context (DEVELOPMENT ONLY!)
        # This should NEVER be used in production - always set PUBLIC_BASE_URL!
        try:
            from flask import request
            if request:
                # Get scheme and host from request
                base = f"{request.scheme}://{request.host}"
                logger.warning(f"[URL_BUILDER] PUBLIC_BASE_URL not set! Using request context fallback: {base}")
        except (RuntimeError, ImportError):
            # No request context available
            pass
    
    if not base:
        # 🔴 CRITICAL: No base URL available - this will break external links!
        logger.error("[URL_BUILDER] PUBLIC_BASE_URL not configured and no request context! Links will be broken!")
        base = "http://localhost:5000"  # Last resort fallback (will break in production)
    
    # Normalize path (ensure leading slash, no trailing slash)
    path = path.lstrip('/').rstrip('/')
    
    # Build full URL
    full_url = f"{base}/{path}"
    
    return full_url


def get_public_base_url() -> str:
    """
    Get the public base URL (without any path)
    
    Returns:
        Base URL (e.g., "https://prosaas.pro")
    """
    base = os.getenv('PUBLIC_BASE_URL', '').strip().rstrip('/')
    
    if not base:
        # Fallback to request context
        try:
            from flask import request
            if request:
                base = f"{request.scheme}://{request.host}"
                logger.warning(f"[URL_BUILDER] PUBLIC_BASE_URL not set! Using request fallback: {base}")
        except (RuntimeError, ImportError):
            pass
    
    if not base:
        logger.error("[URL_BUILDER] PUBLIC_BASE_URL not configured!")
        base = "http://localhost:5000"
    
    return base
