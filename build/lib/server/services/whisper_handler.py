"""
Whisper transcription service for Hebrew audio
Consolidated from legacy/whisper_handler.py
"""
import os
import logging
import tempfile
from typing import Optional

log = logging.getLogger(__name__)

def transcribe_he(audio_bytes: bytes, call_sid: Optional[str] = None) -> Optional[str]:
    """
    Transcribe Hebrew audio using OpenAI Whisper
    
    Args:
        audio_bytes: Raw audio data
        call_sid: Optional call SID for logging
        
    Returns:
        Transcribed text or None if failed
    """
    if os.getenv("NLP_DISABLED", "false").lower() in ("true", "1"):
        log.warning("NLP disabled - returning empty transcription")
        return ""
    
    try:
        import openai
        
        # Save audio to temp file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            temp_file.write(audio_bytes)
            temp_path = temp_file.name
        
        try:
            # Transcribe with Whisper
            with open(temp_path, 'rb') as audio_file:
                transcript = openai.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="he"  # Hebrew
                )
            
            text = transcript.text.strip()
            
            # Filter gibberish
            if len(text) < 3 or text.count('?') > len(text) // 3:
                log.warning("Gibberish detected, ignoring transcription: %s", text[:50])
                return None
                
            log.info("Hebrew transcription successful", extra={
                "call_sid": call_sid,
                "chars": len(text),
                "preview": text[:50]
            })
            
            return text
            
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_path)
            except OSError:
                pass
                
    except Exception as e:
        log.error("Transcription failed", extra={
            "call_sid": call_sid,
            "error": str(e)
        })
        return None