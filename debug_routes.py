#!/usr/bin/env python3
"""
Debug script to check which routes are actually registered
"""
import requests

def test_webhook():
    url = "https://ai-crmd.replit.app/webhook/incoming_call"
    data = {"CallSid": "TEST", "From": "+972500000000"}
    
    try:
        response = requests.post(url, data=data)
        print(f"Status: {response.status_code}")
        content = response.text
        
        if "Play" in content:
            print("✅ FIXED: Using Play verb")
        elif "Say" in content:
            print("❌ BROKEN: Still using Say verb")
            
        if "greeting.mp3" in content:
            print("✅ GOOD: References Hebrew MP3 file")
        else:
            print("❌ BAD: No Hebrew MP3 reference")
            
        print("\nFull response:")
        print(content[:500])
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    print("🔍 Testing which webhook is actually running...")
    test_webhook()