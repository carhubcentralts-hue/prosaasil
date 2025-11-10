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
    """⚡ FAST OpenAI client with short timeout"""
    import openai
    
    if not os.getenv("OPENAI_API_KEY"):
        log.warning("OPENAI_API_KEY missing")
        return None
        
    try:
        client = openai.OpenAI(timeout=3.5)  # ⚡ 3.5s timeout for speed
        # Skip ping test - don't slow down startup
        return client
    except Exception as e:
        log.error(f"OpenAI init failed: {e}")
        return None

@lazy_singleton("gcp_tts_client")  
def get_tts_client():
    """Lazy GCP TTS client with timeout"""
    try:
        from google.cloud import texttospeech
        
        # ✅ CRITICAL FIX: Try JSON string first, then check for file path
        sa_json = os.getenv('GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON')
        if sa_json and sa_json.startswith('{'):
            # It's a JSON string
            credentials_info = json.loads(sa_json)
            client = texttospeech.TextToSpeechClient.from_service_account_info(credentials_info)
        else:
            # Try file path from GOOGLE_APPLICATION_CREDENTIALS
            creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            if creds_path and os.path.exists(creds_path):
                # It's a file path
                client = texttospeech.TextToSpeechClient.from_service_account_json(creds_path)
            elif not sa_json and not creds_path:
                log.warning("Google TTS credentials missing - no GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON or GOOGLE_APPLICATION_CREDENTIALS")
                return None
            else:
                # Default to using environment (will use GOOGLE_APPLICATION_CREDENTIALS automatically)
                client = texttospeech.TextToSpeechClient()
        
        # Just verify client creation worked
        log.info("✅ TTS client created successfully")
        
        return client
    except Exception as e:
        log.error(f"GCP TTS init failed: {e}")
        import traceback
        traceback.print_exc()
        return None

@lazy_singleton("gcp_stt_client")
def get_stt_client():
    """Lazy GCP STT client with timeout"""
    try:
        from google.cloud import speech
        
        # ✅ CRITICAL FIX: Try JSON string first, then check for file path
        sa_json = os.getenv('GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON')
        if sa_json and sa_json.startswith('{'):
            # It's a JSON string
            credentials_info = json.loads(sa_json)
            client = speech.SpeechClient.from_service_account_info(credentials_info)
        else:
            # Try file path from GOOGLE_APPLICATION_CREDENTIALS
            creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            if creds_path and os.path.exists(creds_path):
                # It's a file path
                client = speech.SpeechClient.from_service_account_json(creds_path)
            elif not sa_json and not creds_path:
                log.warning("Google STT credentials missing - no GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON or GOOGLE_APPLICATION_CREDENTIALS")
                return None
            else:
                # Default to using environment (will use GOOGLE_APPLICATION_CREDENTIALS automatically)
                client = speech.SpeechClient()
        
        # Quick ping test - just verify client creation worked
        log.info("✅ STT client created successfully")
        
        return client
    except Exception as e:
        log.error(f"GCP STT init failed: {e}")
        import traceback
        traceback.print_exc()
        return None

def warmup_services_async():
    """⚡ Non-blocking warmup - starts immediately after app init"""
    def _warmup():
        time.sleep(0.5)  # ⚡ Minimal delay - just let Flask finish binding
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
        
        # 🔥 CRITICAL: Warmup Agent Kit to avoid first-call latency
        try:
            from server.app_factory import get_process_app
            from server.agent_tools.agent_factory import get_or_create_agent
            from server.models import Business, BusinessSettings
            
            # 🔥 ARCHITECT FIX: Need app context for database operations!
            app = get_process_app()
            with app.app_context():
                # Load business data from DB
                business = Business.query.get(1)
                if not business:
                    log.warning("WARMUP_AGENT_ERR: Business ID 1 not found")
                else:
                    business_name = business.name
                    
                    # Warmup business 1 for both channels
                    for channel in ['calls', 'whatsapp']:
                        try:
                            # Get prompt from database
                            settings = BusinessSettings.query.filter_by(tenant_id=1).first()
                            custom_instructions = ""  # Default empty string
                            if settings and settings.ai_prompt:
                                import json
                                prompts = json.loads(settings.ai_prompt)
                                custom_instructions = prompts.get(channel, prompts.get('calls', '')) or ""
                            
                            # Create agent (will cache it)
                            import time
                            warmup_start = time.time()
                            agent = get_or_create_agent(
                                business_id=1,
                                channel=channel,
                                business_name=business_name,
                                custom_instructions=custom_instructions
                            )
                            warmup_time = (time.time() - warmup_start) * 1000
                            
                            if agent:
                                log.info(f"WARMUP_AGENT_OK: business=1, channel={channel} ({warmup_time:.0f}ms)")
                                print(f"🔥 WARMUP_AGENT_OK: business=1, channel={channel} ({warmup_time:.0f}ms)")
                            else:
                                log.warning(f"WARMUP_AGENT_ERR: business=1, channel={channel} - agent is None")
                        except Exception as e:
                            log.warning(f"WARMUP_AGENT_ERR: business=1, channel={channel} - {e}")
                            import traceback
                            traceback.print_exc()
        except Exception as e:
            log.warning(f"WARMUP_AGENT_FAILED: {e}")
            import traceback
            traceback.print_exc()
            
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

