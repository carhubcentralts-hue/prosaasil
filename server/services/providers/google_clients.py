"""
Google Clients Singleton Registry
==================================

Thread-safe singleton pattern for Google Cloud STT and Gemini clients.
Prevents per-call/per-session client initialization to eliminate bottlenecks.

🔥 CRITICAL: Functions NEVER return None - they throw detailed exceptions!

Usage:
    from server.services.providers.google_clients import (
        get_stt_client, 
        get_gemini_llm_client, 
        get_gemini_tts_client
    )
    
    # Instead of: speech.SpeechClient(credentials=...)
    try:
        client = get_stt_client()
    except RuntimeError as e:
        logger.error(f"STT unavailable: {e}")
    
    # For LLM:
    try:
        client = get_gemini_llm_client()
    except RuntimeError as e:
        logger.error(f"Gemini LLM unavailable: {e}")
    
    # For TTS:
    try:
        client = get_gemini_tts_client()
    except RuntimeError as e:
        logger.error(f"Gemini TTS unavailable: {e}")
"""
import os
import logging
import threading
from typing import Optional

try:
    import httpx
except ImportError:
    httpx = None  # Will be checked when needed

logger = logging.getLogger(__name__)

# Thread-safe locks for double-checked locking pattern
_stt_lock = threading.Lock()
_gemini_llm_lock = threading.Lock()
_gemini_tts_lock = threading.Lock()

# Global singleton instances
_stt_client = None
_gemini_llm_client = None
_gemini_tts_client = None


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


def get_gemini_llm_client():
    """
    Get Gemini AI client for LLM (singleton).
    
    Returns:
        genai.Client: Initialized Gemini client for LLM
    
    Raises:
        RuntimeError: With detailed reason if initialization fails
    
    Notes:
        - Uses GEMINI_API_KEY environment variable (ONLY - no fallbacks)
        - Thread-safe with double-checked locking
        - Caches failures to avoid repeated init attempts
        - NOT affected by DISABLE_GOOGLE (Gemini is separate from Google Cloud STT/TTS)
        - Configured with timeout: connect=2s, read=10s
        - NEVER returns None - always throws exception with details
    """
    global _gemini_llm_client
    
    # Fast path: already initialized (or failed)
    if _gemini_llm_client is not None:
        # If cached failure (False), throw exception
        if _gemini_llm_client is False:
            raise RuntimeError("Gemini LLM client initialization previously failed - check logs for details")
        return _gemini_llm_client
    
    # Slow path: initialize with lock
    with _gemini_llm_lock:
        # Double-check: another thread may have initialized while we waited
        if _gemini_llm_client is not None:
            if _gemini_llm_client is False:
                raise RuntimeError("Gemini LLM client initialization previously failed - check logs for details")
            return _gemini_llm_client
        
        try:
            from google import genai
            from server.utils.gemini_key_provider import get_gemini_api_key
            
            # 🔥 DETAILED LOGGING: Log configuration before attempting init
            gemini_api_key = get_gemini_api_key()
            api_key_exists = bool(gemini_api_key)
            env_var_used = "GEMINI_API_KEY"
            llm_model = os.getenv('GEMINI_LLM_MODEL', 'gemini-2.0-flash-exp')
            
            # Check if ADC/Service Account is accidentally being used
            google_app_creds = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            using_adc = bool(google_app_creds)
            
            logger.info(
                f"[GEMINI_LLM_INIT] Configuration check: "
                f"api_key_exists={api_key_exists}, "
                f"env_var={env_var_used}, "
                f"llm_model={llm_model}, "
                f"using_adc_or_sa={using_adc}"
            )
            
            if not gemini_api_key:
                error_msg = (
                    f"Gemini LLM client initialization failed: {env_var_used} environment variable not set. "
                    f"Please set {env_var_used} to your Gemini API key. "
                    f"Get your key from: https://makersuite.google.com/app/apikey"
                )
                logger.error(f"❌ {error_msg}")
                _gemini_llm_client = False  # Cache failure
                raise RuntimeError(error_msg)
            
            # Check if key looks valid (not empty, not placeholder)
            if gemini_api_key.strip() == "" or gemini_api_key in ["your-key-here", "CHANGE_ME"]:
                error_msg = (
                    f"Gemini LLM client initialization failed: {env_var_used} is set but appears to be a placeholder. "
                    f"Please set a valid API key from: https://makersuite.google.com/app/apikey"
                )
                logger.error(f"❌ {error_msg}")
                _gemini_llm_client = False
                raise RuntimeError(error_msg)
            
            # 🔥 Initialize with timeout configuration (connect=2s, read=10s)
            if httpx is not None:
                http_client = httpx.Client(
                    timeout=httpx.Timeout(connect=2.0, read=10.0, write=5.0, pool=5.0)
                )
                _gemini_llm_client = genai.Client(api_key=gemini_api_key, http_options={'client': http_client})
                logger.info(f"✅ Gemini LLM client initialized (singleton) - model={llm_model}, timeout=10s")
            else:
                # Fallback without timeout if httpx not available
                _gemini_llm_client = genai.Client(api_key=gemini_api_key)
                logger.warning(f"⚠️ Gemini LLM client initialized without timeout (httpx not available) - model={llm_model}")
            
            return _gemini_llm_client
            
        except RuntimeError:
            # Re-raise our detailed RuntimeError
            raise
        except Exception as e:
            error_msg = f"Gemini LLM client initialization failed with exception: {type(e).__name__}: {str(e)}"
            logger.error(f"❌ {error_msg}")
            logger.exception("Full traceback:")
            _gemini_llm_client = False  # Cache failure
            raise RuntimeError(error_msg)


