#!/usr/bin/env python3
"""
Final comprehensive test of all system components
"""
import requests
import json

base_url = "https://ai-crmd.replit.app"

def test_webhook():
    print("🔍 Testing Twilio webhook...")
    data = {"CallSid": "TEST_FINAL", "From": "+972500000000"}
    
    try:
        response = requests.post(f"{base_url}/webhook/incoming_call", data=data)
        print(f"Status: {response.status_code}")
        content = response.text
        
        if "Play" in content:
            print("✅ FIXED: Using Play verb")
        else:
            print("❌ BROKEN: Still using Say verb")
            
        if "greeting.mp3" in content:
            print("✅ FIXED: References Hebrew MP3 file")
        else:
            print("❌ BROKEN: No Hebrew MP3 reference")
            
        print(f"Response:\n{content}")
        
    except Exception as e:
        print(f"❌ ERROR: {e}")

def test_static_files():
    print("\n🔍 Testing static files...")
    files = ["greeting.mp3", "listening.mp3"]
    
    for file in files:
        try:
            response = requests.head(f"{base_url}/static/{file}")
            if response.status_code == 200:
                print(f"✅ FOUND: {file}")
            else:
                print(f"❌ MISSING: {file} (Status: {response.status_code})")
        except Exception as e:
            print(f"❌ ERROR testing {file}: {e}")

def test_api():
    print("\n🔍 Testing API endpoints...")
    endpoints = [
        "/api/auth/me",
        "/api/admin/stats",
        "/api/crm/customers",
        "/api/customers/1/timeline"
    ]
    
    for endpoint in endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}")
            print(f"{endpoint}: {response.status_code}")
        except Exception as e:
            print(f"❌ ERROR {endpoint}: {e}")

if __name__ == "__main__":
    print("🎯 COMPREHENSIVE SYSTEM TEST")
    print("=" * 50)
    test_webhook()
    test_static_files()
    test_api()
    print("=" * 50)
    print("Done.")