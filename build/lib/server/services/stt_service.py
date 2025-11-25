"""
STT Service - Unified Speech-to-Text with Google v2 Primary + Whisper Fallback
שירות תמלול מאוחד - Google STT v2 מהיר + Whisper כ-fallback
"""
import os
import logging
import tempfile
from typing import Optional

log = logging.getLogger(__name__)

def transcribe_audio_file(audio_file_path: str, call_sid: Optional[str] = None) -> str:
    """
    תמלול קובץ אודיו עם Google STT v2 (Primary) + Whisper (Fallback)
    
    Args:
        audio_file_path: נתיב לקובץ אודיו
        call_sid: מזהה שיחה ללוגים
        
    Returns:
        טקסט מתומלל בעברית
    """
    # 1️⃣ נסה Google STT v2 קודם (מהיר מאוד!)
    try:
        text = _transcribe_with_google_v2(audio_file_path)
        if text and len(text.strip()) > 3:
            log.info(f"✅ Google STT v2 success for {call_sid}: {len(text)} chars")
            return text
    except Exception as e:
        log.warning(f"Google STT v2 failed for {call_sid}, falling back to Whisper: {e}")
    
    # 2️⃣ Fallback ל-Whisper (איטי יותר אבל אמין)
    try:
        with open(audio_file_path, 'rb') as f:
            audio_bytes = f.read()
        
        from server.services.whisper_handler import transcribe_he
        text = transcribe_he(audio_bytes, call_sid)
        
        if text and len(text.strip()) > 3:
            log.info(f"✅ Whisper fallback success for {call_sid}: {len(text)} chars")
            return text
        else:
            log.warning(f"⚠️ Whisper returned empty for {call_sid}")
            return ""
            
    except Exception as e:
        log.error(f"❌ Both Google STT and Whisper failed for {call_sid}: {e}")
        return ""

def _transcribe_with_google_v2(audio_file_path: str) -> str:
    """
    תמלול עם Google Cloud Speech-to-Text v2 (מהיר!)
    
    Args:
        audio_file_path: נתיב לקובץ אודיו (MP3/WAV)
        
    Returns:
        טקסט מתומלל בעברית
    """
    try:
        from google.cloud import speech_v2 as speech
        
        # אתחול Client עם credentials
        client = _get_google_client_v2()
        
        # קריאת קובץ אודיו
        with open(audio_file_path, "rb") as f:
            audio_content = f.read()
        
        # הגדרות תמלול עברית מותאמות לנדל"ן
        config = speech.RecognitionConfig(
            auto_decoding_config=speech.AutoDetectDecodingConfig(),  # זיהוי פורמט אוטומטי
            language_codes=["he-IL"],  # עברית
            model="long",  # מודל ארוך (עד 5 דקות)
            features=speech.RecognitionFeatures(
                enable_automatic_punctuation=True,  # סימני פיסוק אוטומטיים
                enable_word_time_offsets=False,  # לא צריך timestamps
                profanity_filter=False,  # ללא סינון קללות
            )
        )
        
        # בקשת תמלול
        request = speech.RecognizeRequest(
            recognizer=f"projects/{_get_gcp_project_id()}/locations/global/recognizers/_",
            config=config,
            content=audio_content
        )
        
        # שליחת בקשה לGoogle
        response = client.recognize(request=request)
        
        # איסוף תוצאות
        transcript_parts = []
        for result in response.results:
            if result.alternatives:
                transcript_parts.append(result.alternatives[0].transcript)
        
        full_transcript = " ".join(transcript_parts).strip()
        
        return full_transcript
        
    except Exception as e:
        log.error(f"Google STT v2 error: {e}")
        raise

def _get_google_client_v2():
    """יצירת Google Speech v2 Client עם credentials"""
    from google.cloud import speech_v2 as speech
    import json
    
    # נסה להשתמש ב-service account JSON
    sa_json = os.getenv('GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON')
    if sa_json:
        try:
            credentials_info = json.loads(sa_json)
            from google.oauth2 import service_account
            credentials = service_account.Credentials.from_service_account_info(credentials_info)
            client = speech.SpeechClient(credentials=credentials)
            log.info("✅ Google Speech v2 client initialized with service account")
            return client
        except Exception as e:
            log.warning(f"Failed to use service account, falling back to default: {e}")
    
    # Fallback: default credentials
    client = speech.SpeechClient()
    log.info("✅ Google Speech v2 client initialized (default credentials)")
    return client

def _get_gcp_project_id() -> str:
    """קבלת GCP Project ID מהסביבה"""
    # נסה מ-environment variable
    project_id = os.getenv('GOOGLE_CLOUD_PROJECT') or os.getenv('GCP_PROJECT')
    
    if project_id:
        return project_id
    
    # נסה לחלץ מ-service account JSON
    sa_json = os.getenv('GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON')
    if sa_json:
        try:
            import json
            credentials_info = json.loads(sa_json)
            project_id = credentials_info.get('project_id')
            if project_id:
                return project_id
        except:
            pass
    
    # Fallback ברירת מחדל
    log.warning("GCP project ID not found, using default 'my-project'")
    return "my-project"

def transcribe_audio_bytes(audio_bytes: bytes, call_sid: Optional[str] = None) -> str:
    """
    תמלול מ-bytes ישירות (ללא קובץ)
    
    Args:
        audio_bytes: נתוני אודיו
        call_sid: מזהה שיחה
        
    Returns:
        טקסט מתומלל
    """
    # שמור זמנית לקובץ
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        f.write(audio_bytes)
        temp_path = f.name
    
    try:
        result = transcribe_audio_file(temp_path, call_sid)
        return result
    finally:
        # נקה קובץ זמני
        try:
            os.unlink(temp_path)
        except:
            pass
