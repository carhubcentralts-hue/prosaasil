"""
Whisper Audio Processing for Hebrew Speech Recognition
תיקון מלא לפי ההנחיות - August 2, 2025
"""

import os
import requests
import logging
from twilio.rest import Client
from openai import OpenAI

# Import AI service and models
try:
    from ai_service import generate_response
    from models import db  # We'll use basic model or create simple one
except ImportError:
    generate_response = None
    db = None  
    logging.warning("Could not import AI service or models")

logger = logging.getLogger(__name__)

def is_gibberish(text):
    """סינון ג'יבריש - בודק אם הטקסט הוא ג'יבריש"""
    if not text or not text.strip():
        return True
    
    text = text.strip()
    
    # בדיקות בסיסיות לג'יבריש
    if len(text) < 5:
        return True
    
    # אם יש יותר מדי נקודות
    if text.lower().count("...") > 3:
        return True
    
    # אם כל הטקסט הוא תווים מוזרים
    if len([c for c in text if c.isalnum() or c in 'אבגדהוזחטיכלמנסעפצקרשת ']) < len(text) * 0.3:
        return True
    
    return False

def download_audio(recording_sid, filename="audio.wav"):
    """הורדת הקלטה מ-Twilio"""
    try:
        twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
        twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
        
        if not twilio_sid or not twilio_token:
            logger.error("Missing Twilio credentials")
            return None
        
        client = Client(twilio_sid, twilio_token)
        recording = client.recordings(recording_sid).fetch()
        
        # Build URL for audio file
        if recording.uri:
            url = f"https://api.twilio.com{recording.uri.replace('.json', '.wav')}"
        else:
            logger.error("No recording URI found")
            return None
        
        logger.info(f"📥 Downloading audio from: {url}")
        
        # Download with Twilio credentials
        response = requests.get(url, auth=(twilio_sid, twilio_token))
        
        if response.status_code != 200:
            logger.error(f"❌ Failed to download audio: {response.status_code}")
            return None
        
        # Save to temporary file
        temp_path = f"/tmp/{filename}"
        with open(temp_path, "wb") as f:
            f.write(response.content)
        
        logger.info(f"✅ Audio downloaded successfully: {temp_path}")
        return temp_path
        
    except Exception as e:
        logger.error(f"❌ Error downloading audio: {e}")
        return None

def transcribe_audio(audio_path):
    """תמלול אודיו עם Whisper"""
    try:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            logger.error("Missing OpenAI API key")
            return None
            
        client = OpenAI(api_key=api_key)
        
        with open(audio_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="he"  # Hebrew
            )
        
        text = transcript.text.strip()
        logger.info(f"📝 Transcription: {text}")
        return text
        
    except Exception as e:
        logger.error(f"❌ Transcription error: {e}")
        return None

def process_recording(recording_sid, call_sid):
    """תהליך מלא: הורדה → תמלול → בדיקת ג'יבריש → AI → שמירה"""
    try:
        # Step 1: Download audio
        audio_path = download_audio(recording_sid)
        if not audio_path:
            return "שגיאה בהורדת הקלטה"
        
        # Step 2: Transcribe
        transcript = transcribe_audio(audio_path)
        if not transcript:
            return "שגיאה בתמלול"
        
        # Step 3: Check for gibberish
        if is_gibberish(transcript):
            logger.info("🚫 Gibberish detected, ending call")
            return "ג'יבריש זוהה, שיחה הופסקה."
        
        # Step 4: Generate AI response
        ai_text = generate_ai_response(transcript, call_sid)
        
        # Step 5: Save to database
        save_transcription_to_db(call_sid, transcript, ai_text)
        
        logger.info(f"✅ Processing complete: {ai_text}")
        return ai_text
        
    except Exception as e:
        logger.error(f"❌ Processing error: {e}")
        return "שגיאה בעיבוד השיחה"

def generate_ai_response(transcript, call_sid=None):
    """יצירת תגובת AI בעברית"""
    try:
        api_key = os.environ.get("OPENAI_API_KEY") 
        if not api_key:
            logger.error("Missing OpenAI API key")
            return "תודה על פנייתכם. נחזור אליכם בהקדם."
            
        client = OpenAI(api_key=api_key)
        
        # Default AI prompt for Hebrew business assistant
        ai_prompt = "אתה עוזר וירטואלי מועיל בעברית לעסק. תן תשובה קצרה, מועילה ומנומסת. השתמש בפנייה מכבדת ותמיד תודה על הפנייה."
        
        messages = [
            {"role": "system", "content": ai_prompt},
            {"role": "user", "content": transcript}
        ]
        
        response = client.chat.completions.create(
            model="gpt-4o", # the newest OpenAI model is "gpt-4o" which was released May 13, 2024. do not change this unless explicitly requested by the user
            messages=messages,
            max_tokens=150,
            temperature=0.7
        )
        
        ai_text = response.choices[0].message.content.strip()
        logger.info(f"🤖 Generated AI response: {ai_text}")
        return ai_text
        
    except Exception as e:
        logger.error(f"❌ AI response error: {e}")
        return "תודה על פנייתכם. נחזור אליכם בהקדם."

def save_transcription_to_db(call_sid, transcript, response):
    """שמירת תמלול למסד נתונים"""
    try:
        if not db:
            logger.warning("Database not available for saving")
            return
            
        # Try to find existing CallLog
        from models import CallLog
        call_log = CallLog.query.filter_by(call_sid=call_sid).first()
        
        if call_log:
            call_log.transcription = transcript
            call_log.ai_response = response
            call_log.call_status = 'completed'
            call_log.updated_at = datetime.utcnow()
            db.session.commit()
            logger.info(f"✅ Updated CallLog for {call_sid}")
        else:
            logger.warning(f"⚠️ CallLog not found for {call_sid} - cannot save transcription")
            
    except Exception as e:
        logger.error(f"❌ Database save error: {e}")

# Compatibility wrapper for older calls
def process_recording_old(recording_url, call_sid):
    """Legacy compatibility - download from URL"""
    try:
        # Download recording directly from URL
        response = requests.get(recording_url, stream=True)
        if response.status_code != 200:
            return "שגיאה בהורדת הקלטה"
            
        # Save to temp file
        temp_path = "/tmp/recording.wav"
        with open(temp_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # Process with standard flow
        transcript = transcribe_audio(temp_path)
        if not transcript:
            return "שגיאה בתמלול"
            
        if is_gibberish(transcript):
            return "ג'יבריש זוהה, שיחה הופסקה."
            
        ai_response = generate_ai_response(transcript, call_sid)
        save_transcription_to_db(call_sid, transcript, ai_response)
        
        # Cleanup
        os.unlink(temp_path)
        
        return ai_response
        
    except Exception as e:
        logger.error(f"❌ Legacy processing error: {e}")
        return "שגיאה בעיבוד השיחה"

# Class wrapper for compatibility
class WhisperHandler:
    def process_recording(self, recording_sid, call_sid):
        """Compatibility wrapper"""
        return process_recording(recording_sid, call_sid)

# Ready to use instance
whisper_handler = WhisperHandler()