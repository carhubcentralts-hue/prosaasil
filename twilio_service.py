import os
import logging
from twilio.rest import Client
from twilio.base.exceptions import TwilioException

logger = logging.getLogger(__name__)

class TwilioService:
    def __init__(self):
        self.account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
        self.auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
        self.phone_number = os.environ.get("TWILIO_PHONE_NUMBER")
        
        if not all([self.account_sid, self.auth_token, self.phone_number]):
            logger.error("Missing Twilio credentials in environment variables")
            raise ValueError("Twilio credentials not properly configured")
        
        self.client = Client(self.account_sid, self.auth_token)
    
    def send_sms(self, to_phone_number, message):
        """Send SMS message"""
        try:
            message = self.client.messages.create(
                body=message,
                from_=self.phone_number,
                to=to_phone_number
            )
            logger.info(f"SMS sent with SID: {message.sid}")
            return message.sid
        except TwilioException as e:
            logger.error(f"Failed to send SMS: {str(e)}")
            raise
    
    def get_call_details(self, call_sid):
        """Get call details from Twilio"""
        try:
            call = self.client.calls(call_sid).fetch()
            return {
                'sid': call.sid,
                'status': call.status,
                'duration': call.duration,
                'start_time': call.start_time,
                'end_time': call.end_time,
                'from_': call.from_,
                'to': call.to
            }
        except TwilioException as e:
            logger.error(f"Failed to get call details: {str(e)}")
            raise
    
    def get_call_recordings(self, call_sid):
        """Get recordings for a specific call"""
        try:
            recordings = self.client.recordings.list(call_sid=call_sid)
            return [
                {
                    'sid': rec.sid,
                    'uri': rec.uri,
                    'duration': rec.duration,
                    'date_created': rec.date_created
                }
                for rec in recordings
            ]
        except TwilioException as e:
            logger.error(f"Failed to get call recordings: {str(e)}")
            raise
    
    def send_appointment_confirmation(self, phone_number, business_name, appointment_details):
        """Send appointment confirmation SMS"""
        try:
            message = f"""
שלום! אישור תור ב{business_name}:
📅 תאריך: {appointment_details.get('date', 'לא צוין')}
🕐 שעה: {appointment_details.get('time', 'לא צוינה')}
🔧 שירות: {appointment_details.get('service', 'לא צוין')}

לביטול או שינוי, אנא צרו קשר ישיר.
            """.strip()
            
            return self.send_sms(phone_number, message)
        except Exception as e:
            logger.error(f"Failed to send appointment confirmation: {str(e)}")
            raise
