"""
Twilio Routes - Hebrew AI Call Center
מסלולי Twilio למוקד שיחות AI עברית
"""

from flask import request, Response, jsonify
from app import app, db
from models import Business, CallLog, ConversationTurn, Customer
from twilio_service import TwilioService
import openai
import os
import tempfile
import requests
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

@app.route("/handle_recording", methods=["POST"])
def handle_recording():
    """
    מטפל בהקלטות שיחות מ-Twilio
    - מוריד הקלטה
    - מתמלל עם Whisper בעברית  
    - שולח ל-GPT לקבלת מענה
    - מחזיר תשובה בקול עברי
    
    ⚠️ CRITICAL: Must respond within 10 seconds to avoid Twilio timeout
    """
    start_time = datetime.utcnow()
    try:
        # Get recording data from Twilio
        recording_url = request.form.get('RecordingUrl')
        call_sid = request.form.get('CallSid')
        from_number = request.form.get('From')
        to_number = request.form.get('To')
        
        if not recording_url or not call_sid:
            logger.error("Missing recording URL or Call SID")
            return jsonify({'error': 'Missing required parameters'}), 400
            
        # Find business by phone number
        business = Business.query.filter_by(phone_number=to_number).first()
        if not business or not business.calls_enabled:
            logger.warning(f"Business not found or calls disabled for {to_number}")
            return jsonify({'error': 'Business not configured for calls'}), 404
            
        # Find or create call log
        call_log = CallLog.query.filter_by(call_sid=call_sid).first()
        if not call_log:
            call_log = CallLog(
                business_id=business.id,
                call_sid=call_sid,
                from_number=from_number,
                to_number=to_number,
                call_status='in-progress'
            )
            db.session.add(call_log)
            db.session.commit()
            
        # Download recording
        logger.info(f"Downloading recording from: {recording_url}")
        response = requests.get(recording_url, stream=True)
        
        if response.status_code != 200:
            logger.error(f"Failed to download recording: {response.status_code}")
            return jsonify({'error': 'Failed to download recording'}), 500
            
        # Save recording to temporary file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            for chunk in response.iter_content(chunk_size=8192):
                temp_file.write(chunk)
            temp_filename = temp_file.name
            
        # Transcribe with OpenAI Whisper (Hebrew)
        logger.info("Transcribing audio with Whisper...")
        
        client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        
        with open(temp_filename, 'rb') as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="he"  # Hebrew
            )
            
        transcribed_text = transcript.text.strip()
        logger.info(f"Transcribed text: {transcribed_text}")
        
        # Anti-loop protection: check if text is similar to last response
        last_turn = ConversationTurn.query.filter_by(call_log_id=call_log.id).order_by(ConversationTurn.id.desc()).first()
        if last_turn and last_turn.user_text and len(transcribed_text) > 5:
            if transcribed_text.lower() == last_turn.user_text.lower():
                response_text = "לא שמעתי טוב, תוכל לנסח אחרת בבקשה?"
                logger.info("Anti-loop triggered - returning clarification request")
            else:
                # Generate AI response
                response_text = generate_ai_response(transcribed_text, business)
        else:
            response_text = generate_ai_response(transcribed_text, business)
            
        # Save conversation turn
        conversation_turn = ConversationTurn(
            call_log_id=call_log.id,
            user_text=transcribed_text,
            ai_response=response_text,
            timestamp=datetime.utcnow()
        )
        db.session.add(conversation_turn)
        
        # Find or create customer
        customer = Customer.query.filter_by(phone=from_number, business_id=business.id).first()
        if not customer:
            customer = Customer(
                name=f"לקוח {from_number[-4:]}",
                phone=from_number,
                business_id=business.id,
                source='call'
            )
            db.session.add(customer)
            
        # Update customer stats
        customer.total_calls = customer.total_calls + 1 if customer.total_calls else 1
        customer.last_contact_date = datetime.utcnow()
        
        # Record interaction in CRM
        try:
            from crm_service import record_interaction
            record_interaction(
                customer_id=customer.id,
                interaction_type='call',
                direction='inbound',
                content=transcribed_text,
                ai_response=response_text,
                call_sid=call_sid
            )
        except Exception as crm_error:
            logger.warning(f"Failed to record CRM interaction: {crm_error}")
        
        # Commit all database changes
        db.session.commit()
        logger.info("✅ All database changes committed successfully")
        
        # Generate TTS audio and return TwiML
        twiml_response = generate_tts_response(response_text)
        
        # Validate TwiML response before returning
        if not twiml_response or len(twiml_response) < 50:
            logger.error("TwiML response too short, using fallback")
            twiml_response = generate_fallback_twiml()
        
        # Clean up temporary file
        os.unlink(temp_filename)
        
        # Check timing - must respond within 10 seconds
        elapsed_time = (datetime.utcnow() - start_time).total_seconds()
        if elapsed_time > 9:
            logger.warning(f"⚠️ Response took {elapsed_time:.2f}s - close to Twilio timeout!")
        else:
            logger.info(f"✅ Response completed in {elapsed_time:.2f}s")
        
        return Response(twiml_response, mimetype='text/xml')
        
    except Exception as e:
        logger.error(f"Error handling recording: {str(e)}")
        # Return error TwiML
        error_twiml = '''<?xml version="1.0" encoding="UTF-8"?>
        <Response>
            <Say voice="Polly.Hilit" language="he-IL">סליחה, יש לי בעיה טכנית. נסה שוב בעוד רגע.</Say>
            <Hangup/>
        </Response>'''
        return Response(error_twiml, mimetype='text/xml')

