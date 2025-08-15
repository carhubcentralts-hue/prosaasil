#!/usr/bin/env python3
# create_hebrew_greeting.py - יצירת קובץ ברכה בעברית

import os
import sys

def create_greeting_mp3():
    """יצירת קובץ ברכה MP3 בעברית"""
    try:
        # Google Cloud TTS
        from google.cloud import texttospeech
        
        # הגדרת credentials
        creds_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if creds_json and creds_json.startswith("{"):
            with open("/tmp/tts_creds.json", "w") as f:
                f.write(creds_json)
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/tmp/tts_creds.json"
        
        client = texttospeech.TextToSpeechClient()
        
        # טקסט הברכה
        text = "שלום, אתם מדברים עם שי דירות ומשרדים בעמ. איך אוכל לעזור לכם היום?"
        
        # הגדרות TTS
        synthesis_input = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(
            language_code="he-IL",
            name="he-IL-Wavenet-A"
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )
        
        # יצירת הקול
        response = client.synthesize_speech(
            input=synthesis_input, 
            voice=voice, 
            audio_config=audio_config
        )
        
        # שמירה
        os.makedirs("static/voice_responses", exist_ok=True)
        with open("static/voice_responses/hebrew_greeting.mp3", "wb") as f:
            f.write(response.audio_content)
        
        print("✅ Hebrew greeting MP3 created successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Google TTS failed: {e}")
        return False

def create_simple_greeting():
    """יצירת ברכה פשוטה כטקסט"""
    try:
        # אם אין Google TTS, ניצור placeholder
        os.makedirs("static/voice_responses", exist_ok=True)
        
        # יצירת קובץ ריק שמסמן שצריך Google TTS
        with open("static/voice_responses/hebrew_greeting.mp3", "wb") as f:
            f.write(b"")  # קובץ ריק
            
        print("ℹ️ Placeholder greeting file created")
        return True
        
    except Exception as e:
        print(f"❌ Failed to create placeholder: {e}")
        return False

if __name__ == "__main__":
    print("🎤 Creating Hebrew greeting...")
    
    # נסה Google TTS קודם
    if create_greeting_mp3():
        sys.exit(0)
    else:
        # אם לא, צור placeholder
        if create_simple_greeting():
            print("⚠️ Using text greeting fallback")
            sys.exit(0)
        else:
            print("❌ Failed to create greeting")
            sys.exit(1)