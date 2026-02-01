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


def send_scheduled_whatsapp_job(message_id: int, *args, business_id=None, trace_id=None, **kwargs):
    """
    Send a scheduled WhatsApp message
    
    This is the worker job that actually sends the message.
    It's called by the scheduler tick job for each pending message.
    
    Args:
        message_id: ID of the ScheduledMessagesQueue entry to send
        *args: Variable positional arguments (for RQ compatibility)
        business_id: Business ID (passed by RQ enqueue system for metadata)
        trace_id: Trace ID (passed by RQ enqueue system for tracing)
        **kwargs: Additional keyword arguments (for RQ compatibility)
    
    Returns:
        Dict with send result
    
    Note:
        The business_id and trace_id parameters are automatically passed by the
        job enqueue system (server/services/jobs.py) for job metadata tracking.
        They are not used in the function logic but must be accepted to prevent
        TypeError when the job is executed by RQ worker.
    """
    from flask import current_app
    
    with current_app.app_context():
        try:
            logger.info(f"[SEND-SCHEDULED-WA] 📤 Starting send for message {message_id}")
            
            # Load message
            message = ScheduledMessagesQueue.query.get(message_id)
            if not message:
                logger.error(f"[SEND-SCHEDULED-WA] ❌ Message {message_id} not found in database")
                return {'status': 'error', 'error': 'message_not_found'}
            
            logger.info(f"[SEND-SCHEDULED-WA] Message {message_id}: business={message.business_id}, lead={message.lead_id}, status={message.status}")
            
            # Check if already sent (idempotency check)
            if message.status != 'pending':
                logger.warning(f"[SEND-SCHEDULED-WA] ⏭️  Message {message_id} status is '{message.status}', skipping send")
                return {'status': 'skipped', 'reason': f'status_{message.status}'}
            
            # Load lead
            lead = Lead.query.filter_by(
                id=message.lead_id,
                business_id=message.business_id
            ).first()
            
            if not lead:
                error_msg = f"Lead {message.lead_id} not found for business {message.business_id}"
                logger.error(f"[SEND-SCHEDULED-WA] ❌ {error_msg}")
                scheduled_messages_service.mark_failed(message_id, error_msg)
                return {'status': 'error', 'error': 'lead_not_found'}
            
            # 🆕 MULTI-STEP: Check if lead is still in correct status (for apply_mode=ON_ENTER_ONLY)
            # Load the rule to check apply_mode
            from server.models_sql import ScheduledMessageRule, ScheduledRuleStatus, LeadStatus
            rule = ScheduledMessageRule.query.get(message.rule_id)
            if rule:
                # Check if rule applies "WHILE_IN_STATUS" or "ON_ENTER_ONLY"
                apply_mode = getattr(rule, 'apply_mode', 'ON_ENTER_ONLY')
                
                if apply_mode == 'WHILE_IN_STATUS':
                    # Verify lead is still in one of the rule's statuses
                    rule_status_ids = [rs.status_id for rs in ScheduledRuleStatus.query.filter_by(rule_id=rule.id).all()]
                    
                    # Get lead's current status_id
                    current_status = LeadStatus.query.filter_by(
                        business_id=message.business_id,
                        name=lead.status
                    ).first()
                    
                    if not current_status or current_status.id not in rule_status_ids:
                        # Lead has moved out of the trigger status
                        cancel_msg = f"Lead no longer in trigger status (current: {lead.status})"
                        logger.info(f"[SEND-SCHEDULED-WA] {cancel_msg}, cancelling message {message_id}")
                        scheduled_messages_service.mark_cancelled(message_id, cancel_msg)
                        return {'status': 'cancelled', 'reason': 'status_changed'}
                
                logger.info(f"[SEND-SCHEDULED-WA] Status check passed (apply_mode={apply_mode})")
            
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
            
            # Get WhatsApp service with provider selection
            from server.whatsapp_provider import get_whatsapp_service
            tenant_id = f"business_{message.business_id}"
            
            # 🔥 NEW: Use provider from queue entry (baileys or meta)
            provider = getattr(message, 'provider', 'baileys')  # Default to baileys for existing entries
            
            # Map 'meta' to 'twilio' for compatibility (Meta uses Twilio Cloud API)
            if provider == 'meta':
                provider = 'twilio'
            
            logger.info(f"[SEND-SCHEDULED-WA] Using provider: {provider}")
            
            try:
                wa_service = get_whatsapp_service(provider=provider, tenant_id=tenant_id)
            except Exception as e:
                error_msg = f"Failed to get WhatsApp service ({provider}): {str(e)}"
                logger.error(f"[SEND-SCHEDULED-WA] {error_msg}")
                scheduled_messages_service.mark_failed(message_id, error_msg)
                return {'status': 'error', 'error': 'service_unavailable'}
            
            # Send message
            logger.info(f"[SEND-SCHEDULED-WA] Sending to {message.remote_jid[:20]}... (business {message.business_id})")
            
            try:
                result = wa_service.send_message(
                    to=message.remote_jid,
                    message=message.message_text,
                    tenant_id=tenant_id
                )
                
                # Check if send was successful (result is a dict with 'status' key)
                success = result and (result.get('status') in ['sent', 'queued', 'accepted'])
                
                if success:
                    # Mark as sent
                    scheduled_messages_service.mark_sent(message_id)
                    logger.info(f"[SEND-SCHEDULED-WA] ✅ Message {message_id} sent successfully")
                    
                    # Create WhatsApp message record
                    try:
                        from server.models_sql import WhatsAppMessage
                        
                        # Extract recipient phone safely
                        recipient_phone = message.remote_jid.split('@')[0] if '@' in message.remote_jid else message.remote_jid
                        
                        outgoing_msg = WhatsAppMessage(
                            business_id=message.business_id,
                            sender='bot',
                            recipient=recipient_phone,
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
            except Exception:
                pass
            
            return {'status': 'error', 'error': error_msg}
