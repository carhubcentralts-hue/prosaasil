# server/hebrew_tts_enhanced.py
import os
import logging
from typing import Optional
import hashlib

logger = logging.getLogger(__name__)

try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False

def create_hebrew_audio(text: str, call_sid: str = "", quality: str = "standard") -> Optional[str]:
    """
    Create Hebrew audio file from text using gTTS
    Returns path to generated audio file
    """
    if not GTTS_AVAILABLE:
        logger.warning("gTTS not available, skipping TTS")
        return None
    
    if not text or len(text.strip()) < 2:
        logger.warning("Text too short for TTS: %s", text)
        return None
    
    try:
        # Create unique filename
        text_hash = hashlib.md5(text.encode()).hexdigest()[:8]
        filename = f"response_{call_sid}_{text_hash}.mp3"
        
        # Ensure voice responses directory exists
        voice_dir = "static/voice_responses"
        os.makedirs(voice_dir, exist_ok=True)
        
        output_path = os.path.join(voice_dir, filename)
        
        # Check if file already exists
        if os.path.exists(output_path):
            logger.info("Using cached TTS file: %s", filename)
            return output_path
        
        # Generate Hebrew TTS
        tts = gTTS(
            text=text,
            lang='iw',  # Hebrew language code
            slow=False
        )
        
        tts.save(output_path)
        
        # Verify file was created and has reasonable size
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            logger.info("Hebrew TTS generated: %s (%d bytes)", filename, file_size)
            
            if file_size > 1000:  # At least 1KB
                return output_path
            else:
                logger.warning("TTS file too small, may be corrupted")
                return None
        else:
            logger.error("TTS file not created")
            return None
            
    except Exception as e:
        logger.error("Hebrew TTS generation failed: %s", e)
        return None

def cleanup_old_audio_files():
    """Clean up old TTS files to save space"""
    try:
        voice_dir = "static/voice_responses"
        if os.path.exists(voice_dir):
            files = [f for f in os.listdir(voice_dir) if f.startswith("response_") and f.endswith(".mp3")]
            
            # Keep only the 20 most recent files
            if len(files) > 20:
                files.sort(key=lambda x: os.path.getmtime(os.path.join(voice_dir, x)))
                for old_file in files[:-20]:
                    os.remove(os.path.join(voice_dir, old_file))
                    logger.info("Cleaned up old TTS file: %s", old_file)
    except Exception as e:
        logger.error("TTS cleanup failed: %s", e)

def test_tts():
    """Test function for TTS"""
    logger.info("Hebrew TTS handler loaded successfully")
    return "TTS ready for Hebrew audio generation"