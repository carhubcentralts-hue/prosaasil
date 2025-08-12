from flask import Blueprint, request, Response, current_app
import logging
import os

logger = logging.getLogger(__name__)
twilio_bp = Blueprint("twilio_bp", __name__, url_prefix="")

# Import AI conversation with lazy loading to avoid httpcore issues
AI_AVAILABLE = False
simple_ai = None

def get_ai_system():
    """Lazy load AI system to avoid initialization issues"""
    global simple_ai, AI_AVAILABLE
    if simple_ai is None:
        try:
            from simple_ai_conversation import simple_ai as ai_system
            simple_ai = ai_system
            AI_AVAILABLE = True
            logger.info("✅ AI conversation system loaded on demand")
        except Exception as e:
            logger.error(f"❌ Failed to load AI conversation system: {e}")
            AI_AVAILABLE = False
    return simple_ai if AI_AVAILABLE else None

@twilio_bp.route("/webhook/incoming_call", methods=['POST'])
def incoming_call():
    """תחילת שיחה - ברכה וצעד ראשון"""
    call_sid = request.form.get('CallSid', 'unknown')
    from_number = request.form.get('From', 'unknown')
    
    logger.info(f"📞 New call started: {call_sid} from {from_number}")
    
    # Store turn count in temporary storage (no session needed)
    turn_count = 0
    
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>https://ai-crmd.replit.app/static/greeting.mp3</Play>
  <Pause length="1"/>
  <Record action="/webhook/handle_recording"
          method="POST"
          maxLength="45"
          timeout="10"
          finishOnKey="*"
          transcribe="false"/>
</Response>"""
    return Response(xml, mimetype="text/xml")

@twilio_bp.route("/webhook/handle_recording", methods=['POST'])
def handle_recording():
    """עיבוד הקלטה עם תמלול Whisper, תשובת AI ו-TTS"""
    call_sid = request.form.get('CallSid', 'unknown')
    recording_url = request.form.get('RecordingUrl')
    from_number = request.form.get('From', 'unknown')
    
    # Simple turn counter (no session needed for POC)
    turn_count = 1
    
    logger.info(f"🎙️ Processing recording turn #{turn_count} for {call_sid} from {from_number}")
    logger.info(f"Recording URL: {recording_url}")
    
    if not recording_url:
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>https://ai-crmd.replit.app/static/listening.mp3</Play>
  <Pause length="1"/>
  <Record action="/webhook/handle_recording" method="POST" maxLength="45" timeout="10" finishOnKey="*" transcribe="false"/>
</Response>"""
        return Response(xml, mimetype="text/xml")
    
    try:
        # Check if recording URL is available
        if not recording_url:
            logger.warning("No recording URL provided")
            return basic_response("סליחה, לא קיבלתי את ההקלטה. אפשר לנסות שוב?")
        
        # Get AI system on demand
        ai_system = get_ai_system()
        if not ai_system:
            logger.error("AI system not available")
            return basic_response("סליחה, המערכת זמנית לא זמינה. אפשר לנסות שוב?")
        
        # עיבוד מלא עם AI
        result = ai_system.process_conversation_turn(call_sid, recording_url, turn_count)
        
        if not result['success']:
            # שגיאה בעיבוד - נסה שוב
            xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>https://ai-crmd.replit.app/static/listening.mp3</Play>
  <Pause length="1"/>
  <Record action="/webhook/handle_recording" method="POST" maxLength="45" timeout="10" finishOnKey="*" transcribe="false"/>
</Response>"""
            return Response(xml, mimetype="text/xml")
        
        ai_response = result['ai_response']
        should_end = result['end_conversation']
        
        logger.info(f"✅ AI Response: {ai_response}")
        logger.info(f"End conversation: {should_end}")
        
        if should_end:
            # סיום שיחה
            xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="he-IL">{ai_response} תודה שפניתם אלינו. יום נעים!</Say>
  <Hangup/>
</Response>"""
            # End conversation cleanup (no session needed)
        else:
            # המשך שיחה
            xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="he-IL">{ai_response}</Say>
  <Pause length="1"/>
  <Record action="/webhook/handle_recording"
          method="POST"
          maxLength="45"
          timeout="10" 
          finishOnKey="*"
          transcribe="false"/>
</Response>"""
        
        return Response(xml, mimetype="text/xml")
        
    except Exception as e:
        logger.error(f"❌ Error in handle_recording: {e}")
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="he-IL">סליחה, יש לי בעיה טכנית. אנא חייגו מאוחר יותר או השאירו הודעה אחרי הצפצוף.</Say>
  <Record action="/webhook/final_message" method="POST" maxLength="60" timeout="5"/>
</Response>"""
        return Response(xml, mimetype="text/xml")

@twilio_bp.route("/webhook/final_message", methods=['POST']) 
def final_message():
    """הודעה סופית במקרה של שגיאה"""
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="he-IL">תודה. קיבלנו את הודעתכם. נחזור אליכם בהקדם. יום נעים!</Say>
  <Hangup/>
</Response>"""
    return Response(xml, mimetype="text/xml")

def basic_response(message: str, continue_conversation: bool = True) -> Response:
    """יצירת תשובה בסיסית ללא AI"""
    if continue_conversation:
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="he-IL">{message}</Say>
  <Pause length="1"/>
  <Record action="/webhook/handle_recording" method="POST" maxLength="45" timeout="10" finishOnKey="*" transcribe="false"/>
</Response>"""
    else:
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="he-IL">{message}</Say>
  <Hangup/>
</Response>"""
    return Response(xml, mimetype="text/xml")

@twilio_bp.post("/webhook/call_status")
def call_status():
    # Always return 200 for Twilio status updates
    return "OK", 200