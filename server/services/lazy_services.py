"""
Lazy Service Registry - Prevents boot blocking by deferring init to first use
🚫 Google services DISABLED for production stability
"""
import os
import json
import time
import logging
import threading
from functools import wraps


logger = logging.getLogger(__name__)

log = logging.getLogger("lazy_services")

# 🚫 DISABLE_GOOGLE: Hard off - prevents stalls and latency issues
DISABLE_GOOGLE = os.getenv('DISABLE_GOOGLE', 'true').lower() == 'true'

if DISABLE_GOOGLE:
    log.info("🚫 Google services DISABLED (DISABLE_GOOGLE=true)")

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
    """
    🚫 DISABLED - Google TTS client is turned off for production stability
    """
    if DISABLE_GOOGLE:
        log.debug("Google TTS client requested but DISABLE_GOOGLE=true")
        return None
    
    log.warning("⚠️ Google TTS should not be used - DISABLE_GOOGLE flag should be set")
    return None

@lazy_singleton("gcp_stt_client")
def get_stt_client():
    """
    🚫 DISABLED - Google STT client is turned off for production stability
    """
    if DISABLE_GOOGLE:
        log.debug("Google STT client requested but DISABLE_GOOGLE=true")
        return None
    
    log.warning("⚠️ Google STT should not be used - DISABLE_GOOGLE flag should be set")
    return None



