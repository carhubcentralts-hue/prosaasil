#!/usr/bin/env python3
"""
Complete Twilio webhook test as per attached requirements
"""
import requests
import json

# Test according to the attached requirements
HOST = "https://ai-crmd.replit.app"

def test_1_twiml_response():
    """1. Does TwiML return properly?"""
    print("🔍 Test 1: TwiML Response with Play verb")
    
    try:
        response = requests.post(f"{HOST}/webhook/incoming_call", 
                               headers={"Accept": "text/xml"})
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            content = response.text
            if "<Play>" in content and "<Record>" in content:
                print("✅ PASS: TwiML contains Play and Record")
                if "voice_responses/greeting.mp3" in content:
                    print("✅ PASS: Uses Hebrew MP3 file")
                else:
                    print("❌ FAIL: Wrong MP3 path")
            else:
                print("❌ FAIL: Missing Play or Record elements")
        else:
            print(f"❌ FAIL: HTTP {response.status_code}")
            
        print(f"Response XML:\n{response.text}\n")
        
    except Exception as e:
        print(f"❌ ERROR: {e}")

def test_2_greeting_file_access():
    """2. Is greeting file accessible?"""
    print("🔍 Test 2: Hebrew Greeting File Access")
    
    try:
        response = requests.head(f"{HOST}/static/voice_responses/greeting.mp3")
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ PASS: greeting.mp3 is accessible")
        else:
            print(f"❌ FAIL: HTTP {response.status_code}")
            
    except Exception as e:
        print(f"❌ ERROR: {e}")

def test_3_call_status():
    """3. Does call status return 200?"""
    print("🔍 Test 3: Call Status Webhook")
    
    try:
        response = requests.post(f"{HOST}/webhook/call_status")
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ PASS: call_status returns 200")
        else:
            print(f"❌ FAIL: HTTP {response.status_code}")
            
    except Exception as e:
        print(f"❌ ERROR: {e}")

def test_4_handle_recording():
    """4. Does handle_recording work?"""
    print("🔍 Test 4: Handle Recording Webhook")
    
    try:
        data = {
            'CallSid': 'TEST_CALL_SID',
            'RecordingUrl': 'https://example.com/test.wav'
        }
        response = requests.post(f"{HOST}/webhook/handle_recording", data=data)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ PASS: handle_recording returns 200")
            if "listening.mp3" in response.text:
                print("✅ PASS: Contains listening MP3")
        else:
            print(f"❌ FAIL: HTTP {response.status_code}")
            
    except Exception as e:
        print(f"❌ ERROR: {e}")

if __name__ == "__main__":
    print("🎯 TWILIO HEBREW WEBHOOK COMPLETE TEST")
    print("=" * 60)
    test_1_twiml_response()
    test_2_greeting_file_access()
    test_3_call_status() 
    test_4_handle_recording()
    print("=" * 60)
    print("✅ Test complete. Check results above.")
    print("📋 For Twilio Inspector: All webhooks should return 200 OK")