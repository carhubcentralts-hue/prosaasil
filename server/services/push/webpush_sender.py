"""
WebPush Sender - Send push notifications via Web Push protocol
Uses VAPID for authentication with push services

Environment variables required:
- VAPID_PUBLIC_KEY: Base64-encoded public key
- VAPID_PRIVATE_KEY: Base64-encoded private key  
- VAPID_SUBJECT: Contact email or URL (e.g., mailto:admin@example.com)
"""
import os
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

log = logging.getLogger(__name__)

# Try to import pywebpush
try:
    from pywebpush import webpush, WebPushException
    WEBPUSH_AVAILABLE = True
except ImportError:
    WEBPUSH_AVAILABLE = False
    log.warning("pywebpush not installed - push notifications will not work")


@dataclass
class PushPayload:
    """Standard push notification payload"""
    title: str
    body: str
    url: Optional[str] = None  # Deep link URL
    tag: Optional[str] = None  # For deduplication
    notification_type: Optional[str] = None  # appointment_reminder, whatsapp_disconnect, etc.
    entity_id: Optional[str] = None  # Related entity ID
    business_id: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization"""
        return {
            "title": self.title,
            "body": self.body,
            "url": self.url,
            "tag": self.tag,
            "type": self.notification_type,
            "entity_id": self.entity_id,
            "business_id": self.business_id
        }


class WebPushSender:
    """
    Send push notifications using Web Push protocol with VAPID
    
    Usage:
        sender = WebPushSender()
        result = sender.send(subscription_info, payload)
    """
    
    def __init__(self):
        self.vapid_public_key = os.getenv("VAPID_PUBLIC_KEY")
        self.vapid_private_key = os.getenv("VAPID_PRIVATE_KEY")
        self.vapid_subject = os.getenv("VAPID_SUBJECT", "mailto:admin@prosaas.app")
        
        self._validate_config()
    
    def _validate_config(self) -> None:
        """Validate VAPID configuration"""
        if not WEBPUSH_AVAILABLE:
            log.warning("WebPush: pywebpush not available")
            return
            
        if not self.vapid_public_key:
            log.warning("WebPush: VAPID_PUBLIC_KEY not configured")
        if not self.vapid_private_key:
            log.warning("WebPush: VAPID_PRIVATE_KEY not configured")
    
    @property
    def is_configured(self) -> bool:
        """Check if WebPush is properly configured"""
        return (
            WEBPUSH_AVAILABLE and 
            bool(self.vapid_public_key) and 
            bool(self.vapid_private_key)
        )
    
    def get_public_key(self) -> Optional[str]:
        """Get the VAPID public key for client subscription"""
        return self.vapid_public_key
    
    def send(
        self,
        subscription_info: Dict[str, Any],
        payload: PushPayload,
        ttl: int = 86400  # 24 hours
    ) -> Dict[str, Any]:
        """
        Send a push notification to a subscription
        
        Args:
            subscription_info: Dict with endpoint, keys.p256dh, keys.auth
            payload: PushPayload with notification content
            ttl: Time to live in seconds
            
        Returns:
            Dict with success status and any error info
        """
        if not self.is_configured:
            return {
                "success": False,
                "error": "WebPush not configured",
                "should_deactivate": False
            }
        
        try:
            import json
            
            # Build subscription info dict
            sub_info = {
                "endpoint": subscription_info.get("endpoint"),
                "keys": {
                    "p256dh": subscription_info.get("p256dh") or subscription_info.get("keys", {}).get("p256dh"),
                    "auth": subscription_info.get("auth") or subscription_info.get("keys", {}).get("auth")
                }
            }
            
            # Build VAPID claims
            vapid_claims = {
                "sub": self.vapid_subject
            }
            
            # Send the notification
            response = webpush(
                subscription_info=sub_info,
                data=json.dumps(payload.to_dict()),
                vapid_private_key=self.vapid_private_key,
                vapid_claims=vapid_claims,
                ttl=ttl
            )
            
            log.info(f"WebPush sent successfully to {sub_info['endpoint'][:50]}...")
            return {
                "success": True,
                "status_code": response.status_code if hasattr(response, 'status_code') else 201,
                "should_deactivate": False
            }
            
        except WebPushException as e:
            error_code = e.response.status_code if e.response else None
            error_message = str(e)
            
            # Check if subscription is invalid (410 Gone, 404 Not Found)
            should_deactivate = error_code in (404, 410)
            
            if should_deactivate:
                log.warning(f"WebPush subscription invalid (HTTP {error_code}), marking for deactivation")
            else:
                log.error(f"WebPush failed: {error_message}")
            
            return {
                "success": False,
                "error": error_message,
                "status_code": error_code,
                "should_deactivate": should_deactivate
            }
            
        except Exception as e:
            log.error(f"WebPush unexpected error: {e}")
            return {
                "success": False,
                "error": str(e),
                "should_deactivate": False
            }


# Singleton instance
_sender_instance: Optional[WebPushSender] = None


def get_webpush_sender() -> WebPushSender:
    """Get the WebPush sender singleton"""
    global _sender_instance
    if _sender_instance is None:
        _sender_instance = WebPushSender()
    return _sender_instance
