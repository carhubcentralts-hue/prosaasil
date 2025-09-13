"""
Unified WhatsApp API - Production Ready
API WhatsApp מאוחד - מוכן לפרודקשן
Includes webhooks, send API, and Hebrew logic
"""
from flask import Blueprint, request, jsonify, current_app
from server.whatsapp_provider import get_whatsapp_service  
from server.models_sql import WhatsAppMessage, Business
from server.db import db
from server.dao_crm import upsert_thread, insert_message, get_thread_by_peer
from server.whatsapp_templates import validate_and_route_message, send_template_message, get_template_list
from server.twilio_security import require_twilio_signature
from server.extensions import csrf
from twilio.twiml.messaging_response import MessagingResponse
from datetime import datetime
import logging
import hashlib
import hmac
import os
from flask import abort

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
        
        # Smart routing with 24-hour window validation
        routing_result = validate_and_route_message(
            to_number, message, business_id,
            context={"customer_name": data.get("customer_name"), "area": data.get("area")}
        )
        
        if routing_result["route"] == "template_required":
            # Send template message via Twilio
            result = send_template_message(
                to_number,
                routing_result["template"]["name"],
                routing_result["template_parameters"],
                "twilio"
            )
        else:
            # Send regular message with smart provider routing
            thread_data = routing_result.get("window_status")
            provider_pref = routing_result.get("provider_recommendation", provider)
            service = get_whatsapp_service(provider_pref, thread_data)
            result = service.send_message(to_number, message)
        
        # Save to unified DAO system (no duplicates)
        message_id = None
        try:
            provider_used = result.get("provider", routing_result.get("provider_recommendation", provider or "unknown"))
            
            # Find/create thread for outbound message
            thread_id = upsert_thread(
                business_id=business_id, 
                type_="whatsapp", 
                provider=provider_used, 
                peer_number=to_number
            )
            
            # Record outbound message with idempotency
            message_id = insert_message(
                thread_id=thread_id,
                direction="out",
                message_type="text",
                content_text=message,
                provider_msg_id=result.get("sid"),
                status=result.get("status", "sent")
            )
            
            logger.info(f"Message sent and saved via DAO: {to_number} (thread: {thread_id}, msg: {message_id})")
            
        except Exception as db_error:
            logger.error(f"Failed to save sent message via DAO: {db_error}")
        
        return jsonify({
            "success": True,
            "result": result,
            "message_id": message_id,
            "routing_info": {
                "window_status": routing_result["window_status"],
                "route_used": routing_result["route"],
                "template_used": routing_result.get("template", {}).get("name") if routing_result["route"] == "template_required" else None
            }
        })
        
    except Exception as e:
        logger.error(f"Error sending WhatsApp message: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# WEBHOOKS - מוטמעים מ-routes_whatsapp.py מנוקה
@csrf.exempt
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

@csrf.exempt
@whatsapp_unified_bp.route("/webhook/whatsapp/baileys", methods=["POST"])
def wa_in_baileys():
    """Handle Baileys WhatsApp inbound messages with security validation"""
    try:
        # Security: Validate webhook signature
        webhook_secret = os.environ.get('BAILEYS_WEBHOOK_SECRET', '')
        if webhook_secret:
            received_secret = request.headers.get('X-BAILEYS-SECRET')
            if not received_secret or received_secret != webhook_secret:
                current_app.logger.warning("Baileys webhook secret validation failed")
                abort(401)
        
        data = request.get_json() or {}
        
        # Enhanced payload validation
        from_number = data.get("from", "").replace("@c.us", "")
        body = data.get("body", "")
        message_id = data.get("id", "")
        message_type = data.get("type", "text")
        media_url = data.get("mediaUrl", "")
        
        if not from_number or not message_id:
            current_app.logger.warning("Invalid Baileys webhook payload")
            return jsonify({"success": False, "error": "Invalid payload"}), 400

        current_app.logger.info("WA_IN_BAILEYS", extra={
            "from": from_number, "body_len": len(body), "type": message_type
        })

        # Find/create thread
        thread_id = upsert_thread(business_id=1, type_="whatsapp", provider="baileys", peer_number=from_number)

        # Record message with enhanced type detection
        insert_message(
            thread_id=thread_id,
            direction="in",
            message_type=message_type,
            content_text=body,
            media_url=media_url,
            provider_msg_id=message_id,
            status="received"
        )

        # Generate Hebrew response
        response_text = handle_whatsapp_logic(body)
        
        # Send auto-response via Baileys (not through API to avoid loops)
        if response_text and len(response_text.strip()) > 0:
            # Queue response for Baileys to send
            _queue_baileys_response(from_number, response_text)
        
        return jsonify({
            "success": True,
            "response": response_text
        })
        
    except Exception as e:
        current_app.logger.exception("WA_IN_BAILEYS_ERROR")
        return jsonify({"success": True}), 200

@whatsapp_unified_bp.route("/api/whatsapp/messages", methods=["GET"])
def get_messages():
    """Get WhatsApp messages with pagination - UNIFIED DAO VERSION"""
    try:
        # Query parameters
        business_id = request.args.get("business_id", type=int)
        direction = request.args.get("direction")  # "in" or "out"
        status = request.args.get("status")
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        
        # Use DAO instead of WhatsAppMessage for consistency
        from server.dao_crm import get_messages_by_business
        messages_data = get_messages_by_business(
            business_id=business_id or 1,  # Default to business 1 if not specified
            direction=direction,
            status=status,
            page=page,
            per_page=per_page
        )
        
        return jsonify({
            "success": True,
            "messages": messages_data.get("messages", []),
            "pagination": messages_data.get("pagination", {})
        })
        
    except Exception as e:
        logger.error(f"Error fetching WhatsApp messages: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@whatsapp_unified_bp.route("/api/whatsapp/conversations", methods=["GET"])
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

@whatsapp_unified_bp.route("/api/whatsapp/conversation/<phone_number>", methods=["GET"])
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
            "id": len(messages),  # Mock conversation ID
            "phone_number": phone_number,
            "messages": [
                {
                    "id": str(msg.id),
                    "direction": msg.direction,
                    "content_text": msg.body,  # Map body to content_text
                    "sent_at": msg.created_at.isoformat(),  # Map created_at to sent_at
                    "status": msg.status,
                    "provider": msg.provider
                } for msg in messages
            ],
            "total_messages": total,
            "last_message_at": messages[-1].created_at.isoformat() if messages else None
        })
        
    except Exception as e:
        logger.error(f"Error fetching conversation history: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

def _verify_baileys_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify Baileys webhook signature"""
    try:
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        # Support both 'sha256=' prefixed and raw hex signatures
        if signature.startswith('sha256='):
            signature = signature[7:]
        
        return hmac.compare_digest(expected_signature, signature)
    except Exception as e:
        logger.error(f"Signature verification error: {e}")
        return False

def _queue_baileys_response(to: str, text: str):
    """Queue response message for Baileys to send (avoid webhook loops)"""
    try:
        import requests
        import os
        
        baileys_url = os.environ.get('BAILEYS_OUTBOUND_URL', 'http://localhost:3001')
        
        payload = {
            "to": to,
            "type": "text",
            "text": text,
            "webhook_response": True  # Flag to prevent loops
        }
        
        # Fire and forget - don't wait for response
        requests.post(
            f"{baileys_url}/send",
            json=payload,
            timeout=2
        )
        
        logger.info(f"Queued Baileys response to {to}")
        
    except Exception as e:
        logger.error(f"Failed to queue Baileys response: {e}")

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

@whatsapp_unified_bp.route("/api/whatsapp/templates", methods=["GET"])
def get_templates():
    """Get list of approved WhatsApp templates"""
    try:
        templates = get_template_list()
        return jsonify({
            "success": True,
            "templates": templates
        })
    except Exception as e:
        logger.error(f"Error getting templates: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@whatsapp_unified_bp.route("/api/whatsapp/window-check", methods=["POST"])
def check_messaging_window():
    """Check 24-hour messaging window status for a number"""
    try:
        data = request.get_json()
        if not data or not data.get("to"):
            return jsonify({"success": False, "error": "Phone number required"}), 400
        
        from server.whatsapp_templates import window_manager
        business_id = data.get("business_id", 1)
        window_status = window_manager.check_messaging_window(business_id, data["to"])
        
        return jsonify({
            "success": True,
            "window_status": window_status
        })
        
    except Exception as e:
        logger.error(f"Error checking messaging window: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
