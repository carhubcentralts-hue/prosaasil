"""
Enhanced Hebrew TTS Service with better voice quality
תיקון מקיף לאיכות הקול העברי
"""
import os
import uuid
import hashlib
import time
import logging
from pathlib import Path
from gtts import gTTS
import requests
import tempfile

logger = logging.getLogger(__name__)

class EnhancedHebrewTTS:
    def __init__(self):
        """Initialize enhanced Hebrew TTS with multiple quality options"""
        self.output_dir = Path("server/static/voice_responses")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Clean up old files periodically
        self._cleanup_old_files()
        
    def _cleanup_old_files(self):
        """Clean up files older than 1 hour"""
        try:
            current_time = time.time()
            for file_path in self.output_dir.glob("hebrew_*.mp3"):
                if current_time - file_path.stat().st_mtime > 3600:  # 1 hour
                    file_path.unlink()
                    logger.info(f"🧹 Cleaned up old file: {file_path.name}")
        except Exception as e:
            logger.warning(f"⚠️ Cleanup failed: {e}")
    
    def synthesize_professional_hebrew(self, text: str) -> str:
        """Create professional quality Hebrew audio with multiple fallbacks"""
        if not text or len(text.strip()) < 1:
            text = "סליחה, לא שמעתי אותך."
            
        logger.info(f"🎙️ Creating professional Hebrew TTS: '{text[:50]}...'")
        
        # Method 1: Try enhanced gTTS with multiple quality settings
        for method in ['premium', 'standard', 'basic']:
            try:
                audio_path = self._create_gtts_audio(text, method)
                if audio_path:
                    return audio_path
            except Exception as e:
                logger.warning(f"⚠️ Method {method} failed: {e}")
                continue
        
        # Ultimate fallback
        return self._create_fallback_audio()
    
    def _create_gtts_audio(self, text: str, quality: str) -> str:
        """Create gTTS audio with different quality settings"""
        
        # Quality configurations
        configs = {
            'premium': {'lang': 'iw', 'tld': 'co.il', 'slow': False},
            'standard': {'lang': 'iw', 'tld': 'com', 'slow': False}, 
            'basic': {'lang': 'he', 'tld': 'com', 'slow': False}
        }
        
        config = configs.get(quality, configs['standard'])
        
        try:
            # Create unique filename
            text_hash = hashlib.md5(text.encode()).hexdigest()[:8]
            unique_id = str(uuid.uuid4())[:8]
            filename = f"hebrew_{quality}_{text_hash}_{unique_id}.mp3"
            filepath = self.output_dir / filename
            
            logger.info(f"🎵 Creating {quality} quality audio: {filename}")
            
            # Create TTS with configuration
            tts = gTTS(text=text, **config)
            tts.save(str(filepath))
            
            # Verify file creation and quality
            time.sleep(0.3)  # Allow file to be written
            
            if filepath.exists() and filepath.stat().st_size > 2000:
                logger.info(f"✅ Created {quality} Hebrew audio: {filename} ({filepath.stat().st_size} bytes)")
                return f"/voice_responses/{filename}"
            else:
                raise Exception(f"File too small or not created: {filepath.stat().st_size if filepath.exists() else 0} bytes")
                
        except Exception as e:
            logger.error(f"❌ {quality} gTTS failed: {e}")
            raise e
    
    def _create_fallback_audio(self) -> str:
        """Create fallback audio using existing files"""
        fallback_files = ["processing.mp3", "listening.mp3", "greeting.mp3"]
        
        for fallback in fallback_files:
            fallback_path = self.output_dir / fallback
            if fallback_path.exists():
                # Create copy with unique name
                unique_id = str(uuid.uuid4())[:8]
                fallback_filename = f"fallback_{unique_id}.mp3"
                fallback_dest = self.output_dir / fallback_filename
                
                import shutil
                shutil.copy(str(fallback_path), str(fallback_dest))
                logger.warning(f"⚠️ Used fallback audio: {fallback} -> {fallback_filename}")
                return f"/voice_responses/{fallback_filename}"
        
        # Ultimate fallback - return existing file
        logger.error("❌ All TTS methods failed, using processing.mp3")
        return "/voice_responses/processing.mp3"