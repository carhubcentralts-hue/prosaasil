"""
Simple webhook test - בדיקה פשוטה ללא complications
"""
from flask import Blueprint, request, Response
import logging

test_bp = Blueprint("test_bp", __name__)
log = logging.getLogger("test")

@test_bp.post("/test/simple_call")
def simple_call_test():
    """בדיקה פשוטה של webhook שיחה - ללא decorators ו-complications"""
    try:
        from_number = request.form.get("From", "unknown")
        call_sid = request.form.get("CallSid", "unknown")
        
        log.info("TEST Simple call: From=%s CallSid=%s", from_number, call_sid)
        
        # Hebrew TwiML response - פשוט וישיר
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say language="he-IL">שלום, זהו מבחן המערכת. ההקלטה מתחילה עכשיו.</Say>
  <Record maxLength="10" timeout="3" finishOnKey="*"/>
  <Say language="he-IL">תודה על ההודעה. להתראות.</Say>
</Response>"""
        
        return Response(xml, mimetype="text/xml", status=200)
        
    except Exception as e:
        log.error("Error in simple test: %s", e)
        return Response("Error", status=500)

@test_bp.post("/test/simple_whatsapp")  
def simple_whatsapp_test():
    """בדיקה פשוטה של WhatsApp - ללא complications"""
    try:
        from_number = request.form.get("From", "unknown")
        body = request.form.get("Body", "")
        
        log.info("TEST Simple WhatsApp: From=%s Body=%s", from_number, body)
        
        return {"status": "received", "message": "WhatsApp test successful"}, 200
        
    except Exception as e:
        log.error("Error in simple WhatsApp test: %s", e)
        return {"error": str(e)}, 500