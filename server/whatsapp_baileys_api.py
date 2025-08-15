# server/whatsapp_baileys_api.py
"""
Real WhatsApp integration with Baileys client
"""
import logging, os, json, subprocess, time
from pathlib import Path

log = logging.getLogger(__name__)

class BaileysWhatsAppClient:
    def __init__(self):
        self.auth_folder = Path("./baileys_auth_info")
        self.status_file = self.auth_folder / "status.json"
        self.qr_file = self.auth_folder / "qr_code.txt"
        
    def get_connection_status(self):
        """Get current WhatsApp connection status"""
        try:
            if self.status_file.exists():
                with open(self.status_file, 'r') as f:
                    status = json.load(f)
                    return {
                        "connected": status.get("connected", False),
                        "timestamp": status.get("timestamp"),
                        "phone_number": status.get("phone_number")
                    }
            return {"connected": False}
        except Exception as e:
            log.error(f"Error reading status: {e}")
            return {"connected": False}
    
    def get_qr_code(self):
        """Get QR code for connection"""
        try:
            if self.qr_file.exists():
                with open(self.qr_file, 'r') as f:
                    qr_data = f.read().strip()
                    if qr_data:
                        return {"available": True, "qr_code": qr_data}
            return {"available": False}
        except Exception as e:
            log.error(f"Error reading QR: {e}")
            return {"available": False}
    
    def send_message(self, to_number: str, message: str, customer_id=None):
        """Send WhatsApp message via Baileys"""
        try:
            status = self.get_connection_status()
            if not status.get("connected"):
                return {"success": False, "error": "WhatsApp not connected"}
            
            # Create message file for baileys to process
            msg_data = {
                "to": to_number,
                "message": message,
                "timestamp": time.time(),
                "customer_id": customer_id
            }
            
            # Write message to queue file
            queue_file = self.auth_folder / "message_queue.json"
            if queue_file.exists():
                with open(queue_file, 'r') as f:
                    queue = json.load(f)
            else:
                queue = []
            
            queue.append(msg_data)
            
            with open(queue_file, 'w') as f:
                json.dump(queue, f)
            
            log.info(f"Queued WhatsApp message to {to_number}")
            return {"success": True, "message_id": f"wa_{int(time.time())}"}
            
        except Exception as e:
            log.error(f"Error sending WhatsApp message: {e}")
            return {"success": False, "error": str(e)}
    
    def restart_client(self):
        """Restart Baileys client"""
        try:
            # Remove status file to force reconnection
            if self.status_file.exists():
                self.status_file.unlink()
            
            log.info("Baileys client restart requested")
            return {"success": True}
        except Exception as e:
            log.error(f"Error restarting client: {e}")
            return {"success": False, "error": str(e)}

# Global instance
whatsapp_client = BaileysWhatsAppClient()