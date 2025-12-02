"""
WhatsApp Webhook Routes - OPTIMIZED FOR SPEED ⚡
מסלולי Webhook של WhatsApp - מותאם למהירות מקסימלית
"""
import os
import logging
from flask import Blueprint, request, jsonify
from server.extensions import csrf
from threading import Thread
import time
from server.services.n8n_integration import n8n_whatsapp_incoming, n8n_whatsapp_outgoing
from server.services.whatsapp_session_service import update_session_activity

logger = logging.getLogger(__name__)

webhook_bp = Blueprint('webhook', __name__, url_prefix='/webhook')
INTERNAL_SECRET = os.getenv('INTERNAL_SECRET')

# ⚡ CRITICAL FIX: Reuse app instance across threads - massive speed boost
from threading import Lock, Semaphore
_cached_app = None
_cached_app_lock = Lock()  # ⚡ Initialize at module load to prevent race condition

# ⚡ BUILD 112: Limit concurrent WhatsApp processing threads
MAX_CONCURRENT_WA_THREADS = int(os.getenv("MAX_WA_THREADS", "10"))
_wa_thread_semaphore = Semaphore(MAX_CONCURRENT_WA_THREADS)
_active_wa_threads = 0
_wa_threads_lock = Lock()

def get_or_create_app():
    """Get cached app or create new one - thread-safe"""
    global _cached_app
    
    if _cached_app is None:
        with _cached_app_lock:
            if _cached_app is None:  # Double-check pattern
                from server.app_factory import get_process_app
                _cached_app = get_process_app()
                logger.info("✅ Got process app instance")
    
    return _cached_app

def validate_internal_secret():
    """Validate that request has correct internal secret"""
    received_secret = request.headers.get('X-Internal-Secret')
    if not received_secret or received_secret != INTERNAL_SECRET:
        logger.warning(f"Webhook called without valid internal secret from {request.remote_addr}")
        return False
    return True

@csrf.exempt
@webhook_bp.route('/whatsapp/incoming', methods=['POST'])
def whatsapp_incoming():
    """
    ⚡ ULTRA-FAST WhatsApp webhook - ACK immediately, process in background
    תגובה מהירה לווטסאפ - מחזיר 200 מיד, מעבד ברקע
    """
    try:
        if not validate_internal_secret():
            return jsonify({"error": "unauthorized"}), 401
        
        payload = request.get_json() or {}
        tenant_id = payload.get('tenantId', '1')
        events = payload.get('payload', {})
        messages = events.get('messages', [])
        
        if messages:
            # ⚡ BUILD 112: Check thread capacity before spawning
            global _active_wa_threads
            with _wa_threads_lock:
                if _active_wa_threads >= MAX_CONCURRENT_WA_THREADS:
                    logger.warning(f"⚠️ WhatsApp thread pool full ({_active_wa_threads}/{MAX_CONCURRENT_WA_THREADS}) - processing synchronously")
                    # Process inline to avoid dropping messages
                    _process_whatsapp_fast(tenant_id, messages)
                else:
                    # ⚡ FAST PATH: Spawn thread with tracking
                    _active_wa_threads += 1
                    Thread(target=_process_whatsapp_with_cleanup, args=(tenant_id, messages), daemon=True).start()
        
        # ⚡ ACK immediately - don't wait for processing
        return '', 200
        
    except Exception as e:
        logger.error(f"WhatsApp webhook error: {e}")
        return '', 200  # Still ACK to avoid retries

