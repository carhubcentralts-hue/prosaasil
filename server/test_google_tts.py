"""
Test Google Cloud TTS separately
"""
import os
import json
import tempfile

def test_google_cloud_tts():
    try:
        from google.cloud import texttospeech
        print("✅ Successfully imported google.cloud.texttospeech")
        
        # Get credentials
        credentials_json = os.environ.get('GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON')
        if not credentials_json:
            print("❌ No GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON found")
            return False
            
        print("✅ Found credentials JSON")
        
        # Parse JSON
        credentials_data = json.loads(credentials_json)
        print("✅ Successfully parsed JSON credentials")
        
        # Create temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(credentials_data, f)
            temp_path = f.name
            
        print(f"✅ Created temp credentials file: {temp_path}")
        
        # Set environment variable
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = temp_path
        print("✅ Set GOOGLE_APPLICATION_CREDENTIALS")
        
        # Initialize client
        client = texttospeech.TextToSpeechClient()
        print("✅ Successfully created TextToSpeechClient")
        
        # Test synthesis
        synthesis_input = texttospeech.SynthesisInput(text="בדיקה")
        
        voice = texttospeech.VoiceSelectionParams(
            language_code="he-IL",
            name="he-IL-Wavenet-A",
            ssml_gender=texttospeech.SsmlVoiceGender.FEMALE,
        )
        
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )
        
        print("✅ Attempting synthesis...")
        response = client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )
        
        print(f"✅ SUCCESS! Got {len(response.audio_content)} bytes of audio")
        
        # Cleanup
        os.unlink(temp_path)
        
        return True
        
    except Exception as e:
        import traceback
        print(f"❌ Error: {e}")
        print(f"❌ Full traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    test_google_cloud_tts()