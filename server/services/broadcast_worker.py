"""
WhatsApp Broadcast Worker - Processes broadcast campaigns
Handles throttling, retries, and status tracking
"""
import os
import time
import logging
from datetime import datetime
from server.db import db
from server.models_sql import WhatsAppBroadcast, WhatsAppBroadcastRecipient, Business
from server.app_factory import get_process_app

log = logging.getLogger(__name__)


class BroadcastWorker:
    """Process WhatsApp broadcast campaigns with throttling and retries"""
    
    def __init__(self, broadcast_id: int):
        self.broadcast_id = broadcast_id
        self.broadcast = None
        self.rate_limit = float(os.getenv('BROADCAST_RATE_LIMIT', '2.0'))  # msgs per second
        self.max_retries = int(os.getenv('BROADCAST_MAX_RETRIES', '3'))
        
    def process_campaign(self):
        """Main entry point - process entire campaign"""
        app = get_process_app()
        
        with app.app_context():
            # Load broadcast
            self.broadcast = WhatsAppBroadcast.query.get(self.broadcast_id)
            if not self.broadcast:
                log.error(f"Broadcast {self.broadcast_id} not found")
                return False
            
            # Mark as running
            self.broadcast.status = 'running'
            self.broadcast.started_at = datetime.utcnow()
            db.session.commit()
            
            log.info(f"🚀 Starting broadcast {self.broadcast_id}: {self.broadcast.total_recipients} recipients")
            
            # Get recipients
            recipients = WhatsAppBroadcastRecipient.query.filter_by(
                broadcast_id=self.broadcast_id,
                status='queued'
            ).all()
            
            # Process each recipient
            for recipient in recipients:
                self._process_recipient(recipient)
                
                # Throttle
                time.sleep(1.0 / self.rate_limit)
            
            # Update campaign status
            self._finalize_campaign()
            
            return True
    
    def _process_recipient(self, recipient: WhatsAppBroadcastRecipient):
        """Send message to a single recipient"""
        from server.whatsapp_provider import get_whatsapp_service
        
        tenant_id = f"business_{self.broadcast.business_id}"
        
        try:
            # Get WhatsApp service
            wa_service = get_whatsapp_service(tenant_id=tenant_id)
            
            # Prepare message
            if self.broadcast.message_type == 'template':
                # Template-based (Meta)
                # TODO: Implement template sending with variables
                log.warning(f"Template sending not yet implemented for recipient {recipient.id}")
                recipient.status = 'failed'
                recipient.error_message = 'Template sending not implemented'
            else:
                # Free text (Baileys)
                text = self.broadcast.message_text
                formatted_number = f"{recipient.phone}@s.whatsapp.net"
                
                # Send with retries
                for attempt in range(self.max_retries):
                    try:
                        result = wa_service.send_message(formatted_number, text, tenant_id=tenant_id)
                        
                        if result and result.get('status') == 'sent':
                            recipient.status = 'sent'
                            recipient.message_id = result.get('sid')
                            recipient.sent_at = datetime.utcnow()
                            
                            # Update counters
                            self.broadcast.sent_count += 1
                            
                            log.info(f"✅ Sent to {recipient.phone}")
                            break
                        else:
                            error = result.get('error', 'unknown') if result else 'no_result'
                            if attempt == self.max_retries - 1:
                                recipient.status = 'failed'
                                recipient.error_message = f"Failed after {self.max_retries} attempts: {error}"
                                self.broadcast.failed_count += 1
                                log.error(f"❌ Failed {recipient.phone}: {error}")
                            else:
                                time.sleep(2 ** attempt)  # Exponential backoff
                    
                    except Exception as e:
                        if attempt == self.max_retries - 1:
                            recipient.status = 'failed'
                            recipient.error_message = str(e)[:500]
                            self.broadcast.failed_count += 1
                            log.error(f"❌ Exception {recipient.phone}: {e}")
                        else:
                            time.sleep(2 ** attempt)
            
            db.session.commit()
            
        except Exception as e:
            log.error(f"Fatal error processing recipient {recipient.id}: {e}")
            recipient.status = 'failed'
            recipient.error_message = str(e)[:500]
            self.broadcast.failed_count += 1
            db.session.commit()
    
    def _finalize_campaign(self):
        """Update campaign final status"""
        remaining = WhatsAppBroadcastRecipient.query.filter_by(
            broadcast_id=self.broadcast_id,
            status='queued'
        ).count()
        
        if remaining == 0:
            if self.broadcast.failed_count == 0:
                self.broadcast.status = 'completed'
            elif self.broadcast.sent_count > 0:
                self.broadcast.status = 'partial'
            else:
                self.broadcast.status = 'failed'
        else:
            self.broadcast.status = 'paused'
        
        self.broadcast.completed_at = datetime.utcnow()
        db.session.commit()
        
        log.info(f"🏁 Broadcast {self.broadcast_id} finished: {self.broadcast.sent_count} sent, {self.broadcast.failed_count} failed")


def process_broadcast(broadcast_id: int):
    """Convenience function to process a broadcast"""
    worker = BroadcastWorker(broadcast_id)
    return worker.process_campaign()


if __name__ == '__main__':
    # For testing: python -m server.services.broadcast_worker 123
    import sys
    if len(sys.argv) > 1:
        broadcast_id = int(sys.argv[1])
        process_broadcast(broadcast_id)
