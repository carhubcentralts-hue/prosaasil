"""
Enhanced Hebrew Audio Quality for Twilio Calls
יצירת קבצי קול איכותיים בעברית
"""
import os
from pathlib import Path

def create_premium_hebrew_audio():
    """Create premium quality Hebrew audio files"""
    
    print("🎙️ יצירת קבצי קול איכותיים בעברית")
    print("=====================================")
    
    # Check available TTS options
    output_dir = Path("static/voice_responses")
    output_dir.mkdir(exist_ok=True)
    
    # Option 1: gTTS with enhanced settings
    try:
        from gtts import gTTS
        print("✅ gTTS זמין - יוצר עם הגדרות מתקדמות")
        
        texts = {
            "greeting_premium": "שלום, אני עוזרת הווירטואלית של שי דירות ומשרדים",
            "listening_premium": "אני מאזינה דבר עכשיו"
        }
        
        for name, text in texts.items():
            # Enhanced gTTS settings for better quality
            tts = gTTS(
                text=text, 
                lang='iw',  # Hebrew
                slow=True,  # Slower speech for clarity
                tld='co.il'  # Israeli Google domain for better Hebrew
            )
            
            output_path = output_dir / f"{name}.mp3"
            tts.save(str(output_path))
            print(f"✅ נוצר: {output_path} ({len(text)} תווים)")
            
    except ImportError:
        print("❌ gTTS לא זמין")
    
    # Option 2: Check if Google Cloud TTS is available
    try:
        from google.cloud import texttospeech
        import json
        
        print("✅ Google Cloud TTS זמין - יוצר איכות פרימיום")
        
        client = texttospeech.TextToSpeechClient()
        
        texts = {
            "greeting_cloud": "שלום, אני עוזרת הווירטואלית של שי דירות ומשרדים",
            "listening_cloud": "אני מאזינה דבר עכשיו"
        }
        
        # Hebrew voice configuration
        voice = texttospeech.VoiceSelectionParams(
            language_code="he-IL",  # Hebrew Israel
            ssml_gender=texttospeech.SsmlVoiceGender.FEMALE,
            name="he-IL-Standard-A"  # Best Hebrew voice
        )
        
        # High quality audio configuration
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=0.9,  # Slightly slower
            pitch=0.0,  # Natural pitch
            volume_gain_db=0.0  # Natural volume
        )
        
        for name, text in texts.items():
            synthesis_input = texttospeech.SynthesisInput(text=text)
            
            response = client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config
            )
            
            output_path = output_dir / f"{name}.mp3"
            with open(output_path, "wb") as out:
                out.write(response.audio_content)
            
            print(f"✅ Google Cloud: {output_path}")
            
    except Exception as e:
        print(f"⚠️ Google Cloud TTS לא זמין: {e}")
    
    print()
    print("🔍 סיכום קבצי הקול שנוצרו:")
    for file in output_dir.glob("*.mp3"):
        size = file.stat().st_size
        print(f"📄 {file.name}: {size:,} bytes")

if __name__ == "__main__":
    create_premium_hebrew_audio()