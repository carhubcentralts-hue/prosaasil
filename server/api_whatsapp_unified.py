"""
Unified WhatsApp API - Production Ready
API WhatsApp מאוחד - מוכן לפרודקשן
Includes webhooks, send API, and Hebrew logic
"""
from flask import Blueprint, request, jsonify, current_app
from server.whatsapp_provider import get_whatsapp_service  
from server.models_sql import WhatsAppMessage, Business
from server.db import db
from server.dao_crm import upsert_thread, insert_message
from server.twilio_security import require_twilio_signature
from twilio.twiml.messaging_response import MessagingResponse
from datetime import datetime
import logging

# Single unified WhatsApp blueprint - no more duplicates
whatsapp_unified_bp = Blueprint("whatsapp_unified", __name__)
logger = logging.getLogger(__name__)

@whatsapp_unified_bp.route("/status", methods=["GET"])
def get_status():
    """Get WhatsApp service status"""
    try:
        service = get_whatsapp_service()
        status = service.get_status()
        
        return jsonify({
            "success": True,
            "provider": status.get("provider", "unknown"),
            "ready": status.get("ready", False),
            "connected": status.get("connected", False),
            "configured": status.get("configured", False)
        })
        
    except Exception as e:
        logger.error(f"Error getting WhatsApp status: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@whatsapp_unified_bp.route("/api/whatsapp/send", methods=["POST"])
def send_message():
    """Send WhatsApp message via current provider"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        # 3) WhatsApp outbound תואם מפרט (פוליש)
        to_number = data.get("to")
        message = data.get("message") or data.get("text")  # Support text alias
        provider = data.get("provider")  # Per-request provider
        business_id = data.get("business_id", 1)
        
        if not to_number or not message:
            return jsonify({
                "success": False, 
                "error": "to and message are required"
            }), 400
        
        # Send via service (עם provider per-request לפי הדו"ח)
        service = get_whatsapp_service(provider)
        result = service.send_message(to_number, message)
        
        # Save to database
        message_id = None
        try:
            wa_message = WhatsAppMessage()
            wa_message.business_id = business_id
            wa_message.to_number = to_number
            wa_message.direction = "out/sent"  # שמירה ב-CRM כ-out/sent
            wa_message.body = message
            wa_message.message_type = "text"
            wa_message.status = result.get("status", "sent")  # Default to sent
            wa_message.provider = result.get("provider", provider or "unknown")
            wa_message.provider_message_id = result.get("sid")
            
            db.session.add(wa_message)
            db.session.commit()
            
            message_id = wa_message.id
            logger.info(f"Message sent and saved: {to_number}")
            
        except Exception as db_error:
            logger.error(f"Failed to save sent message: {db_error}")
        
        return jsonify({
            "success": True,
            "result": result,
            "message_id": message_id
        })
        
    except Exception as e:
        logger.error(f"Error sending WhatsApp message: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# WEBHOOKS - מוטמעים מ-routes_whatsapp.py מנוקה
@whatsapp_unified_bp.route("/webhook/whatsapp/twilio", methods=["POST"])
@require_twilio_signature
def wa_in_twilio():
    """Handle Twilio WhatsApp inbound messages"""
    try:
        form = request.form
        from_number = form.get("From", "")
        to_number = form.get("To", "")
        body = form.get("Body", "")
        num_media = int(form.get("NumMedia", "0"))
        media_url = form.get("MediaUrl0") if num_media > 0 else None
        message_sid = form.get("MessageSid", "")

        current_app.logger.info("WA_IN_TWILIO", extra={
            "from": from_number, "to": to_number, "body_len": len(body), "media": bool(media_url)
        })

        # Find/create thread unified
        thread_id = upsert_thread(business_id=1, type_="whatsapp", provider="twilio", peer_number=from_number)

        # Record inbound message - safe types
        insert_message(
            thread_id=thread_id, 
            direction="in", 
            message_type="text" if not media_url else "media",
            content_text=body, 
            media_url=media_url or "", 
            provider_msg_id=message_sid, 
            status="received"
        )

        # Generate Hebrew response
        response_text = handle_whatsapp_logic(body)
        
        # Send auto-response via TwiML
        resp = MessagingResponse()
        resp.message(response_text)
        return str(resp), 200, {'Content-Type': 'text/xml'}
        
    except Exception as e:
        current_app.logger.exception("WA_IN_TWILIO_ERROR")
        return "", 204  # Always return 204 to Twilio

@whatsapp_unified_bp.route("/webhook/whatsapp/baileys", methods=["POST"])
def wa_in_baileys():
    """Handle Baileys WhatsApp inbound messages"""
    try:
        data = request.get_json() or {}
        from_number = data.get("from", "")
        body = data.get("body", "")
        message_id = data.get("id", "")

        # Find/create thread
        thread_id = upsert_thread(business_id=1, type_="whatsapp", provider="baileys", peer_number=from_number)

        # Record message
        insert_message(
            thread_id=thread_id,
            direction="in",
            message_type="text",
            content_text=body,
            media_url="",
            provider_msg_id=message_id,
            status="received"
        )

        # Generate and send Hebrew response
        response_text = handle_whatsapp_logic(body)
        
        return jsonify({
            "success": True,
            "response": response_text
        })
        
    except Exception as e:
        current_app.logger.exception("WA_IN_BAILEYS_ERROR")
        return jsonify({"success": True}), 200

@whatsapp_unified_bp.route("/messages", methods=["GET"])
def get_messages():
    """Get WhatsApp messages with pagination"""
    try:
        # Query parameters
        business_id = request.args.get("business_id", type=int)
        direction = request.args.get("direction")  # "in" or "out"
        status = request.args.get("status")
        
        # Base query
        query = WhatsAppMessage.query
        
        # Apply filters
        if business_id:
            query = query.filter(WhatsAppMessage.business_id == business_id)
        
        if direction:
            query = query.filter(WhatsAppMessage.direction == direction)
        
        if status:
            query = query.filter(WhatsAppMessage.status == status)
        
        # Order by newest first
        query = query.order_by(WhatsAppMessage.created_at.desc())
        
        # Get results with basic pagination
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        
        messages = query.offset((page - 1) * per_page).limit(per_page).all()
        total = query.count()
        
        return jsonify({
            "success": True,
            "messages": [
                {
                    "id": msg.id,
                    "business_id": msg.business_id,
                    "to_number": msg.to_number,
                    "direction": msg.direction,
                    "body": msg.body,
                    "message_type": msg.message_type,
                    "media_url": msg.media_url,
                    "status": msg.status,
                    "provider": msg.provider,
                    "provider_message_id": msg.provider_message_id,
                    "created_at": msg.created_at.isoformat(),
                    "delivered_at": msg.delivered_at.isoformat() if msg.delivered_at else None,
                    "read_at": msg.read_at.isoformat() if msg.read_at else None
                } for msg in messages
            ],
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "pages": (total + per_page - 1) // per_page
            }
        })
        
    except Exception as e:
        logger.error(f"Error fetching WhatsApp messages: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@whatsapp_unified_bp.route("/conversations", methods=["GET"])
def get_conversations():
    """Get WhatsApp conversations grouped by phone number"""
    try:
        business_id = request.args.get("business_id", type=int)
        
        # Base query
        query = db.session.query(WhatsAppMessage)
        
        if business_id:
            query = query.filter(WhatsAppMessage.business_id == business_id)
        
        # Group conversations by to_number and get latest message for each
        subquery = query.order_by(
            WhatsAppMessage.to_number, 
            WhatsAppMessage.created_at.desc()
        ).distinct(WhatsAppMessage.to_number).subquery()
        
        # Get the conversations - simplified approach
        conversations_dict = {}
        all_messages = query.order_by(WhatsAppMessage.created_at.desc()).all()
        
        # Group by phone number, keeping only the latest message
        for msg in all_messages:
            if msg.to_number not in conversations_dict:
                conversations_dict[msg.to_number] = msg
        
        conversations = list(conversations_dict.values())
        
        result = []
        for conv in conversations:
            result.append({
                "phone_number": conv.to_number,
                "last_message": conv.body,
                "last_message_time": conv.created_at.isoformat(),
                "direction": conv.direction,
                "status": conv.status,
                "provider": conv.provider
            })
        
        return jsonify({
            "success": True,
            "conversations": result,
            "total": len(result)
        })
        
    except Exception as e:
        logger.error(f"Error fetching conversations: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@whatsapp_unified_bp.route("/conversation/<phone_number>", methods=["GET"])
def get_conversation_history(phone_number):
    """Get conversation history with specific phone number"""
    try:
        business_id = request.args.get("business_id", type=int)
        
        # Query messages for this conversation
        query = WhatsAppMessage.query.filter(
            WhatsAppMessage.to_number == phone_number
        )
        
        if business_id:
            query = query.filter(WhatsAppMessage.business_id == business_id)
        
        # Order chronologically
        query = query.order_by(WhatsAppMessage.created_at.asc())
        
        # Get results with basic pagination  
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 50, type=int), 100)
        
        messages = query.offset((page - 1) * per_page).limit(per_page).all()
        total = query.count()
        
        return jsonify({
            "success": True,
            "conversation": [
                {
                    "id": msg.id,
                    "direction": msg.direction,
                    "body": msg.body,
                    "message_type": msg.message_type,
                    "media_url": msg.media_url,
                    "status": msg.status,
                    "created_at": msg.created_at.isoformat(),
                    "delivered_at": msg.delivered_at.isoformat() if msg.delivered_at else None,
                    "read_at": msg.read_at.isoformat() if msg.read_at else None
                } for msg in messages
            ],
            "phone_number": phone_number,
            "pagination": {
                "page": page,
                "per_page": per_page, 
                "total": total,
                "pages": (total + per_page - 1) // per_page
            }
        })
        
    except Exception as e:
        logger.error(f"Error fetching conversation history: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

def handle_whatsapp_logic(body: str) -> str:
    """Handle WhatsApp message logic with Hebrew responses"""
    try:
        # Simple Hebrew responses for WhatsApp
        body_lower = body.lower().strip()
        
        if any(word in body_lower for word in ["שלום", "היי", "הלו", "hello", "hi"]):
            return "שלום וברוכים הבאים לשי דירות ומשרדים! איך אוכל לעזור לכם?"
        
        elif any(word in body_lower for word in ["דירה", "דירות", "נכס", "apartment", "house"]):
            return "אשמח לעזור לכם למצוא דירה מתאימה! אתם מחפשים לקניה או להשכרה? באיזה אזור?"
        
        elif any(word in body_lower for word in ["מחיר", "עלות", "כמה", "price", "cost"]):
            return "המחירים משתנים לפי גודל הנכס, מיקום ומצב. נשמח לשלוח לכם הצעות מותאמות אישית!"
        
        elif any(word in body_lower for word in ["תודה", "תודה רבה", "thanks", "thank you"]):
            return "בשמחה! אנחנו כאן לעזור. אל תהססו לפנות אלינו בכל שאלה נוספת."
        
        else:
            return "תודה על הפנייה! אחד הסוכנים שלנו יחזור אליכם בהקדם עם מענה מפורט. נשמח לעזור!"
    
    except Exception as e:
        logger.error(f"WhatsApp logic error: {e}")
        return "תודה על הפנייה! נחזור אליכם בהקדם."
