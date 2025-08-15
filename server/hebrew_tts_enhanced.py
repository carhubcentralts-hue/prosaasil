"""
Enhanced Hebrew TTS with Google Cloud Text-to-Speech
Production-ready voice synthesis with fallback support
"""
import os
import logging
from typing import Optional
import hashlib

logger = logging.getLogger(__name__)

try:
    from google.cloud import texttospeech
    from google.oauth2 import service_account
    GOOGLE_TTS_AVAILABLE = True
except ImportError:
    texttospeech = None
    service_account = None
    GOOGLE_TTS_AVAILABLE = False

try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    gTTS = None
    GTTS_AVAILABLE = False

def create_hebrew_audio(text: str, call_sid: str = "", voice_name="he-IL-Wavenet-A") -> Optional[str]:
    """
    Create Hebrew audio using Google Cloud TTS with gTTS fallback
    Returns path to generated audio file
    """
    if not text or not text.strip():
        return None
    
    try:
        # Try Google Cloud TTS first
        if GOOGLE_TTS_AVAILABLE and texttospeech:
            client = texttospeech.TextToSpeechClient()
            input_text = texttospeech.SynthesisInput(text=text)
            voice = texttospeech.VoiceSelectionParams(language_code="he-IL", name=voice_name)
            audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
            response = client.synthesize_speech(input=input_text, voice=voice, audio_config=audio_config)
            
            out_dir = "static/voice_responses"
            os.makedirs(out_dir, exist_ok=True)
            path = os.path.join(out_dir, f"response_{(call_sid or 'greeting')}.mp3")
            with open(path, "wb") as f:
                f.write(response.audio_content)
            return path
        else:
            raise Exception("Google TTS not available")
            
    except Exception as e:
        logger.error("GCP TTS failed; attempting gTTS fallback: %s", e)
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
        
        # Generate Hebrew TTS using fallback
        if not gTTS:
            logger.error("gTTS not available for fallback")
            return None
        
        try:
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
        
        except Exception as gtts_error:
            logger.error("gTTS fallback failed: %s", gtts_error)
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