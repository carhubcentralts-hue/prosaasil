"""
WhatsApp Twilio webhook routes
Handles incoming WhatsApp messages and status updates via Twilio
"""
from flask import Blueprint, request, jsonify
from server.twilio_security import require_twilio_signature
from server.models_sql import WhatsAppMessage
from server.db import db
from server.whatsapp_provider import get_provider
import logging

whatsapp_twilio_bp = Blueprint("whatsapp_twilio", __name__, url_prefix="/webhook/whatsapp")
logger = logging.getLogger(__name__)

@whatsapp_twilio_bp.post("/incoming")
@require_twilio_signature
def incoming_whatsapp():
    """Handle incoming WhatsApp message from Twilio"""
    try:
        # Get message data from Twilio
        from_number = request.form.get('From', '').replace('whatsapp:', '')
        to_number = request.form.get('To', '').replace('whatsapp:', '')
        body = request.form.get('Body', '')
        message_sid = request.form.get('MessageSid', '')
        media_url = request.form.get('MediaUrl0', '')
        media_content_type = request.form.get('MediaContentType0', '')
        
        # Determine message type
        message_type = "media" if media_url else "text"
        
        # Save to database
        try:
            wa_message = WhatsAppMessage()
            wa_message.business_id = 1  # Default business for now
            wa_message.to_number = from_number  # From the sender's perspective
            wa_message.direction = "in"
            wa_message.body = body
            wa_message.message_type = message_type
            wa_message.media_url = media_url
            wa_message.status = "received"
            wa_message.provider = "twilio"
            wa_message.provider_message_id = message_sid
            db.session.add(wa_message)
            db.session.commit()
            logger.info("Saved incoming WhatsApp message from %s", from_number)
        except Exception as db_error:
            logger.error("Failed to save WhatsApp message: %s", db_error)
        
        # Process message (AI response, etc.)
        # TODO: Add AI processing logic here
        
        return jsonify({"status": "received"}), 200
        
    except Exception as e:
        logger.error("Error processing incoming WhatsApp: %s", e)
        # Always return success to Twilio to avoid retries
        return jsonify({"status": "received"}), 200

@whatsapp_twilio_bp.post("/status")
@require_twilio_signature 
def whatsapp_status_new():
    """Handle WhatsApp message status updates from Twilio"""
    try:
        from datetime import datetime
        
        sid = request.form.get("MessageSid")
        status = request.form.get("MessageStatus")  # queued/sent/delivered/read/failed/undelivered
        
        if not sid or not status:
            logger.warning("Missing MessageSid or MessageStatus in webhook")
            return ("missing sid/status", 400)
            
        # Update message status in database
        msg = WhatsAppMessage.query.filter_by(provider_message_id=sid).first()
        now = datetime.utcnow()
        
        if msg:
            msg.status = status
            if status == "delivered":
                msg.delivered_at = now
            elif status == "read":
                msg.read_at = now
            db.session.commit()
            logger.info("Updated WhatsApp status: %s -> %s", sid, status)
        else:
            logger.warning("WhatsApp message not found: %s", sid)
        
        # Return success to Twilio
        return ("", 204)
        
    except Exception as e:
        logger.error("Error updating WhatsApp status: %s", e)
        # Always return success to avoid retries
        return ("", 204)
        
        if msg:
            msg.status = status
            if status == "delivered" and hasattr(msg, 'delivered_at'):
                msg.delivered_at = now
            if status == "read" and hasattr(msg, 'read_at'):
                msg.read_at = now
            db.session.commit()
            logger.info("Updated WhatsApp message status: %s -> %s", sid, status)
        else:
            logger.warning("WhatsApp message not found for SID: %s", sid)
            
        return ("", 204)
        


# OLD FUNCTION REMOVED TO AVOID DUPLICATES