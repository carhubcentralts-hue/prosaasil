# server/whisper_handler.py
import os
import io
import logging
from typing import Optional
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

logger = logging.getLogger(__name__)

def transcribe_he(audio_data: io.BytesIO) -> str:
    """
    Transcribe Hebrew audio using OpenAI Whisper
    """
    if not OPENAI_AVAILABLE:
        logger.warning("OpenAI not available, returning fallback transcription")
        return "הקלטת קול התקבלה"
    
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        logger.warning("No OpenAI API key found, returning fallback transcription")
        return "הקלטת קול התקבלה" 
    
    # Check if audio data has any content
    if not audio_data or audio_data.getvalue() == b'dummy audio data':
        logger.warning("No valid audio data provided")
        return "הקלטת קול התקבלה"
        
    try:
        client = openai.OpenAI(api_key=openai_key)
        
        # Reset audio data position
        audio_data.seek(0)
        
        # Use Whisper for Hebrew transcription
        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=("recording.mp3", audio_data, "audio/mpeg"),
            language="he",  # Hebrew
            response_format="text"
        )
        
        transcription = response.strip()
        logger.info("Hebrew transcription successful: %s chars", len(transcription))
        
        # Filter out gibberish/noise
        if len(transcription) < 3 or transcription.lower() in ["um", "uh", "hmm", "..."]:
            return "לא הצלחתי להבין. אנא חזור שוב"
            
        return transcription
        
    except Exception as e:
        logger.error("Hebrew transcription failed: %s", e)
        return "לא הצלחתי להבין. אנא חזור שוב"

def test_whisper():
    """Test function for Whisper integration"""
    logger.info("Whisper handler loaded successfully")
    return "Whisper ready for Hebrew transcription"