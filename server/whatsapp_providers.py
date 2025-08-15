"""
Unified WhatsApp Provider System
Supports both Baileys and Twilio providers with ENV-based switching
"""
import os
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional

class WhatsAppProvider:
    """Base class for WhatsApp providers"""
    def send_text(self, to: str, text: str) -> dict:
        raise NotImplementedError
    
    def send_media(self, to: str, media_url: str, caption: str = "") -> dict:
        raise NotImplementedError
    
    def send_template(self, to: str, template: str, lang: str = "he", variables=None) -> dict:
        raise NotImplementedError

class BaileysProvider(WhatsAppProvider):
    """Baileys provider using file-based message queue"""
    
    def __init__(self, base_dir="baileys_auth_info"):
        self.queue = Path(base_dir) / "message_queue.json"
        self.queue.parent.mkdir(parents=True, exist_ok=True)
        if not self.queue.exists():
            self.queue.write_text("[]", encoding="utf-8")
    
    def _enqueue(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Add message to queue for Baileys client to process"""
        try:
            data = json.loads(self.queue.read_text("utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            data = []
        
        data.append({**payload, "ts": int(time.time())})
        self.queue.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"provider": "baileys", "status": "queued"}
    
    def send_text(self, to: str, text: str) -> dict:
        return self._enqueue({"to": to, "message": text, "type": "text"})
    
    def send_media(self, to: str, media_url: str, caption: str = "") -> dict:
        return self._enqueue({
            "to": to, 
            "media_url": media_url, 
            "caption": caption, 
            "type": "media"
        })
    
    def send_template(self, to: str, template: str, lang: str = "he", variables=None) -> dict:
        # Baileys doesn't manage official templates - use as composed text
        text = template if not variables else template.format(*variables)
        return self._enqueue({"to": to, "message": text, "type": "text"})

class TwilioProvider(WhatsAppProvider):
    """Twilio provider for WhatsApp Business API"""
    
    def __init__(self):
        try:
            from twilio.rest import Client
            self.client = Client(
                os.getenv("TWILIO_ACCOUNT_SID"), 
                os.getenv("TWILIO_AUTH_TOKEN")
            )
            self.from_num = os.getenv("TWILIO_WA_FROM")
            if not self.from_num:
                raise ValueError("TWILIO_WA_FROM environment variable required")
        except ImportError:
            raise ImportError("Twilio package required for TwilioProvider")
    
    def _to_whatsapp(self, to: str) -> str:
        """Ensure number has whatsapp: prefix"""
        return f"whatsapp:{to}" if not str(to).startswith("whatsapp:") else to
    
    def send_text(self, to: str, text: str) -> dict:
        try:
            msg = self.client.messages.create(
                from_=self.from_num,
                to=self._to_whatsapp(to),
                body=text
            )
            return {"provider": "twilio", "status": msg.status, "sid": msg.sid}
        except Exception as e:
            return {"provider": "twilio", "status": "failed", "error": str(e)}
    
    def send_media(self, to: str, media_url: str, caption: str = "") -> dict:
        try:
            msg = self.client.messages.create(
                from_=self.from_num,
                to=self._to_whatsapp(to),
                body=caption or None,
                media_url=[media_url]
            )
            return {"provider": "twilio", "status": msg.status, "sid": msg.sid}
        except Exception as e:
            return {"provider": "twilio", "status": "failed", "error": str(e)}
    
    def send_template(self, to: str, template: str, lang: str = "he", variables=None) -> dict:
        # For Twilio/WhatsApp: official templates only for initiated conversations
        # Here we do basic substitution
        try:
            body = template if not variables else template.format(*variables)
            msg = self.client.messages.create(
                from_=self.from_num,
                to=self._to_whatsapp(to),
                body=body
            )
            return {"provider": "twilio", "status": msg.status, "sid": msg.sid}
        except Exception as e:
            return {"provider": "twilio", "status": "failed", "error": str(e)}

def get_provider() -> WhatsAppProvider:
    """Get WhatsApp provider based on environment configuration"""
    provider_type = os.getenv("WHATSAPP_PROVIDER", "baileys").lower()
    
    if provider_type == "twilio":
        return TwilioProvider()
    else:
        return BaileysProvider()