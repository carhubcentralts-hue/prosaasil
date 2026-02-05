"""
WhatsApp AI Response Job - Background processing for AI responses
🔥 CRITICAL: This job handles the heavy AI processing in the background after webhook ACK
This includes:
- Loading conversation history
- Loading customer memory
- Calling AgentKit with ALL TOOLS (appointments, lead updates, etc.)
- Sending the response via Baileys

This ensures webhook returns 200 in < 1s while AI processing happens async
"""
import logging
import time
from datetime import datetime, timedelta
from server.db import db
from server.models_sql import WhatsAppMessage, Lead, Customer, Business, WhatsAppConversationState
from rq import get_current_job

logger = logging.getLogger(__name__)

# 🔥 RATE LIMITING: Prevent sending messages too fast (causes Baileys blocks)
_last_send_time = {}
MIN_SEND_INTERVAL_SECONDS = 2  # Wait at least 2 seconds between messages to same number


def whatsapp_ai_response_job(
    business_id: int,
    message_id: int,
    remote_jid: str,
    conversation_key: str,
    message_text: str,
    from_number_e164: str,
    lead_id: int
):
    """
    Process WhatsApp message with AI in background
    
    Args:
        business_id: Business ID
        message_id: WhatsAppMessage ID (already saved)
        remote_jid: Remote JID for reply
        conversation_key: Conversation key for state tracking
        message_text: The message text
        from_number_e164: Customer phone
        lead_id: Lead ID
    """
    job = get_current_job()
    job_id = job.id if job else 'N/A'
    
    logger.info(f"[WA-AI-JOB] 🚀 Started job {job_id} for message_id={message_id}, lead_id={lead_id}")
    
    try:
        # Load message from DB
        wa_msg = WhatsAppMessage.query.get(message_id)
        if not wa_msg:
            logger.error(f"[WA-AI-JOB] ❌ Message {message_id} not found!")
            return {'success': False, 'error': 'Message not found'}
        
        # Load lead
        lead = Lead.query.get(lead_id)
        if not lead:
            logger.error(f"[WA-AI-JOB] ❌ Lead {lead_id} not found!")
            return {'success': False, 'error': 'Lead not found'}
        
        # Load customer (for backwards compatibility)
        customer = Customer.query.filter_by(
            business_id=business_id,
            phone_e164=lead.phone_e164
        ).first() if lead.phone_e164 else None
        
        # Check if AI is enabled
        ai_enabled = True
        try:
            conv_state = WhatsAppConversationState.query.filter_by(
                business_id=business_id,
                phone=conversation_key
            ).first()
            if conv_state:
                ai_enabled = conv_state.ai_active
        except Exception as e:
            logger.warning(f"[WA-AI-JOB] Could not check AI state: {e}")
        
        if not ai_enabled:
            logger.info(f"[WA-AI-JOB] 🚫 AI disabled for {conversation_key[:30]} - skipping")
            return {'success': True, 'ai_disabled': True}
        
        # Load conversation history (20 messages)
        previous_messages = []
        quoted_context = None  # Store reply context if current message is a reply
        try:
            recent_msgs = WhatsAppMessage.query.filter_by(
                business_id=business_id,
                to_number=conversation_key
            ).order_by(WhatsAppMessage.created_at.desc()).limit(20).all()
            
            for msg_hist in reversed(recent_msgs):
                # 🔥 LAYER 1: Include source info for better context understanding
                sender_label = "לקוח"
                if msg_hist.direction in ['in', 'inbound']:
                    sender_label = "לקוח"
                else:
                    # Outbound message - use source to determine who sent it
                    # Handle legacy messages where source is None
                    source = msg_hist.source
                    if source == 'bot':
                        sender_label = "עוזר (בוט)"
                    elif source == 'human':
                        sender_label = "נציג"
                    elif source == 'automation':
                        sender_label = "אוטומציה"
                    elif source == 'system':
                        sender_label = "מערכת"
                    else:
                        # Legacy messages without source field
                        sender_label = "עוזר"
                
                previous_messages.append(f"{sender_label}: {msg_hist.body}")
            
            # 🔥 LAYER 2: Check if the current message (latest incoming) is a reply to something
            # Find the most recent incoming message (which should be the one we're responding to)
            current_incoming = WhatsAppMessage.query.filter_by(
                business_id=business_id,
                to_number=conversation_key,
                direction='in'
            ).order_by(WhatsAppMessage.created_at.desc()).first()
            
            if current_incoming and current_incoming.reply_to_message_id:
                # Customer is replying to a specific message - fetch it for context
                quoted_msg = WhatsAppMessage.query.get(current_incoming.reply_to_message_id)
                if quoted_msg:
                    # Only add '...' if message is longer than 100 characters
                    body_preview = quoted_msg.body[:100]
                    if len(quoted_msg.body) > 100:
                        body_preview += '...'
                    quoted_context = f"[הלקוח ענה להודעה הזאת: '{body_preview}']"
                    logger.info(f"[WA-AI-JOB] 🔗 Customer replied to message: {quoted_msg.id}")
        except Exception as e:
            logger.warning(f"[WA-AI-JOB] ⚠️ Could not load history: {e}")
        
        # Load customer memory
        customer_memory_text = ""
        ask_continue_or_fresh = False
        try:
            from server.services.customer_memory_service import (
                is_customer_service_enabled,
                get_customer_memory,
                format_memory_for_ai,
                should_ask_continue_or_fresh,
                update_interaction_timestamp
            )
            
            if is_customer_service_enabled(business_id):
                customer_memory = get_customer_memory(lead.id, business_id, max_notes=5)
                customer_memory_text = format_memory_for_ai(customer_memory)
                ask_continue_or_fresh = should_ask_continue_or_fresh(lead.id, business_id)
                update_interaction_timestamp(lead.id, business_id, 'whatsapp')
        except Exception as e:
            logger.warning(f"[WA-AI-JOB] ⚠️ Could not load customer memory: {e}")
        
        # Load unified lead context
        lead_context_payload = None
        try:
            from server.services.unified_lead_context_service import get_unified_context_for_lead
            lead_context_payload = get_unified_context_for_lead(
                business_id=business_id,
                lead_id=lead.id,
                channel='whatsapp'
            )
            if lead_context_payload and lead_context_payload.found:
                logger.info(f"[WA-AI-JOB] ✅ Loaded unified lead context: lead_id={lead.id}, appointments={len(lead_context_payload.past_appointments)}")
        except Exception as e:
            logger.error(f"[WA-AI-JOB] ❌ Failed to load lead context: {e}")
        
        # Build AI context - 🔥 CRITICAL: Include ALL context for AgentKit tools
        ai_context = {
            'phone': from_number_e164,
            'remote_jid': remote_jid,  # Critical for LID replies
            'customer_name': customer.name if customer else None,
            'lead_status': lead.status if lead else None,
            'lead_id': lead.id,
            'previous_messages': previous_messages,
            'quoted_context': quoted_context,  # 🔥 LAYER 2: Include reply threading context
            'appointment_created': False,  # Will be updated by appointment handler if needed
            'customer_memory': customer_memory_text,
            'ask_continue_or_fresh': ask_continue_or_fresh,
            'last_user_message': conv_state.last_user_message if conv_state else None,
            'last_agent_message': conv_state.last_agent_message if conv_state else None,
            'conversation_stage': conv_state.conversation_stage if conv_state else None,
            'conversation_has_history': len(previous_messages) >= 2,
            'lead_context': lead_context_payload.dict() if (lead_context_payload and lead_context_payload.found) else None
        }
        
        # 🔥 CRITICAL: Generate AI response with AgentKit (ALL TOOLS ENABLED!)
        # This includes: appointments, lead updates, calendar access, etc.
        ai_start = time.time()
        from server.services.ai_service import get_ai_service
        ai_service = get_ai_service()
        
        logger.info(f"[WA-AI-JOB] 🤖 Calling AgentKit with FULL TOOLS for lead_id={lead.id}")
        logger.info(f"[WA-AI-JOB]    Context: history={len(previous_messages)} msgs, has_memory={bool(customer_memory_text)}, has_lead_context={bool(lead_context_payload)}")
        
        # 🔥 AgentKit with ALL TOOLS - this is the FULL power of the bot!
        ai_response = ai_service.generate_response_with_agent(
            message=message_text,
            business_id=business_id,
            context=ai_context,
            channel='whatsapp',
            customer_phone=conversation_key,
            customer_name=customer.name if customer else None
        )
        
        # Handle response
        actions = []
        if isinstance(ai_response, dict):
            response_text = ai_response.get('text', '')
            actions = ai_response.get('actions', [])
            logger.info(f"[WA-AI-JOB] AI returned {len(actions)} actions")
        else:
            response_text = str(ai_response)
        
        ai_duration = time.time() - ai_start
        logger.info(f"[WA-AI-JOB] ✅ AI response generated in {ai_duration:.2f}s, length={len(response_text)}")
        
        # Update conversation state
        try:
            if not conv_state:
                conv_state = WhatsAppConversationState()
                conv_state.business_id = business_id
                conv_state.phone = conversation_key
                conv_state.ai_active = True
                db.session.add(conv_state)
            
            conv_state.last_user_message = message_text
            conv_state.last_agent_message = response_text
            conv_state.updated_at = datetime.utcnow()
            db.session.commit()
            logger.info(f"[WA-AI-JOB] ✅ Updated conversation state")
        except Exception as e:
            logger.warning(f"[WA-AI-JOB] Could not update conv state: {e}")
            try:
                db.session.rollback()
            except:
                pass
        
        # 🔥 RATE LIMITING: Prevent sending too fast (causes Baileys blocks)
        # Wait if we sent a message to this number recently
        last_send = _last_send_time.get(conversation_key)
        if last_send:
            elapsed = time.time() - last_send
            if elapsed < MIN_SEND_INTERVAL_SECONDS:
                wait_time = MIN_SEND_INTERVAL_SECONDS - elapsed
                logger.info(f"[WA-AI-JOB] 🕐 Rate limiting: waiting {wait_time:.1f}s before sending to {conversation_key[:20]}")
                time.sleep(wait_time)
        
        # Enqueue send job
        if response_text and not response_text.isspace():
            from server.services.jobs import enqueue_job
            from server.jobs.send_whatsapp_message_job import send_whatsapp_message_job
            
            # Get tenant_id format
            tenant_id = f"business_{business_id}"
            
            send_job_id = enqueue_job(
                queue_name='default',
                func=send_whatsapp_message_job,
                business_id=business_id,
                tenant_id=tenant_id,
                remote_jid=remote_jid,  # Use original remote_jid for LID support
                response_text=response_text,
                wa_msg_id=message_id,
                timeout=60,
                retry=2,
                description=f"Send WhatsApp AI response to {remote_jid[:15]}"
            )
            
            # Update last send time for rate limiting
            _last_send_time[conversation_key] = time.time()
            
            logger.info(f"[WA-AI-JOB] ✅ Enqueued send job: {send_job_id}")
        else:
            logger.warning(f"[WA-AI-JOB] ⚠️ AI returned empty response - not sending")
        
        return {
            'success': True,
            'response_length': len(response_text) if response_text else 0,
            'ai_duration': ai_duration,
            'actions_count': len(actions) if isinstance(ai_response, dict) else 0
        }
        
    except Exception as e:
        logger.error(f"[WA-AI-JOB] ❌ Job failed: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}
