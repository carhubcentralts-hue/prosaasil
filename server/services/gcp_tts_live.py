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
        self.client = texttospeech.TextToSpeechClient()
        self.voice = texttospeech.VoiceSelectionParams(
            language_code="he-IL",
            name="he-IL-Wavenet-A"  # High quality Hebrew voice
        )
        self.audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=1.1,  # Slightly faster for real-time feel
        )
        
    def synthesize_hebrew(self, text, output_path=None):
        """
        Generate Hebrew speech from text
        
        Args:
            text: Hebrew text to speak
            output_path: Path to save MP3 file (optional)
            
        Returns:
            Path to generated MP3 file
        """
        try:
            if not text.strip():
                return None
                
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

# Global instance
hebrew_tts = HebrewTTSLive()

def generate_hebrew_response(text, call_sid):
    """Convenience function for generating Hebrew speech responses"""
    return hebrew_tts.quick_response(text, call_sid)