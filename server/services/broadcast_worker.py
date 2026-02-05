"""
WhatsApp Broadcast Worker - Processes broadcast campaigns
✅ FIX: Enhanced with throttling, retries, and comprehensive logging per problem statement
Handles rate limiting (1-3 msgs/sec), exponential backoff, and detailed status tracking
"""
import os
import time
import base64
import logging
import random
from datetime import datetime
from server.db import db
from server.models_sql import WhatsAppBroadcast, WhatsAppBroadcastRecipient, Business, Attachment, WhatsAppMessage
from server.app_factory import get_process_app
from server.services.attachment_service import get_attachment_service
from server.services.whatsapp_send_service import send_message
from server.utils.whatsapp_utils import normalize_whatsapp_to

log = logging.getLogger(__name__)


class BroadcastWorker:
    """Process WhatsApp broadcast campaigns with throttling and retries"""
    
    def __init__(self, broadcast_id: int):
        self.broadcast_id = broadcast_id
        self.broadcast = None
        # 🔥 SAFE MODE: Slow and steady - 3-4 second delay between messages to prevent blocking
        # This ensures WhatsApp won't block the account for sending too fast
        self.rate_limit = float(os.getenv('BROADCAST_RATE_LIMIT', '0.3'))  # msgs per second (1 msg every ~3.3s)
        self.batch_size = 1000  # Effectively disabled - no batch waits
        self.batch_delay = 0.0  # No additional batch delay needed
        self.max_retries = int(os.getenv('BROADCAST_MAX_RETRIES', '3'))
        # 🔥 CRITICAL: 3-4 second delay between messages (prevents WhatsApp blocking)
        self.random_delay_range = (3.0, 4.0)
        self.stop_requested = False
        
    def process_campaign(self):
        """Main entry point - process entire campaign"""
        app = get_process_app()
        
        with app.app_context():
            # Load broadcast
            self.broadcast = WhatsAppBroadcast.query.get(self.broadcast_id)
            if not self.broadcast:
                log.error(f"[WA_BROADCAST] Broadcast {self.broadcast_id} not found")
                return False
            
            # ✅ FIX (Problem 2): Check canSend BEFORE starting broadcast
            # If canSend=False, fail immediately with clear error
            tenant_id = f"business_{self.broadcast.business_id}"
            
            try:
                import requests
                BAILEYS_BASE = os.getenv('BAILEYS_BASE_URL', 'http://127.0.0.1:3300')
                INT_SECRET = os.getenv('INTERNAL_SECRET')
                
                status_response = requests.get(
                    f"{BAILEYS_BASE}/whatsapp/{tenant_id}/status",
                    headers={'X-Internal-Secret': INT_SECRET},
                    timeout=5
                )
                
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    can_send = status_data.get('canSend', False)
                    is_connected = status_data.get('connected', False)
                    is_auth_paired = status_data.get('authPaired', False)
                    
                    # ✅ FIX: Require ALL three conditions for broadcast to proceed
                    if not (is_connected and is_auth_paired and can_send):
                        error_reason = "WA_NOT_READY_CAN_SEND_FALSE" if not can_send else "WA_NOT_CONNECTED"
                        log.error(f"[WA_BROADCAST] broadcast_id={self.broadcast_id} BLOCKED: connected={is_connected} authPaired={is_auth_paired} canSend={can_send}")
                        
                        self.broadcast.status = 'failed'
                        self.broadcast.started_at = datetime.utcnow()
                        self.broadcast.completed_at = datetime.utcnow()
                        db.session.commit()
                        
                        log.error(f"[WA_BROADCAST] broadcast_id={self.broadcast_id} failed reason={error_reason} - needs QR rescan")
                        return False
                else:
                    log.warning(f"[WA_BROADCAST] broadcast_id={self.broadcast_id} Could not verify WhatsApp status (HTTP {status_response.status_code}) - proceeding anyway")
            except Exception as status_check_err:
                log.warning(f"[WA_BROADCAST] broadcast_id={self.broadcast_id} Status check failed: {status_check_err} - proceeding anyway")
            
            # Mark as running
            self.broadcast.status = 'running'
            self.broadcast.started_at = datetime.utcnow()
            db.session.commit()
            
            # ✅ FIX: Log with structured format [WA_BROADCAST]
            log.info(f"[WA_BROADCAST] broadcast_id={self.broadcast_id} total={self.broadcast.total_recipients} provider={self.broadcast.provider} status=started")
            
            # Get recipients
            recipients = WhatsAppBroadcastRecipient.query.filter_by(
                broadcast_id=self.broadcast_id,
                status='queued'
            ).all()
            
            log.info(f"[WA_BROADCAST] broadcast_id={self.broadcast_id} queued_recipients={len(recipients)}")
            
            # ✅ FIX: Smart rate limiting - batch-based (30 msgs every 3 seconds)
            # Process each recipient in batches to avoid blocking
            for idx, recipient in enumerate(recipients, 1):
                # Check if stop was requested
                if self._check_stop_requested():
                    log.info(f"[WA_BROADCAST] broadcast_id={self.broadcast_id} stopped_by_user at {idx}/{len(recipients)}")
                    break
                
                self._process_recipient(recipient, idx, len(recipients))
                
                # 🔥 SAFE MODE: Wait 3-4 seconds between EVERY message to prevent WhatsApp blocking
                # This is the safest approach - slow but will never get blocked
                if idx < len(recipients):  # Don't wait after last message
                    random_jitter = random.uniform(*self.random_delay_range)
                    log.debug(f"[WA_BROADCAST] broadcast_id={self.broadcast_id} message={idx}/{len(recipients)} waiting={random_jitter:.1f}s")
                    time.sleep(random_jitter)
            
            # Update campaign status
            self._finalize_campaign()
            
            return True
    
    def _process_recipient(self, recipient: WhatsAppBroadcastRecipient, idx: int, total: int):
        """🎯 UNIFIED: Send message using unified send service (SSOT)
        
        This method now uses whatsapp_send_service.send_message() which is the
        same path used by regular chat and lead sends. This ensures:
        - Consistent phone normalization
        - Same provider selection logic
        - Same error handling
        - No duplicate retries (retries=0 for broadcast context)
        """
        # ✅ FIX: Structured logging per message
        log.info(f"[WA_SEND] broadcast_id={self.broadcast_id} recipient={idx}/{total} to={recipient.phone} status=sending")
        
        # 🎯 FIX #4: Wrap in try/except to never kill entire job on single failure
        try:
            # Prepare message
            if self.broadcast.message_type == 'template':
                # Template-based (Meta)
                # Template sending with variables - using direct text for now
                log.warning(f"[WA_SEND] Template sending not yet implemented for recipient {recipient.id}")
                recipient.status = 'failed'
                recipient.error_message = 'Template sending not implemented'
                self.broadcast.failed_count += 1
                db.session.commit()
                return
            
            # Free text or media (Baileys or Meta based on business settings)
            text = self.broadcast.message_text
            
            # Check if broadcast has media attachment
            media_bytes = None
            media_type = 'image'  # Default media type
            media_filename = None
            media_mimetype = None
            attachment_id = None
            
            if self.broadcast.audience_filter and isinstance(self.broadcast.audience_filter, dict):
                attachment_id = self.broadcast.audience_filter.get('attachment_id')
            
            # 🔥 FIX: For R2 storage, download bytes instead of relying on signed URLs
            # Baileys can work with URLs, but bytes are more reliable (no URL expiration issues)
            if attachment_id:
                try:
                    attachment = Attachment.query.get(attachment_id)
                    if attachment and attachment.storage_path:
                        attachment_service = get_attachment_service()
                        media_filename, media_mimetype, media_bytes = attachment_service.open_file(
                            storage_key=attachment.storage_path,
                            filename=attachment.filename_original,
                            mime_type=attachment.mime_type
                        )
                        
                        # Determine media type from mime
                        if media_mimetype:
                            if media_mimetype.startswith('image/'):
                                media_type = 'image'
                            elif media_mimetype.startswith('video/'):
                                media_type = 'video'
                            elif media_mimetype.startswith('audio/'):
                                media_type = 'audio'
                            else:
                                media_type = 'document'
                        
                        log.info(f"[WA_SEND] Loaded attachment bytes: {media_filename} ({len(media_bytes)} bytes, {media_type})")
                except Exception as e:
                    log.error(f"[WA_SEND] Failed to load attachment bytes: {e}")
                    # Continue without media
            
            # Prepare media dict if we have media bytes
            media_dict = None
            if media_bytes:
                media_dict = {
                    'data': base64.b64encode(media_bytes).decode('utf-8'),
                    'mimetype': media_mimetype or 'application/octet-stream',
                    'filename': media_filename or 'attachment'
                }
            
            # 🎯 FIX #3: Single retry layer - broadcast_worker handles retries
            # Send with retries=0 to disable provider-level retries
            backoff_delays = [1, 3, 10]  # seconds
            for attempt in range(self.max_retries):
                try:
                    # 🎯 UNIFIED: Use send_message() - same path as regular sends
                    result = send_message(
                        business_id=self.broadcast.business_id,
                        to_phone=recipient.phone,
                        text=text or '',
                        media=media_dict,
                        media_type=media_type if media_dict else None,
                        context='broadcast',
                        retries=0  # 🎯 FIX #3: No provider retries, broadcast_worker handles it
                    )
                    
                    if result and result.get('status') in ['sent', 'queued', 'accepted']:
                        recipient.status = 'sent'
                        recipient.message_id = result.get('sid') or result.get('message_id')
                        recipient.sent_at = datetime.utcnow()
                        
                        # Update counters
                        self.broadcast.sent_count += 1
                        
                        # 🔥 CONTEXT FIX: Save broadcast message to history for LLM context
                        try:
                            # Normalize phone to JID for consistent history lookup
                            normalized_jid, _ = normalize_whatsapp_to(
                                to=recipient.phone,
                                business_id=self.broadcast.business_id
                            )
                            
                            outgoing_msg = WhatsAppMessage(
                                business_id=self.broadcast.business_id,
                                to_number=normalized_jid,  # Store full JID for history matching
                                body=text or '',
                                direction='outbound',
                                provider=self.broadcast.provider or 'baileys',
                                status='sent',
                                message_type=media_type if media_dict else 'text',
                                source='automation',  # Mark as automation (broadcast campaign)
                                provider_message_id=result.get('sid') or result.get('message_id')
                            )
                            db.session.add(outgoing_msg)
                            log.info(f"✅ [WA_SEND] broadcast_id={self.broadcast_id} to={recipient.phone} saved_to_history (source=automation)")
                        except Exception as db_err:
                            log.warning(f"⚠️ [WA_SEND] broadcast_id={self.broadcast_id} to={recipient.phone} failed_to_save_history: {db_err}")
                        
                        log.info(f"✅ [WA_SEND] broadcast_id={self.broadcast_id} to={recipient.phone} status=sent")
                        break
                    else:
                        error = result.get('error', 'unknown') if result else 'no_result'
                        if attempt == self.max_retries - 1:
                            recipient.status = 'failed'
                            recipient.error_message = f"Failed after {self.max_retries} attempts: {error}"
                            self.broadcast.failed_count += 1
                            log.error(f"❌ [WA_SEND] broadcast_id={self.broadcast_id} to={recipient.phone} status=failed error={error}")
                        else:
                            # ✅ FIX: Exponential backoff
                            delay = backoff_delays[attempt]
                            log.warning(f"⚠️ [WA_SEND] broadcast_id={self.broadcast_id} to={recipient.phone} attempt={attempt+1}/{self.max_retries} retry_in={delay}s")
                            time.sleep(delay)
                
                except Exception as e:
                    if attempt == self.max_retries - 1:
                        recipient.status = 'failed'
                        recipient.error_message = str(e)[:500]
                        self.broadcast.failed_count += 1
                        log.error(f"❌ [WA_SEND] broadcast_id={self.broadcast_id} to={recipient.phone} status=failed exception={str(e)[:100]}")
                    else:
                        delay = backoff_delays[attempt]
                        log.warning(f"⚠️ [WA_SEND] broadcast_id={self.broadcast_id} to={recipient.phone} attempt={attempt+1}/{self.max_retries} exception={str(e)[:50]} retry_in={delay}s")
                        time.sleep(delay)
            
            db.session.commit()
            
        except Exception as e:
            # 🎯 FIX #4: Continue-on-error - mark recipient as failed but NEVER raise
            log.error(f"❌ [WA_SEND] broadcast_id={self.broadcast_id} fatal_error processing recipient {recipient.id}: {e}")
            recipient.status = 'failed'
            recipient.error_message = str(e)[:500]
            self.broadcast.failed_count += 1
            db.session.commit()
    
    def _check_stop_requested(self):
        """Check if the broadcast was stopped by user"""
        try:
            # Refresh broadcast from DB to check latest status
            db.session.refresh(self.broadcast)
            if self.broadcast.status == 'stopped':
                self.stop_requested = True
                return True
            return False
        except Exception as e:
            log.warning(f"[WA_BROADCAST] Error checking stop status: {e}")
            return False
    
    def _finalize_campaign(self):
        """Update campaign final status"""
        remaining = WhatsAppBroadcastRecipient.query.filter_by(
            broadcast_id=self.broadcast_id,
            status='queued'
        ).count()
        
        # Don't change status if already stopped by user
        if self.broadcast.status != 'stopped':
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
        
        # ✅ FIX: Final summary log
        log.info(f"🏁 [WA_BROADCAST] broadcast_id={self.broadcast_id} total={self.broadcast.total_recipients} sent={self.broadcast.sent_count} failed={self.broadcast.failed_count} status={self.broadcast.status}")


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
