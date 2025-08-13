"""
Create simple listening audio: "אני מאזינה דבר עכשיו"
"""
import os
from gtts import gTTS
from pathlib import Path

def create_listening_audio():
    """Create simple Hebrew audio for listening prompt"""
    
    # Text in Hebrew
    text = "אני מאזינה דבר עכשיו"
    
    # Create audio
    tts = gTTS(text=text, lang='iw', slow=False)
    
    # Save to voice responses directory
    output_dir = Path("static/voice_responses")
    output_dir.mkdir(exist_ok=True)
    
    output_path = output_dir / "listening_simple.mp3"
    tts.save(str(output_path))
    
    print(f"✅ Created: {output_path}")
    print(f"📝 Text: '{text}'")
    
    # Also create a greeting
    greeting_text = "שלום, אני עוזרת של שי דירות ומשרדים"
    greeting_tts = gTTS(text=greeting_text, lang='iw', slow=False)
    
    greeting_path = output_dir / "greeting_simple.mp3"
    greeting_tts.save(str(greeting_path))
    
    print(f"✅ Created: {greeting_path}")
    print(f"📝 Text: '{greeting_text}'")

if __name__ == "__main__":
    create_listening_audio()