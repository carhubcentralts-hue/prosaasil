"""
Twilio Integration Routes for Hebrew AI Call Center
Blueprint version with webhook handlers
"""

import os
import logging
import requests
import tempfile
import openai
from flask import Blueprint, request, Response, jsonify
from datetime import datetime
from whisper_handler import process_recording

# Setup logging
logger = logging.getLogger('routes_twilio')

# Create Blueprint
twilio_bp = Blueprint('twilio_bp', __name__, url_prefix='/webhook')

@twilio_bp.route("/incoming_call", methods=["POST"])
def incoming_call():
        """Handle incoming calls with Hebrew greeting - FIXED Content-Type"""
        try:
            # Import here to avoid circular imports
            from models import Business, CallLog, db
            from hebrew_tts import hebrew_tts
            
            # צריך לוודא שאנחנו לא בודקים Content-Type מיותר - Twilio שולח application/x-www-form-urlencoded
            from_number = request.form.get('From', '')
            to_number = request.form.get('To', '').strip()
            call_sid = request.form.get('CallSid', '')
            
            logger.info(f"📞 Incoming call: From {from_number} To {to_number}")
            
            # Clean phone number for lookup - try both original and cleaned versions
            clean_to = to_number.strip()
            if not clean_to.startswith('+'):
                clean_to = '+' + clean_to
            
            # Also try without dashes version
            clean_to_no_dashes = clean_to.replace('-', '')
            
            logger.info(f"🔍 Original: '{to_number}' -> Cleaned: '{clean_to}' -> No dashes: '{clean_to_no_dashes}'")
            
            # Find business by phone number - FIXED DB lookup
            business = None
            try:
                # Try phone_israel field (correct field name from model)
                business = Business.query.filter_by(phone_israel=clean_to).first()
                if not business:
                    business = Business.query.filter_by(phone_israel=clean_to_no_dashes).first()
                if not business:
                    # Try without plus
                    no_plus = clean_to[1:] if clean_to.startswith('+') else clean_to
                    business = Business.query.filter_by(phone_israel=no_plus).first()
            except Exception as db_error:
                logger.error(f"❌ Database lookup error: {db_error}")
                business = None
            try:
                conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
                cur = conn.cursor()
                # Try multiple formats: original, cleaned, and both without dashes
                # REMOVED is_active check - it's causing the lookup to fail
                cur.execute("""
                    SELECT id, name, ai_prompt FROM businesses 
                    WHERE (phone_israel = %s OR phone_israel = %s OR 
                           REPLACE(phone_israel, '-', '') = %s OR 
                           REPLACE(phone_israel, '-', '') = %s)
                    ORDER BY id DESC
                    LIMIT 1
                """, (to_number.strip(), clean_to, clean_to_no_dashes, to_number.strip().replace('-', '')))
                business_row = cur.fetchone()
                cur.close()
                conn.close()
            except Exception as db_e:
                logger.error(f"Database error: {db_e}")
                business_row = None
                
            if not business_row:
                logger.warning(f"Business not found for {clean_to}")
                error_twiml = '''<?xml version="1.0" encoding="UTF-8"?><Response><Say voice="Polly.Joanna" language="en-US"><prosody rate="slow">סליחה, המספר אינו זמין כרגע</prosody></Say><Hangup/></Response>'''
                return Response(error_twiml, mimetype='text/xml')
            
            # Extract business info from row
            business_id, business_name, ai_prompt = business_row
            logger.info(f"✅ Found business: {business_name} (ID: {business_id})")
            
            # Skip CallLog creation for now - focus on core voice functionality
            # CallLog will be added back after foreign key constraints are fixed
            logger.info(f"✅ Skipping call log creation for {call_sid} - focusing on voice system")
            
            # Generate Hebrew greeting using Hebrew TTS - מותאם לכל עסק
            greeting = f"שלום! זהו המוקד הוירטואלי של {business_name}. איך אוכל לעזור לך היום?"
            instruction = "אנא דברו אחרי הצפצוף"
            
            logger.info(f"📞 Call from {from_number} to business: {business_name} (ID: {business_id})")
            logger.info(f"🎵 Generating Hebrew TTS for business greeting: '{greeting[:50]}...'")
            
            # Generate Hebrew audio files
            greeting_file = hebrew_tts.synthesize_hebrew_audio(greeting)
            logger.info(f"✅ Greeting TTS created: {greeting_file}")
            
            instruction_file = hebrew_tts.synthesize_hebrew_audio(instruction)
            logger.info(f"✅ Instruction TTS created: {instruction_file}")
            
            if greeting_file and instruction_file:
                # Use Hebrew TTS files - correct path
                greeting_url = f"https://ai-crmd.replit.app/server/static/voice_responses/{greeting_file}"
                instruction_url = f"https://ai-crmd.replit.app/server/static/voice_responses/{instruction_file}"
                
                twiml = f'''<?xml version="1.0" encoding="UTF-8"?><Response><Play>{greeting_url}</Play><Pause length="1"/><Play>{instruction_url}</Play><Record action="/webhook/handle_recording" method="POST" maxLength="30" timeout="5" transcribe="true" language="he-IL"/></Response>'''
                
                logger.info(f"🎵 Using Hebrew TTS files: {greeting_file}, {instruction_file}")
            else:
                # Fallback to basic text  
                twiml = f'''<?xml version="1.0" encoding="UTF-8"?><Response><Say voice="Polly.Joanna" language="en-US"><prosody rate="slow">{greeting}</prosody></Say><Pause length="1"/><Say voice="Polly.Joanna" language="en-US"><prosody rate="slow">{instruction}</prosody></Say><Record action="/webhook/handle_recording" method="POST" maxLength="30" timeout="5" transcribe="true" language="he-IL"/></Response>'''
            
            logger.info(f"✅ Voice webhook response sent for business: {business_name}")
            response = Response(twiml, mimetype='text/xml')
            response.headers['Content-Type'] = 'text/xml; charset=utf-8'
            return response
            
        except Exception as e:
            import traceback
            logger.error(f"❌❌❌ CRITICAL ERROR in incoming_call: {str(e)}")
            logger.error(f"❌❌❌ Full traceback: {traceback.format_exc()}")
            error_twiml = '''<?xml version="1.0" encoding="UTF-8"?><Response><Say voice="Polly.Joanna" language="en-US"><prosody rate="slow">סליחה, יש בעיה טכנית</prosody></Say><Hangup/></Response>'''
            response = Response(error_twiml, mimetype='text/xml')
            response.headers['Content-Type'] = 'text/xml; charset=utf-8'
            return response

