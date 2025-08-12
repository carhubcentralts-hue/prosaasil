#!/usr/bin/env python3
"""
Test all webhook endpoints to see which ones work
"""
import requests

def test_webhook_endpoint(endpoint_name, endpoint_url):
    print(f"\n🔍 Testing {endpoint_name}: {endpoint_url}")
    print("=" * 60)
    
    data = {"CallSid": "TEST", "From": "+972500000000"}
    
    try:
        response = requests.post(endpoint_url, data=data)
        print(f"Status: {response.status_code}")
        content = response.text
        
        if "Play" in content:
            print("✅ GOOD: Using Play verb")
        elif "Say" in content:
            print("❌ BAD: Still using Say verb")
            
        if "greeting.mp3" in content:
            print("✅ GOOD: References Hebrew MP3 file")
        else:
            print("❌ BAD: No Hebrew MP3 reference")
            
        print(f"Response (first 300 chars):\n{content[:300]}")
        
    except Exception as e:
        print(f"❌ ERROR: {e}")

if __name__ == "__main__":
    base_url = "https://ai-crmd.replit.app"
    
    endpoints = [
        ("Original Webhook", f"{base_url}/webhook/incoming_call"),
        ("Fixed Webhook", f"{base_url}/webhook/incoming_call_fixed"),
    ]
    
    for name, url in endpoints:
        test_webhook_endpoint(name, url)
        
    print(f"\n{'='*60}")
    print("🎯 RECOMMENDATION: Use the endpoint that shows Play verb + Hebrew MP3")
    print("Update your Twilio webhook URL to use the working endpoint.")