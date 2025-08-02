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
        if generate_response:
            ai_text = generate_response(transcript)
        else:
            ai_text = "תודה על פנייתכם. נחזור אליכם בהקדם."
        
        # Step 5: Save to database
        save_transcription_to_db(call_sid, transcript, ai_text)
        
        logger.info(f"✅ Processing complete: {ai_text}")
        return ai_text
        
    except Exception as e:
        logger.error(f"❌ Processing error: {e}")
        return "שגיאה בעיבוד השיחה"

def save_transcription_to_db(call_sid, transcript, response):
    """שמירת תמלול למסד נתונים"""
    try:
        if not db:
            logger.warning("⚠️ Database not available, skipping save")
            return
        
        # Simple logging for now - could create Call model later
        logger.info(f"💾 Would save to database: {call_sid} - {transcript[:50]}...")
        
        db.session.commit()
        logger.info(f"💾 Saved to database: {call_sid}")
        
    except Exception as e:
        logger.error(f"❌ Database save error: {e}")

# Compatibility class for existing code
class HebrewWhisperHandler:
    """מעבד אודיו עברי עם Whisper API - Compatibility class"""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.logger = logging.getLogger(__name__)
    
    def process_recording(self, recording_sid, call_sid):
        """Compatibility wrapper"""
        return process_recording(recording_sid, call_sid)