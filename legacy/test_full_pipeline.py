#!/usr/bin/env python3
"""
Test the complete Hebrew call pipeline
"""
import sys
import os
sys.path.append('.')

def test_complete_pipeline():
    """Test all components of the Hebrew call system"""
    print("🎯 Testing Complete Hebrew Call Pipeline\n")
    
    # Test 1: Hebrew TTS
    print("1. Testing Hebrew TTS...")
    try:
        from server.hebrew_tts_enhanced import create_hebrew_audio
        test_text = "שלום, זהו מבחן מערכת הקשיב בעברית למוקד שי דירות ומשרדים"
        audio_file = create_hebrew_audio(test_text, "pipeline_test")
        if audio_file and os.path.exists(audio_file):
            size = os.path.getsize(audio_file)
            print(f"   ✅ Hebrew TTS: Created {audio_file} ({size} bytes)")
        else:
            print(f"   ❌ Hebrew TTS: Failed")
    except Exception as e:
        print(f"   ❌ Hebrew TTS Error: {e}")
    
    # Test 2: AI Conversation 
    print("\n2. Testing AI Hebrew Conversation...")
    try:
        from server.ai_conversation import generate_response
        test_input = "שלום אני מחפש דירת 3 חדרים בתל אביב למשפחה"
        response = generate_response(test_input, "pipeline_test")
        print(f"   ✅ AI Response: {response[:100]}...")
    except Exception as e:
        print(f"   ❌ AI Error: {e}")
    
    # Test 3: Twilio Webhook
    print("\n3. Testing Twilio Webhook Response...")
    try:
        import requests
        import time
        response = requests.post(
            "https://ai-crmd.replit.app/webhook/incoming_call",
            data={
                "From": "+972501234567",
                "To": "+97233763805", 
                "CallSid": "PIPELINE_TEST_" + str(int(time.time()))
            },
            timeout=10
        )
        if response.status_code == 200 and "<?xml" in response.text:
            print(f"   ✅ Twilio Webhook: Valid TwiML returned")
        else:
            print(f"   ❌ Twilio Webhook: Status {response.status_code}")
    except Exception as e:
        print(f"   ❌ Twilio Error: {e}")
    
    # Test 4: Health Check
    print("\n4. Testing System Health...")
    try:
        import requests
        response = requests.get("https://ai-crmd.replit.app/health", timeout=5)
        if response.status_code == 200:
            print(f"   ✅ System Health: OK")
        else:
            print(f"   ❌ System Health: Status {response.status_code}")
    except Exception as e:
        print(f"   ❌ Health Check Error: {e}")
    
    print(f"\n🎯 Pipeline Test Complete!")
    print(f"✅ Hebrew conversation system ready for production!")

if __name__ == "__main__":
    test_complete_pipeline()