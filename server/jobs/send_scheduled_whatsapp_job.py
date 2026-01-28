"""
Send Scheduled WhatsApp Message Job
Worker job that sends individual scheduled WhatsApp messages
"""
import logging
from datetime import datetime
from server.services import scheduled_messages_service
from server.models_sql import ScheduledMessagesQueue, Lead
from server.db import db

logger = logging.getLogger(__name__)


def send_scheduled_whatsapp_job(message_id: int):
    """
    Send a scheduled WhatsApp message
    
    This is the worker job that actually sends the message.
    It's called by the scheduler tick job for each pending message.
    
    Args:
        message_id: ID of the ScheduledMessagesQueue entry to send
    
    Returns:
        Dict with send result
    """
    from flask import current_app
    
    with current_app.app_context():
        try:
            logger.info(f"[SEND-SCHEDULED-WA] Starting send for message {message_id}")
            
            # Load message
            message = ScheduledMessagesQueue.query.get(message_id)
            if not message:
                logger.error(f"[SEND-SCHEDULED-WA] Message {message_id} not found")
                return {'status': 'error', 'error': 'message_not_found'}
            
            # Check if already sent (idempotency check)
            if message.status != 'pending':
                logger.warning(f"[SEND-SCHEDULED-WA] Message {message_id} status is {message.status}, skipping")
                return {'status': 'skipped', 'reason': f'status_{message.status}'}
            
            # Load lead
            lead = Lead.query.filter_by(
                id=message.lead_id,
                business_id=message.business_id
            ).first()
            
            if not lead:
                error_msg = f"Lead {message.lead_id} not found"
                logger.error(f"[SEND-SCHEDULED-WA] {error_msg}")
                scheduled_messages_service.mark_failed(message_id, error_msg)
                return {'status': 'error', 'error': 'lead_not_found'}
            
            # Verify remote_jid is valid
            if not message.remote_jid:
                error_msg = "No WhatsApp JID available"
                logger.error(f"[SEND-SCHEDULED-WA] {error_msg}")
                scheduled_messages_service.mark_failed(message_id, error_msg)
                return {'status': 'error', 'error': 'no_jid'}
            
            # Safety check: don't send to groups
            if (message.remote_jid.endswith('@g.us') or 
                message.remote_jid.endswith('@broadcast') or 
                'status@broadcast' in message.remote_jid):
                error_msg = f"Cannot send to non-private chat: {message.remote_jid}"
                logger.error(f"[SEND-SCHEDULED-WA] {error_msg}")
                scheduled_messages_service.mark_failed(message_id, error_msg)
                return {'status': 'error', 'error': 'non_private_chat'}
            
            # Get WhatsApp service
            from server.whatsapp_provider import get_whatsapp_service
            tenant_id = f"business_{message.business_id}"
            
            try:
                wa_service = get_whatsapp_service(tenant_id)
            except Exception as e:
                error_msg = f"Failed to get WhatsApp service: {str(e)}"
                logger.error(f"[SEND-SCHEDULED-WA] {error_msg}")
                scheduled_messages_service.mark_failed(message_id, error_msg)
                return {'status': 'error', 'error': 'service_unavailable'}
            
            # Send message
            logger.info(f"[SEND-SCHEDULED-WA] Sending to {message.remote_jid[:20]}... (business {message.business_id})")
            
            try:
                success = wa_service.send_text(
                    remote_jid=message.remote_jid,
                    text=message.message_text,
                    business_id=message.business_id
                )
                
                if success:
                    # Mark as sent
                    scheduled_messages_service.mark_sent(message_id)
                    logger.info(f"[SEND-SCHEDULED-WA] ✅ Message {message_id} sent successfully")
                    
                    # Create WhatsApp message record
                    try:
                        from server.models_sql import WhatsAppMessage
                        
                        outgoing_msg = WhatsAppMessage(
                            business_id=message.business_id,
                            sender='bot',
                            recipient=message.remote_jid.split('@')[0],
                            message_text=message.message_text,
                            timestamp=datetime.utcnow(),
                            direction='outbound',
                            lead_id=message.lead_id
                        )
                        db.session.add(outgoing_msg)
                        db.session.commit()
                        logger.debug(f"[SEND-SCHEDULED-WA] Created WhatsApp message record {outgoing_msg.id}")
                    except Exception as db_err:
                        logger.error(f"[SEND-SCHEDULED-WA] Failed to create message record: {db_err}")
                        db.session.rollback()
                    
                    return {'status': 'success', 'message_id': message_id}
                else:
                    # Send failed
                    error_msg = "WhatsApp service returned false"
                    logger.error(f"[SEND-SCHEDULED-WA] ❌ Failed to send message {message_id}")
                    scheduled_messages_service.mark_failed(message_id, error_msg)
                    return {'status': 'failed', 'error': error_msg}
                    
            except Exception as send_err:
                error_msg = f"Exception during send: {str(send_err)}"
                logger.error(f"[SEND-SCHEDULED-WA] ❌ {error_msg}", exc_info=True)
                scheduled_messages_service.mark_failed(message_id, error_msg)
                return {'status': 'error', 'error': error_msg}
                
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(f"[SEND-SCHEDULED-WA] ❌ {error_msg}", exc_info=True)
            
            # Try to mark as failed
            try:
                scheduled_messages_service.mark_failed(message_id, error_msg)
            except:
                pass
            
            return {'status': 'error', 'error': error_msg}
