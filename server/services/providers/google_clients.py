"""
Google Clients Singleton Registry
==================================

Thread-safe singleton pattern for Google Cloud STT and Gemini clients.
Prevents per-call/per-session client initialization to eliminate bottlenecks.

Usage:
    from server.services.providers.google_clients import get_stt_client, get_gemini_client
    
    # Instead of: speech.SpeechClient(credentials=...)
    client = get_stt_client()
    
    # Instead of: genai.Client(api_key=...)
    client = get_gemini_client()
"""
import os
import logging
import threading
from typing import Optional

logger = logging.getLogger(__name__)

# Thread-safe locks for double-checked locking pattern
_stt_lock = threading.Lock()
_gemini_lock = threading.Lock()

# Global singleton instances
_stt_client = None
_gemini_client = None


def get_stt_client():
    """
    Get Google Cloud Speech-to-Text client (singleton).
    
    Returns:
        speech.SpeechClient or None: Initialized STT client or None if disabled/failed
    
    Notes:
        - Respects DISABLE_GOOGLE environment variable (defaults to 'true')
        - Uses GOOGLE_APPLICATION_CREDENTIALS for authentication
        - Thread-safe with double-checked locking
        - Caches failures to avoid repeated init attempts
    """
    global _stt_client
    
    # Fast path: already initialized (or failed)
    if _stt_client is not None:
        # Return None if cached failure (False), otherwise return client
        return None if _stt_client is False else _stt_client
    
    # Check if Google services are disabled
    disable_google = os.getenv('DISABLE_GOOGLE', 'true').lower() == 'true'
    if disable_google:
        logger.debug("Google STT client requested but DISABLE_GOOGLE=true")
        return None
    
    # Slow path: initialize with lock
    with _stt_lock:
        # Double-check: another thread may have initialized while we waited
        if _stt_client is not None:
            # Return None if cached failure (False), otherwise return client
            return None if _stt_client is False else _stt_client
        
        try:
            from google.cloud import speech
            from google.oauth2 import service_account
            
            credentials_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
            if not credentials_path:
                logger.error("GOOGLE_APPLICATION_CREDENTIALS environment variable is not set")
                _stt_client = False  # Cache failure
                return None
            
            if not os.path.exists(credentials_path):
                logger.error(f"Service account file not found: {credentials_path}")
                _stt_client = False  # Cache failure
                return None
            
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path
            )
            _stt_client = speech.SpeechClient(credentials=credentials)
            logger.info(f"✅ Google STT client initialized (singleton) from {credentials_path}")
            return _stt_client
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Google STT client: {e}")
            _stt_client = False  # Cache failure to prevent repeated attempts
            return None


def get_gemini_client():
    """
    Get Gemini AI client (singleton).
    
    Returns:
        genai.Client or None: Initialized Gemini client or None if failed
    
    Notes:
        - Uses GEMINI_API_KEY for authentication
        - Thread-safe with double-checked locking
        - Caches failures to avoid repeated init attempts
        - NOT affected by DISABLE_GOOGLE (Gemini is separate from Google Cloud STT/TTS)
    """
    global _gemini_client
    
    # Fast path: already initialized (or failed)
    if _gemini_client is not None:
        # Return None if cached failure (False), otherwise return client
        return None if _gemini_client is False else _gemini_client
    
    # Slow path: initialize with lock
    with _gemini_lock:
        # Double-check: another thread may have initialized while we waited
        if _gemini_client is not None:
            # Return None if cached failure (False), otherwise return client
            return None if _gemini_client is False else _gemini_client
        
        try:
            from google import genai
            from server.utils.gemini_key_provider import get_gemini_api_key
            
            gemini_api_key = get_gemini_api_key()
            if not gemini_api_key:
                logger.error("GEMINI_API_KEY not set - cannot initialize Gemini client")
                _gemini_client = False  # Cache failure
                return None
            
            _gemini_client = genai.Client(api_key=gemini_api_key)
            logger.info("✅ Gemini client initialized (singleton)")
            return _gemini_client
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Gemini client: {e}")
            _gemini_client = False  # Cache failure to prevent repeated attempts
            return None


def warmup_google_clients():
    """
    Warmup function to initialize Google clients at server startup.
    
    Call this from app factory/startup hook to catch configuration issues early
    rather than during first call/session.
    
    This is optional but recommended for production deployments.
    """
    logger.info("🔥 Warming up Google clients...")
    
    # Attempt to initialize STT client (respects DISABLE_GOOGLE)
    stt_client = get_stt_client()
    if stt_client:
        logger.info("  ✅ Google STT client warmed up")
    else:
        disable_google = os.getenv('DISABLE_GOOGLE', 'true').lower() == 'true'
        if disable_google:
            logger.info("  🚫 Google STT warmup SKIPPED (DISABLE_GOOGLE=true)")
        else:
            logger.warning("  ⚠️ Google STT client failed to initialize during warmup")
    
    # Attempt to initialize Gemini client
    gemini_client = get_gemini_client()
    if gemini_client:
        logger.info("  ✅ Gemini client warmed up")
    else:
        logger.warning("  ⚠️ Gemini client failed to initialize during warmup")
    
    logger.info("🔥 Google clients warmup complete")


def reset_clients():
    """
    Reset all cached clients (for testing purposes only).
    
    This should NOT be called in production code.
    """
    global _stt_client, _gemini_client
    with _stt_lock:
        _stt_client = None
    with _gemini_lock:
        _gemini_client = None
    logger.debug("🔄 Google clients cache reset")