def warmup_services_async():
    """⚡ Non-blocking warmup - starts immediately after app init"""
    def _warmup():
        import time  # Import at start of function
        time.sleep(0.5)  # ⚡ Minimal delay - just let Flask finish binding
        logger.info("🔥🔥🔥 WARMUP STARTING - Preloading services...")
        log.info("🔥 Starting service warmup...")
        
        # Check if agent warmup is disabled
        disable_agent_warmup = os.getenv('DISABLE_AGENT_WARMUP', '0') in ('1', 'true', 'True')
        
        # Warmup OpenAI
        logger.info("  🔥 Warming OpenAI client...")
        client = get_openai_client()
        if client:
            logger.info("    ✅ OpenAI client ready")
            log.info("WARMUP_OPENAI_OK")
        else:
            logger.error("    ❌ OpenAI client failed")
            log.warning("WARMUP_OPENAI_ERR")
        
        # 🚫 SKIP Google TTS warmup (DISABLED)
        logger.info("  🚫 Google TTS warmup SKIPPED (DISABLE_GOOGLE=true)")
        log.info("WARMUP_TTS_SKIPPED")
        
        # 🚫 SKIP Google STT warmup (DISABLED)
        logger.info("  🚫 Google STT warmup SKIPPED (DISABLE_GOOGLE=true)")
        log.info("WARMUP_STT_SKIPPED")
        
        # 🔥 CRITICAL: Warmup Agent Kit to avoid first-call latency
        # Can be disabled with DISABLE_AGENT_WARMUP=1 if schema issues occur
        if disable_agent_warmup:
            logger.info("  🚫 Agent warmup SKIPPED (DISABLE_AGENT_WARMUP=1)")
            log.info("WARMUP_AGENT_SKIPPED: disabled by environment variable")
        else:
            try:
                from server.app_factory import get_process_app
                from server.agent_tools.agent_factory import get_or_create_agent
                from server.models_sql import Business, BusinessSettings, db
                from sqlalchemy.exc import SQLAlchemyError
                
                # 🔥 ARCHITECT FIX: Need app context for database operations!
                app = get_process_app()
                with app.app_context():
                    # 🔥 MULTI-TENANT: Warmup ALL active businesses (up to 10 for reasonable startup time)
                    try:
                        businesses = Business.query.filter_by(is_active=True).limit(10).all()
                    except SQLAlchemyError as db_error:
                        # 🔥 CRITICAL FIX: Rollback transaction to prevent "InFailedSqlTransaction"
                        db.session.rollback()
                        logger.error(f"    ❌ Database query failed during warmup: {db_error}")
                        log.error(f"WARMUP_DB_ERR: {db_error}")
                        businesses = []
                    
                    if not businesses:
                        logger.warning("    ⚠️ No active businesses to warm up")
                        log.warning("WARMUP_AGENT_ERR: No active businesses found")
                    else:
                        log.info(f"🔥 WARMUP: Found {len(businesses)} active businesses to warm up")
                        logger.info(f"  🔥 Warming {len(businesses)} active businesses (Agent Cache)...")
                        
                        total_start = time.time()
                        success_count = 0
                        
                        for business in businesses:
                            business_id = business.id
                            business_name = business.name
                            
                            # Warmup both channels for each business
                            for channel in ['calls', 'whatsapp']:
                                try:
                                    # Get prompt from database for THIS business
                                    try:
                                        settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
                                    except SQLAlchemyError as db_error:
                                        # 🔥 CRITICAL FIX: Rollback transaction to prevent "InFailedSqlTransaction"
                                        db.session.rollback()
                                        log.warning(f"WARMUP_SETTINGS_ERR: business={business_id} - {db_error}")
                                        settings = None
                                        
                                    custom_instructions = ""  # Default empty string
                                    if settings and settings.ai_prompt:
                                        import json
                                        prompts = json.loads(settings.ai_prompt)
                                        custom_instructions = prompts.get(channel, prompts.get('calls', '')) or ""
                                    
                                    # Create agent (will cache it)
                                    warmup_start = time.time()
                                    agent = get_or_create_agent(
                                        business_id=business_id,
                                        channel=channel,
                                        business_name=business_name,
                                        custom_instructions=custom_instructions
                                    )
                                    warmup_time = (time.time() - warmup_start) * 1000
                                    
                                    if agent:
                                        success_count += 1
                                        log.info(f"WARMUP_AGENT_OK: business={business_id} ({business_name}), channel={channel} ({warmup_time:.0f}ms)")
                                        logger.info(f"  ✅ {business_name} ({channel}): {warmup_time:.0f}ms")
                                    else:
                                        log.warning(f"WARMUP_AGENT_ERR: business={business_id}, channel={channel} - agent is None")
                                except Exception as e:
                                    log.warning(f"WARMUP_AGENT_ERR: business={business_id}, channel={channel} - {e}")
                                    import traceback
                                    traceback.print_exc()
                        
                        total_time = (time.time() - total_start) * 1000
                        logger.info(f"\n🔥🔥🔥 WARMUP COMPLETE: {success_count}/{len(businesses)*2} agents ready in {total_time:.0f}ms")
                        logger.info(f"🚀 System preheated - First AI response will be FAST!\n")
                        log.info(f"🔥 WARMUP COMPLETE: {success_count} agents warmed in {total_time:.0f}ms")
            except Exception as e:
                logger.error(f"    ❌ Agent warmup failed: {e}")
                log.warning(f"WARMUP_AGENT_FAILED: {e}")
                import traceback
                traceback.print_exc()
        
        # 🔥 CRITICAL: Warmup AIService cache for business prompts
        logger.info("  🔥 Warming AIService cache...")
        try:
            from server.services.ai_service import get_ai_service, _warmup_ai_cache
            ai_service = get_ai_service()
            _warmup_ai_cache(ai_service)
            logger.info("    ✅ AIService cache warmed successfully")
            log.info("WARMUP_AI_CACHE_OK")
        except Exception as e:
            logger.warning(f"    ⚠️ AIService cache warmup failed (non-critical): {e}")
            log.warning(f"WARMUP_AI_CACHE_WARN: {e}")
            
        logger.info("✅ Service warmup thread completed")
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
    🚫 DISABLED - Periodic warmup for Google services is turned off
    
    Google STT/TTS periodic ping is disabled for production stability.
    This function is a no-op when DISABLE_GOOGLE=true.
    """
    if DISABLE_GOOGLE:
        log.info("🚫 Periodic warmup DISABLED (Google services are off)")
        return
    
    # If somehow called with DISABLE_GOOGLE=false, still don't start warmup
    log.warning("⚠️ Periodic warmup requested but Google services should be disabled")
    return