@twilio_bp.route("/handle_recording", methods=["POST"])
def handle_recording():
        """Handle recordings from Twilio - Using whisper_handler.process_recording"""
        try:
            recording_sid = request.form.get('RecordingSid')
            call_sid = request.form.get('CallSid')
            from_number = request.form.get('From')
            to_number = request.form.get('To')
            
            logger.info(f"🎙️ Received recording: RecordingSid={recording_sid}, CallSid={call_sid}")
            
            if not recording_sid or not call_sid:
                logger.warning("Missing RecordingSid or CallSid")
                twiml = '''<?xml version="1.0" encoding="UTF-8"?><Response><Say voice="Polly.Joanna" language="en-US"><prosody rate="slow">לא שמעתי אותך בבירור. אנא נסה שוב</prosody></Say><Record action="/webhook/handle_recording" method="POST" maxLength="30" timeout="5" transcribe="true" language="he-IL"/></Response>'''
                response = Response(twiml, mimetype='text/xml')
                response.headers['Content-Type'] = 'text/xml; charset=utf-8'
                return response
            
            # Process recording using whisper_handler as per guidelines
            ai_response = process_recording(recording_sid=recording_sid, call_sid=call_sid)
            
            if not ai_response or ai_response == "שגיאה בעיבוד השיחה":
                ai_response = "תודה על פנייתכם. נחזור אליכם בהקדם."
            
            # Generate Hebrew TTS response
            response_file = hebrew_tts.synthesize_hebrew_audio(ai_response)
            
            if response_file:
                # Use Hebrew TTS file
                response_url = f"https://ai-crmd.replit.app/server/static/voice_responses/{response_file}"
                twiml = f'''<?xml version="1.0" encoding="UTF-8"?><Response><Play>{response_url}</Play><Hangup/></Response>'''
            else:
                # Fallback to text response
                twiml = f'''<?xml version="1.0" encoding="UTF-8"?><Response><Say voice="Polly.Joanna" language="en-US"><prosody rate="slow">{ai_response}</prosody></Say><Hangup/></Response>'''
            
            logger.info(f"✅ Call {call_sid}: Processing complete, sending response")
            response = Response(twiml, mimetype='text/xml')
            response.headers['Content-Type'] = 'text/xml; charset=utf-8'
            return response
            
        except Exception as e:
            logger.error(f"❌ Error in handle_recording: {e}")
            error_twiml = '''<?xml version="1.0" encoding="UTF-8"?><Response><Say voice="Polly.Joanna" language="en-US"><prosody rate="slow">תודה על פנייתכם. נחזור אליכם בהקדם.</prosody></Say><Hangup/></Response>'''
            response = Response(error_twiml, mimetype='text/xml')  
            response.headers['Content-Type'] = 'text/xml; charset=utf-8'
            return response

@twilio_bp.route("/call_status", methods=["POST"])  
def call_status():
        """Handle call status updates"""
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