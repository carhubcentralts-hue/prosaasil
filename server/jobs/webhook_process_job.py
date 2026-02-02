"""
WhatsApp Webhook Processing Job

This job processes incoming WhatsApp webhook messages asynchronously.
Replaces threading.Thread approach with proper RQ queue processing.
"""
import logging
import time
from typing import List, Dict, Any
from server.services.unified_lead_context_service import get_unified_context_for_phone, UnifiedLeadContextService

logger = logging.getLogger(__name__)


def webhook_process_job(tenant_id: str, messages: List[Dict[str, Any]], business_id: int):
    """
    Process WhatsApp webhook messages for a tenant
    
    Args:
        tenant_id: Tenant/business phone ID
        messages: List of WhatsApp messages to process
        business_id: Business ID (for faster resolution)
    
    This job is idempotent - messages have unique IDs and won't be duplicated.
    """
    process_start = time.time()
    logger.info(f"🚀 [WEBHOOK_JOB] tenant={tenant_id} messages={len(messages)} business_id={business_id}")
    
    try:
        from server.services.business_resolver import resolve_business_with_fallback
        from server.whatsapp_provider import get_whatsapp_service
        from server.services.ai_service import get_ai_service
        from server.services.customer_intelligence import CustomerIntelligence
        from server.models_sql import WhatsAppMessage, Lead, WhatsAppConversation
        from server.db import db
        from server.services.whatsapp_session_service import update_session_activity
        from server.services.n8n_integration import n8n_whatsapp_incoming, n8n_whatsapp_outgoing
        from server.utils.whatsapp_utils import extract_inbound_text, generate_trace_id
        from flask import current_app
        import re
        
        # Process in app context
        with current_app.app_context():
            # Verify business ID
            if not business_id:
                business_id, status = resolve_business_with_fallback('whatsapp', tenant_id)
            
            # 🔒 SECURITY: Reject unknown tenants
            if not business_id:
                logger.error(f"❌ REJECTED WhatsApp message: Unknown tenant '{tenant_id}' - no business match")
                return  # Idempotent - skip silently
            
            wa_service = get_whatsapp_service()
            ci = CustomerIntelligence(business_id)
            
            for msg in messages:
                jid = None
                trace_id = None
                try:
                    # Parse message
                    # 🔥 FIX: Use remoteJid as the single source of truth for the chat JID
                    # DO NOT reconstruct the JID - use it exactly as received from WhatsApp
                    from_jid = msg.get('key', {}).get('remoteJid', '')
                    message_id = msg.get('key', {}).get('id', '')
                    phone_number = from_jid.split('@')[0] if '@' in from_jid else from_jid
                    push_name = msg.get('pushName')  # Extract WhatsApp display name
                    
                    # 🔥 DEBUG: Log phone extraction
                    logger.info(f"📞 [PHONE_EXTRACT] from_jid={from_jid} -> phone_number={phone_number} push_name={push_name}")
                    
                    # Generate trace ID
                    trace_id = generate_trace_id(business_id, from_jid, message_id)
                    
                    # 🔥 FIX: Add debug logging to prove no mismatch
                    # Log the incoming remoteJid before any processing
                    logger.info(f"📨 [WEBHOOK_JOB] trace_id={trace_id} incoming_remoteJid={from_jid}")
                    
                    # Extract text from message
                    message_text, message_format = extract_inbound_text(msg)
                    
                    if not phone_number:
                        logger.warning(f"⚠️ [SKIP] no_phone trace_id={trace_id}")
                        continue
                    
                    if not message_text:
                        message_keys = list(msg.get('message', {}).keys())
                        logger.info(f"⚠️ [SKIP] empty_text trace_id={trace_id} format={message_format} keys={message_keys}")
                        continue
                    
                    logger.info(f"📝 [TEXT_EXTRACTED] trace_id={trace_id} format={message_format} len={len(message_text)}")
                    
                    # 🔥 CRITICAL FIX: Use remoteJid directly as the JID for all operations
                    # This is the "iron rule" - NEVER reconstruct the JID from phone_number
                    # For DMs: remoteJid ends with @s.whatsapp.net
                    # For Groups: remoteJid ends with @g.us
                    # For Android LID: remoteJid ends with @lid, use participant as actual JID
                    
                    # 🔥 CRITICAL LID FIX: Extract real phone from participant field
                    # @lid digits are NOT phone numbers - they're WhatsApp's internal identifiers
                    # We MUST get the real phone from participant or Baileys resolution
                    phone_e164_for_lead = None  # Will store normalized E.164 phone
                    
                    if from_jid.endswith('@lid'):
                        logger.info(f"[WA-LID] trace_id={trace_id} LID detected: {from_jid[:30]}")
                        
                        # Check metadata first (added by Baileys service)
                        lid_metadata = msg.get('_lid_metadata', {})
                        
                        # 🔥 NEW: STEP 0 - Check if Baileys already resolved the phone!
                        if lid_metadata.get('resolved_phone'):
                            phone_e164_for_lead = lid_metadata['resolved_phone']
                            logger.info(f"[WA-LID-RESOLVE] ✅ source=baileys_resolved phone={phone_e164_for_lead}")
                        
                        # STEP 1: Try to extract participant from ALL possible locations
                        if not phone_e164_for_lead:
                            participant_jid = None
                            
                            if lid_metadata and lid_metadata.get('participant_jid'):
                                participant_jid = lid_metadata['participant_jid']
                                logger.info(f"[WA-LID-RESOLVE] source=metadata participant={participant_jid}")
                        
                            # Fallback: check standard locations
                            if not participant_jid:
                                participant_jid = msg.get('key', {}).get('participant')
                                if participant_jid:
                                    logger.info(f"[WA-LID-RESOLVE] source=key.participant participant={participant_jid}")
                            
                            # STEP 2: If participant found, extract phone from it
                            if participant_jid and participant_jid.endswith('@s.whatsapp.net'):
                                # Extract phone digits from participant JID
                                phone_raw = participant_jid.replace('@s.whatsapp.net', '').split(':')[0]
                                
                                # Normalize to E.164
                                from server.agent_tools.phone_utils import normalize_phone
                                phone_e164_for_lead = normalize_phone(phone_raw)
                                
                                if phone_e164_for_lead:
                                    jid = participant_jid  # Use participant as reply JID
                                    logger.info(f"[WA-LID-RESOLVE] ✅ source=participant phone={phone_e164_for_lead}")
                                else:
                                    logger.warning(f"[WA-LID-RESOLVE] ⚠️ Failed to normalize participant phone: {phone_raw}")
                        
                        # STEP 3: If no participant, try mapping table lookup
                        if not phone_e164_for_lead:
                            from server.services.contact_identity_service import ContactIdentityService
                            phone_e164_for_lead = ContactIdentityService.lookup_phone_by_lid(
                                business_id=business_id,
                                lid_jid=from_jid
                            )
                            if phone_e164_for_lead:
                                logger.info(f"[WA-LID-RESOLVE] ✅ source=mapping phone={phone_e164_for_lead}")
                        
                        # STEP 4: If still no phone, try Baileys resolution endpoint
                        if not phone_e164_for_lead:
                            try:
                                import requests
                                from server.whatsapp_provider import get_whatsapp_service
                                
                                # Get Baileys base URL from service
                                wa_service = get_whatsapp_service(tenant_id=f"business_{business_id}")
                                baileys_base_url = wa_service.base_url if hasattr(wa_service, 'base_url') else None
                                
                                if baileys_base_url:
                                    resolve_url = f"{baileys_base_url}/internal/resolve-jid"
                                    response = requests.get(
                                        resolve_url,
                                        params={'jid': from_jid, 'tenantId': f"business_{business_id}"},
                                        timeout=5
                                    )
                                    
                                    if response.status_code == 200:
                                        data = response.json()
                                        phone_e164_for_lead = data.get('phone_e164')
                                        if phone_e164_for_lead:
                                            logger.info(f"[WA-LID-RESOLVE] ✅ source=baileys phone={phone_e164_for_lead}")
                            except Exception as resolve_error:
                                logger.warning(f"[WA-LID-RESOLVE] Baileys resolution failed: {resolve_error}")
                        
                        # STEP 5: Set JID for reply (prefer participant if available)
                        if participant_jid:
                            jid = participant_jid
                        else:
                            jid = from_jid  # Use @lid as fallback for reply routing
                        
                        # Log final resolution result
                        if phone_e164_for_lead:
                            logger.info(f"[WA-LID-RESOLVE] ✅ FINAL: phone={phone_e164_for_lead} reply_jid={jid[:30]}")
                        else:
                            logger.warning(f"[WA-LID-RESOLVE] ⚠️ NO PHONE RESOLVED for {from_jid[:30]} - lead will be created without phone")
                    
                    else:
                        # Standard @s.whatsapp.net JID - extract phone directly
                        jid = from_jid
                        phone_raw = from_jid.replace('@s.whatsapp.net', '').split(':')[0]
                        from server.agent_tools.phone_utils import normalize_phone
                        phone_e164_for_lead = normalize_phone(phone_raw)
                        
                        if phone_e164_for_lead:
                            logger.info(f"[WA-PHONE] ✅ Standard JID phone={phone_e164_for_lead}")
                    
                    # 🔥 FIX: Add verification logging to ensure no mismatch
                    logger.info(f"🎯 [JID_COMPUTED] trace_id={trace_id} computed_to={jid}")
                    typing_started = False
                    
                    try:
                        # Send typing indicator
                        try:
                            typing_start = time.time()
                            wa_service.send_typing(jid, True)
                            typing_started = True
                            logger.info(f"⏱️ typing took: {time.time() - typing_start:.2f}s")
                        except Exception as e:
                            logger.warning(f"⚠️ Typing indicator failed: {e}")
                        
                        # Check if AI is active
                        from server.routes_whatsapp import is_ai_active_for_conversation
                        if not is_ai_active_for_conversation(business_id, phone_number):
                            logger.info(f"🔕 AI is INACTIVE for {phone_number} - skipping AI response")
                            
                            # Save incoming message only
                            incoming_msg = WhatsAppMessage()
                            incoming_msg.business_id = business_id
                            incoming_msg.to_number = phone_number
                            incoming_msg.direction = 'in'
                            incoming_msg.body = message_text
                            incoming_msg.message_type = 'text'
                            incoming_msg.status = 'received'
                            incoming_msg.provider = 'baileys'
                            db.session.add(incoming_msg)
                            db.session.commit()
                            
                            # Track session
                            try:
                                update_session_activity(
                                    business_id=business_id,
                                    customer_wa_id=phone_number,
                                    direction="in",
                                    provider="baileys"
                                )
                            except Exception as e:
                                logger.error(f"🔴 [WA-SESSION] Session tracking FAILED: {e}", exc_info=True)
                            
                            continue
                        
                        # Customer lookup
                        lookup_start = time.time()
                        logger.info(f"🔍 [LEAD_UPSERT_START] trace_id={trace_id} phone={phone_number} push_name={push_name}")
                        # 🔥 LID FIX: Pass phone_e164_for_lead to ensure proper phone resolution
                        customer, lead, was_created = ci.find_or_create_customer_from_whatsapp(
                            phone_number, 
                            message_text,
                            push_name=push_name,
                            phone_e164_override=phone_e164_for_lead  # 🔥 NEW: Pass resolved phone
                        )
                        action = "created" if was_created else "updated"
                        normalized_phone = lead.phone_e164 if lead else phone_number
                        logger.info(f"✅ [LEAD_UPSERT_DONE] trace_id={trace_id} lead_id={lead.id if lead else 'N/A'} action={action} phone={normalized_phone}")
                        logger.info(f"⏱️ customer lookup took: {time.time() - lookup_start:.2f}s")
                        
                        # Extract previous messages for context (keep last 10)
                        previous_messages = []
                        if lead.notes:
                            note_lines = lead.notes.split('\n')
                            for line in note_lines[-10:]:
                                match = re.match(r'\[(WhatsApp|AI|עוזרת|עוזר|סוכן)\s+\d+:\d+:\d+\]:\s*(.+)', line)
                                if match:
                                    sender, content = match.group(1), match.group(2).strip()
                                    previous_messages.append(f"{'לקוח' if sender == 'WhatsApp' else 'עוזר'}: {content}")
                        
                        # 🔥 NEW: Load conversation summary if exists
                        conversation_summary = None
                        try:
                            conversation = WhatsAppConversation.query.filter_by(
                                business_id=business_id,
                                customer_number=phone_number
                            ).order_by(WhatsAppConversation.last_message_at.desc()).first()
                            
                            if conversation and conversation.summary:
                                conversation_summary = conversation.summary
                                logger.info(f"📋 Loaded conversation summary for {phone_number}: {len(conversation_summary)} chars")
                        except Exception as e:
                            logger.warning(f"⚠️ Could not load conversation summary: {e}")
                        
                        # 🔥 NEW: Load unified lead context if customer service enabled
                        lead_context = None
                        try:
                            service = UnifiedLeadContextService(business_id)
                            if service.is_customer_service_enabled():
                                lead_context = get_unified_context_for_phone(business_id, phone_number, channel="whatsapp")
                                if lead_context and lead_context.found:
                                    logger.info(f"[UnifiedContext] ✅ Loaded context for lead #{lead_context.lead_id}: "
                                              f"{len(lead_context.recent_notes)} notes, "
                                              f"next_apt={'Yes' if lead_context.next_appointment else 'No'}")
                                else:
                                    logger.info(f"[UnifiedContext] No context found for phone {phone_number}")
                            else:
                                logger.info(f"[UnifiedContext] Customer service disabled for business {business_id}")
                        except Exception as ctx_err:
                            logger.warning(f"[UnifiedContext] Error loading context: {ctx_err}")
                        
                        # Generate AI response
                        ai_start = time.time()
                        logger.info(f"🤖 [AGENTKIT_START] trace_id={trace_id} business_id={business_id} message='{message_text[:50]}...'")
                        
                        ai_service = get_ai_service()
                        ai_response = None
                        
                        try:
                            # 🔥 NEW: Build context for new Prompt Stack architecture
                            context = {
                                # Basic customer info
                                'customer_name': customer.name,
                                'phone_number': phone_number,
                                # New: Add lead_id for proper context
                                'lead_id': lead.id if lead else None,
                                # New: Add conversation summary if exists
                                'summary': conversation_summary,
                                # History (formatted for prompt stack)
                                'history': previous_messages,  # New key name for prompt stack
                                'previous_messages': previous_messages,  # Keep old key for backwards compatibility
                                # Channel & trace
                                'channel': 'whatsapp',
                                'trace_id': trace_id,
                                # 🔥 NEW: Add unified lead context
                                'lead_context': lead_context.model_dump() if lead_context and lead_context.found else None,
                                'remote_jid': jid  # Add JID for tool context
                            }
                            
                            ai_response = ai_service.generate_response_with_agent(
                                message=message_text,
                                business_id=business_id,
                                customer_phone=phone_number,
                                customer_name=customer.name,
                                context=context,
                                channel='whatsapp',
                                is_first_turn=(len(previous_messages) == 0)
                            )
                            ai_time = time.time() - ai_start
                            
                            if not ai_response:
                                logger.warning(f"⚠️ [AGENTKIT_EMPTY] trace_id={trace_id} response=None")
                                ai_response = "סליחה, לא הבנתי. אפשר לנסח מחדש?"
                            
                            logger.info(f"✅ [AGENTKIT_DONE] trace_id={trace_id} latency_ms={ai_time*1000:.0f} response_len={len(ai_response)}")
                        except Exception as ai_error:
                            ai_time = time.time() - ai_start
                            logger.error(f"❌ [AGENTKIT_ERROR] trace_id={trace_id} latency_ms={ai_time*1000:.0f} error={ai_error}")
                            import traceback
                            logger.error(f"❌ [AGENTKIT_ERROR] trace_id={trace_id} stack={traceback.format_exc()}")
                            ai_response = "סליחה, אני לא יכול לעזור לך כרגע. בבקשה נסה שוב או התקשר אלינו."
                        
                        # Send response
                        # 🔥 FIX: Add final verification before sending
                        # Verify that computed target JID matches incoming remoteJid
                        if jid != from_jid:
                            logger.error(f"⚠️ [JID_MISMATCH_WARNING] trace_id={trace_id} incoming={from_jid} computed={jid}")
                            # Force correction to use incoming remoteJid
                            jid = from_jid
                            logger.info(f"🔧 [JID_CORRECTED] trace_id={trace_id} forced_to={jid}")
                        
                        logger.info(f"📤 [SEND_ATTEMPT] trace_id={trace_id} to={jid[:30]} len={len(ai_response)}")
                        send_start = time.time()
                        
                        try:
                            send_result = wa_service.send_message(jid, ai_response)
                            send_time = time.time() - send_start
                            logger.info(f"✅ [SEND_RESULT] trace_id={trace_id} status={send_result.get('status')} latency_ms={send_time*1000:.0f} final_to={jid[:30]}")
                        except Exception as send_error:
                            send_time = time.time() - send_start
                            logger.error(f"❌ [SEND_ERROR] trace_id={trace_id} error={send_error} latency_ms={send_time*1000:.0f}")
                            import traceback
                            logger.error(f"❌ [SEND_ERROR] trace_id={trace_id} stack={traceback.format_exc()}")
                            send_result = {"status": "error", "error": str(send_error)}
                        
                        logger.info(f"⏱️ TOTAL processing: {time.time() - process_start:.2f}s")
                        
                        # Save to DB
                        timestamp = time.strftime('%H:%M:%S')
                        
                        # Save incoming
                        incoming_msg = WhatsAppMessage()
                        incoming_msg.business_id = business_id
                        incoming_msg.to_number = phone_number
                        incoming_msg.lead_id = lead.id if lead else None  # 🔥 FIX: Add lead_id
                        incoming_msg.direction = 'in'
                        incoming_msg.body = message_text
                        incoming_msg.message_type = 'text'
                        incoming_msg.status = 'received'
                        incoming_msg.provider = 'baileys'
                        incoming_msg.provider_message_id = message_id  # 🔥 FIX: Add for dedupe
                        incoming_msg.lead_id = None  # Will be set by future lead link
                        db.session.add(incoming_msg)
                        
                        # Track session for incoming
                        try:
                            update_session_activity(
                                business_id=business_id,
                                customer_wa_id=phone_number,
                                direction="in",
                                provider="baileys"
                            )
                        except Exception as e:
                            logger.error(f"🔴 [WA-SESSION] Session tracking (in) FAILED: {e}", exc_info=True)
                        
                        # n8n: Send incoming message event
                        n8n_whatsapp_incoming(
                            phone=phone_number,
                            message=message_text,
                            business_id=str(business_id),
                            lead_id=lead.id if lead else None,
                            lead_name=customer.name if customer else None
                        )
                        
                        # Save outgoing if sent
                        if send_result.get('status') == 'sent':
                            outgoing_msg = WhatsAppMessage()
                            outgoing_msg.business_id = business_id
                            outgoing_msg.to_number = phone_number
                            outgoing_msg.lead_id = lead.id if lead else None  # 🔥 FIX: Add lead_id for history
                            outgoing_msg.direction = 'out'
                            outgoing_msg.body = ai_response
                            outgoing_msg.message_type = 'text'
                            outgoing_msg.status = 'sent'
                            outgoing_msg.provider = send_result.get('provider', 'baileys')
                            outgoing_msg.provider_message_id = send_result.get('message_id')
                            db.session.add(outgoing_msg)
                            
                            # Track session for outgoing
                            try:
                                update_session_activity(
                                    business_id=business_id,
                                    customer_wa_id=phone_number,
                                    direction="out",
                                    provider="baileys"
                                )
                            except Exception as e:
                                logger.error(f"🔴 [WA-SESSION] Session tracking (out) FAILED: {e}", exc_info=True)
                            
                            # n8n: Send outgoing message event
                            n8n_whatsapp_outgoing(
                                phone=phone_number,
                                message=ai_response,
                                business_id=str(business_id),
                                lead_id=lead.id if lead else None,
                                is_ai=True
                            )
                        
                        # Update lead notes
                        new_note = f"[WhatsApp {timestamp}]: {message_text}\n[עוזר {timestamp}]: {ai_response}"
                        if lead.notes:
                            note_lines = lead.notes.split('\n')
                            if len(note_lines) > 50:
                                lead.notes = '\n'.join(note_lines[-50:]) + f"\n{new_note}"
                            else:
                                lead.notes += f"\n{new_note}"
                        else:
                            lead.notes = new_note
                        
                        # Generate conversation summary asynchronously
                        from server.jobs import enqueue_job
                        enqueue_job(
                            'conversation_analysis_job',
                            business_id=business_id,
                            lead_id=lead.id,
                            message_text=message_text,
                            phone_number=phone_number,
                            queue='low'
                        )
                        
                        db.session.commit()
                    finally:
                        # Always stop typing indicator
                        if typing_started:
                            try:
                                wa_service.send_typing(jid, False)
                                logger.info(f"✅ Typing indicator stopped for {phone_number}")
                            except Exception as e:
                                logger.warning(f"⚠️ Failed to stop typing indicator: {e}")
                
                except Exception as msg_error:
                    logger.error(f"❌ WhatsApp message processing error: {msg_error}")
                    import traceback
                    traceback.print_exc()
                    
                    # Try to send error message to user
                    if jid:
                        try:
                            wa_service.send_message(jid, "סליחה, נתקלתי בבעיה. אנא נסה שוב.")
                        except:
                            pass
                    continue
        
        logger.info(f"✅ [WEBHOOK_JOB] Completed in {time.time() - process_start:.2f}s")
        
    except Exception as e:
        logger.error(f"❌ [WEBHOOK_JOB] Failed: {e}")
        import traceback
        traceback.print_exc()
        raise  # Re-raise for RQ to handle retry
