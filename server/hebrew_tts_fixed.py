"""
Hebrew Text-to-Speech Service - gTTS Only
שירות המרת טקסט לקול בעברית עם gTTS
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
        """Initialize Hebrew TTS Service with gTTS"""
        self.voice_dir = Path("server/static/voice_responses")
        self.voice_dir.mkdir(parents=True, exist_ok=True)
        logger.info("✅ Hebrew TTS Service initialized with gTTS")
        
    def synthesize_hebrew_audio(self, text):
        """יצירת אודיו עברי בלבד עם gTTS"""
        
        # Log every TTS generation event
        logger.info(f"🎵 TTS Request: '{text[:50]}...' ({len(text)} chars)")
        
        # Check if text is empty or too short
        if not text or len(text.strip()) < 1:
            text = "סליחה, לא שמעתי אותך."
            logger.warning("⚠️ Empty text provided, using fallback message")
        
        try:
            # Use gTTS for Hebrew synthesis
            from gtts import gTTS
            
            # Create Hebrew TTS with gTTS (Hebrew uses 'iw' code)
            tts = gTTS(text=text, lang='iw', slow=False)
            
            # Generate unique filename
            unique_id = str(uuid.uuid4())[:8]
            text_hash = hashlib.md5(text.encode()).hexdigest()[:8]
            filename = f"hebrew_{text_hash}_{unique_id}.mp3"
            filepath = self.voice_dir / filename
            
            logger.info(f"🎵 Creating TTS file: {filename} for text: '{text[:50]}...'")
            
            # Ensure unique filenames to avoid cache issues
            if filepath.exists():
                timestamp = str(int(time.time()))
                filename = f"hebrew_{text_hash}_{timestamp}.mp3"
                filepath = self.voice_dir / filename
                logger.info(f"🔄 File exists, using new timestamp: {filename}")
            
            # Save TTS to file
            tts.save(str(filepath))
            
            # Add delay and verify file creation
            time.sleep(0.5)
            
            # Verify file was created and has minimum size
            if filepath.exists() and filepath.stat().st_size > 3000:
                logger.info(f"✅ Created {filename} using gTTS Hebrew ({filepath.stat().st_size} bytes)")
                # Return URL path for Flask routing
                return f"/voice_responses/{filename}"
            else:
                logger.error(f"❌ TTS file creation failed or too small: {filepath}")
                raise Exception("TTS file creation failed")
            
        except Exception as e:
            logger.error(f"❌ gTTS Hebrew synthesis failed: {e}")
            
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