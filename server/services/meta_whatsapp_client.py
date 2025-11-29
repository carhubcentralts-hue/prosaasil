"""
Meta WhatsApp Cloud API Client
ספק WhatsApp Cloud API רשמי של Meta

This module handles all communication with Meta's WhatsApp Business Cloud API.
"""
import os
import logging
import requests
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class MetaWhatsAppClient:
    """Meta WhatsApp Cloud API client for sending messages"""
    
    def __init__(self, business_id: Optional[int] = None):
        self.business_id = business_id
        self.access_token = os.getenv("META_WA_ACCESS_TOKEN")
        self.phone_number_id = os.getenv("META_WA_PHONE_NUMBER_ID")
        self.waba_id = os.getenv("META_WA_WABA_ID")
        self.api_version = os.getenv("META_WA_API_VERSION", "v21.0")
        self.timeout = 15.0
        
        self._session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=0
        )
        self._session.mount('https://', adapter)
    
    def is_configured(self) -> bool:
        """Check if Meta WhatsApp Cloud API is properly configured"""
        return bool(self.access_token and self.phone_number_id)
    
    def _get_headers(self) -> Dict[str, str]:
        """Get authorization headers for API requests"""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
    
    def _get_messages_url(self) -> str:
        """Get the messages endpoint URL"""
        return f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}/messages"
    
    def send_text(self, to: str, text: str, tenant_id: str = None) -> Dict[str, Any]:
        """Send a text message via Meta WhatsApp Cloud API
        
        Args:
            to: Recipient phone number (E.164 format without +)
            text: Message text to send
            tenant_id: Optional tenant ID for logging (not used in Meta API)
        
        Returns:
            Dict with status, message_id on success or error details
        """
        if not self.is_configured():
            logger.error("[META-WA] Not configured - missing access_token or phone_number_id")
            return {
                "provider": "meta",
                "status": "error",
                "error": "Meta WhatsApp Cloud API is not fully configured"
            }
        
        to_clean = to.replace("whatsapp:", "").replace("+", "").strip()
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_clean,
            "type": "text",
            "text": {"body": text}
        }
        
        try:
            logger.info(f"[META-WA] Sending message to {to_clean[:8]}...")
            
            response = self._session.post(
                self._get_messages_url(),
                json=payload,
                headers=self._get_headers(),
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                message_id = result.get("messages", [{}])[0].get("id", "")
                logger.info(f"[META-WA] Message sent successfully: {message_id[:20]}...")
                return {
                    "provider": "meta",
                    "status": "sent",
                    "message_id": message_id,
                    "sid": message_id
                }
            else:
                error_data = response.json() if response.text else {}
                error_msg = error_data.get("error", {}).get("message", f"HTTP {response.status_code}")
                logger.error(f"[META-WA] Send failed: {response.status_code} - {error_msg}")
                return {
                    "provider": "meta",
                    "status": "error",
                    "error": error_msg,
                    "http_status": response.status_code
                }
                
        except requests.exceptions.Timeout:
            logger.error("[META-WA] Request timed out")
            return {
                "provider": "meta",
                "status": "error",
                "error": "Request timed out"
            }
        except Exception as e:
            logger.error(f"[META-WA] Exception: {e}")
            return {
                "provider": "meta",
                "status": "error",
                "error": str(e)
            }
    
    def send_media(self, to: str, media_url: str, caption: str = "", tenant_id: str = None) -> Dict[str, Any]:
        """Send a media message via Meta WhatsApp Cloud API
        
        Args:
            to: Recipient phone number
            media_url: URL of the media to send
            caption: Optional caption for the media
            tenant_id: Optional tenant ID for logging
        
        Returns:
            Dict with status and message_id
        """
        if not self.is_configured():
            return {
                "provider": "meta",
                "status": "error",
                "error": "Meta WhatsApp Cloud API is not fully configured"
            }
        
        to_clean = to.replace("whatsapp:", "").replace("+", "").strip()
        
        media_type = "image"
        if any(ext in media_url.lower() for ext in ['.pdf', '.doc', '.docx', '.xls', '.xlsx']):
            media_type = "document"
        elif any(ext in media_url.lower() for ext in ['.mp4', '.mov', '.avi']):
            media_type = "video"
        elif any(ext in media_url.lower() for ext in ['.mp3', '.wav', '.ogg']):
            media_type = "audio"
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_clean,
            "type": media_type,
            media_type: {
                "link": media_url,
            }
        }
        
        if caption and media_type in ["image", "document", "video"]:
            payload[media_type]["caption"] = caption
        
        try:
            logger.info(f"[META-WA] Sending {media_type} to {to_clean[:8]}...")
            
            response = self._session.post(
                self._get_messages_url(),
                json=payload,
                headers=self._get_headers(),
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                message_id = result.get("messages", [{}])[0].get("id", "")
                logger.info(f"[META-WA] Media sent successfully: {message_id[:20]}...")
                return {
                    "provider": "meta",
                    "status": "sent",
                    "message_id": message_id,
                    "sid": message_id
                }
            else:
                error_data = response.json() if response.text else {}
                error_msg = error_data.get("error", {}).get("message", f"HTTP {response.status_code}")
                logger.error(f"[META-WA] Media send failed: {response.status_code} - {error_msg}")
                return {
                    "provider": "meta",
                    "status": "error",
                    "error": error_msg
                }
                
        except Exception as e:
            logger.error(f"[META-WA] Media exception: {e}")
            return {
                "provider": "meta",
                "status": "error",
                "error": str(e)
            }
    
    def send_template(self, to: str, template_name: str, language_code: str = "he", 
                      components: list = None, tenant_id: str = None) -> Dict[str, Any]:
        """Send a template message via Meta WhatsApp Cloud API
        
        Template messages can be sent outside the 24-hour window.
        
        Args:
            to: Recipient phone number
            template_name: Name of the pre-approved template
            language_code: Language code (default: "he" for Hebrew)
            components: Template components (header, body, buttons)
            tenant_id: Optional tenant ID for logging
        
        Returns:
            Dict with status and message_id
        """
        if not self.is_configured():
            return {
                "provider": "meta",
                "status": "error",
                "error": "Meta WhatsApp Cloud API is not fully configured"
            }
        
        to_clean = to.replace("whatsapp:", "").replace("+", "").strip()
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_clean,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code}
            }
        }
        
        if components:
            payload["template"]["components"] = components
        
        try:
            logger.info(f"[META-WA] Sending template '{template_name}' to {to_clean[:8]}...")
            
            response = self._session.post(
                self._get_messages_url(),
                json=payload,
                headers=self._get_headers(),
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                message_id = result.get("messages", [{}])[0].get("id", "")
                logger.info(f"[META-WA] Template sent successfully: {message_id[:20]}...")
                return {
                    "provider": "meta",
                    "status": "sent",
                    "message_id": message_id,
                    "sid": message_id
                }
            else:
                error_data = response.json() if response.text else {}
                error_msg = error_data.get("error", {}).get("message", f"HTTP {response.status_code}")
                logger.error(f"[META-WA] Template send failed: {error_msg}")
                return {
                    "provider": "meta",
                    "status": "error",
                    "error": error_msg
                }
                
        except Exception as e:
            logger.error(f"[META-WA] Template exception: {e}")
            return {
                "provider": "meta",
                "status": "error",
                "error": str(e)
            }


def send_message_meta(business, to: str, text: str) -> Dict[str, Any]:
    """Convenience function to send a message via Meta WhatsApp Cloud API
    
    This is the unified interface called by whatsapp_gateway.py
    
    Args:
        business: Business object (for logging context)
        to: Recipient phone number
        text: Message text
    
    Returns:
        Dict with send result
    """
    business_id = getattr(business, 'id', None)
    client = MetaWhatsAppClient(business_id=business_id)
    return client.send_text(to, text)
