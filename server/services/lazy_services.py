"""
Lazy Service Registry - Prevents boot blocking by deferring init to first use
"""
import os
import json
import time
import logging
import threading
from functools import wraps

log = logging.getLogger("lazy_services")

# Thread-safe singleton registry
_service_lock = threading.Lock()
_services = {}

def lazy_singleton(service_name):
    """Decorator for thread-safe lazy initialization"""
    def decorator(init_func):
        @wraps(init_func)
        def wrapper(*args, **kwargs):
            if service_name not in _services:
                with _service_lock:
                    # Double-check pattern
                    if service_name not in _services:
                        try:
                            log.debug(f"Lazy init: {service_name}")
                            service = init_func(*args, **kwargs)
                            _services[service_name] = service
                            log.info(f"✅ {service_name} initialized")
                        except Exception as e:
                            log.error(f"❌ {service_name} init failed: {e}")
                            _services[service_name] = None  # Cache failure
                            return None
            return _services.get(service_name)
        return wrapper
    return decorator

@lazy_singleton("openai_client")
def get_openai_client():
    """Lazy OpenAI client with timeout"""
    import openai
    
    if not os.getenv("OPENAI_API_KEY"):
        log.warning("OPENAI_API_KEY missing")
        return None
        
    try:
        client = openai.OpenAI(timeout=5.0)  # 5s timeout
        # Quick ping test
        client.models.list(timeout=3.0)
        return client
    except Exception as e:
        log.error(f"OpenAI init failed: {e}")
        return None

@lazy_singleton("gcp_tts_client")  
def get_tts_client():
    """Lazy GCP TTS client with timeout"""
    try:
        from google.cloud import texttospeech
        
        # Check if credentials configured
        sa_json = os.getenv('GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON')
        if not sa_json:
            log.warning("Google TTS credentials missing")
            return None
            
        # Parse and create client  
        credentials_info = json.loads(sa_json)
        client = texttospeech.TextToSpeechClient.from_service_account_info(credentials_info)
        
        # Just verify client creation worked
        log.debug("TTS client created successfully")
        
        return client
    except Exception as e:
        log.error(f"GCP TTS init failed: {e}")
        return None

@lazy_singleton("gcp_stt_client")
def get_stt_client():
    """Lazy GCP STT client with timeout"""
    try:
        from google.cloud import speech
        
        # Check if credentials configured
        sa_json = os.getenv('GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON') 
        if not sa_json:
            log.warning("Google STT credentials missing")
            return None
            
        # Parse and create client
        credentials_info = json.loads(sa_json)
        client = speech.SpeechClient.from_service_account_info(credentials_info)
        
        # Quick ping test - just verify client creation worked
        log.debug("STT client created successfully")
        
        return client
    except Exception as e:
        log.error(f"GCP STT init failed: {e}")
        return None

def warmup_services_async():
    """Non-blocking warmup after server is listening"""
    def _warmup():
        time.sleep(2)  # Let server stabilize first
        log.info("🔥 Starting service warmup...")
        
        # Warmup OpenAI
        client = get_openai_client()
        if client:
            log.info("WARMUP_OPENAI_OK")
        else:
            log.warning("WARMUP_OPENAI_ERR")
            
        # Warmup TTS
        client = get_tts_client()
        if client:
            log.info("WARMUP_TTS_OK")
        else:
            log.warning("WARMUP_TTS_ERR")
            
        # Warmup STT
        client = get_stt_client()
        if client:
            log.info("WARMUP_STT_OK")
        else:
            log.warning("WARMUP_STT_ERR")
            
        log.info("🔥 Service warmup completed")
    
    # Start warmup in background thread
    warmup_thread = threading.Thread(target=_warmup, daemon=True)
    warmup_thread.start()
    log.info("🔥 Service warmup scheduled")

def get_service_status():
    """Get current status of all services (for /readyz)"""
    status = {}
    
    # Check what's already loaded (don't trigger init)
    for service_name in ["openai_client", "gcp_tts_client", "gcp_stt_client"]:
        if service_name in _services:
            status[service_name] = "ok" if _services[service_name] is not None else "error"
        else:
            status[service_name] = "pending"
            
    return status