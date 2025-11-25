"""
WhatsApp Provider Layer - Unified Baileys and Twilio Support
שכבת ספקי WhatsApp - תמיכה מאוחדת ב-Baileys ו-Twilio
"""
import os
import json
import time
import pathlib
import logging
import requests
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Global service instance
_whatsapp_service = None

class Provider:
    """Abstract WhatsApp provider interface"""
    def send_text(self, to: str, text: str, tenant_id: str = None) -> Dict[str, Any]:
        raise NotImplementedError
        
    def send_media(self, to: str, media_url: str, caption: str = "", tenant_id: str = None) -> Dict[str, Any]:
        raise NotImplementedError

class BaileysProvider(Provider):
    """⚡ OPTIMIZED Baileys HTTP API provider with health checks and failover"""
    
    def __init__(self):
        self.outbound_url = os.getenv("BAILEYS_BASE_URL", "http://127.0.0.1:3300")
        self.webhook_secret = os.getenv("BAILEYS_WEBHOOK_SECRET", "")
        self.internal_secret = os.getenv("INTERNAL_SECRET", "")  # 🔒 For internal API calls
        self.timeout = 15.0  # ⚡ FIXED: 15s timeout for WhatsApp message sending
        self._last_health_check = 0
        self._health_status = False
        self._health_cache_duration = 30  # 30 seconds cache
        
        # ⚡ Connection pooling for speed
        self._session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=0  # 🔥 FIX #2: NO retries - single attempt only!
        )
        self._session.mount('http://', adapter)
        self._session.mount('https://', adapter)
        
        if not self.webhook_secret:
            logger.warning("BAILEYS_WEBHOOK_SECRET not set - security risk!")
        if not self.internal_secret:
            logger.warning("INTERNAL_SECRET not set - auto-restart will fail!")

    def _check_health(self) -> bool:
        """⚡ Check Baileys WhatsApp connection status with caching"""
        now = time.time()
        if now - self._last_health_check < self._health_cache_duration:
            return self._health_status
            
        try:
            # 🔥 FIX: Check actual WhatsApp connection, not just service health!
            headers = {"X-Internal-Secret": self.internal_secret}
            # ✅ Multi-tenant: Check first available tenant for service health
            response = self._session.get(
                f"{self.outbound_url}/health",  # General service health
                headers=headers,
                timeout=1.0  # ⚡ Fast health check
            )
            
            if response.status_code == 200:
                data = response.json()
                # Check if actually connected to WhatsApp, not just service running
                self._health_status = data.get("connected", False)
            else:
                self._health_status = False
                
            self._last_health_check = now
            return self._health_status
        except Exception as e:
            logger.warning(f"Baileys health check failed: {e}")
            self._health_status = False
            self._last_health_check = now
            return False
    
    def _start_baileys(self, tenant_id: str = "business_1") -> bool:
        """🔥 Start Baileys session if not running"""
        try:
            logger.info(f"🚀 Starting Baileys session for {tenant_id}...")
            headers = {"X-Internal-Secret": self.internal_secret}
            response = self._session.post(
                f"{self.outbound_url}/whatsapp/{tenant_id}/start",
                headers=headers,
                timeout=3.0
            )
            if response.status_code == 200:
                logger.info(f"✅ Baileys session started for {tenant_id}")
                return True
            else:
                logger.warning(f"⚠️ Failed to start Baileys: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ Failed to start Baileys: {e}")
            return False
    
    def _wait_for_ready(self, tenant_id: str = "business_1", timeout: float = 10.0) -> bool:
        """🔥 Wait for Baileys to become ready"""
        start = time.time()
        headers = {"X-Internal-Secret": self.internal_secret}
        while time.time() - start < timeout:
            try:
                response = self._session.get(
                    f"{self.outbound_url}/whatsapp/{tenant_id}/status",
                    headers=headers,
                    timeout=1.0
                )
                if response.status_code == 200:
                    data = response.json()
                    if data.get("connected"):
                        logger.info("✅ Baileys is now connected!")
                        self._health_status = True
                        self._last_health_check = time.time()
                        return True
            except:
                pass
            time.sleep(0.5)  # Check every 500ms
        
        logger.warning(f"⏰ Baileys didn't connect within {timeout}s")
        return False
    
    def send_typing(self, jid: str, is_typing: bool = True, tenant_id: str = None) -> Dict[str, Any]:
        """⚡ Send typing indicator - instant user feedback (MULTI-TENANT)"""
        try:
            payload = {
                "jid": jid,
                "typing": is_typing,
                "tenantId": tenant_id or "business_1"  # Multi-tenant support
            }
            
            response = self._session.post(
                f"{self.outbound_url}/sendTyping",
                json=payload,
                timeout=0.5  # ⚡ Super fast - don't wait
            )
            
            return {"status": "sent" if response.status_code == 200 else "error"}
        except Exception as e:
            # Don't log - typing is optional
            return {"status": "error", "error": str(e)}
    
    def send_text(self, to: str, text: str, tenant_id: str = None) -> Dict[str, Any]:
        """⚡ Send text message via Baileys HTTP API with AUTO-RESTART (MULTI-TENANT)"""
        max_attempts = 1  # 🔥 Single attempt to prevent loops
        last_error = None
        effective_tenant = tenant_id or "business_1"  # MULTI-TENANT support
        
        for attempt in range(max_attempts):
            try:
                # 🔥 AUTO-RESTART: If Baileys is down, try to start it!
                if not self._check_health():
                    logger.warning("⚠️ Baileys service unavailable - attempting auto-restart...")
                    
                    # Try to start Baileys for this tenant
                    if self._start_baileys(effective_tenant):
                        # Wait for it to become ready (10s max)
                        if not self._wait_for_ready(effective_tenant, timeout=10.0):
                            logger.error("❌ Baileys auto-restart timed out")
                            return {
                                "provider": "baileys",
                                "status": "error",
                                "error": "WhatsApp service not connected (auto-restart failed)"
                            }
                        logger.info("✅ Baileys auto-restart successful!")
                    else:
                        logger.error("❌ Failed to trigger Baileys restart")
                        return {
                            "provider": "baileys",
                            "status": "error",
                            "error": "WhatsApp service not connected (restart failed)"
                        }
                
                # Generate idempotency key
                idempotency_key = str(uuid.uuid4())
                
                payload = {
                    "to": to.replace("whatsapp:", "").replace("+", ""),
                    "type": "text",
                    "text": text,
                    "idempotencyKey": idempotency_key,
                    "tenantId": effective_tenant  # MULTI-TENANT: Route to correct session
                }
                
                logger.info(f"⚡ Sending WhatsApp to {to[:15]}...")
                
                response = self._session.post(
                    f"{self.outbound_url}/send",
                    json=payload,
                    timeout=5  # 🔥 5s timeout (reduced from 15s)
                )
                
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"✅ WhatsApp sent successfully to {to[:15]}...")
                    return {
                        "provider": "baileys",
                        "status": "sent",
                        "sid": result.get("messageId", idempotency_key),
                        "message_id": result.get("messageId", idempotency_key)
                    }
                else:
                    last_error = f"Service unavailable (HTTP {response.status_code})"
                    logger.warning(f"⚠️ Baileys returned {response.status_code}")
                    # NO RETRY - fail fast!
                    break
                    
            except requests.exceptions.Timeout as e:
                last_error = "WhatsApp service timeout"
                logger.warning(f"⚠️ Timeout: {e}")
                # NO RETRY - fail fast!
                break
            except Exception as e:
                last_error = "WhatsApp service error"
                logger.error(f"❌ Baileys send error: {e}")
                # NO RETRY - fail fast!
                break
        
        # Failed - return graceful error
        logger.error(f"❌ WhatsApp send failed: {last_error}")
        return {
            "provider": "baileys",
            "status": "error",
            "error": last_error
        }
    
    def send_media(self, to: str, media_url: str, caption: str = "", tenant_id: str = None) -> Dict[str, Any]:
        """Send media message via Baileys HTTP API (MULTI-TENANT)"""
        try:
            if not self._check_health():
                return {
                    "provider": "baileys",
                    "status": "error",
                    "error": "Baileys service unavailable"
                }
            
            # Generate idempotency key
            idempotency_key = str(uuid.uuid4())
            effective_tenant = tenant_id or "business_1"  # MULTI-TENANT support
            
            payload = {
                "to": to.replace("whatsapp:", "").replace("+", ""),
                "type": "media",
                "mediaUrl": media_url,
                "caption": caption,
                "idempotencyKey": idempotency_key,
                "tenantId": effective_tenant  # MULTI-TENANT: Route to correct session
            }
            
            response = requests.post(
                f"{self.outbound_url}/send",
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Baileys media sent: {to}")
                return {
                    "provider": "baileys",
                    "status": "sent",
                    "sid": result.get("messageId", idempotency_key)
                }
            else:
                logger.error(f"Baileys media send failed: {response.status_code} {response.text}")
                return {
                    "provider": "baileys",
                    "status": "error",
                    "error": f"HTTP {response.status_code}"
                }
                
        except Exception as e:
            logger.error(f"Baileys media send exception: {e}")
            return {
                "provider": "baileys",
                "status": "error",
                "error": str(e)
            }

class TwilioProvider(Provider):
    """Twilio WhatsApp Business API provider"""
    
    def __init__(self):
        self.account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
        self.auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
        raw_from_number = os.environ.get('TWILIO_WA_FROM', '')
        
        # Ensure from_number has whatsapp: prefix (avoid double prefix)
        if raw_from_number and not raw_from_number.startswith('whatsapp:'):
            self.from_number = f'whatsapp:{raw_from_number}'
        else:
            self.from_number = raw_from_number
        
        if not all([self.account_sid, self.auth_token, self.from_number]):
            raise RuntimeError(
                "Missing Twilio WhatsApp ENV variables: "
                "TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WA_FROM"
            )
        
        try:
            from twilio.rest import Client
            self.client = Client(self.account_sid, self.auth_token)
        except ImportError:
            raise RuntimeError("Twilio package not installed")

    def _format_number(self, number: str) -> str:
        """Ensure number has whatsapp: prefix but avoid double prefix"""
        number_str = str(number)
        if number_str.startswith("whatsapp:"):
            return number_str
        return f"whatsapp:{number_str}"

    def send_text(self, to: str, text: str, tenant_id: str = None) -> Dict[str, Any]:
        """Send text message via Twilio WhatsApp API (tenant_id unused - Twilio is single-tenant)"""
        try:
            # Add status callback URL if PUBLIC_BASE_URL is available
            public_base = os.environ.get('PUBLIC_BASE_URL', '').rstrip('/')
            status_callback = f"{public_base}/webhook/whatsapp/status" if public_base else None
            
            message_params = {
                'body': text,
                'from_': self.from_number,
                'to': self._format_number(to)
            }
            
            if status_callback:
                message_params['status_callback'] = status_callback
                
            message = self.client.messages.create(**message_params)
            
            logger.info(f"Twilio message sent: {message.sid}")
            return {
                "provider": "twilio",
                "status": "sent",
                "sid": message.sid
            }
            
        except Exception as e:
            logger.error(f"Twilio send failed: {e}")
            return {
                "provider": "twilio",
                "status": "error", 
                "error": str(e)
            }
    
    def send_media(self, to: str, media_url: str, caption: str = "", tenant_id: str = None) -> Dict[str, Any]:
        """Send media message via Twilio WhatsApp API (tenant_id unused - Twilio is single-tenant)"""
        try:
            # Add status callback
            public_base = os.environ.get('PUBLIC_BASE_URL', '').rstrip('/')
            status_callback = f"{public_base}/webhook/whatsapp/status" if public_base else None
            
            message_params = {
                'body': caption,
                'media_url': [media_url],
                'from_': self.from_number,
                'to': self._format_number(to)
            }
            
            if status_callback:
                message_params['status_callback'] = status_callback
            
            message = self.client.messages.create(**message_params)
            
            logger.info(f"Twilio media sent: {message.sid}")
            return {
                "provider": "twilio",
                "status": "sent",
                "sid": message.sid
            }
            
        except Exception as e:
            logger.error(f"Twilio media send failed: {e}")
            return {
                "provider": "twilio",
                "status": "error",
                "error": str(e)
            }

def get_provider() -> Provider:
    """
    Factory function to get the configured WhatsApp provider with auto-failover
    פונקציית מפעל להחזרת ספק WhatsApp מוגדר עם failover אוטומטי
    """
    provider_name = os.getenv("WHATSAPP_PROVIDER", "auto").lower()
    
    if provider_name == "twilio":
        logger.info("Using Twilio WhatsApp provider")
        return TwilioProvider()
    elif provider_name == "baileys":
        logger.info("Using Baileys WhatsApp provider")
        return BaileysProvider()
    else:  # auto
        # Try Baileys first, fallback to Twilio
        try:
            baileys = BaileysProvider()
            if baileys._check_health():
                logger.info("Auto-selected Baileys provider")
                return baileys
        except Exception as e:
            logger.warning(f"Baileys not available: {e}")
        
        logger.info("Auto-selected Twilio provider (fallback)")
        return TwilioProvider()

def get_whatsapp_service(provider: str | None = None, thread_data: Dict[str, Any] | None = None, tenant_id: str = None):
    """Get WhatsApp service with smart routing and failover (MULTI-TENANT)
    
    IMPORTANT: When tenant_id is provided, we ALWAYS create a fresh BaileysProvider 
    to ensure multi-tenant routing works correctly. The singleton is only used for 
    non-tenant-specific calls (like health checks).
    """
    global _whatsapp_service
    
    # 🔥 MULTI-TENANT: If tenant_id is provided, ALWAYS use fresh Baileys (no singleton)
    if tenant_id:
        print(f"🔌 get_whatsapp_service: tenant_id={tenant_id} → using fresh BaileysProvider", flush=True)
        return WhatsAppService(BaileysProvider(), tenant_id=tenant_id)
    
    # Provider override for specific request
    if provider:
        p = provider.lower()
        print(f"🔌 get_whatsapp_service: explicit provider={p}", flush=True)
        if p == "twilio":
            return WhatsAppService(TwilioProvider(), tenant_id=tenant_id)
        if p == "baileys":
            return WhatsAppService(BaileysProvider(), tenant_id=tenant_id)
    
    # Smart routing logic
    if thread_data:
        resolved_provider = _resolve_smart_provider(thread_data)
        print(f"🔌 get_whatsapp_service: smart routing → {resolved_provider}", flush=True)
        if resolved_provider == "twilio":
            return WhatsAppService(TwilioProvider(), tenant_id=tenant_id)
        elif resolved_provider == "baileys":
            return WhatsAppService(BaileysProvider(), tenant_id=tenant_id)
    
    # Default service with auto-routing (singleton for non-tenant calls)
    if _whatsapp_service is None:
        provider_type = os.getenv("WHATSAPP_PROVIDER", "auto").lower()
        print(f"🔌 get_whatsapp_service: creating singleton (provider_type={provider_type})", flush=True)
        
        if provider_type == "auto":
            # Auto-routing: prefer Baileys if available, fallback to Twilio
            baileys = BaileysProvider()
            if baileys._check_health():
                _whatsapp_service = WhatsAppService(baileys, tenant_id=tenant_id)
            else:
                logger.info("Baileys unavailable, using Twilio")
                _whatsapp_service = WhatsAppService(TwilioProvider(), tenant_id=tenant_id)
        elif provider_type == "baileys":
            _whatsapp_service = WhatsAppService(BaileysProvider(), tenant_id=tenant_id)
        elif provider_type == "twilio":
            _whatsapp_service = WhatsAppService(TwilioProvider(), tenant_id=tenant_id)
        else:
            logger.warning(f"Unknown provider: {provider_type}, using auto")
            _whatsapp_service = WhatsAppService(BaileysProvider(), tenant_id=tenant_id)
    
    return _whatsapp_service

def _resolve_smart_provider(thread_data: Dict[str, Any]) -> str:
    """Smart provider resolution based on thread history and 24h window"""
    try:
        # Rule 1: Reply-via-source (prefer same provider as incoming)
        last_provider = thread_data.get("last_provider")
        
        # Rule 2: Check 24-hour window
        last_user_message_time = thread_data.get("last_user_message_time")
        if last_user_message_time:
            time_diff = datetime.now() - last_user_message_time
            within_24h = time_diff < timedelta(hours=24)
            
            if not within_24h:
                # Outside 24h window - use Twilio only (Templates)
                return "twilio"
        
        # Rule 3: Provider availability check
        if last_provider == "baileys":
            baileys = BaileysProvider()
            if baileys._check_health():
                return "baileys"
            else:
                logger.info("Baileys down, failing over to Twilio")
                return "twilio"
        
        # Rule 4: Default preference within 24h window
        baileys = BaileysProvider()
        if baileys._check_health():
            return "baileys"
        else:
            return "twilio"
            
    except Exception as e:
        logger.error(f"Smart provider resolution failed: {e}")
        return "twilio"  # Safe fallback

class WhatsAppService:
    """⚡ OPTIMIZED Unified WhatsApp service interface (MULTI-TENANT)"""
    
    def __init__(self, provider: Provider, tenant_id: str = None):
        self.provider = provider
        self.tenant_id = tenant_id  # MULTI-TENANT: Store tenant context
    
    def send_typing(self, jid: str, is_typing: bool = True, tenant_id: str = None) -> Dict[str, Any]:
        """⚡ Send typing indicator - creates instant UX feel (MULTI-TENANT)"""
        effective_tenant = tenant_id or self.tenant_id or "business_1"
        if hasattr(self.provider, 'send_typing'):
            return self.provider.send_typing(jid, is_typing, tenant_id=effective_tenant)
        return {"status": "unsupported"}
        
    def send_message(self, to: str, message: str, tenant_id: str = None) -> Dict[str, Any]:
        """Send text message via provider (MULTI-TENANT)"""
        effective_tenant = tenant_id or self.tenant_id or "business_1"
        return self.provider.send_text(to, message, tenant_id=effective_tenant)
        
    def send_media(self, to: str, media_url: str, caption: str = "", tenant_id: str = None) -> Dict[str, Any]:
        """Send media message via provider (MULTI-TENANT)"""
        effective_tenant = tenant_id or self.tenant_id or "business_1"
        return self.provider.send_media(to, media_url, caption, tenant_id=effective_tenant)
        
    def get_status(self) -> Dict[str, Any]:
        """Get service status with health checks"""
        try:
            provider_name = type(self.provider).__name__.replace("Provider", "").lower()
            
            # Check provider-specific health
            if hasattr(self.provider, '_check_health'):
                health = getattr(self.provider, '_check_health', lambda: True)()
            else:
                health = True  # Assume Twilio is always available
            
            return {
                "provider": provider_name,
                "ready": health,
                "connected": health,
                "configured": True
            }
        except Exception as e:
            return {
                "provider": "unknown",
                "ready": False, 
                "connected": False,
                "configured": False,
                "error": str(e)
            }
    
    def send_with_failover(self, to: str, message: str, thread_data: Dict[str, Any] | None = None, tenant_id: str = None) -> Dict[str, Any]:
        """Send message with automatic failover (MULTI-TENANT)"""
        effective_tenant = tenant_id or self.tenant_id or "business_1"
        
        # Try primary provider
        result = self.send_message(to, message, tenant_id=effective_tenant)
        
        if result.get("status") == "error":
            # Get alternative provider
            current_provider = type(self.provider).__name__.replace("Provider", "").lower()
            alternative = "twilio" if current_provider == "baileys" else "baileys"
            
            try:
                logger.info(f"Failing over from {current_provider} to {alternative}")
                alt_service = get_whatsapp_service(alternative, tenant_id=effective_tenant)
                result = alt_service.send_message(to, message, tenant_id=effective_tenant)
                result["failover"] = True
                result["original_provider"] = current_provider
            except Exception as e:
                logger.error(f"Failover to {alternative} also failed: {e}")
                result["failover_error"] = str(e)
        
        return result

def get_provider_status() -> Dict[str, Any]:
    """Get comprehensive status of all providers"""
    status = {
        "primary_provider": os.getenv("WHATSAPP_PROVIDER", "auto"),
        "providers": {}
    }
    
    # Check Twilio
    try:
        twilio_provider = TwilioProvider()
        status["providers"]["twilio"] = {
            "configured": True,
            "ready": True,
            "connected": True
        }
    except Exception as e:
        status["providers"]["twilio"] = {
            "configured": False,
            "ready": False,
            "connected": False,
            "error": str(e)
        }
    
    # Check Baileys
    try:
        baileys_provider = BaileysProvider()
        health = baileys_provider._check_health()
        status["providers"]["baileys"] = {
            "configured": True,
            "ready": health,
            "connected": health,
            "url": baileys_provider.outbound_url
        }
    except Exception as e:
        status["providers"]["baileys"] = {
            "configured": False,
            "ready": False,
            "connected": False,
            "error": str(e)
        }
    
    return status