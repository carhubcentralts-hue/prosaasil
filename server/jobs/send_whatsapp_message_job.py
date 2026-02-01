"""
WhatsApp Message Sending Job
Send WhatsApp messages with retry and Twilio fallback

This replaces the background thread in routes_whatsapp.py
"""
import logging
import time
from datetime import datetime

logger = logging.getLogger(__name__)


def send_whatsapp_message_job(
    business_id: int,
    tenant_id: str,
    remote_jid: str,
    response_text: str,
    wa_msg_id: int = None
):
    """
    Send WhatsApp message with retry logic and Twilio fallback.
    
    Args:
        business_id: Business ID for multi-tenant routing
        tenant_id: Tenant ID (e.g., "business_1") for Baileys routing
        remote_jid: FULL WhatsApp JID (e.g., 972501234567@s.whatsapp.net or 823...@lid)
        response_text: The message text to send
        wa_msg_id: Optional incoming message ID for tracking
    
    Returns:
        dict: Send result summary
    """
    from server.whatsapp_provider import get_whatsapp_service
    from server.models_sql import WhatsAppMessage, db
    
    send_start = time.time()
    
    # 🔥 SAFETY CHECK: Never send to groups, broadcasts, newsletters, or status updates
    if (remote_jid.endswith('@g.us') or 
        remote_jid.endswith('@broadcast') or 
        remote_jid.endswith('@newsletter') or
        'status@broadcast' in remote_jid):
        logger.error(f"[WA-SEND-JOB] ❌ BLOCKED: Attempted to send to non-private chat {remote_jid[:30]}...")
        return {
            'status': 'blocked',
            'reason': 'non-private-chat',
            'remote_jid': remote_jid[:30],
            'timestamp': datetime.utcnow().isoformat()
        }
    
    logger.info(f"[WA-SEND-JOB] Starting send to {remote_jid[:20]}... business_id={business_id}")
    
    # 🔥 LID FIX: Log clear message for LID vs standard JID
    if remote_jid.endswith('@lid'):
        logger.info(f"[WA-SEND-JOB] 🔵 Sending to LID: {remote_jid}")
    elif remote_jid.endswith('@s.whatsapp.net'):
        logger.info(f"[WA-SEND-JOB] 📱 Sending to standard WhatsApp: {remote_jid}")
    else:
        logger.warning(f"[WA-SEND-JOB] ⚠️ Sending to non-standard JID: {remote_jid}")
    
    # 🔥 CRITICAL: Use app context for DB operations
    from flask import current_app
    
    with current_app.app_context():
        try:
            # Get WhatsApp service (Baileys or Twilio)
            wa_service = get_whatsapp_service(tenant_id)
            
            # Send message (handles retries internally)
            result = wa_service.send_message(to=remote_jid, message=response_text, tenant_id=tenant_id)
            
            # Create outgoing message record
            try:
                outgoing_msg = WhatsAppMessage(
                    business_id=business_id,
                    to_number=remote_jid.split('@')[0],  # Extract phone number
                    body=response_text,
                    direction='outbound',
                    provider='baileys',  # Default provider for this job
                    status='sent',
                    message_type='text'
                )
                db.session.add(outgoing_msg)
                db.session.commit()
                logger.info(f"[WA-SEND-JOB] ✅ Outgoing message saved to DB: {outgoing_msg.id}")
            except Exception as db_err:
                logger.error(f"[WA-SEND-JOB] ⚠️ Failed to save outgoing message to DB: {db_err}")
                db.session.rollback()
            
            send_duration = time.time() - send_start
            
            # Check if send was successful (result is a dict with 'status' key)
            success = result and (result.get('status') in ['sent', 'queued', 'accepted'])
            
            if success:
                logger.info(f"[WA-SEND-JOB] ✅ Message sent successfully in {send_duration:.2f}s")
                return {
                    'status': 'success',
                    'remote_jid': remote_jid[:20],
                    'duration': send_duration,
                    'timestamp': datetime.utcnow().isoformat()
                }
            else:
                logger.error(f"[WA-SEND-JOB] ❌ Message send failed after {send_duration:.2f}s")
                return {
                    'status': 'failed',
                    'remote_jid': remote_jid[:20],
                    'duration': send_duration,
                    'timestamp': datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            send_duration = time.time() - send_start
            logger.error(f"[WA-SEND-JOB] ❌ Exception during send: {e}", exc_info=True)
            return {
                'status': 'error',
                'error': str(e),
                'remote_jid': remote_jid[:20],
                'duration': send_duration,
                'timestamp': datetime.utcnow().isoformat()
            }
