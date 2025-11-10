"""
Google Cloud Text-to-Speech for Live Hebrew Response
✅ UPGRADED: Natural Hebrew voice with SSML, telephony profile, and smart pronunciation
"""
from google.cloud import texttospeech
import os
import logging
import time
import hashlib
from typing import Optional, Dict

log = logging.getLogger("gcp_tts_live")

# ✅ Import SSML Builder
try:
    from server.services.hebrew_ssml_builder import get_ssml_builder, NamePronunciationHelper
    SSML_AVAILABLE = True
except ImportError:
    SSML_AVAILABLE = False
    get_ssml_builder = lambda **kwargs: None  # Dummy function for type safety
    log.warning("SSML Builder not available - using plain text")


class HebrewTTSLive:
    """Real-time Hebrew TTS with natural voice and smart pronunciation"""
    
    def __init__(self):
        self.client = None
        
        # ✅ 1. קול טבעי - WaveNet-D (גברי) או לפי ENV
        voice_name = os.getenv("TTS_VOICE", "he-IL-Wavenet-D")  # ✅ D = קול גברי טבעי
        speaking_rate = float(os.getenv("TTS_RATE", "1.05"))     # ⚡ BUILD 107: 1.05 = קצב מהיר יותר
        pitch = float(os.getenv("TTS_PITCH", "-2.0"))            # ✅ -2.0 = גובה טבעי
        
        log.info(f"TTS Config: voice={voice_name}, rate={speaking_rate}, pitch={pitch}")
        
        self.voice = texttospeech.VoiceSelectionParams(
            language_code="he-IL",
            name=voice_name
        )
        
        # ⚡ BUILD 107: טלפוניה - PCM16 עם speaking_rate מואץ
        self.audio_config_telephony = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16,  # PCM16 לטלפוניה
            speaking_rate=speaking_rate,  # ⚡ 1.05 = מהיר יותר!
            pitch=pitch,
            sample_rate_hertz=8000,
            effects_profile_id=["telephony-class-application"]  # ✅ מנקה "פלסטיקיות"
        )
        
        # MP3 config (for UI/downloads)
        self.audio_config_mp3 = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=speaking_rate,
            pitch=pitch,
            effects_profile_id=["telephony-class-application"]
        )
        
        # ✅ 3. SSML Builder
        self.enable_ssml = os.getenv("ENABLE_TTS_SSML_BUILDER", "true").lower() == "true"
        if SSML_AVAILABLE and self.enable_ssml:
            self.ssml_builder = get_ssml_builder(enable_ssml=True)
            log.info("✅ SSML Builder enabled - smart pronunciation active")
        else:
            self.ssml_builder = None
            log.info("ℹ️ SSML Builder disabled - using plain text")
        
        # ✅ 4. Cache לפתיחים נפוצים
        self.cache_enabled = os.getenv("TTS_CACHE_ENABLED", "true").lower() == "true"
        self.tts_cache: Dict[str, bytes] = {}
        
    def _ensure_client(self):
        """Lazy initialization of TTS client"""
        if self.client is None:
            try:
                self.client = texttospeech.TextToSpeechClient()
                log.info("Google Cloud TTS client initialized")
            except Exception as e:
                log.error(f"Failed to initialize TTS client: {e}")
                self.client = None
                return False
        return True
    
    def _get_cache_key(self, text: str, config_name: str) -> str:
        """יצירת מפתח cache"""
        voice_name = os.getenv("TTS_VOICE", "he-IL-Wavenet-D")
        rate = os.getenv("TTS_RATE", "0.96")
        pitch = os.getenv("TTS_PITCH", "-2.0")
        
        # Hash של הטקסט + תצורה
        content = f"{text}_{voice_name}_{rate}_{pitch}_{config_name}"
        return hashlib.md5(content.encode()).hexdigest()[:16]
    
    def _prepare_synthesis_input(self, text: str) -> texttospeech.SynthesisInput:
        """
        הכנת input לסינתזה - עם SSML או טקסט רגיל
        
        ✅ זה הקסם - כאן קורה התיקון האוטומטי!
        """
        if not text.strip():
            return texttospeech.SynthesisInput(text="")
        
        # אם SSML מופעל - בנה SSML חכם
        if self.ssml_builder and self.enable_ssml:
            try:
                ssml_text = self.ssml_builder.build_ssml(text)
                log.debug(f"SSML built: {len(text)} chars → {len(ssml_text)} SSML chars")
                return texttospeech.SynthesisInput(ssml=ssml_text)
            except Exception as e:
                log.warning(f"SSML build failed, using plain text: {e}")
                return texttospeech.SynthesisInput(text=text)
        
        # ברירת מחדל - טקסט רגיל
        return texttospeech.SynthesisInput(text=text)
        
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
            
            # ✅ Create synthesis input (with SSML if enabled)
            synthesis_input = self._prepare_synthesis_input(text)
            
            # Call TTS API
            if not self.client:
                log.error("TTS client not initialized")
                return None
                
            response = self.client.synthesize_speech(
                input=synthesis_input,
                voice=self.voice, 
                audio_config=self.audio_config_mp3
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

    def synthesize_hebrew_pcm16_8k(self, text: str) -> Optional[bytes]:
        """
        ✅ סינתזה ישירה ל-PCM16 8kHz (ל־Media Streams) 
        עם SSML חכם, פרופיל טלפוניה, וקול טבעי!
        """
        try:
            if not text.strip():
                return None
            
            # בדיקת cache
            if self.cache_enabled:
                cache_key = self._get_cache_key(text, "pcm16_8k")
                if cache_key in self.tts_cache:
                    log.debug(f"✅ TTS Cache hit: {text[:40]}...")
                    return self.tts_cache[cache_key]
            
            if not self._ensure_client():
                log.error("TTS client not available")
                return None
            
            if self.client is None:
                log.error("TTS client is None after ensure")
                return None
            
            # ✅ הכנת input עם SSML חכם
            synthesis_input = self._prepare_synthesis_input(text)
            
            # ✅ סינתזה עם פרופיל טלפוניה + קול טבעי
            response = self.client.synthesize_speech(
                input=synthesis_input,
                voice=self.voice,
                audio_config=self.audio_config_telephony,  # ✅ טלפוניה!
            )
            
            audio_bytes = response.audio_content
            
            # שמירה ב-cache
            if self.cache_enabled and audio_bytes:
                cache_key = self._get_cache_key(text, "pcm16_8k")
                self.tts_cache[cache_key] = audio_bytes
                log.debug(f"💾 TTS cached: {cache_key}")
            
            return audio_bytes
            
        except Exception as e:
            log.error(f"TTS_PCM16_ERROR: {e}")
            return None
    
    
    def _split_into_chunks(self, text: str, max_chunk_size: int = 200) -> list[str]:
        """
        Split text into chunks for streaming TTS
        Tries to split on sentence boundaries, falls back to word boundaries
        """
        if len(text) <= max_chunk_size:
            return [text]
        
        chunks = []
        
        # Try splitting on sentence boundaries first
        sentences = []
        current = ""
        for char in text:
            current += char
            if char in '.!?' and len(current.strip()) > 0:
                sentences.append(current.strip())
                current = ""
        if current.strip():
            sentences.append(current.strip())
        
        # Group sentences into chunks
        current_chunk = ""
        for sentence in sentences:
            if len(current_chunk) + len(sentence) <= max_chunk_size:
                current_chunk += " " + sentence if current_chunk else sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence
        
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks if chunks else [text]

# Global instance - lazy initialization
_hebrew_tts = None
_last_warm = 0  # ⚡ Phase 2: Pre-warming timestamp

def maybe_warmup():
    """
    ⚡ Phase 2: TTS Pre-warming
    חימום של TTS client כל 8 דקות למניעת cold starts
    """
    global _last_warm
    now = time.time()
    
    # חימום כל 8 דקות
    if now - _last_warm > 8 * 60:
        tts = get_hebrew_tts()
        # ✅ Force client initialization
        if not tts._ensure_client():
            log.error("❌ TTS warmup FAILED: Client initialization failed")
            raise RuntimeError("TTS client initialization failed during warmup")
        
        # שאילתת חימום קצרה (ייכנס ל-cache)
        result = tts.synthesize_hebrew_pcm16_8k("בדיקה")
        if result is None:
            log.error("❌ TTS warmup FAILED: Synthesis returned None")
            raise RuntimeError("TTS synthesis failed during warmup")
        
        _last_warm = now
        log.info(f"✅ TTS warmed up successfully (audio={len(result)} bytes)")
        return True

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