def generate_ai_response(user_text, business):
    """יוצר תגובת AI עבור הטקסט של המשתמש"""
    try:
        # Check for gibberish/unclear speech
        if len(user_text) < 3 or not any(c.isalpha() for c in user_text):
            return "לא הבנתי את מה שאמרת. תוכל לחזור בבקשה?"
            
        # Create AI prompt based on business context
        system_prompt = business.system_prompt or "אתה עוזר וירטואלי מועיל לעסק בישראל."
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text}
        ]
        
        client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=150,
            temperature=0.7
        )
        
        ai_response = response.choices[0].message.content.strip()
        logger.info(f"AI Response: {ai_response}")
        
        return ai_response
        
    except Exception as e:
        logger.error(f"Error generating AI response: {str(e)}")
        return "סליחה, יש לי בעיה טכנית. איך אוכל לעזור לך?"

def generate_tts_response(text):
    """יוצר TwiML עם קול עברי"""
    try:
        # Validate input text
        if not text or len(text.strip()) == 0:
            logger.warning("Empty text for TTS, using default message")
            text = "תודה לך על הפנייה"
        
        # Ensure text is not too long for TTS
        if len(text) > 500:
            text = text[:497] + "..."
            
        # Escape XML special characters
        text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        # Use Amazon Polly Hebrew voice through Twilio
        twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
        <Response>
            <Say voice="Polly.Hilit" language="he-IL">{text}</Say>
            <Record action="/handle_recording" method="POST" maxLength="30" timeout="3" transcribe="false"/>
        </Response>'''
        
        logger.info(f"✅ Generated TwiML response: {len(twiml)} characters")
        return twiml
        
    except Exception as e:
        logger.error(f"Error generating TTS: {str(e)}")
        return generate_fallback_twiml()

def generate_fallback_twiml():
    """יוצר TwiML חלופי במקרה של כשל"""
    fallback_twiml = '''<?xml version="1.0" encoding="UTF-8"?>
    <Response>
        <Say voice="Polly.Hilit" language="he-IL">תודה לך על הפנייה. נחזור אליך בהקדם.</Say>
        <Hangup/>
    </Response>'''
    logger.info("✅ Using fallback TwiML")
    return fallback_twiml

@app.route("/twilio/incoming_call", methods=["POST"])
def incoming_call():
    """מטפל בשיחות נכנסות מ-Twilio"""
    try:
        from_number = request.form.get('From')
        to_number = request.form.get('To')
        call_sid = request.form.get('CallSid')
        
        # Find business
        business = Business.query.filter_by(phone_number=to_number).first()
        if not business or not business.calls_enabled:
            twiml = '''<?xml version="1.0" encoding="UTF-8"?>
            <Response>
                <Say voice="Polly.Hilit" language="he-IL">המספר שחייגת אליו לא פעיל כרגע.</Say>
                <Hangup/>
            </Response>'''
            return Response(twiml, mimetype='text/xml')
            
        # Create call log
        call_log = CallLog(
            business_id=business.id,
            call_sid=call_sid,
            from_number=from_number,
            to_number=to_number,
            call_status='answered'
        )
        db.session.add(call_log)
        db.session.commit()
        
        # Start conversation with greeting
        greeting = business.greeting_message or "שלום! איך אפשר לעזור לך היום?"
        
        twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
        <Response>
            <Say voice="Polly.Hilit" language="he-IL">{greeting}</Say>
            <Record action="/handle_recording" method="POST" maxLength="30" timeout="5" transcribe="false"/>
        </Response>'''
        
        return Response(twiml, mimetype='text/xml')
        
    except Exception as e:
        logger.error(f"Error handling incoming call: {str(e)}")
        error_twiml = '''<?xml version="1.0" encoding="UTF-8"?>
        <Response>
            <Say voice="Polly.Hilit" language="he-IL">סליחה, יש בעיה טכנית.</Say>
            <Hangup/>
        </Response>'''
        return Response(error_twiml, mimetype='text/xml')

@app.route("/twilio/call_status", methods=["POST"])  
def call_status():
    """מטפל בעדכוני סטטוס שיחה"""
    try:
        call_sid = request.form.get('CallSid')
        call_status = request.form.get('CallStatus')
        call_duration = request.form.get('CallDuration')
        
        call_log = CallLog.query.filter_by(call_sid=call_sid).first()
        if call_log:
            call_log.call_status = call_status
            if call_duration:
                call_log.call_duration = int(call_duration)
            if call_status == 'completed':
                call_log.ended_at = datetime.utcnow()
            db.session.commit()
            
        return jsonify({'status': 'updated'})
        
    except Exception as e:
        logger.error(f"Error updating call status: {str(e)}")
        return jsonify({'error': 'Failed to update status'}), 500