def get_gemini_tts_client():
    """
    Get Gemini AI client for TTS (singleton).
    
    Returns:
        genai.Client: Initialized Gemini client for TTS
    
    Raises:
        RuntimeError: With detailed reason if initialization fails
    
    Notes:
        - Uses GEMINI_API_KEY environment variable (ONLY - no fallbacks)
        - Thread-safe with double-checked locking
        - Caches failures to avoid repeated init attempts
        - NOT affected by DISABLE_GOOGLE (Gemini is separate from Google Cloud STT/TTS)
        - Configured with timeout: connect=2s, read=10s
        - NEVER returns None - always throws exception with details
    """
    global _gemini_tts_client
    
    # Fast path: already initialized (or failed)
    if _gemini_tts_client is not None:
        # If cached failure (False), throw exception
        if _gemini_tts_client is False:
            raise RuntimeError("Gemini TTS client initialization previously failed - check logs for details")
        return _gemini_tts_client
    
    # Slow path: initialize with lock
    with _gemini_tts_lock:
        # Double-check: another thread may have initialized while we waited
        if _gemini_tts_client is not None:
            if _gemini_tts_client is False:
                raise RuntimeError("Gemini TTS client initialization previously failed - check logs for details")
            return _gemini_tts_client
        
        try:
            from google import genai
            from server.utils.gemini_key_provider import get_gemini_api_key
            
            # 🔥 DETAILED LOGGING: Log configuration before attempting init
            gemini_api_key = get_gemini_api_key()
            api_key_exists = bool(gemini_api_key)
            env_var_used = "GEMINI_API_KEY"
            tts_model = os.getenv('GEMINI_TTS_MODEL', 'gemini-2.5-flash-preview-tts')
            
            # Check if ADC/Service Account is accidentally being used
            google_app_creds = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            using_adc = bool(google_app_creds)
            
            logger.info(
                f"[GEMINI_TTS_INIT] Configuration check: "
                f"api_key_exists={api_key_exists}, "
                f"env_var={env_var_used}, "
                f"tts_model={tts_model}, "
                f"using_adc_or_sa={using_adc}"
            )
            
            if not gemini_api_key:
                error_msg = (
                    f"Gemini TTS client initialization failed: {env_var_used} environment variable not set. "
                    f"Please set {env_var_used} to your Gemini API key. "
                    f"Get your key from: https://makersuite.google.com/app/apikey"
                )
                logger.error(f"❌ {error_msg}")
                _gemini_tts_client = False  # Cache failure
                raise RuntimeError(error_msg)
            
            # Check if key looks valid (not empty, not placeholder)
            if gemini_api_key.strip() == "" or gemini_api_key in ["your-key-here", "CHANGE_ME"]:
                error_msg = (
                    f"Gemini TTS client initialization failed: {env_var_used} is set but appears to be a placeholder. "
                    f"Please set a valid API key from: https://makersuite.google.com/app/apikey"
                )
                logger.error(f"❌ {error_msg}")
                _gemini_tts_client = False
                raise RuntimeError(error_msg)
            
            # 🔥 Initialize with timeout configuration (connect=2s, read=10s)
            if httpx is not None:
                http_client = httpx.Client(
                    timeout=httpx.Timeout(connect=2.0, read=10.0, write=5.0, pool=5.0)
                )
                _gemini_tts_client = genai.Client(api_key=gemini_api_key, http_options={'client': http_client})
                logger.info(f"✅ Gemini TTS client initialized (singleton) - model={tts_model}, timeout=10s")
            else:
                # Fallback without timeout if httpx not available
                _gemini_tts_client = genai.Client(api_key=gemini_api_key)
                logger.warning(f"⚠️ Gemini TTS client initialized without timeout (httpx not available) - model={tts_model}")
            
            return _gemini_tts_client
            
        except RuntimeError:
            # Re-raise our detailed RuntimeError
            raise
        except Exception as e:
            error_msg = f"Gemini TTS client initialization failed with exception: {type(e).__name__}: {str(e)}"
            logger.error(f"❌ {error_msg}")
            logger.exception("Full traceback:")
            _gemini_tts_client = False  # Cache failure
            raise RuntimeError(error_msg)


