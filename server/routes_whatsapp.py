"""
4) WhatsApp webhook routes
"""
from flask import request, current_app
from twilio.twiml.messaging_response import MessagingResponse
import logging
import psycopg2
import datetime
import os

log = logging.getLogger(__name__)

def register_whatsapp_routes(app):
    """Register WhatsApp webhook routes"""
    
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