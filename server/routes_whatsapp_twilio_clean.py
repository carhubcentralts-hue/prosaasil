"""
WhatsApp Twilio webhook routes - CLEAN VERSION
Handles incoming WhatsApp messages and status updates via Twilio
"""
from flask import Blueprint, request, jsonify
from server.twilio_security import require_twilio_signature
from server.models_sql import WhatsAppMessage
from server.db import db
import logging
from datetime import datetime

whatsapp_twilio_bp = Blueprint("whatsapp_twilio", __name__, url_prefix="/webhook/whatsapp")
logger = logging.getLogger(__name__)

@whatsapp_twilio_bp.post("/incoming")
@require_twilio_signature
def incoming_whatsapp():
    """Handle incoming WhatsApp message from Twilio"""
    try:
        from_number = request.form.get('From', '').replace('whatsapp:', '')
        body = request.form.get('Body', '')
        message_sid = request.form.get('MessageSid', '')
        media_url = request.form.get('MediaUrl0', '')
        
        logger.info("Incoming WhatsApp: From=%s Body=%s", from_number, body[:50] if body else "")
        
        # Save to database (graceful failure)
        try:
            wa_message = WhatsAppMessage()
            wa_message.business_id = 1
            wa_message.to_number = from_number
            wa_message.direction = "in"
            wa_message.body = body
            wa_message.message_type = "media" if media_url else "text"
            wa_message.media_url = media_url
            wa_message.status = "received"
            wa_message.provider = "twilio"
            wa_message.provider_message_id = message_sid
            db.session.add(wa_message)
            db.session.commit()
            logger.info("WhatsApp message saved: %s", message_sid)
        except Exception as db_error:
            logger.error("Database save failed: %s", db_error)
        
        return jsonify({"status": "received"}), 200
        
    except Exception as e:
        logger.error("WhatsApp incoming error: %s", e)
        return jsonify({"status": "received"}), 200

@whatsapp_twilio_bp.post("/status")
@require_twilio_signature
def whatsapp_status_new():
    """Handle WhatsApp message status updates from Twilio"""
    try:
        sid = request.form.get("MessageSid")
        status = request.form.get("MessageStatus")
        
        if not sid or not status:
            logger.warning("Missing MessageSid or MessageStatus")
            return ("", 204)
            
        # Update database (graceful failure)
        try:
            msg = WhatsAppMessage.query.filter_by(provider_message_id=sid).first()
            if msg:
                msg.status = status
                now = datetime.utcnow()
                if status == "delivered":
                    msg.delivered_at = now
                elif status == "read":
                    msg.read_at = now
                db.session.commit()
                logger.info("Status updated: %s -> %s", sid, status)
            else:
                logger.warning("Message not found: %s", sid)
        except Exception as db_error:
            logger.error("Status update failed: %s", db_error)
        
        return ("", 204)
        
    except Exception as e:
        logger.error("WhatsApp status error: %s", e)
        return ("", 204)