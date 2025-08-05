"""
WhatsApp Routes - Hebrew AI CRM System
מסלולי WhatsApp למערכת CRM עברית
Support for both Baileys and Twilio WhatsApp API
"""

from flask import request, jsonify, Response
from app import app, db
from models import Business, WhatsAppConversation, WhatsAppMessage, Customer
import json
import logging
from datetime import datetime
import openai
import os

logger = logging.getLogger(__name__)

@app.route("/whatsapp/webhook", methods=["POST", "GET"])
def whatsapp_webhook():
    """
    Webhook for Twilio WhatsApp Business API
    מטפל בהודעות WhatsApp מ-Twilio
    """
    if request.method == "GET":
        # Webhook verification
        return jsonify({"status": "ok"})
        
    try:
        # Get WhatsApp message data from Twilio
        from_number = request.form.get('From', '').replace('whatsapp:', '')
        to_number = request.form.get('To', '').replace('whatsapp:', '')
        message_body = request.form.get('Body', '')
        message_sid = request.form.get('MessageSid')
        media_url = request.form.get('MediaUrl0')  # For media messages
        
        logger.info(f"WhatsApp message from {from_number}: {message_body}")
        
        # Find business by WhatsApp number
        business = Business.query.filter_by(whatsapp_number=to_number).first()
        if not business or not business.whatsapp_enabled:
            logger.warning(f"Business not found or WhatsApp disabled for {to_number}")
            return jsonify({'error': 'Business not configured for WhatsApp'}), 404
            
        # Find or create customer
        customer = Customer.query.filter_by(phone=from_number, business_id=business.id).first()
        if not customer:
            customer = Customer(
                name=f"לקוח WhatsApp {from_number[-4:]}",
                phone=from_number,
                business_id=business.id,
                source='whatsapp'
            )
            db.session.add(customer)
            db.session.flush()  # Get customer ID
            
        # Find or create WhatsApp conversation
        conversation = WhatsAppConversation.query.filter_by(
            business_id=business.id,
            customer_number=from_number
        ).first()
        
        if not conversation:
            conversation = WhatsAppConversation(
                business_id=business.id,
                customer_number=from_number
            )
            db.session.add(conversation)
            db.session.flush()
            
        # Save incoming message
        incoming_message = WhatsAppMessage(
            conversation_id=conversation.id,
            business_id=business.id,
            from_number=from_number,
            to_number=to_number,
            message_body=message_body,
            direction='inbound',
            status='received',
            message_sid=message_sid,
            media_url=media_url
        )
        db.session.add(incoming_message)
        
        # Update customer stats
        customer.total_messages = (customer.total_messages or 0) + 1
        customer.last_contact_date = datetime.utcnow()
        
        # Generate AI response if enabled
        if hasattr(business, 'ai_prompt') and business.ai_prompt and message_body:
            ai_response = generate_whatsapp_ai_response(message_body, business)
            
            # Save AI response message
            response_message = WhatsAppMessage(
                conversation_id=conversation.id,
                business_id=business.id,
                from_number=to_number,
                to_number=from_number,
                message_body=ai_response,
                direction='outbound',
                status='sent'
            )
            db.session.add(response_message)
            
            db.session.commit()
            
            # Send response via Twilio
            send_twilio_whatsapp_message(from_number, ai_response)
            
        else:
            db.session.commit()
            
        return jsonify({'status': 'processed'})
        
    except Exception as e:
        logger.error(f"Error processing WhatsApp webhook: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route("/whatsapp/baileys", methods=["POST"])
def baileys_webhook():
    """
    Webhook for Baileys WhatsApp Web integration
    מטפל בהודעות מ-Baileys
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        message_type = data.get('type')
        
        if message_type == 'message':
            # Handle incoming message from Baileys
            from_number = data.get('from', '').replace('@s.whatsapp.net', '')
            message_body = data.get('message', {}).get('conversation', '')
            message_id = data.get('id')
            
            # For group messages, extract user
            if '@g.us' in data.get('from', ''):
                from_number = data.get('participant', '').replace('@s.whatsapp.net', '')
                
            logger.info(f"Baileys message from {from_number}: {message_body}")
            
            # Process similar to Twilio webhook
            # Find business (for Baileys, we use the first active business)
            business = Business.query.filter_by(whatsapp_enabled=True, is_active=True).first()
            
            if not business:
                logger.warning("No active business with WhatsApp enabled")
                return jsonify({'error': 'No active business'}), 404
                
            # Find or create customer
            customer = Customer.query.filter_by(phone=from_number, business_id=business.id).first()
            if not customer:
                customer = Customer(
                    name=f"לקוח Baileys {from_number[-4:]}",
                    phone=from_number,
                    business_id=business.id,
                    source='whatsapp'
                )
                db.session.add(customer)
                db.session.flush()
                
            # Find or create conversation
            conversation = WhatsAppConversation.query.filter_by(
                business_id=business.id,
                customer_phone=from_number
            ).first()
            
            if not conversation:
                conversation = WhatsAppConversation(
                    business_id=business.id,
                    customer_phone=from_number,
                    customer_name=customer.name,
                    platform='baileys'
                )
                db.session.add(conversation)
                db.session.flush()
                
            # Save message
            incoming_message = WhatsAppMessage(
                conversation_id=conversation.id,
                business_id=business.id,
                sender_phone=from_number,
                message_text=message_body,
                message_type='text',
                direction='incoming',
                platform='baileys',
                external_id=message_id
            )
            db.session.add(incoming_message)
            
            # Update customer
            customer.total_messages = (customer.total_messages or 0) + 1
            customer.last_contact_date = datetime.utcnow()
            
            # Generate AI response
            if business.system_prompt and message_body:
                ai_response = generate_whatsapp_ai_response(message_body, business)
                
                response_message = WhatsAppMessage(
                    conversation_id=conversation.id,
                    business_id=business.id,
                    sender_phone=business.whatsapp_number or business.phone_number,
                    message_text=ai_response,
                    message_type='text',
                    direction='outgoing',
                    platform='baileys'
                )
                db.session.add(response_message)
                
                db.session.commit()
                
                # Send response via Baileys
                return jsonify({
                    'action': 'send_message',
                    'to': data.get('from'),
                    'message': ai_response
                })
            else:
                db.session.commit()
                
        return jsonify({'status': 'processed'})
        
    except Exception as e:
        logger.error(f"Error processing Baileys webhook: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

def generate_whatsapp_ai_response(message_text, business):
    """יוצר תגובת AI עבור הודעת WhatsApp"""
    try:
        if len(message_text.strip()) < 2:
            return "אני לא הבנתי את ההודעה. תוכל לכתוב שוב?"
            
        # Use business-specific WhatsApp greeting or system prompt
        system_prompt = business.whatsapp_greeting or business.system_prompt or "אתה עוזר וירטואלי עבור עסק בישראל דרך WhatsApp."
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message_text}
        ]
        
        import openai
        client = openai.OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
        response = client.chat.completions.create(
            model="gpt-4o",  # the newest OpenAI model is "gpt-4o" which was released May 13, 2024. do not change this unless explicitly requested by the user
            messages=messages,
            max_tokens=200,
            temperature=0.7
        )
        
        ai_response = response.choices[0].message.content.strip()
        return ai_response
        
    except Exception as e:
        logger.error(f"Error generating WhatsApp AI response: {str(e)}")
        return "סליחה, יש לי בעיה טכנית. איך אוכל לעזור?"

def send_twilio_whatsapp_message(to_number, message):
    """שולח הודעת WhatsApp דרך Twilio"""
    try:
        from twilio.rest import Client
        
        client = Client(
            os.environ.get('TWILIO_ACCOUNT_SID'),
            os.environ.get('TWILIO_AUTH_TOKEN')
        )
        
        message = client.messages.create(
            body=message,
            from_=f"whatsapp:{os.environ.get('TWILIO_WHATSAPP_NUMBER')}",
            to=f"whatsapp:{to_number}"
        )
        
        logger.info(f"WhatsApp message sent via Twilio: {message.sid}")
        return message.sid
        
    except Exception as e:
        logger.error(f"Error sending Twilio WhatsApp message: {str(e)}")
        return None

@app.route("/whatsapp/send", methods=["POST"])
def send_whatsapp_message():
    """
    API endpoint to send WhatsApp message
    נקודת קצה לשליחת הודעת WhatsApp
    """
    try:
        data = request.get_json()
        
        to_number = data.get('to')
        message = data.get('message')
        business_id = data.get('business_id')
        
        if not all([to_number, message, business_id]):
            return jsonify({'error': 'Missing required fields'}), 400
            
        # Verify business has WhatsApp enabled
        business = Business.query.get(business_id)
        if not business or not business.whatsapp_enabled:
            return jsonify({'error': 'Business not configured for WhatsApp'}), 403
            
        # Find or create conversation
        conversation = WhatsAppConversation.query.filter_by(
            business_id=business.id,
            customer_phone=to_number
        ).first()
        
        if not conversation:
            customer = Customer.query.filter_by(phone=to_number, business_id=business.id).first()
            conversation = WhatsAppConversation(
                business_id=business.id,
                customer_phone=to_number,
                customer_name=customer.name if customer else f"לקוח {to_number[-4:]}",
                platform='manual'
            )
            db.session.add(conversation)
            db.session.flush()
            
        # Save outgoing message
        outgoing_message = WhatsAppMessage(
            conversation_id=conversation.id,
            business_id=business.id,
            sender_phone=business.whatsapp_number or business.phone_number,
            message_text=message,
            message_type='text',
            direction='outgoing',
            platform='manual'
        )
        db.session.add(outgoing_message)
        db.session.commit()
        
        # Try to send via Twilio first, fallback to Baileys
        message_sid = send_twilio_whatsapp_message(to_number, message)
        
        if message_sid:
            outgoing_message.external_id = message_sid
            db.session.commit()
            return jsonify({'status': 'sent', 'platform': 'twilio', 'message_id': message_sid})
        else:
            # TODO: Implement Baileys sending
            return jsonify({'status': 'queued', 'platform': 'baileys'})
            
    except Exception as e:
        logger.error(f"Error sending WhatsApp message: {str(e)}")
        return jsonify({'error': 'Failed to send message'}), 500

@app.route("/whatsapp/conversations/<int:business_id>")
def get_whatsapp_conversations(business_id):
    """
    Get WhatsApp conversations for a business
    מקבל שיחות WhatsApp לעסק
    """
    try:
        business = Business.query.get(business_id)
        if not business or not business.whatsapp_enabled:
            return jsonify({'error': 'Business not found or WhatsApp disabled'}), 404
            
        conversations = WhatsAppConversation.query.filter_by(business_id=business_id).all()
        
        conversations_data = []
        for conv in conversations:
            last_message = WhatsAppMessage.query.filter_by(conversation_id=conv.id).order_by(WhatsAppMessage.timestamp.desc()).first()
            
            conversations_data.append({
                'id': conv.id,
                'customer_phone': conv.customer_phone,
                'customer_name': conv.customer_name,
                'platform': conv.platform,
                'last_message': last_message.message_text if last_message else None,
                'last_message_time': last_message.timestamp.isoformat() if last_message else None,
                'message_count': WhatsAppMessage.query.filter_by(conversation_id=conv.id).count()
            })
            
        return jsonify({
            'conversations': conversations_data,
            'total': len(conversations_data)
        })
        
    except Exception as e:
        logger.error(f"Error getting WhatsApp conversations: {str(e)}")
        return jsonify({'error': 'Failed to get conversations'}), 500