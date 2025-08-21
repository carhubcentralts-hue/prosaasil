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

def save_call_status(call_sid, status):
    """Update call status in database"""
    try:
        import sqlite3
        
        # Update call status in SQLite
        db_path = "database.db"
        conn = sqlite3.connect(db_path)
        
        # Add status column if it doesn't exist
        try:
            conn.execute("ALTER TABLE call_logs ADD COLUMN call_status TEXT DEFAULT 'unknown'")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Update call status
        conn.execute("""
            UPDATE call_logs 
            SET call_status = ?
            WHERE call_sid = ?
        """, (status, call_sid))
            
        conn.commit()
        conn.close()
        
        log.info("Call status updated: %s -> %s", call_sid, status)
        
    except Exception as e:
        log.error("Failed to update call status: %s", e)

def transcribe_with_whisper_api(audio_file):
    """תמלול עם OpenAI Whisper API (לא מקומי)"""
    try:
        from server.services.whisper_handler import transcribe_he
        
        with open(audio_file, "rb") as f:
            audio_bytes = f.read()
            
        return transcribe_he(audio_bytes) or "לא זוהה טקסט"
        
    except Exception as e:
        log.error("Whisper API transcription failed: %s", e)
        return "תמלול Whisper נכשל"

