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
                        # Find business by tenant_id (convert from business_X format)
                        business_id = int(tenant_id.replace('business_', '')) if 'business_' in tenant_id else int(tenant_id)
                        business = Business.query.get(business_id)
                        
                        if not business:
                            logger.error(f"Business not found for tenant {tenant_id}")
                            return
                        
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
                                
                                # Update lead notes with WhatsApp message
                                timestamp = time.strftime('%H:%M:%S')
                                if lead.notes:
                                    lead.notes += f"\n[WhatsApp {timestamp}]: {message_text[:100]}..."
                                else:
                                    lead.notes = f"[WhatsApp {timestamp}]: {message_text[:100]}..."
                                
                                db.session.commit()
                                
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