"""
Background Recording Processing - תמלול והקלטות ברקע
"""
import os
import requests
import logging
from threading import Thread
from datetime import datetime

log = logging.getLogger("tasks.recording")

def enqueue_recording(form_data):
    """שלח הקלטה לעיבוד ברקע (Thread) למנוע timeout"""
    thread = Thread(target=process_recording_async, args=(form_data,))
    thread.daemon = True
    thread.start()
    log.info("Recording processing queued for CallSid=%s", form_data.get("CallSid"))

def process_recording_async(form_data):
    """עיבוד הקלטה אסינכרוני מלא"""
    try:
        recording_url = form_data.get("RecordingUrl")
        call_sid = form_data.get("CallSid")
        from_number = form_data.get("From", "")
        
        log.info("Starting async processing for CallSid=%s", call_sid)
        
        # 1. הורד קובץ הקלטה
        audio_file = download_recording(recording_url, call_sid)
        
        # 2. תמלול עברית
        transcription = transcribe_hebrew(audio_file)
        
        # 3. שמור לDB
        save_call_to_db(call_sid, from_number, recording_url, transcription)
        
        log.info("Recording processed successfully: CallSid=%s", call_sid)
        
    except Exception as e:
        log.error("Recording processing failed: %s", e)

def download_recording(recording_url, call_sid):
    """הורד קובץ הקלטה מTwilio"""
    try:
        # Twilio מחזיר רק metadata, צריך להוסיף .mp3
        mp3_url = f"{recording_url}.mp3"
        
        # הורד עם Basic Auth של Twilio
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        
        if not account_sid or not auth_token:
            log.error("Missing Twilio credentials for download")
            return None
            
        auth = (account_sid, auth_token)
        response = requests.get(mp3_url, auth=auth, timeout=30)
        response.raise_for_status()
        
        # שמור לדיסק
        recordings_dir = "server/recordings"
        os.makedirs(recordings_dir, exist_ok=True)
        
        file_path = f"{recordings_dir}/{call_sid}.mp3"
        with open(file_path, "wb") as f:
            f.write(response.content)
        
        log.info("Recording downloaded: %s (%d bytes)", file_path, len(response.content))
        return file_path
        
    except Exception as e:
        log.error("Failed to download recording: %s", e)
        return None

def transcribe_hebrew(audio_file):
    """תמלול עברית עם OpenAI Whisper"""
    if not audio_file or not os.path.exists(audio_file):
        log.error("Audio file not found: %s", audio_file)
        return ""
    
    try:
        from server.services.whisper_handler import transcribe_he
        
        with open(audio_file, "rb") as f:
            audio_bytes = f.read()
            
        transcription = transcribe_he(audio_bytes)
        log.info("Transcription completed: %d chars", len(transcription or ""))
        return transcription or ""
        
    except Exception as e:
        log.error("Transcription failed: %s", e)
        return ""

def save_call_to_db(call_sid, from_number, recording_url, transcription):
    """שמור שיחה ותמלול ל-DB"""
    try:
        # Import here to avoid circular imports
        import sqlite3
        
        # Use simple SQLite for now (later PostgreSQL)
        db_path = "database.db"
        conn = sqlite3.connect(db_path)
        
        # Create table if not exists
        conn.execute("""
            CREATE TABLE IF NOT EXISTS call_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                call_sid TEXT UNIQUE,
                from_number TEXT,
                recording_url TEXT,
                transcription TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Insert/update call
        conn.execute("""
            INSERT OR REPLACE INTO call_logs 
            (call_sid, from_number, recording_url, transcription)
            VALUES (?, ?, ?, ?)
        """, (call_sid, from_number, recording_url, transcription))
        
        conn.commit()
        conn.close()
        
        log.info("Call saved to DB: %s", call_sid)
        
    except Exception as e:
        log.error("DB save failed: %s", e)
    
    try:
        # נסה Google Speech-to-Text אם מוגדר
        if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            return transcribe_with_google(audio_file)
        else:
            # Fallback ל-Whisper מקומי
            return transcribe_with_whisper(audio_file)
            
    except Exception as e:
        log.error("Transcription failed: %s", e)
        return "תמלול נכשל"

def transcribe_with_google(audio_file):
    """תמלול עם Google Cloud Speech-to-Text"""
    try:
        try:
            from google.cloud import speech
            client = speech.SpeechClient()
        except ImportError:
            log.error("google-cloud-speech not installed")
            return "Google TTS לא מותקן"
        except Exception as e:
            log.error("Failed to create Google Speech client: %s", e)
            return "Google TTS לא זמין"
        
        with open(audio_file, "rb") as f:
            audio_content = f.read()
        
        audio = speech.RecognitionAudio(content=audio_content)
        config = speech.RecognitionConfig(  # type: ignore
            encoding=speech.RecognitionConfig.AudioEncoding.MP3,
            sample_rate_hertz=8000,  # Twilio recordings
            language_code="he-IL",
        )
        
        response = client.recognize(config=config, audio=audio)
        
        transcript = " ".join([result.alternatives[0].transcript for result in response.results])
        return transcript or "לא זוהה טקסט"
        
    except Exception as e:
        log.error("Google transcription failed: %s", e)
        return "תמלול Google נכשל"

def transcribe_with_whisper(audio_file):
    """תמלול עם Whisper מקומי"""
    try:
        try:
            import whisper
            model = whisper.load_model("base")
        except ImportError:
            log.error("whisper not installed")
            return "Whisper לא מותקן"
        except Exception as e:
            log.error("Failed to load Whisper model: %s", e)
            return "Whisper לא זמין"
        result = model.transcribe(audio_file, language="he")  # type: ignore
        return result["text"].strip() or "לא זוהה טקסט"
        
    except Exception as e:
        log.error("Whisper transcription failed: %s", e)
        return "תמלול Whisper נכשל"

def save_call_to_db(call_sid, from_number, recording_url, transcription):
    """שמור נתוני השיחה לבסיס הנתונים"""
    try:
        # TODO: שמירה לDB אמיתי
        # כרגע רק לוג
        call_data = {
            "call_sid": call_sid,
            "from_number": from_number,
            "recording_url": recording_url,
            "transcription": transcription,
            "created_at": datetime.now().isoformat()
        }
        
        log.info("Call data to save: %s", call_data)
        
        # כאן תהיה השמירה לטבלת calls
        # db.session.add(Call(**call_data))
        # db.session.commit()
        
    except Exception as e:
        log.error("Failed to save call to DB: %s", e)