def get_gemini_client():
    """
    DEPRECATED: Use get_gemini_llm_client() or get_gemini_tts_client() instead.
    
    This function is kept for backwards compatibility and returns the LLM client.
    
    Returns:
        genai.Client: Initialized Gemini client for LLM
    
    Raises:
        RuntimeError: With detailed reason if initialization fails
    """
    logger.warning("⚠️ get_gemini_client() is deprecated - use get_gemini_llm_client() or get_gemini_tts_client()")
    return get_gemini_llm_client()


def warmup_google_clients():
    """
    Warmup function to initialize Google clients at server startup.
    
    Call this from app factory/startup hook to catch configuration issues early
    rather than during first call/session.
    
    This is optional but recommended for production deployments.
    """
    logger.info("🔥 Warming up Google clients...")
    
    # Attempt to initialize STT client (respects DISABLE_GOOGLE)
    try:
        stt_client = get_stt_client()
        logger.info("  ✅ Google STT client warmed up")
    except RuntimeError as e:
        disable_google = os.getenv('DISABLE_GOOGLE', 'true').lower() == 'true'
        if disable_google:
            logger.info("  🚫 Google STT warmup SKIPPED (DISABLE_GOOGLE=true)")
        else:
            logger.warning(f"  ⚠️ Google STT client failed to initialize: {e}")
    except Exception as e:
        logger.error(f"  ❌ Google STT client warmup error: {e}")
    
    # Attempt to initialize Gemini LLM client
    try:
        gemini_llm_client = get_gemini_llm_client()
        logger.info("  ✅ Gemini LLM client warmed up")
    except RuntimeError as e:
        logger.warning(f"  ⚠️ Gemini LLM client not available: {e}")
    except Exception as e:
        logger.error(f"  ❌ Gemini LLM client warmup error: {e}")
    
    # Attempt to initialize Gemini TTS client
    try:
        gemini_tts_client = get_gemini_tts_client()
        logger.info("  ✅ Gemini TTS client warmed up")
    except RuntimeError as e:
        logger.warning(f"  ⚠️ Gemini TTS client not available: {e}")
    except Exception as e:
        logger.error(f"  ❌ Gemini TTS client warmup error: {e}")
    
    logger.info("🔥 Google clients warmup complete")


def reset_clients():
    """
    Reset all cached clients (for testing purposes only).
    
    This should NOT be called in production code.
    """
    global _stt_client, _gemini_llm_client, _gemini_tts_client
    with _stt_lock:
        _stt_client = None
    with _gemini_llm_lock:
        _gemini_llm_client = None
    with _gemini_tts_lock:
        _gemini_tts_client = None
    logger.debug("🔄 Google clients cache reset")
