"""
STT Service - Whisper-only Speech-to-Text (Google DISABLED for production stability)
שירות תמלול - רק Whisper (גוגל מנוטרל ליציבות)
"""
import os
import logging
import tempfile
from typing import Optional

log = logging.getLogger(__name__)

# 🚫 DISABLE_GOOGLE: Hard off - prevents stalls and latency issues
DISABLE_GOOGLE = os.getenv('DISABLE_GOOGLE', 'true').lower() == 'true'

if DISABLE_GOOGLE:
    log.info("🚫 Google STT DISABLED (DISABLE_GOOGLE=true) - using Whisper only")

def transcribe_audio_file(audio_file_path: str, call_sid: Optional[str] = None) -> str:
    """
    תמלול קובץ אודיו עם Whisper בלבד (Google DISABLED)
    
    Args:
        audio_file_path: נתיב לקובץ אודיו
        call_sid: מזהה שיחה ללוגים
        
    Returns:
        טקסט מתומלל בעברית
    """
    # ✅ Use Whisper for transcription (Google STT is disabled)
    try:
        with open(audio_file_path, 'rb') as f:
            audio_bytes = f.read()
        
        from server.services.whisper_handler import transcribe_he
        text = transcribe_he(audio_bytes, call_sid)
        
        if text and len(text.strip()) > 3:
            log.info(f"✅ Whisper transcription success for {call_sid}: {len(text)} chars")
            return text
        else:
            log.warning(f"⚠️ Whisper returned empty for {call_sid}")
            return ""
            
    except Exception as e:
        log.error(f"❌ Whisper transcription failed for {call_sid}: {e}")
        return ""

def _transcribe_with_google_v2(audio_file_path: str) -> str:
    """
    🚫 DISABLED - Google STT v2 is turned off for production stability
    
    This function is deprecated and should not be called.
    Use Whisper transcription instead.
    """
    if DISABLE_GOOGLE:
        log.warning("⚠️ _transcribe_with_google_v2 called but Google is DISABLED")
        raise NotImplementedError("Google STT is disabled (DISABLE_GOOGLE=true)")
    
    log.error("❌ Google STT should not be used - DISABLE_GOOGLE flag should be set")
    raise NotImplementedError("Google STT is disabled for production stability")

def _get_google_client_v2():
    """
    🚫 DISABLED - Google client creation is turned off
    """
    if DISABLE_GOOGLE:
        log.warning("⚠️ _get_google_client_v2 called but Google is DISABLED")
        return None
    
    raise NotImplementedError("Google STT client is disabled (DISABLE_GOOGLE=true)")

def _get_gcp_project_id() -> str:
    """
    🚫 DISABLED - GCP project ID lookup is turned off
    """
    if DISABLE_GOOGLE:
        return "disabled"
    
    raise NotImplementedError("GCP project ID lookup is disabled (DISABLE_GOOGLE=true)")

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
