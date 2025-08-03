"""
Twilio Integration Routes for Hebrew AI Call Center
Clean version with only working functions
"""

import os
import logging
from flask import request, Response, jsonify
from models import Business, CallLog, db
from datetime import datetime

# Setup logging
logger = logging.getLogger('routes_twilio')

# Import app from main
from main import app

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
                
            logger.info(f"🔍 Original: '{to_number}' -> Cleaned: '{clean_to}'")
            
            # Find business by phone number using raw SQL
            import psycopg2
            try:
                conn = psycopg2.connect(os.environ.get('DATABASE_URL'))
                cur = conn.cursor()
                # Try both original format and cleaned format
                cur.execute("SELECT id, name FROM businesses WHERE (phone_israel = %s OR phone_israel = %s) AND is_active = true", (to_number.strip(), clean_to))
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
                    <Say voice="he-IL-Wavenet-C" language="he-IL">סליחה, המספר אינו זמין כרגע.</Say>
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
                call_status='ringing',
                started_at=datetime.utcnow()
            )
            db.session.add(call_log)
            db.session.commit()
            
            # Start conversation with greeting  
            greeting = f"שלום! זהו המוקד הוירטואלי של {business_name}. איך אוכל לעזור לך היום?"
            
            twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
            <Response>
                <Say voice="he-IL-Wavenet-C" language="he-IL">{greeting}</Say>
                <Record action="/twilio/handle_recording" method="POST" maxLength="30" timeout="5" transcribe="false"/>
            </Response>'''
            
            logger.info(f"✅ Voice webhook response sent for business: {business_name}")
            return Response(twiml, mimetype='text/xml')
            
        except Exception as e:
            logger.error(f"Error handling incoming call: {str(e)}")
            error_twiml = '''<?xml version="1.0" encoding="UTF-8"?>
            <Response>
                <Say voice="he-IL-Wavenet-C" language="he-IL">סליחה, יש בעיה טכנית.</Say>
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
                    <Say voice="he-IL-Wavenet-C" language="he-IL">לא קלטתי אותך. אנא נסה שוב.</Say>
                    <Record action="/twilio/handle_recording" method="POST" maxLength="30" timeout="5" transcribe="false"/>
                </Response>'''
                return Response(twiml, mimetype='text/xml')
            
            # Process with AI (simplified for now)
            ai_response = f"תודה על פנייתך ל{business_name}. נחזור אליך בהקדם האפשרי."
            
            # Generate response TwiML
            twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
            <Response>
                <Say voice="he-IL-Wavenet-C" language="he-IL">{ai_response}</Say>
                <Hangup/>
            </Response>'''
            
            logger.info(f"✅ Recording processed and response sent for {business_name}")
            return Response(twiml, mimetype='text/xml')
            
        except Exception as e:
            logger.error(f"Error handling recording: {str(e)}")
            error_twiml = '''<?xml version="1.0" encoding="UTF-8"?>
            <Response>
                <Say voice="he-IL-Wavenet-C" language="he-IL">סליחה, הייתה בעיה בעיבוד ההקלטה.</Say>
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