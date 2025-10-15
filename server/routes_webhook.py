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

logger = logging.getLogger(__name__)

webhook_bp = Blueprint('webhook', __name__, url_prefix='/webhook')
INTERNAL_SECRET = os.getenv('INTERNAL_SECRET')

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
            # ⚡ FAST PATH: Queue job and return immediately
            Thread(target=_process_whatsapp_fast, args=(tenant_id, messages), daemon=True).start()
        
        # ⚡ ACK immediately - don't wait for processing
        return '', 200
        
    except Exception as e:
        logger.error(f"WhatsApp webhook error: {e}")
        return '', 200  # Still ACK to avoid retries

def _process_whatsapp_fast(tenant_id: str, messages: list):
    """⚡ FAST background processor - typing first, then response"""
    try:
        from server.app_factory import create_app
        from server.services.business_resolver import resolve_business_with_fallback
        from server.whatsapp_provider import get_whatsapp_service
        from server.services.ai_service import generate_ai_response
        from server.services.customer_intelligence import CustomerIntelligence
        from server.models_sql import WhatsAppMessage, Lead
        from server.db import db
        import re
        
        app = create_app()
        with app.app_context():
            business_id, _ = resolve_business_with_fallback('whatsapp', tenant_id)
            wa_service = get_whatsapp_service()
            ci = CustomerIntelligence(business_id)
            
            for msg in messages:
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
                    
                    # ⚡ STEP 1: Send typing indicator immediately (creates instant feel)
                    wa_service.send_typing(jid, True)
                    
                    # ⚡ STEP 2: Quick customer/lead lookup (no heavy processing)
                    customer, lead, _ = ci.find_or_create_customer_from_whatsapp(phone_number, message_text)
                    
                    # ⚡ STEP 3: Extract ONLY last 4 messages for context (not 10)
                    previous_messages = []
                    if lead.notes:
                        note_lines = lead.notes.split('\n')
                        for line in note_lines[-4:]:  # ⚡ Only 4 messages for speed
                            match = re.match(r'\[(WhatsApp|לאה)\s+\d+:\d+:\d+\]:\s*(.+)', line)
                            if match:
                                sender, content = match.group(1), match.group(2).replace('...', '').strip()
                                previous_messages.append(f"{'לקוח' if sender == 'WhatsApp' else 'לאה'}: {content}")
                    
                    # ⚡ STEP 4: Fast AI response with SHORT timeout
                    ai_response = generate_ai_response(
                        message=message_text,
                        business_id=business_id,
                        context={
                            'customer_name': customer.name,
                            'phone_number': phone_number,
                            'previous_messages': previous_messages
                        },
                        channel='whatsapp'
                    )
                    
                    # ⚡ STEP 5: Send response
                    send_result = wa_service.send_message(jid, ai_response)
                    
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
                    
                    # Update lead notes (compact)
                    if lead.notes:
                        lead.notes += f"\n[WhatsApp {timestamp}]: {message_text[:80]}\n[לאה {timestamp}]: {ai_response[:80]}"
                    else:
                        lead.notes = f"[WhatsApp {timestamp}]: {message_text[:80]}\n[לאה {timestamp}]: {ai_response[:80]}"
                    
                    # ⚡ Background: conversation summary (don't block)
                    Thread(target=_async_conversation_analysis, args=(ci, lead, message_text, phone_number), daemon=True).start()
                    
                    db.session.commit()
                    
                except Exception as msg_error:
                    logger.error(f"WhatsApp message processing error: {msg_error}")
                    continue
                    
    except Exception as e:
        logger.error(f"WhatsApp background processing failed: {e}")

def _async_conversation_analysis(ci, lead, message_text, phone_number):
    """⚡ Run conversation analysis in parallel - doesn't block response"""
    try:
        from server.app_factory import create_app
        from server.db import db
        
        app = create_app()
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
