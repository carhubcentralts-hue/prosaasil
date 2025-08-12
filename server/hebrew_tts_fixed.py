#!/usr/bin/env python3
"""
Hebrew Google Cloud TTS System
מערכת קול עברי מקצועית עם Google Cloud
"""

import os
import hashlib
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def generate_hebrew_tts(text: str, filename: str = None) -> str:
    """Generate Hebrew TTS audio using Google Cloud or fallback"""
    
    try:
        # Import Google Cloud TTS (optional)
        from google.cloud import texttospeech
        
        # Initialize client
        client = texttospeech.TextToSpeechClient()
        
        # Configure Hebrew voice
        input_text = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(
            language_code="he-IL",
            name="he-IL-Standard-D",  # Female Hebrew voice
            ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=0.9,  # Slightly slower for clarity
            pitch=-2.0          # Slightly lower pitch
        )
        
        # Generate speech
        response = client.synthesize_speech(
            input=input_text, voice=voice, audio_config=audio_config
        )
        
        # Save to file
        if not filename:
            filename = hashlib.md5(text.encode()).hexdigest()
        
        static_dir = "server/static/voice_responses"
        os.makedirs(static_dir, exist_ok=True)
        
        audio_path = f"{static_dir}/{filename}.mp3"
        with open(audio_path, "wb") as out:
            out.write(response.audio_content)
        
        # Return public URL for Replit deployment  
        return f"https://ai-crmd.replit.app/static/voice_responses/{filename}.mp3"
        
    except ImportError:
        logger.warning("Google Cloud TTS not available, using gtts fallback")
        return generate_gtts_fallback(text, filename)
    except Exception as e:
        logger.error(f"Error generating TTS: {e}")
        return generate_gtts_fallback(text, filename)

def generate_gtts_fallback(text: str, filename: str = None) -> str:
    """Fallback using gTTS (Google Text-to-Speech)"""
    try:
        from gtts import gTTS
        
        if not filename:
            filename = hashlib.md5(text.encode()).hexdigest()
        
        static_dir = "server/static/voice_responses"
        os.makedirs(static_dir, exist_ok=True)
        
        # Generate Hebrew speech (use 'iw' for Hebrew in gTTS)
        tts = gTTS(text=text, lang='iw', slow=False)
        audio_path = f"{static_dir}/{filename}.mp3"
        tts.save(audio_path)
        
        logger.info(f"✅ Generated Hebrew TTS: {filename}.mp3")
        return f"https://ai-crmd.replit.app/static/voice_responses/{filename}.mp3"
        
    except Exception as e:
        logger.error(f"❌ TTS fallback failed: {e}")
        # Return pre-recorded greeting as ultimate fallback
        return "https://ai-crmd.replit.app/static/greeting.mp3"

# Pre-generate common messages
def generate_common_messages():
    """Generate commonly used Hebrew messages"""
    
    messages = {
        "greeting": "שלום וברכה! הגעתם לשי דירות ומשרדים בע״מ. אני כאן לעזור לכם למצוא את הנכס המושלם. במה אוכל לעזור לכם?",
        "listening": "אני מקשיב לכם, אנא דברו אחרי הצפירה",
        "goodbye": "תודה שפניתם אלינו! נשמח לעזור לכם בעתיד. יום טוב!",
        "error": "סליחה, יש בעיה זמנית במערכת. אפשר לנסות שוב?",
        "no_recording": "לא קיבלתי את ההקלטה שלכם. אנא נסו שוב"
    }
    
    for name, text in messages.items():
        try:
            static_dir = "server/static"
            os.makedirs(static_dir, exist_ok=True)
            
            url = generate_hebrew_tts(text, name)
            logger.info(f"✅ Generated {name}: {url}")
        except Exception as e:
            logger.error(f"❌ Error generating {name}: {e}")

if __name__ == "__main__":
    # Test Hebrew TTS
    test_text = "שלום! זהו מבחן למערכת הקול העברי החדש"
    url = generate_hebrew_tts(test_text, "test")
    print(f"Generated: {url}")