"""
Twilio Integration Routes for Hebrew AI Call Center
Clean version with only working functions
"""

import os
import logging
import requests
import tempfile
import openai
from flask import request, Response, jsonify
from models import Business, CallLog, db
from datetime import datetime

# Setup logging
logger = logging.getLogger('routes_twilio')

# Import app 
from app import app

@app.route("/twilio/incoming_call", methods=["POST"])
def incoming_call():
        """Handle incoming calls with Hebrew greeting"""
        try:
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
            
            # Find business by phone number using raw SQL
            import psycopg2
            try:
                conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
                cur = conn.cursor()
                # Try multiple formats: original, cleaned, and both without dashes
                cur.execute("""
                    SELECT id, name FROM businesses 
                    WHERE (phone_israel = %s OR phone_israel = %s OR 
                           REPLACE(phone_israel, '-', '') = %s OR 
                           REPLACE(phone_israel, '-', '') = %s) 
                    AND is_active = true
                """, (to_number.strip(), clean_to, clean_to_no_dashes, to_number.strip().replace('-', '')))
                business_row = cur.fetchone()
                cur.close()
                conn.close()
            except Exception as db_e:
                logger.error(f"Database error: {db_e}")
                business_row = None
                
            if not business_row:
                logger.warning(f"Business not found for {clean_to}")
                error_twiml = '''<?xml version="1.0" encoding="UTF-8"?>
                <Response>
                    <Say voice="alice" language="he-IL">סליחה, המספר אינו זמין כרגע.</Say>
                    <Hangup/>
                </Response>'''
                return Response(error_twiml, mimetype='text/xml')
            
            # Extract business info from row
            business_id, business_name = business_row
            logger.info(f"✅ Found business: {business_name} (ID: {business_id})")
            
            # Create call log
            call_log = CallLog(
                business_id=business_id,
                call_sid=call_sid,
                from_number=from_number,
                to_number=to_number,
                call_status='ringing'
            )
            db.session.add(call_log)
            db.session.commit()
            
            # Start conversation with greeting  
            greeting = f"שלום! זהו המוקד הוירטואלי של {business_name}. איך אוכל לעזור לך היום?"
            
            twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
            <Response>
                <Say voice="alice" language="he-IL">{greeting}</Say>
                <Record action="/twilio/handle_recording" method="POST" maxLength="30" timeout="5" transcribe="false"/>
            </Response>'''
            
            logger.info(f"✅ Voice webhook response sent for business: {business_name}")
            return Response(twiml, mimetype='text/xml')
            
        except Exception as e:
            logger.error(f"Error handling incoming call: {str(e)}")
            error_twiml = '''<?xml version="1.0" encoding="UTF-8"?>
            <Response>
                <Say voice="alice" language="he-IL">סליחה, יש בעיה טכנית.</Say>
                <Hangup/>
            </Response>'''
            return Response(error_twiml, mimetype='text/xml')

@app.route("/twilio/handle_recording", methods=["POST"])
def handle_recording():
        """Handle recordings from users"""
        try:
            recording_url = request.form.get('RecordingUrl')
            call_sid = request.form.get('CallSid')
            from_number = request.form.get('From')
            to_number = request.form.get('To')
            
            logger.info(f"🎙️ Received recording: {recording_url} for call {call_sid}")
            
            # Find business by call_sid from existing call log
            call_log = CallLog.query.filter_by(call_sid=call_sid).first()
            business_name = "לקוח יקר"
            
            if call_log:
                business = Business.query.get(call_log.business_id)
                if business:
                    business_name = business.name
            
            if not recording_url:
                logger.warning("No recording URL provided")
                twiml = '''<?xml version="1.0" encoding="UTF-8"?>
                <Response>
                    <Say voice="alice" language="he-IL">לא קלטתי אותך. אנא נסה שוב.</Say>
                    <Record action="/twilio/handle_recording" method="POST" maxLength="30" timeout="5" transcribe="false"/>
                </Response>'''
                return Response(twiml, mimetype='text/xml')
            
            # Download and process recording with AI
            ai_response = "תודה על פנייתך. נחזור אליך בהקדם."
            
            if recording_url:
                try:
                    # Download recording from Twilio
                    logger.info(f"⬇️ Downloading recording from: {recording_url}")
                    
                    recording_response = requests.get(recording_url, stream=True)
                    if recording_response.status_code == 200:
                        # Save to temporary file
                        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                            for chunk in recording_response.iter_content(chunk_size=8192):
                                temp_file.write(chunk)
                            temp_filename = temp_file.name
                        
                        # Transcribe with OpenAI Whisper (Hebrew)
                        logger.info("🎙️ Transcribing with Whisper...")
                        client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
                        
                        with open(temp_filename, 'rb') as audio_file:
                            transcript = client.audio.transcriptions.create(
                                model="whisper-1",
                                file=audio_file,
                                language="he"
                            )
                        
                        transcribed_text = transcript.text.strip()
                        logger.info(f"📝 Transcribed: {transcribed_text}")
                        
                        if transcribed_text and len(transcribed_text) > 2:
                            # Get business info for AI prompt
                            business = Business.query.get(call_log.business_id) if call_log else None
                            ai_prompt = business.ai_prompt if business and business.ai_prompt else "אתה עוזר וירטואלי מועיל בעברית"
                            
                            # Generate AI response
                            logger.info("🤖 Generating GPT response...")
                            messages = [
                                {"role": "system", "content": ai_prompt},
                                {"role": "user", "content": transcribed_text}
                            ]
                            
                            gpt_response = client.chat.completions.create(
                                model="gpt-4o",
                                messages=messages,
                                max_tokens=150,
                                temperature=0.7
                            )
                            
                            ai_response = gpt_response.choices[0].message.content.strip() if gpt_response.choices[0].message.content else "תודה על פנייתך"
                            logger.info(f"🎯 GPT Response: {ai_response}")
                        
                        # Cleanup
                        os.unlink(temp_filename)
                        
                except Exception as ai_error:
                    logger.error(f"AI processing error: {ai_error}")
                    ai_response = f"תודה על פנייתך ל{business_name}. נחזור אליך בהקדם."
            
            # Generate response TwiML
            twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
            <Response>
                <Say voice="alice" language="he-IL">{ai_response}</Say>
                <Hangup/>
            </Response>'''
            
            logger.info(f"✅ Recording processed and response sent for {business_name}")
            return Response(twiml, mimetype='text/xml')
            
        except Exception as e:
            logger.error(f"Error handling recording: {str(e)}")
            error_twiml = '''<?xml version="1.0" encoding="UTF-8"?>
            <Response>
                <Say voice="alice" language="he-IL">סליחה, הייתה בעיה בעיבוד ההקלטה.</Say>
                <Hangup/>
            </Response>'''
            return Response(error_twiml, mimetype='text/xml')

@app.route("/twilio/call_status", methods=["POST"])  
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