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
from hebrew_tts import hebrew_tts

# Setup logging
logger = logging.getLogger('routes_twilio')

# Import app 
from app import app

@app.route("/twilio/incoming_call", methods=["POST"])
def incoming_call():
        """Handle incoming calls with Hebrew greeting - FIXED Content-Type"""
        try:
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
    <Say voice="Polly.Joanna" language="en-US"><prosody rate="slow">סליחה, המספר אינו זמין כרגע</prosody></Say>
    <Hangup/>
</Response>'''
                return Response(error_twiml, mimetype='text/xml')
            
            # Extract business info from row
            business_id, business_name = business_row
            logger.info(f"✅ Found business: {business_name} (ID: {business_id})")
            
            # Create call log - handle duplicates
            call_log = CallLog.query.filter_by(call_sid=call_sid).first()
            if not call_log:
                call_log = CallLog(
                    business_id=business_id,
                    call_sid=call_sid,
                    from_number=from_number,
                    to_number=to_number,
                    call_status='ringing'
                )
                db.session.add(call_log)
                db.session.commit()
                logger.info(f"✅ Created new call log for {call_sid}")
            else:
                logger.info(f"📞 Using existing call log for {call_sid}")
            
            # Generate Hebrew greeting using Hebrew TTS
            greeting = f"שלום! זהו המוקד הוירטואלי של {business_name}. איך אוכל לעזור לך היום?"
            instruction = "אנא דברו אחרי הצפצוף"
            
            # Generate Hebrew audio files
            logger.info(f"🎵 Generating Hebrew TTS for: '{greeting[:30]}...'")
            greeting_file = hebrew_tts.synthesize_hebrew_audio(greeting)
            logger.info(f"🎵 Greeting TTS result: {greeting_file}")
            
            logger.info(f"🎵 Generating Hebrew TTS for: '{instruction[:30]}...'")
            instruction_file = hebrew_tts.synthesize_hebrew_audio(instruction)
            logger.info(f"🎵 Instruction TTS result: {instruction_file}")
            
            if greeting_file and instruction_file:
                # Use Hebrew TTS files - correct path
                greeting_url = f"https://ai-crmd.replit.app/server/static/voice_responses/{greeting_file}"
                instruction_url = f"https://ai-crmd.replit.app/server/static/voice_responses/{instruction_file}"
                
                twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{greeting_url}</Play>
    <Pause length="1"/>
    <Play>{instruction_url}</Play>
    <Record action="/twilio/handle_recording" method="POST" maxLength="30" timeout="5" transcribe="true" language="he-IL"/>
</Response>'''
                
                logger.info(f"🎵 Using Hebrew TTS files: {greeting_file}, {instruction_file}")
            else:
                # Fallback to basic text  
                twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna" language="en-US"><prosody rate="slow">{greeting}</prosody></Say>
    <Pause length="1"/>
    <Say voice="Polly.Joanna" language="en-US"><prosody rate="slow">{instruction}</prosody></Say>
    <Record action="/twilio/handle_recording" method="POST" maxLength="30" timeout="5" transcribe="true" language="he-IL"/>
</Response>'''
            
            logger.info(f"✅ Voice webhook response sent for business: {business_name}")
            return Response(twiml, mimetype='text/xml')
            
        except Exception as e:
            logger.error(f"Error handling incoming call: {str(e)}")
            error_twiml = '''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna" language="en-US"><prosody rate="slow">סליחה, יש בעיה טכנית</prosody></Say>
    <Hangup/>
</Response>'''
            return Response(error_twiml, mimetype='text/xml')

@app.route("/twilio/handle_recording", methods=["POST"])
def handle_recording():
        """Handle recordings from users - FIXED Content-Type and XML"""
        try:
            # Twilio שולח application/x-www-form-urlencoded - אין צורך לבדוק Content-Type
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
    <Say voice="Polly.Joanna" language="en-US"><prosody rate="slow">לא שמעתי אותך בבירור. אנא נסה שוב</prosody></Say>
    <Record action="/twilio/handle_recording" method="POST" maxLength="30" timeout="5" transcribe="true" language="he-IL"/>
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
            
            # Generate Hebrew response using Hebrew TTS
            hebrew_response = ai_response if ai_response else f"תודה על פנייתך ל{business_name}. נחזור אליך בהקדם."
            
            # Generate Hebrew TTS for response
            response_file = hebrew_tts.synthesize_hebrew_audio(hebrew_response)
            
            # עכשיו נעדכן את CallLog עם ההקלטה והתמלול
            if call_log and recording_url:
                call_log.recording_url = recording_url
                if 'transcribed_text' in locals() and transcribed_text:
                    call_log.transcription = transcribed_text
                if 'ai_response' in locals() and ai_response:
                    call_log.ai_response = ai_response
                call_log.call_status = 'completed'
                call_log.ended_at = datetime.utcnow()
                db.session.commit()
                logger.info(f"✅ Updated call log with recording: {recording_url}")

            if response_file:
                response_url = f"https://ai-crmd.replit.app/server/static/voice_responses/{response_file}"
                twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{response_url}</Play>
    <Hangup/>
</Response>'''
                logger.info(f"🎵 Using Hebrew TTS response: {response_file}")
            else:
                # Fallback
                twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna" language="en-US"><prosody rate="slow">{hebrew_response}</prosody></Say>
    <Hangup/>
</Response>'''
            
            logger.info(f"✅ Recording processed and response sent for {business_name}")
            return Response(twiml, mimetype='text/xml')
            
        except Exception as e:
            logger.error(f"Error handling recording: {str(e)}")
            error_twiml = '''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna" language="en-US"><prosody rate="slow">סליחה, הייתה בעיה בעיבוד ההקלטה</prosody></Say>
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