def _process_whatsapp_with_cleanup(tenant_id: str, messages: list):
    """⚡ Wrapper with thread cleanup"""
    global _active_wa_threads
    try:
        _process_whatsapp_fast(tenant_id, messages)
    except Exception as e:
        logger.error(f"❌ WhatsApp thread crashed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        with _wa_threads_lock:
            _active_wa_threads -= 1
            logger.info(f"✅ WhatsApp thread finished (active: {_active_wa_threads}/{MAX_CONCURRENT_WA_THREADS})")

def _process_whatsapp_fast(tenant_id: str, messages: list):
    """⚡ FAST background processor - typing first, then response"""
    process_start = time.time()
    print(f"🚀 [WA_START] Processing {len(messages)} WhatsApp messages for tenant={tenant_id}")
    logger.info(f"🚀 [WA_START] Processing {len(messages)} messages")
    
    try:
        from server.services.business_resolver import resolve_business_with_fallback
        from server.whatsapp_provider import get_whatsapp_service
        from server.services.ai_service import get_ai_service
        from server.services.customer_intelligence import CustomerIntelligence
        from server.models_sql import WhatsAppMessage, Lead
        from server.db import db
        import re
        
        # ⚡ CRITICAL FIX: Reuse cached app - saves 1-2 seconds per message!
        app_start = time.time()
        app = get_or_create_app()
        logger.info(f"⏱️ get_or_create_app took: {time.time() - app_start:.3f}s")
        
        with app.app_context():
            business_id, status = resolve_business_with_fallback('whatsapp', tenant_id)
            
            # 🔒 SECURITY: Reject unknown tenants instead of processing with wrong business
            if not business_id:
                logger.error(f"❌ REJECTED WhatsApp message: Unknown tenant '{tenant_id}' - no business match")
                logger.error(f"   → Add phone {tenant_id} to Business.phone_e164 or create BusinessContactChannel")
                return  # Silently reject - message already ACKed to WhatsApp
            
            wa_service = get_whatsapp_service()
            ci = CustomerIntelligence(business_id)
            
            for msg in messages:
                jid = None  # Initialize to avoid unbound variable error
                try:
                    # Parse message
                    from_jid = msg.get('key', {}).get('remoteJid', '')
                    phone_number = from_jid.split('@')[0] if '@' in from_jid else from_jid
                    message_content = msg.get('message', {})
                    message_text = (
                        message_content.get('conversation', '') or
                        message_content.get('extendedTextMessage', {}).get('text', '') or
                        ''
                    )
                    
                    if not phone_number or not message_text:
                        continue
                    
                    jid = f"{phone_number}@s.whatsapp.net"
                    typing_started = False
                    
                    try:
                        # ⚡ STEP 1: Send typing indicator immediately (creates instant feel)
                        try:
                            typing_start = time.time()
                            wa_service.send_typing(jid, True)
                            typing_started = True
                            logger.info(f"⏱️ typing took: {time.time() - typing_start:.2f}s")
                        except Exception as e:
                            logger.warning(f"⚠️ Typing indicator failed: {e}")
                        
                        # 🤖 BUILD 150: Check if AI is active for this conversation
                        from server.routes_whatsapp import is_ai_active_for_conversation
                        if not is_ai_active_for_conversation(business_id, phone_number):
                            logger.info(f"🔕 AI is INACTIVE for conversation with {phone_number} - skipping AI response")
                            print(f"🔕 AI is INACTIVE for {phone_number} - customer service handling manually")
                            
                            # Still save the incoming message but don't generate AI response
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
                            
                            # ✅ BUILD 162: Track session for summary even when AI is off
                            try:
                                update_session_activity(
                                    business_id=business_id,
                                    customer_wa_id=phone_number,
                                    direction="in",
                                    provider="baileys"
                                )
                            except Exception as e:
                                logger.warning(f"⚠️ Session tracking failed: {e}")
                            
                            continue  # Skip AI response generation, finally block will stop typing
                        
                        # ⚡ STEP 2: Quick customer/lead lookup (no heavy processing)
                        lookup_start = time.time()
                        customer, lead, _ = ci.find_or_create_customer_from_whatsapp(phone_number, message_text)
                        logger.info(f"⏱️ customer lookup took: {time.time() - lookup_start:.2f}s")
                        
                        # ⚡ STEP 3: Extract last 10 messages for better context (FIXED from 4)
                        previous_messages = []
                        if lead.notes:
                            note_lines = lead.notes.split('\n')
                            # ⚡ FIXED: Get more context - last 10 messages (5 exchanges)
                            for line in note_lines[-10:]:
                                match = re.match(r'\[(WhatsApp|AI|עוזרת|עוזר|סוכן)\s+\d+:\d+:\d+\]:\s*(.+)', line)  # ✅ דינמי - תומך בכל סוג עוזר
                                if match:
                                    sender, content = match.group(1), match.group(2).strip()
                                    # Don't truncate - keep full message
                                    previous_messages.append(f"{'לקוח' if sender == 'WhatsApp' else 'עוזר'}: {content}")  # ✅ עוזר!
                        
                        # ⚡ STEP 4: Agent SDK response with FULL automation (appointments, leads, WhatsApp)
                        ai_start = time.time()
                        print(f"🤖 [WA_AI_START] Calling generate_response_with_agent for business={business_id}")
                        logger.info(f"🤖 [WA_AI_START] Calling AgentKit for business={business_id}, message='{message_text[:50]}...'")
                        
                        ai_service = get_ai_service()
                        ai_response = None  # Initialize to catch any issues
                        
                        try:
                            ai_response = ai_service.generate_response_with_agent(
                                message=message_text,
                                business_id=business_id,
                                customer_phone=phone_number,
                                customer_name=customer.name,
                                context={
                                    'customer_name': customer.name,
                                    'phone_number': phone_number,
                                    'previous_messages': previous_messages,
                                    'channel': 'whatsapp'
                                },
                                channel='whatsapp',
                                is_first_turn=(len(previous_messages) == 0)  # First message = no history
                            )
                            ai_time = time.time() - ai_start
                            
                            # 🔥 CRITICAL CHECK: Verify response is not None/empty
                            if not ai_response:
                                print(f"⚠️ [WA_AI_EMPTY] Agent returned empty response!")
                                ai_response = "סליחה, לא הבנתי. אפשר לנסח מחדש?"
                            
                            print(f"✅ [WA_AI_DONE] Agent response received in {ai_time:.2f}s: '{ai_response[:100]}...'")
                            logger.info(f"⏱️ AI Agent response took: {ai_time:.2f}s")
                        except Exception as ai_error:
                            ai_time = time.time() - ai_start
                            print(f"❌ [WA_AI_ERROR] Agent failed after {ai_time:.2f}s: {ai_error}")
                            logger.error(f"❌ Agent error after {ai_time:.2f}s: {ai_error}")
                            import traceback
                            traceback.print_exc()
                            # Fallback response
                            ai_response = "סליחה, אני לא יכול לעזור לך כרגע. בבקשה נסה שוב או התקשר אלינו."
                        
                        # ⚡ STEP 5: Send response
                        print(f"📤 [WA_SEND_START] About to send response to {jid[:20]}... (len={len(ai_response)})")
                        send_start = time.time()
                        
                        try:
                            send_result = wa_service.send_message(jid, ai_response)
                            print(f"✅ [WA_SEND_OK] Sent successfully: {send_result}")
                        except Exception as send_error:
                            print(f"❌ [WA_SEND_ERROR] Failed to send: {send_error}")
                            logger.error(f"❌ WhatsApp send failed: {send_error}")
                            import traceback
                            traceback.print_exc()
                            send_result = {"status": "error", "error": str(send_error)}
                        logger.info(f"⏱️ send_message took: {time.time() - send_start:.2f}s")
                        logger.info(f"⏱️ TOTAL processing: {time.time() - process_start:.2f}s")
                        
                        # ⚡ STEP 6: Save to DB AFTER response sent (async logging)
                        timestamp = time.strftime('%H:%M:%S')
                        
                        # Save incoming
                        incoming_msg = WhatsAppMessage()
                        incoming_msg.business_id = business_id
                        incoming_msg.to_number = phone_number
                        incoming_msg.direction = 'in'
                        incoming_msg.body = message_text
                        incoming_msg.message_type = 'text'
                        incoming_msg.status = 'received'
                        incoming_msg.provider = 'baileys'
                        db.session.add(incoming_msg)
                        
                        # ✅ BUILD 162: Track session for incoming message
                        try:
                            update_session_activity(
                                business_id=business_id,
                                customer_wa_id=phone_number,
                                direction="in",
                                provider="baileys"
                            )
                        except Exception as e:
                            logger.warning(f"⚠️ Session tracking (in) failed: {e}")
                        
                        # 🔗 n8n: Send incoming message event (async, non-blocking)
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
                            outgoing_msg.direction = 'out'
                            outgoing_msg.body = ai_response
                            outgoing_msg.message_type = 'text'
                            outgoing_msg.status = 'sent'
                            outgoing_msg.provider = send_result.get('provider', 'baileys')
                            outgoing_msg.provider_message_id = send_result.get('message_id')
                            db.session.add(outgoing_msg)
                            
                            # ✅ BUILD 162: Track session for outgoing message
                            try:
                                update_session_activity(
                                    business_id=business_id,
                                    customer_wa_id=phone_number,
                                    direction="out",
                                    provider="baileys"
                                )
                            except Exception as e:
                                logger.warning(f"⚠️ Session tracking (out) failed: {e}")
                            
                            # 🔗 n8n: Send outgoing message event (async, non-blocking)
                            n8n_whatsapp_outgoing(
                                phone=phone_number,
                                message=ai_response,
                                business_id=str(business_id),
                                lead_id=lead.id if lead else None,
                                is_ai=True
                            )
                        
                        # Update lead notes (FIXED: store full messages, not truncated)
                        new_note = f"[WhatsApp {timestamp}]: {message_text}\n[עוזר {timestamp}]: {ai_response}"  # ✅ עוזר!
                        if lead.notes:
                            # Keep only last 50 messages (25 exchanges) to prevent bloat
                            note_lines = lead.notes.split('\n')
                            if len(note_lines) > 50:
                                lead.notes = '\n'.join(note_lines[-50:]) + f"\n{new_note}"
                            else:
                                lead.notes += f"\n{new_note}"
                        else:
                            lead.notes = new_note
                        
                        # ⚡ Background: conversation summary (don't block)
                        Thread(target=_async_conversation_analysis, args=(ci, lead, message_text, phone_number), daemon=True).start()
                        
                        db.session.commit()
                    finally:
                        # 🛑 BUILD 150: ALWAYS stop typing indicator, regardless of success/failure
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
                    
    except Exception as e:
        logger.error(f"WhatsApp background processing failed: {e}")

def _async_conversation_analysis(ci, lead, message_text, phone_number):
    """⚡ Run conversation analysis in parallel - doesn't block response"""
    try:
        from server.db import db
        
        # ⚡ Reuse cached app
        app = get_or_create_app()
        with app.app_context():
            conversation_summary = ci.generate_conversation_summary(
                message_text,
                conversation_data={'source': 'whatsapp', 'phone': phone_number}
            )
            ci.auto_update_lead_status(lead, conversation_summary)
            db.session.commit()
    except Exception as e:
        logger.error(f"Async conversation analysis failed: {e}")

@csrf.exempt
@webhook_bp.route('/whatsapp/status', methods=['POST'])
def whatsapp_status():
    """
    Receive WhatsApp connection status updates from Baileys service
    """
    try:
        if not validate_internal_secret():
            return jsonify({"error": "unauthorized"}), 401
        
        payload = request.get_json() or {}
        tenant_id = payload.get('tenantId', '1')
        connection_status = payload.get('connection', 'unknown')
        push_name = payload.get('pushName', '')
        
        logger.info(f"WhatsApp status - tenant: {tenant_id}, status: {connection_status}, name: {push_name}")
        
        return '', 200
        
    except Exception as e:
        logger.error(f"WhatsApp status webhook error: {e}")
        return '', 200
