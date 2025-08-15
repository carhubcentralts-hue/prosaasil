#!/usr/bin/env python3
"""
Create Hebrew greeting MP3 for voice responses using Google TTS
"""
import os
import sys
sys.path.append('.')

def create_greeting():
    try:
        from server.hebrew_tts_enhanced import create_hebrew_audio
        
        greeting_text = "שלום וברוכים הבאים לשי דירות ומשרדים. אנא השאירו הודעה קצרה ונחזור אליכם בהקדם."
        
        # Create greeting MP3
        audio_path = create_hebrew_audio(greeting_text, "greeting")
        
        if audio_path and os.path.exists(audio_path):
            # Copy to static directory
            target_path = "static/voice_responses/welcome.mp3"
            os.makedirs("static/voice_responses", exist_ok=True)
            
            import shutil
            shutil.copy2(audio_path, target_path)
            print(f"✅ Hebrew greeting created: {target_path}")
            return True
        else:
            print("❌ Failed to create Hebrew greeting")
            return False
            
    except Exception as e:
        print(f"❌ Error creating greeting: {e}")
        return False

if __name__ == "__main__":
    create_greeting()