"""
Unified WhatsApp Service - Production Ready
שירות WhatsApp מאוחד - מוכן לפרודקשן
Uses environment variables and provider abstraction
"""
import os
import logging
from server.whatsapp_provider import get_provider, get_provider_status

logger = logging.getLogger(__name__)

class WhatsAppServiceUnified:
    """
    Unified WhatsApp service using provider abstraction
    שירות WhatsApp מאוחד עם שכבת הפשטה לספקים
    """
    
    def __init__(self):
        """Initialize with current provider"""
        self.provider = get_provider()
        self.provider_name = os.getenv("WHATSAPP_PROVIDER", "baileys").lower()
        logger.info(f"WhatsApp service initialized with {self.provider_name} provider")
    
    def send_message(self, to_number: str, message: str) -> dict:
        """
        Send text message using current provider
        שליחת הודעת טקסט באמצעות הספק הנוכחי
        """
        try:
            # Clean phone number format
            clean_number = to_number.replace("whatsapp:", "").strip()
            
            # Send via provider
            result = self.provider.send_text(clean_number, message)
            
            logger.info(f"Message sent to {clean_number[:5]}*** via {self.provider_name}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to send WhatsApp message: {e}")
            return {
                "provider": self.provider_name,
                "status": "error",
                "error": str(e)
            }
    
    def send_media(self, to_number: str, media_url: str, caption: str = "") -> dict:
        """
        Send media message using current provider
        שליחת הודעת מדיה באמצעות הספק הנוכחי
        """
        try:
            # Clean phone number format
            clean_number = to_number.replace("whatsapp:", "").strip()
            
            # Send via provider
            result = self.provider.send_media(clean_number, media_url, caption)
            
            logger.info(f"Media sent to {clean_number[:5]}*** via {self.provider_name}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to send WhatsApp media: {e}")
            return {
                "provider": self.provider_name,
                "status": "error",
                "error": str(e)
            }
    
    def get_status(self) -> dict:
        """Get current provider status"""
        return get_provider_status()
    
    def is_ready(self) -> bool:
        """Check if service is ready to send messages"""
        status = self.get_status()
        return status.get("ready", False)

# Global service instance
_service = None

def get_whatsapp_service() -> WhatsAppServiceUnified:
    """Get singleton WhatsApp service instance"""
    global _service
    if _service is None:
        _service = WhatsAppServiceUnified()
    return _service