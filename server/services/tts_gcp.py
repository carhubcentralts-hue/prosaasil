"""
Google Cloud Text-to-Speech service for Hebrew greeting generation
"""
import os
import json
from typing import Optional
from google.cloud import texttospeech

def create_tts_client() -> Optional[texttospeech.TextToSpeechClient]:
    """Create TTS client using service account JSON from environment"""
    try:
        # Use GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON secret (not GOOGLE_APPLICATION_CREDENTIALS)
        sa_json = os.getenv('GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON')
        if not sa_json:
            print("❌ GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON not found")
            return None
            
        # Parse and create client
        credentials_info = json.loads(sa_json)
        client = texttospeech.TextToSpeechClient.from_service_account_info(credentials_info)
        print("✅ Google Cloud TTS client created")
        return client
    except Exception as e:
        print(f"❌ Failed to create TTS client: {e}")
        return None

def synthesize_hebrew_to_mp3(text: str, output_path: str, voice: str = "he-IL-Wavenet-A") -> bool:
    """
    Synthesize Hebrew text to MP3 file using Google Cloud TTS
    """
    try:
        client = create_tts_client()
        if not client:
            return False
            
        # Configure synthesis
        synthesis_input = texttospeech.SynthesisInput(text=text)
        voice_selection = texttospeech.VoiceSelectionParams(
            language_code="he-IL", 
            name=voice
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )
        
        # Synthesize speech
        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice_selection,
            audio_config=audio_config
        )
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Write audio file
        with open(output_path, "wb") as f:
            f.write(response.audio_content)
            
        print(f"✅ Hebrew TTS saved to: {output_path}")
        return True
        
    except Exception as e:
        print(f"❌ TTS synthesis failed: {e}")
        return False

def ensure_greeting_files():
    """Ensure Hebrew greeting files exist"""
    try:
        greetings = {
            "static/tts/greeting_he.mp3": "שלום וברוכים הבאים לשי דירות ומשרדים בעמ. איך אפשר לסייע לך היום?",
            "static/tts/fallback_he.mp3": "שלום, אנא המתן רגע."
        }
        
        for file_path, text in greetings.items():
            if not os.path.exists(file_path):
                print(f"🎯 Creating Hebrew greeting: {file_path}")
                if synthesize_hebrew_to_mp3(text, file_path):
                    print(f"✅ Created: {file_path}")
                else:
                    print(f"❌ Failed to create: {file_path}")
                    
    except Exception as e:
        print(f"❌ Error ensuring greeting files: {e}")

if __name__ == "__main__":
    ensure_greeting_files()