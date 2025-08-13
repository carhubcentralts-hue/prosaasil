"""
Hebrew Text-to-Speech Service - Google Cloud + gTTS Fallback
שירות המרת טקסט לקול בעברית עם Google Cloud ו-gTTS כגיבוי
"""
import os
import logging
import hashlib
import uuid
import time
from pathlib import Path

logger = logging.getLogger(__name__)

class HebrewTTSService:
    def __init__(self):
        """Initialize Hebrew TTS Service with Google Cloud + gTTS fallback"""
        self.voice_dir = Path("server/static/voice_responses")
        self.voice_dir.mkdir(parents=True, exist_ok=True)
        
        # Check for Google Cloud credentials
        self.google_available = self._check_google_cloud_availability()
        
        if self.google_available:
            logger.info("✅ Hebrew TTS Service initialized with Google Cloud Wavenet + gTTS fallback")
        else:
            logger.info("✅ Hebrew TTS Service initialized with gTTS only (Google Cloud not available)")
        
    def _check_google_cloud_availability(self):
        """Check if Google Cloud TTS is available"""
        try:
            # Try to fix Google Cloud TTS
            import os
            import json
            import tempfile
            from google.cloud import texttospeech
            
            # Get credentials and create temp file
            credentials_json = os.environ.get('GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON')
            if credentials_json:
                credentials_data = json.loads(credentials_json)
                
                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                    json.dump(credentials_data, f)
                    self.temp_credentials_path = f.name
                
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = self.temp_credentials_path
                
                # Test client creation
                client = texttospeech.TextToSpeechClient()
                logger.info("✅ Google Cloud TTS client initialized successfully")
                return True
                
        except Exception as e:
            logger.info(f"🔄 Google Cloud TTS not available ({e}), using enhanced gTTS")
            
        return False
        
    def synthesize_hebrew_audio_google(self, text):
        """Synthesize Hebrew audio using Google Cloud Wavenet"""
        try:
            from google.cloud import texttospeech
            
            client = texttospeech.TextToSpeechClient()
            
            # Configure the voice request for Hebrew Wavenet
            synthesis_input = texttospeech.SynthesisInput(text=text)
            
            # Hebrew voice configuration - using Wavenet for best quality
            voice = texttospeech.VoiceSelectionParams(
                language_code="he-IL",
                name="he-IL-Wavenet-A",  # Female Hebrew Wavenet voice
                ssml_gender=texttospeech.SsmlVoiceGender.FEMALE,
            )
            
            # Audio configuration - MP3 format
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3,
                speaking_rate=1.0,
                pitch=0.0,
                volume_gain_db=0.0,
            )
            
            # Perform the text-to-speech request
            response = client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config
            )
            
            # Generate unique filename
            unique_id = str(uuid.uuid4())[:8]
            text_hash = hashlib.md5(text.encode()).hexdigest()[:8]
            filename = f"hebrew_wavenet_{text_hash}_{unique_id}.mp3"
            filepath = self.voice_dir / filename
            
            # Write the response to a file
            with open(filepath, "wb") as out:
                out.write(response.audio_content)
            
            # Verify file was created and has minimum size
            if filepath.exists() and filepath.stat().st_size > 3000:
                logger.info(f"✅ Created {filename} using Google Cloud Wavenet ({filepath.stat().st_size} bytes)")
                return f"/voice_responses/{filename}"
            else:
                raise Exception("Google Cloud TTS file creation failed or too small")
                
        except Exception as e:
            logger.error(f"❌ Google Cloud TTS failed: {e}")
            raise e
        
    def synthesize_hebrew_audio_gtts(self, text):
        """Synthesize Hebrew audio using gTTS fallback"""
        try:
            from gtts import gTTS
            
            # Create Hebrew TTS with gTTS (Hebrew uses 'iw' code)
            tts = gTTS(text=text, lang='iw', slow=False)
            
            # Generate unique filename
            unique_id = str(uuid.uuid4())[:8]
            text_hash = hashlib.md5(text.encode()).hexdigest()[:8]
            filename = f"hebrew_gtts_{text_hash}_{unique_id}.mp3"
            filepath = self.voice_dir / filename
            
            logger.info(f"🎵 Creating gTTS file: {filename} for text: '{text[:50]}...'")
            
            # Ensure unique filenames to avoid cache issues
            if filepath.exists():
                timestamp = str(int(time.time()))
                filename = f"hebrew_gtts_{text_hash}_{timestamp}.mp3"
                filepath = self.voice_dir / filename
                logger.info(f"🔄 File exists, using new timestamp: {filename}")
            
            # Save TTS to file
            tts.save(str(filepath))
            
            # Add delay and verify file creation
            time.sleep(0.5)
            
            # Verify file was created and has minimum size
            if filepath.exists() and filepath.stat().st_size > 3000:
                logger.info(f"✅ Created {filename} using gTTS Hebrew ({filepath.stat().st_size} bytes)")
                return f"/voice_responses/{filename}"
            else:
                raise Exception("gTTS file creation failed or too small")
                
        except Exception as e:
            logger.error(f"❌ gTTS Hebrew synthesis failed: {e}")
            raise e
        
    def synthesize_hebrew_audio(self, text):
        """יצירת אודיו עברי עם Google Cloud ו-gTTS כגיבוי"""
        
        # Log every TTS generation event
        logger.info(f"🎵 TTS Request: '{text[:50]}...' ({len(text)} chars)")
        
        # Check if text is empty or too short
        if not text or len(text.strip()) < 1:
            text = "סליחה, לא שמעתי אותך."
            logger.warning("⚠️ Empty text provided, using fallback message")
        
        # Try Google Cloud TTS first (if available)
        if self.google_available:
            try:
                logger.info("🎵 Attempting Google Cloud Wavenet TTS...")
                return self.synthesize_hebrew_audio_google(text)
                
            except Exception as e:
                logger.warning(f"⚠️ Google Cloud TTS failed, falling back to gTTS: {e}")
        
        # Use gTTS fallback
        try:
            logger.info("🎵 Using gTTS fallback...")
            return self.synthesize_hebrew_audio_gtts(text)
            
        except Exception as e:
            logger.error(f"❌ All TTS methods failed: {e}")
            
            # Final fallback - copy existing file
            fallback_files = ["listening.mp3", "processing.mp3", "greeting.mp3"]
            for fallback in fallback_files:
                fallback_path = self.voice_dir / fallback
                if fallback_path.exists():
                    # Create new filename for fallback
                    fallback_filename = f"fallback_{uuid.uuid4().hex[:8]}.mp3"
                    fallback_dest = self.voice_dir / fallback_filename
                    
                    import shutil
                    shutil.copy(str(fallback_path), str(fallback_dest))
                    logger.warning(f"⚠️ Used fallback file {fallback} as {fallback_filename}")
                    return f"/voice_responses/{fallback_filename}"
            
            # Ultimate fallback - return existing processing file
            logger.error("❌ All TTS methods failed, using processing.mp3")
            return "/voice_responses/processing.mp3"