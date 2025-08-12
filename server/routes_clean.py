#!/usr/bin/env python3
"""
Clean Twilio Routes - נתיבי Twilio נקיים וללא בעיות
"""

import logging
from flask import Blueprint, request, Response
from ai_system_clean import clean_ai

logger = logging.getLogger(__name__)
clean_twilio_bp = Blueprint("clean_twilio", __name__, url_prefix="")

@clean_twilio_bp.route("/webhook/incoming_call", methods=['POST'])
def clean_incoming_call():
    """התחלת שיחה - ברכה וצעד ראשון"""
    call_sid = request.form.get('CallSid')
    from_number = request.form.get('From')
    to_number = request.form.get('To')
    
    logger.info(f"📞 New call started: {call_sid} from {from_number}")
    
    # Hebrew greeting with business name
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="he-IL">שלום וברכה! הגעתם לשי דירות ומשרדים בעמ. אני כאן לעזור לכם למצוא את הנכס המושלם. במה אוכל לעזור לכם?</Say>
  <Pause length="1"/>
  <Record action="/webhook/handle_recording"
          method="POST"
          maxLength="45"
          timeout="10"
          finishOnKey="*"
          transcribe="false"/>
</Response>"""
    
    return Response(xml, mimetype="text/xml")

@clean_twilio_bp.route("/webhook/handle_recording", methods=['POST'])
def clean_handle_recording():
    """עיבוד הקלטה עם AI מלא"""
    call_sid = request.form.get('CallSid')
    recording_url = request.form.get('RecordingUrl')
    from_number = request.form.get('From')
    
    logger.info(f"🎙️ Processing recording for call: {call_sid}")
    logger.info(f"📍 Recording URL: {recording_url}")
    
    # Count turn number (simple implementation)
    turn_count = 1  # You can implement more sophisticated turn counting
    
    def basic_response(message: str) -> Response:
        """תשובה בסיסית עם האפשרות להמשיך"""
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="he-IL">{message}</Say>
  <Pause length="1"/>
  <Record action="/webhook/handle_recording"
          method="POST"
          maxLength="45"
          timeout="10"
          finishOnKey="*"
          transcribe="false"/>
</Response>"""
        return Response(xml, mimetype="text/xml")
    
    def end_call_response(message: str) -> Response:
        """תשובת סיום שיחה"""
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="he-IL">{message}</Say>
  <Pause length="2"/>
  <Hangup/>
</Response>"""
        return Response(xml, mimetype="text/xml")
    
    try:
        # Check if we have a recording URL
        if not recording_url:
            logger.warning("No recording URL provided")
            return basic_response("סליחה, לא קיבלתי את ההקלטה. אפשר לנסות שוב?")
        
        # Process with clean AI system
        result = clean_ai.process_complete_turn(call_sid, recording_url, turn_count)
        
        ai_response = result['ai_response']
        should_end = result['should_end']
        
        logger.info(f"✅ AI Response: {ai_response}")
        logger.info(f"📊 Should end conversation: {should_end}")
        
        if should_end:
            return end_call_response(ai_response)
        else:
            return basic_response(ai_response)
    
    except Exception as e:
        logger.error(f"❌ Error processing recording: {e}")
        return basic_response("סליחה, יש בעיה זמנית במערכת. אפשר לנסות שוב?")

@clean_twilio_bp.route("/test/ai", methods=['GET'])
def test_ai_system():
    """בדיקת מערכת AI"""
    try:
        # Test business context
        context = clean_ai.get_business_context(1)
        
        # Test AI response
        test_input = "שלום, אני מחפש דירה בתל אביב"
        response = clean_ai.generate_response(test_input, context)
        
        return {
            'status': 'success',
            'business': context['name'],
            'phone': context['phone'],
            'test_input': test_input,
            'ai_response': response
        }
    
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }

@clean_twilio_bp.route("/test/conversation", methods=['POST'])
def test_conversation():
    """בדיקת שיחה מלאה"""
    data = request.get_json()
    user_input = data.get('user_input', 'שלום')
    
    try:
        context = clean_ai.get_business_context(1)
        ai_response = clean_ai.generate_response(user_input, context)
        should_end = clean_ai.should_end_conversation(user_input, ai_response)
        
        return {
            'status': 'success',
            'user_input': user_input,
            'ai_response': ai_response,
            'should_end': should_end,
            'business': context['name']
        }
    
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }