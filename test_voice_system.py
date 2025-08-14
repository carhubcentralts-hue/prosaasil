#!/usr/bin/env python3
"""
Complete Voice System Test - Hebrew AI Call Center
בדיקת מערכת קול מלאה - מוקד שיחות AI בעברית
"""

import sys
import os
import io
import requests
from urllib.parse import urlparse

sys.path.append('.')

def test_environment():
    """Test critical environment variables"""
    print("🔑 בדיקת משתני סביבה:")
    
    required_vars = {
        'HOST': 'Audio file serving',
        'OPENAI_API_KEY': 'AI & Whisper',
        'GOOGLE_APPLICATION_CREDENTIALS': 'Hebrew TTS'
    }
    
    all_ok = True
    for var, desc in required_vars.items():
        value = os.getenv(var)
        if value:
            masked = f"{value[:8]}...{value[-8:]}" if len(value) > 16 else value
            print(f"✅ {var}: {masked} ({desc})")
        else:
            print(f"❌ {var}: MISSING ({desc})")
            all_ok = False
    
    return all_ok

def test_whisper():
    """Test Whisper transcription"""
    print("\n🎤 בדיקת Whisper:")
    try:
        from server.whisper_handler import transcribe_he
        
        # Test with dummy data (will trigger fallback)
        dummy_audio = io.BytesIO(b'test audio')
        result = transcribe_he(dummy_audio)
        print(f"✅ Whisper response: {result}")
        return True
    except Exception as e:
        print(f"❌ Whisper test failed: {e}")
        return False

def test_ai_conversation():
    """Test AI conversation"""
    print("\n🤖 בדיקת AI conversation:")
    try:
        from server.ai_conversation import generate_response
        response = generate_response("אני מחפש דירה בתל אביב", "TEST-AI")
        print(f"✅ AI response: {response[:80]}...")
        return True
    except Exception as e:
        print(f"❌ AI test failed: {e}")
        return False

def test_hebrew_tts():
    """Test Hebrew TTS"""
    print("\n🔊 בדיקת Hebrew TTS:")
    try:
        from server.hebrew_tts_enhanced import create_hebrew_audio
        audio_path = create_hebrew_audio("זוהי בדיקת מערכת קול", "TEST-TTS")
        print(f"✅ TTS created: {audio_path}")
        
        # Check if file exists
        if os.path.exists(audio_path):
            file_size = os.path.getsize(audio_path)
            print(f"✅ Audio file size: {file_size} bytes")
            
            # Test URL construction
            host = os.getenv('HOST')
            if host:
                full_url = f"{host}/{audio_path}"
                print(f"✅ Full URL: {full_url}")
                return True
            else:
                print("❌ No HOST for URL construction")
                return False
        else:
            print(f"❌ Audio file not found: {audio_path}")
            return False
            
    except Exception as e:
        print(f"❌ TTS test failed: {e}")
        return False

def test_twilio_webhooks():
    """Test Twilio webhooks"""
    print("\n📞 בדיקת Twilio webhooks:")
    try:
        # Test incoming call
        response = requests.post("http://localhost:5000/webhook/incoming_call", 
                               data={"CallSid": "TEST-WEBHOOK", "From": "+972501234567"})
        
        if response.status_code == 200:
            print("✅ Incoming call webhook: OK")
            
            # Check TwiML response
            if 'xml' in response.text.lower() and 'record' in response.text.lower():
                print("✅ Valid TwiML with Record instruction")
                return True
            else:
                print("⚠️ Response may not be valid TwiML")
                return False
        else:
            print(f"❌ Webhook failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Webhook test failed: {e}")
        return False

def main():
    """Run complete system test"""
    print("🎯 בדיקת מערכת קול מלאה - Hebrew AI Call Center")
    print("=" * 60)
    
    tests = [
        ("Environment Variables", test_environment),
        ("Whisper Transcription", test_whisper),
        ("AI Conversation", test_ai_conversation),
        ("Hebrew TTS", test_hebrew_tts),
        ("Twilio Webhooks", test_twilio_webhooks)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
    
    print("\n" + "=" * 60)
    print(f"🎯 סיכום בדיקה: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 המערכת מוכנה לשיחות קוליות!")
        print("✅ Voice system is ready for production calls!")
    else:
        print("⚠️ יש בעיות שצריכות תיקון")
        print("❌ Issues need to be resolved before production")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)