"""
WhatsApp Webhook Routes - Receive incoming events from Baileys service
מסלולי Webhook של WhatsApp - קבלת אירועים נכנסים מ-Baileys service
"""
import os
import logging
from flask import Blueprint, request, jsonify
from server.extensions import csrf

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

@csrf.exempt  # Bypass CSRF for internal webhook
@webhook_bp.route('/whatsapp/incoming', methods=['POST'])
def whatsapp_incoming():
    """
    Receive incoming WhatsApp events from Baileys service
    קבלת אירועי WhatsApp נכנסים מ-Baileys service
    """
    try:
        # Validate internal secret
        if not validate_internal_secret():
            return jsonify({"error": "unauthorized"}), 401
        
        # Get payload
        payload = request.get_json() or {}
        tenant_id = payload.get('tenantId', '1')
        events = payload.get('payload', {})
        
        logger.info(f"WhatsApp incoming webhook - tenant: {tenant_id}, events: {len(events.get('messages', []))}")
        
        # ✨ CUSTOMER INTELLIGENCE: Process incoming WhatsApp messages
        messages = events.get('messages', [])
        
        if messages:
            # Process in background to not block webhook response
            from threading import Thread
            
            def process_whatsapp_messages():
                try:
                    from server.app_factory import create_app
                    from server.services.customer_intelligence import CustomerIntelligence
                    from server.db import db
                    from server.models_sql import Business
                    import time
                    
                    app = create_app()
                    with app.app_context():
                        # ✅ BUILD 91: Multi-tenant - חכם! זיהוי business לפי tenantId
                        from server.services.business_resolver import resolve_business_with_fallback
                        business_id, status = resolve_business_with_fallback('whatsapp', tenant_id)
                        
                        if status == 'found':
                            logger.info(f"✅ Resolved business_id={business_id} from tenantId={tenant_id}")
                        else:
                            logger.warning(f"⚠️ Using fallback business_id={business_id} ({status}) for tenantId={tenant_id}")
                        ci = CustomerIntelligence(business_id)
                        
                        for msg in messages:
                            try:
                                # Parse WhatsApp message
                                from_jid = msg.get('key', {}).get('remoteJid', '')
                                phone_number = from_jid.split('@')[0] if '@' in from_jid else from_jid
                                
                                # Get message text
                                message_content = msg.get('message', {})
                                message_text = (
                                    message_content.get('conversation', '') or
                                    message_content.get('extendedTextMessage', {}).get('text', '') or
                                    '[Media/Unsupported message]'
                                )
                                
                                if not phone_number or not message_text or message_text == '[Media/Unsupported message]':
                                    continue
                                
                                logger.info(f"Processing WhatsApp message from {phone_number}: {message_text[:50]}...")
                                
                                # ✨ Create/update customer and lead using Customer Intelligence
                                customer, lead, was_created = ci.find_or_create_customer_from_whatsapp(
                                    phone_number, message_text
                                )
                                
                                # ✨ Generate conversation summary
                                conversation_summary = ci.generate_conversation_summary(
                                    message_text,
                                    conversation_data={'source': 'whatsapp', 'phone': phone_number}
                                )
                                
                                # ✨ Auto-update lead status based on message content
                                new_status = ci.auto_update_lead_status(lead, conversation_summary)
                                
                                # ✅ Save incoming message to WhatsAppMessage table
                                from server.models_sql import WhatsAppMessage
                                
                                incoming_msg = WhatsAppMessage()
                                incoming_msg.business_id = business_id
                                incoming_msg.to_number = phone_number
                                incoming_msg.direction = 'in'
                                incoming_msg.body = message_text
                                incoming_msg.message_type = 'text'
                                incoming_msg.status = 'received'
                                incoming_msg.provider = 'baileys'
                                db.session.add(incoming_msg)
                                
                                # Update lead notes with WhatsApp message
                                timestamp = time.strftime('%H:%M:%S')
                                if lead.notes:
                                    lead.notes += f"\n[WhatsApp {timestamp}]: {message_text[:100]}..."
                                else:
                                    lead.notes = f"[WhatsApp {timestamp}]: {message_text[:100]}..."
                                
                                db.session.commit()
                                
                                # ✅ Extract previous messages from lead notes for conversation memory
                                previous_messages = []
                                if lead.notes:
                                    import re
                                    # חילוץ הודעות קודמות מה-notes (פורמט: [WhatsApp HH:MM:SS]: message או [לאה HH:MM:SS]: message)
                                    note_lines = lead.notes.split('\n')
                                    for line in note_lines[-10:]:  # רק 10 הודעות אחרונות
                                        # Match: [WhatsApp 18:49:50]: דירה ברמלה...
                                        match = re.match(r'\[(WhatsApp|לאה)\s+\d+:\d+:\d+\]:\s*(.+)', line)
                                        if match:
                                            sender = match.group(1)
                                            content = match.group(2).replace('...', '').strip()
                                            if sender == 'WhatsApp':
                                                previous_messages.append(f"לקוח: {content}")
                                            else:  # לאה
                                                previous_messages.append(f"לאה: {content}")
                                
                                # ✨ Generate AI response using WhatsApp prompt
                                from server.services.ai_service import generate_ai_response
                                from server.whatsapp_provider import get_whatsapp_service
                                
                                try:
                                    ai_response = generate_ai_response(
                                        message=message_text,
                                        business_id=business_id,
                                        context={
                                            'customer_name': customer.name,
                                            'phone_number': phone_number,
                                            'source': 'whatsapp',
                                            'previous_messages': previous_messages  # ✅ הוספת היסטוריית שיחה!
                                        },
                                        channel='whatsapp'  # ✅ Use WhatsApp prompt
                                    )
                                    
                                    # Send AI response back to customer
                                    wa_service = get_whatsapp_service()
                                    send_result = wa_service.send_message(f"{phone_number}@s.whatsapp.net", ai_response)
                                    
                                    if send_result.get('status') == 'sent':
                                        logger.info(f"✅ AI response sent to {phone_number}: {ai_response[:50]}...")
                                        
                                        # ✅ Save AI response to WhatsAppMessage table
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
                                        
                                        # Add AI response to lead notes
                                        if lead.notes:
                                            lead.notes += f"\n[לאה {timestamp}]: {ai_response[:100]}..."
                                        else:
                                            lead.notes = f"[לאה {timestamp}]: {ai_response[:100]}..."
                                        db.session.commit()
                                    else:
                                        logger.warning(f"⚠️ Failed to send AI response: {send_result}")
                                        
                                except Exception as ai_error:
                                    logger.error(f"❌ AI response failed: {ai_error}")
                                
                                # Detailed logging
                                logger.info(f"🎯 WhatsApp AI Processing: Customer {customer.name} ({'NEW' if was_created else 'EXISTING'})")
                                logger.info(f"📱 WhatsApp Intent: {conversation_summary.get('intent', 'N/A')}")
                                logger.info(f"📊 WhatsApp Status: {new_status}")
                                logger.info(f"⚡ WhatsApp Next Action: {conversation_summary.get('next_action', 'N/A')}")
                                
                            except Exception as msg_error:
                                logger.error(f"Failed to process WhatsApp message: {msg_error}")
                                continue
                                
                except Exception as e:
                    logger.error(f"WhatsApp background processing failed: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Start background processing
            Thread(target=process_whatsapp_messages, daemon=True).start()
        
        return '', 204  # Acknowledge receipt immediately
        
    except Exception as e:
        logger.error(f"WhatsApp incoming webhook error: {e}")
        return jsonify({"error": "processing_failed"}), 500

@csrf.exempt  # Bypass CSRF for internal webhook  
@webhook_bp.route('/whatsapp/status', methods=['POST'])
def whatsapp_status():
    """
    Receive WhatsApp connection status updates from Baileys service
    קבלת עדכוני סטטוס חיבור WhatsApp מ-Baileys service  
    """
    try:
        # Validate internal secret
        if not validate_internal_secret():
            return jsonify({"error": "unauthorized"}), 401
        
        # Get payload
        payload = request.get_json() or {}
        tenant_id = payload.get('tenantId', '1')
        connection_status = payload.get('connection', 'unknown')
        push_name = payload.get('pushName', '')
        
        logger.info(f"WhatsApp status update - tenant: {tenant_id}, status: {connection_status}, name: {push_name}")
        
        # TODO: Update database with connection status
        # This is where you would:
        # 1. Update business WhatsApp connection status
        # 2. Notify UI of connection changes
        # 3. Log connection events for monitoring
        
        return '', 204  # Acknowledge receipt
        
    except Exception as e:
        logger.error(f"WhatsApp status webhook error: {e}")
        return jsonify({"error": "processing_failed"}), 500