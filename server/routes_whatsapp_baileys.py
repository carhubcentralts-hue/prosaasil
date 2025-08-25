"""
WhatsApp Baileys webhook handler
"""
import os
from flask import Blueprint, request, jsonify
from server.models_sql import WhatsAppMessage

baileys_bp = Blueprint("baileys_bp", __name__)

@baileys_bp.route("/webhook/whatsapp/baileys", methods=["POST"])
def webhook_baileys():
    """Handle incoming messages from Baileys bridge"""
    try:
        # Security check
        expected_secret = os.getenv("BAILEYS_SECRET", "")
        if expected_secret and request.headers.get("X-BAILEYS-SECRET") != expected_secret:
            return ("", 403)
            
        data = request.get_json() or {}
        from_number = data.get("from", "")
        text = data.get("text", "")
        message_id = data.get("message_id", "")
        
        if not from_number:
            return ("", 204)  # No error, just ignore
            
        print(f"📩 Baileys inbound: {from_number} -> {text[:50]}...")
        
        # Save to CRM
        try:
            # Simple direct save to WhatsApp messages table
            wa_message = WhatsAppMessage()
            wa_message.business_id = 1  # Default business
            wa_message.to_number = from_number
            wa_message.direction = "in/received"
            wa_message.body = text
            wa_message.message_type = "text"
            wa_message.status = "received"
            wa_message.provider = "baileys"
            wa_message.provider_message_id = message_id
            
            from server.models_sql import db
            db.session.add(wa_message)
            db.session.commit()
            
            print(f"✅ Baileys message saved to CRM: {from_number}")
            
        except Exception as db_error:
            print(f"❌ Failed to save Baileys message: {db_error}")
            # Continue anyway - don't fail webhook
            
        return ("", 204)
        
    except Exception as e:
        print(f"❌ Baileys webhook error: {e}")
        return ("", 500)


def send_via_baileys_local(to: str, text: str) -> str:
    """Send message via local Baileys bridge"""
    import requests
    
    try:
        port = int(os.getenv("BAILEYS_PORT", 4001))
        url = f"http://127.0.0.1:{port}/sendMessage"
        
        response = requests.post(url, json={
            "to": to,
            "text": text
        }, timeout=10)
        
        response.raise_for_status()
        result = response.json()
        
        if result.get("ok"):
            return result.get("message_id", "baileys_sent")
        else:
            raise Exception(result.get("error", "Unknown error"))
            
    except Exception as e:
        print(f"❌ Baileys send error: {e}")
        raise e