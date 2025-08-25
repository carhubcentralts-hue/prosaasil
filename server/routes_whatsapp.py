"""
4) WhatsApp webhook routes - Enhanced for unified CRM
"""
from flask import Blueprint, request, current_app
from twilio.twiml.messaging_response import MessagingResponse
from server.dao_crm import upsert_thread, insert_message
from server.twilio_security import require_twilio_signature
import logging
import hmac
import hashlib
import os
import json

log = logging.getLogger(__name__)

whatsapp_bp = Blueprint("whatsapp", __name__, url_prefix="/webhook/whatsapp")

@whatsapp_bp.route("/twilio", methods=["POST"])
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
        message_sid = form.get("MessageSid")

        current_app.logger.info("WA_IN_TWILIO", extra={
            "from": from_number, "to": to_number, "body_len": len(body), "media": bool(media_url)
        })

        # Find/create thread unified
        thread_id = upsert_thread(business_id=1, type_="whatsapp", provider="twilio", peer_number=from_number)

        # Record inbound message
        insert_message(
            thread_id=thread_id, 
            direction="in", 
            message_type="text" if not media_url else "media",
            content_text=body, 
            media_url=media_url, 
            provider_msg_id=message_sid, 
            status="received"
        )

        return "", 204
        
    except Exception as e:
        current_app.logger.exception("WA_IN_TWILIO_ERROR")
        return "", 204  # Always return 204 to Twilio

@whatsapp_bp.route("/baileys", methods=["POST"])
def wa_in_baileys():
    """Handle Baileys WhatsApp inbound messages with HMAC verification"""
    try:
        secret = os.getenv("WA_SHARED_SECRET", "")
        raw = request.get_data() or b""
        sig = request.headers.get("X-BAILEYS-SIGNATURE", "")
        good = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        
        if not secret or sig != good:
            current_app.logger.warning("WA_BAILEYS_BAD_SIG")
            return "", 403

        ev = request.get_json(force=True, silent=True) or {}
        from_number = ev.get("from", "")
        text = ev.get("text", "")
        media_url = ev.get("media_url")
        provider_msg_id = ev.get("provider_msg_id")

        current_app.logger.info("WA_IN_BAILEYS", extra={
            "from": from_number, "text_len": len(text), "media": bool(media_url)
        })

        # Find/create thread unified
        thread_id = upsert_thread(business_id=1, type_="whatsapp", provider="baileys", peer_number=from_number)

        # Record inbound message
        insert_message(
            thread_id=thread_id, 
            direction="in", 
            message_type="text" if not media_url else "media",
            content_text=text, 
            media_url=media_url, 
            provider_msg_id=provider_msg_id, 
            status="received"
        )

        return "", 204
        
    except Exception as e:
        current_app.logger.exception("WA_IN_BAILEYS_ERROR")
        return "", 204

def register_whatsapp_routes(app):
    """Register WhatsApp webhook routes - LEGACY COMPATIBILITY"""
    
    @app.route("/webhook/whatsapp/inbound", methods=["POST"])
    def whatsapp_inbound():
        """Handle incoming WhatsApp messages"""
        try:
            from_ = request.form.get("From", "")      # whatsapp:+972...
            body = request.form.get("Body", "")
            to_ = request.form.get("To", "")
            
            log.info("WhatsApp inbound message", extra={
                "from": from_,
                "to": to_,
                "body_length": len(body)
            })
            
            # Insert interaction to database
            try:
                
                conn = psycopg2.connect(os.getenv('DATABASE_URL'))
                cur = conn.cursor()
                
                # Insert WhatsApp interaction
                cur.execute("""
                    INSERT INTO call_log (call_sid, from_number, to_number, business_id, created_at, call_status, transcription)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    f"whatsapp_{int(datetime.datetime.now().timestamp())}", 
                    from_, 
                    to_, 
                    1,  # business_id
                    datetime.datetime.now(), 
                    'whatsapp_received', 
                    f"WhatsApp message: {body}"
                ))
                
                conn.commit()
                cur.close()
                conn.close()
                
                log.info("WhatsApp message saved to database")
                
            except Exception as db_error:
                log.error("Database error: %s", db_error)
            
            # Handle WhatsApp logic
            reply = handle_whatsapp_logic(body)
            
            # Insert reply to database
            try:
                conn = psycopg2.connect(os.getenv('DATABASE_URL'))
                cur = conn.cursor()
                
                cur.execute("""
                    INSERT INTO call_log (call_sid, from_number, to_number, business_id, created_at, call_status, transcription)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    f"whatsapp_reply_{int(datetime.datetime.now().timestamp())}", 
                    to_, 
                    from_, 
                    1,
                    datetime.datetime.now(), 
                    'whatsapp_replied', 
                    f"WhatsApp reply: {reply}"
                ))
                
                conn.commit()
                cur.close()
                conn.close()
                
            except Exception as db_error:
                log.error("Database reply save error: %s", db_error)
            
            # Send TwiML response
            resp = MessagingResponse()
            resp.message(reply)
            
            return str(resp), 200
            
        except Exception as e:
            log.error("WhatsApp webhook error: %s", e)
            
            # Fallback response
            resp = MessagingResponse()
            resp.message("שלום! תודה על הפנייה. נחזור אליכם בהקדם.")
            return str(resp), 200

def handle_whatsapp_logic(body: str) -> str:
    """Handle WhatsApp message logic"""
    try:
        # Simple Hebrew responses for WhatsApp
        body_lower = body.lower().strip()
        
        if any(word in body_lower for word in ["שלום", "היי", "הלו"]):
            return "שלום וברוכים הבאים לשי דירות ומשרדים! איך אוכל לעזור לכם?"
        
        elif any(word in body_lower for word in ["דירה", "דירות", "נכס"]):
            return "אשמח לעזור לכם למצוא דירה מתאימה! אתם מחפשים לקניה או להשכרה? באיזה אזור?"
        
        elif any(word in body_lower for word in ["מחיר", "עלות", "כמה"]):
            return "המחירים משתנים לפי גודל הנכס, מיקום ומצב. נשמח לשלוח לכם הצעות מותאמות אישית!"
        
        elif any(word in body_lower for word in ["תודה", "תודה רבה"]):
            return "בשמחה! אנחנו כאן לעזור. אל תהססו לפנות אלינו בכל שאלה נוספת."
        
        else:
            return "תודה על הפנייה! אחד הסוכנים שלנו יחזור אליכם בהקדם עם מענה מפורט. נשמח לעזור!"
    
    except Exception as e:
        log.error("WhatsApp logic error: %s", e)
        return "תודה על הפנייה! נחזור אליכם בהקדם."