def start_periodic_warmup():
    """
    🔥 Phase 2F: Periodic warmup ping every 7-8 minutes
    Prevents cold start by keeping Google STT/TTS clients warm
    """
    import random
    
    def _warmup_loop():
        """Background loop that pings services every 7-8 minutes"""
        # First ping immediately (don't wait 7-8min on startup)
        first_run = True
        
        while True:
            if not first_run:
                # Random interval 7-8 minutes (420-480 seconds)
                interval = random.uniform(420, 480)
                log.info(f"🔥 PERIODIC_WARMUP: Next ping in {interval/60:.1f}min")
                time.sleep(interval)
            else:
                first_run = False
                log.info("🔥 PERIODIC_WARMUP: First ping starting immediately")
            
            try:
                # 🔥 CRITICAL: Make ACTUAL API requests to keep connections alive!
                
                # Ping TTS with real synthesis request
                tts_client = get_tts_client()
                if tts_client:
                    try:
                        from google.cloud import texttospeech
                        
                        # Synthesize 1 Hebrew word to keep connection alive
                        synthesis_input = texttospeech.SynthesisInput(text="שלום")
                        voice = texttospeech.VoiceSelectionParams(
                            language_code="he-IL",
                            name="he-IL-Wavenet-D"
                        )
                        audio_config = texttospeech.AudioConfig(
                            audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                            sample_rate_hertz=8000
                        )
                        
                        # Actual API call!
                        response = tts_client.synthesize_speech(
                            input=synthesis_input,
                            voice=voice,
                            audio_config=audio_config,
                            timeout=5.0
                        )
                        
                        log.info(f"WARMUP_TTS_PING: OK (generated {len(response.audio_content)} bytes)")
                    except Exception as e:
                        log.warning(f"WARMUP_TTS_PING: FAILED - {e}")
                else:
                    log.warning("WARMUP_TTS_PING: No client")
                
                # Ping STT with minimal audio (100ms silence)
                stt_client = get_stt_client()
                if stt_client:
                    try:
                        from google.cloud import speech
                        
                        # Create 100ms of silence at 8kHz PCM16
                        # 8000 samples/sec * 0.1 sec * 2 bytes/sample = 1600 bytes
                        silent_audio = b'\x00' * 1600
                        
                        # Minimal STT config
                        config = speech.RecognitionConfig(
                            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                            sample_rate_hertz=8000,
                            language_code="he-IL",
                            max_alternatives=1
                        )
                        
                        audio = speech.RecognitionAudio(content=silent_audio)
                        
                        # Actual API call!
                        response = stt_client.recognize(
                            config=config,
                            audio=audio,
                            timeout=5.0
                        )
                        
                        log.info(f"WARMUP_STT_PING: OK (results={len(response.results)})")
                    except Exception as e:
                        log.warning(f"WARMUP_STT_PING: FAILED - {e}")
                else:
                    log.warning("WARMUP_STT_PING: No client")
                    
            except Exception as e:
                log.error(f"WARMUP_PING_ERROR: {e}")
    
    # Start warmup loop in background daemon thread
    warmup_thread = threading.Thread(target=_warmup_loop, daemon=True, name="periodic-warmup")
    warmup_thread.start()
    log.info("🔥 Periodic warmup started (every 7-8 minutes)")