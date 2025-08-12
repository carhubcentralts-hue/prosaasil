#!/usr/bin/env python3
"""
Test Twilio Webhook Response - בדיקת תגובות Webhook  
"""

import requests
import json

def test_incoming_call():
    """Test incoming call webhook"""
    
    # Simulate Twilio call data
    data = {
        'CallSid': 'CA_test_123',
        'From': '+972504294724', 
        'To': '+97233763805',
        'Direction': 'inbound'
    }
    
    try:
        response = requests.post(
            'https://ai-crmd.replit.app/webhook/incoming_call',
            data=data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=10
        )
        
        print(f"Status: {response.status_code}")
        print(f"Content-Type: {response.headers.get('Content-Type')}")
        print(f"Response:\n{response.text}")
        
        if response.status_code == 200:
            # Check if TwiML contains Play instead of Say
            if '<Play>' in response.text:
                print("\n✅ SUCCESS: Using Play verb instead of Say!")
            if 'greeting.mp3' in response.text:
                print("✅ SUCCESS: Hebrew greeting audio found!")
            if '<Record' in response.text:
                print("✅ SUCCESS: Recording setup correct!")
        
    except Exception as e:
        print(f"❌ Error: {e}")

def test_audio_url():
    """Test if Hebrew audio files are accessible"""
    
    urls = [
        'https://ai-crmd.replit.app/static/greeting.mp3',
        'https://ai-crmd.replit.app/static/voice_responses/greeting.mp3'
    ]
    
    for url in urls:
        try:
            response = requests.head(url, timeout=5)
            print(f"Audio URL {url}: {response.status_code}")
            if response.status_code == 200:
                print(f"  ✅ Size: {response.headers.get('Content-Length')} bytes")
        except Exception as e:
            print(f"  ❌ Error accessing {url}: {e}")

if __name__ == "__main__":
    print("🔧 Testing Hebrew AI Call System\n")
    
    print("1. Testing Twilio Incoming Call Webhook:")
    test_incoming_call()
    
    print("\n2. Testing Hebrew Audio Files:")  
    test_audio_url()