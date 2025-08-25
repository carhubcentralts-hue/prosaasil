"""
WhatsApp Provider Layer - Unified Baileys and Twilio Support
שכבת ספקי WhatsApp - תמיכה מאוחדת ב-Baileys ו-Twilio
"""
import os
import json
import time
import pathlib
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Global service instance
_whatsapp_service = None

class Provider:
    """Abstract WhatsApp provider interface"""
    def send_text(self, to: str, text: str) -> Dict[str, Any]:
        raise NotImplementedError
        
    def send_media(self, to: str, media_url: str, caption: str = "") -> Dict[str, Any]:
        raise NotImplementedError

class BaileysProvider(Provider):
    """Baileys WebSocket client provider"""
    
    def __init__(self, base_dir: str = "baileys_auth_info"):
        self.base_path = pathlib.Path(base_dir)
        self.queue_file = self.base_path / "message_queue.json"
        self.status_file = self.base_path / "status.json"
        
        # Ensure directories exist
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize queue file
        if not self.queue_file.exists():
            self.queue_file.write_text("[]", encoding="utf-8")
            
        # Initialize status file
        if not self.status_file.exists():
            self.status_file.write_text('{"connected": false}', encoding="utf-8")

    def send_text(self, to: str, text: str) -> Dict[str, Any]:
        """Queue text message for Baileys client"""
        try:
            # Load existing queue
            queue_data = json.loads(self.queue_file.read_text("utf-8"))
            
            # Add new message
            message = {
                "to": to,
                "message": text,
                "type": "text",
                "timestamp": int(time.time())
            }
            queue_data.append(message)
            
            # Save updated queue
            self.queue_file.write_text(
                json.dumps(queue_data, ensure_ascii=False, indent=2), 
                encoding="utf-8"
            )
            
            logger.info(f"Message queued for Baileys: {to}")
            return {
                "provider": "baileys",
                "status": "queued",
                "timestamp": message["timestamp"]
            }
            
        except Exception as e:
            logger.error(f"Failed to queue message for Baileys: {e}")
            return {
                "provider": "baileys", 
                "status": "error",
                "error": str(e)
            }
    
    def send_media(self, to: str, media_url: str, caption: str = "") -> Dict[str, Any]:
        """Queue media message for Baileys client"""
        try:
            # Load existing queue
            queue_data = json.loads(self.queue_file.read_text("utf-8"))
            
            # Add new media message
            message = {
                "to": to,
                "media_url": media_url,
                "caption": caption,
                "type": "media",
                "timestamp": int(time.time())
            }
            queue_data.append(message)
            
            # Save updated queue
            self.queue_file.write_text(
                json.dumps(queue_data, ensure_ascii=False, indent=2), 
                encoding="utf-8"
            )
            
            logger.info(f"Media message queued for Baileys: {to}")
            return {
                "provider": "baileys",
                "status": "queued",
                "timestamp": message["timestamp"]
            }
            
        except Exception as e:
            logger.error(f"Failed to queue media message for Baileys: {e}")
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
        raw_from_number = os.environ.get('TWILIO_WHATSAPP_NUMBER', '')
        
        # Ensure from_number has whatsapp: prefix (avoid double prefix)
        if raw_from_number and not raw_from_number.startswith('whatsapp:'):
            self.from_number = f'whatsapp:{raw_from_number}'
        else:
            self.from_number = raw_from_number
        
        if not all([self.account_sid, self.auth_token, self.from_number]):
            raise RuntimeError(
                "Missing Twilio WhatsApp ENV variables: "
                "TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_NUMBER"
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

    def send_text(self, to: str, text: str) -> Dict[str, Any]:
        """Send text message via Twilio WhatsApp API"""
        try:
            # Add status callback URL if PUBLIC_HOST is available
            public_host = os.environ.get('PUBLIC_HOST', '').rstrip('/')
            status_callback = f"{public_host}/webhook/whatsapp/status" if public_host else None
            
            message_params = {
                'body': text,
                'from_': self.from_number,
                'to': self._format_number(to)
            }
            
            if status_callback:
                message_params['status_callback'] = status_callback
                
            message = self.client.messages.create(**message_params)
            
            logger.info(f"Text message sent via Twilio: {message.sid}")
            return {
                "provider": "twilio",
                "status": message.status,
                "sid": message.sid,
                "price": message.price
            }
            
        except Exception as e:
            logger.error(f"Failed to send message via Twilio: {e}")
            return {
                "provider": "twilio",
                "status": "error", 
                "error": str(e)
            }
    
    def send_media(self, to: str, media_url: str, caption: str = "") -> Dict[str, Any]:
        """Send media message via Twilio WhatsApp API"""
        try:
            message = self.client.messages.create(
                body=caption,
                media_url=media_url,
                from_=self.from_number,
                to=self._format_number(to)
            )
            
            logger.info(f"Media message sent via Twilio: {message.sid}")
            return {
                "provider": "twilio",
                "status": message.status,
                "sid": message.sid,
                "price": message.price
            }
            
        except Exception as e:
            logger.error(f"Failed to send media message via Twilio: {e}")
            return {
                "provider": "twilio",
                "status": "error",
                "error": str(e)
            }

def get_provider() -> Provider:
    """
    Factory function to get the configured WhatsApp provider
    פונקציית מפעל להחזרת ספק WhatsApp מוגדר
    """
    provider_name = os.getenv("WHATSAPP_PROVIDER", "baileys").lower()
    
    if provider_name == "twilio":
        logger.info("Using Twilio WhatsApp provider")
        return TwilioProvider()
    else:
        logger.info("Using Baileys WhatsApp provider")
        return BaileysProvider()

def get_whatsapp_service(provider: str | None = None):
    """Get WhatsApp service instance - unified interface"""
    global _whatsapp_service
    
    # per-request override
    if provider:
        p = provider.lower()
        if p == "twilio":
            return WhatsAppService(TwilioProvider())
        if p == "baileys":
            return WhatsAppService(BaileysProvider())
    
    if _whatsapp_service is None:
        provider_type = os.getenv("WHATSAPP_PROVIDER", "baileys").lower()
        
        if provider_type == "baileys":
            _whatsapp_service = WhatsAppService(BaileysProvider())
        elif provider_type == "twilio":
            _whatsapp_service = WhatsAppService(TwilioProvider())
        else:
            logger.warning(f"Unknown provider: {provider_type}, defaulting to baileys")
            _whatsapp_service = WhatsAppService(BaileysProvider())
    
    return _whatsapp_service

class WhatsAppService:
    """Unified WhatsApp service interface"""
    
    def __init__(self, provider: Provider):
        self.provider = provider
        
    def send_message(self, to: str, message: str) -> Dict[str, Any]:
        """Send text message via provider"""
        return self.provider.send_text(to, message)
        
    def send_media(self, to: str, media_url: str, caption: str = "") -> Dict[str, Any]:
        """Send media message via provider"""
        return self.provider.send_media(to, media_url, caption)
        
    def get_status(self) -> Dict[str, Any]:
        """Get service status"""
        try:
            provider_name = type(self.provider).__name__.replace("Provider", "").lower()
            return {
                "provider": provider_name,
                "ready": True,
                "connected": True,
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

def get_provider_status() -> Dict[str, Any]:
    """Get status of the current provider"""
    provider_name = os.getenv("WHATSAPP_PROVIDER", "baileys").lower()
    
    if provider_name == "twilio":
        # Check Twilio credentials
        required_vars = ['TWILIO_ACCOUNT_SID', 'TWILIO_AUTH_TOKEN', 'TWILIO_WHATSAPP_NUMBER']
        missing = [var for var in required_vars if not os.getenv(var)]
        
        return {
            "provider": "twilio",
            "configured": len(missing) == 0,
            "missing_vars": missing,
            "ready": len(missing) == 0
        }
    else:
        # Check Baileys status
        status_file = pathlib.Path("baileys_auth_info/status.json")
        if status_file.exists():
            try:
                status = json.loads(status_file.read_text())
                return {
                    "provider": "baileys",
                    "configured": True,
                    "connected": status.get("connected", False),
                    "ready": status.get("connected", False)
                }
            except:
                pass
        
        return {
            "provider": "baileys",
            "configured": False,
            "connected": False,
            "ready": False
        }