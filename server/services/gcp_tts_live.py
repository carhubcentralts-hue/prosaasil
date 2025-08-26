"""
Google Cloud Text-to-Speech for Live Hebrew Response
Real-time Hebrew TTS for Twilio calls
"""
from google.cloud import texttospeech
import os
import logging
import tempfile
import time

log = logging.getLogger("gcp_tts_live")

class HebrewTTSLive:
    """Real-time Hebrew TTS for live call responses"""
    
    def __init__(self):
        self.client = None
        self.voice = texttospeech.VoiceSelectionParams(
            language_code="he-IL",
            name="he-IL-Wavenet-A"  # High quality Hebrew voice
        )
        self.audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=1.1,  # Slightly faster for real-time feel
        )
        self.audio_config_pcm16_8k = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16,
            speaking_rate=1.1,
            sample_rate_hertz=8000,   # ← PCM16 8kHz מונו
        )
        
    def _ensure_client(self):
        """Lazy initialization of TTS client"""
        if self.client is None:
            try:
                self.client = texttospeech.TextToSpeechClient()
                log.info("Google Cloud TTS client initialized")
            except Exception as e:
                log.error(f"Failed to initialize TTS client: {e}")
                raise
        
    def synthesize_hebrew(self, text, output_path=None):
        """סינתזה ל-MP3 (נשאר לצורכי UI/הורדה)"""
        try:
            if not text.strip():
                return None
                
            # Ensure client is initialized
            self._ensure_client()
                
            # Generate output path if not provided
            if not output_path:
                timestamp = int(time.time() * 1000)
                filename = f"hebrew_response_{timestamp}.mp3"
                output_path = os.path.join("static", "tts", filename)
                
            # Ensure directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Create synthesis input
            synthesis_input = texttospeech.SynthesisInput(text=text)
            
            # Call TTS API
            response = self.client.synthesize_speech(
                input=synthesis_input,
                voice=self.voice, 
                audio_config=self.audio_config
            )
            
            # Save audio file
            with open(output_path, "wb") as f:
                f.write(response.audio_content)
                
            log.info(f"Hebrew TTS generated: {len(text)} chars → {output_path}")
            return output_path
            
        except Exception as e:
            log.error(f"Hebrew TTS synthesis failed: {e}")
            return None
            
    def quick_response(self, hebrew_text, call_sid):
        """
        Generate quick Hebrew response for live call
        
        Args:
            hebrew_text: Hebrew response text
            call_sid: Twilio call SID for unique filename
            
        Returns:
            Public URL for the generated MP3
        """
        try:
            # Generate unique filename
            timestamp = int(time.time() * 1000)
            filename = f"live_{call_sid}_{timestamp}.mp3"
            file_path = os.path.join("static", "tts", filename)
            
            # Synthesize speech
            result_path = self.synthesize_hebrew(hebrew_text, file_path)
            
            if result_path:
                # Return public URL
                return f"/static/tts/{filename}"
            else:
                return None
                
        except Exception as e:
            log.error(f"Quick Hebrew response failed: {e}")
            return None

    def synthesize_hebrew_pcm16_8k(self, text: str) -> bytes | None:
        """סינתזה ישירה ל-PCM16 8kHz (ל־Media Streams)"""
        try:
            if not text.strip():
                return None
            self._ensure_client()
            synthesis_input = texttospeech.SynthesisInput(text=text)
            response = self.client.synthesize_speech(
                input=synthesis_input,
                voice=self.voice,
                audio_config=self.audio_config_pcm16_8k,
            )
            return response.audio_content  # LINEAR16 bytes
        except Exception as e:
            log.error(f"TTS_PCM16_ERROR: {e}")
            return None

# Global instance - lazy initialization
_hebrew_tts = None

def get_hebrew_tts():
    """Get the global Hebrew TTS instance"""
    global _hebrew_tts
    if _hebrew_tts is None:
        _hebrew_tts = HebrewTTSLive()
    return _hebrew_tts


def generate_hebrew_response(text, call_sid):
    """Convenience function for generating Hebrew speech responses"""
    try:
        return get_hebrew_tts().quick_response(text, call_sid)
    except Exception as e:
        log.error(f"Hebrew TTS failed, falling back: {e}")
        return None