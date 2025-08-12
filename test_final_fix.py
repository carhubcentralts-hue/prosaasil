#!/usr/bin/env python3
"""
Final Test - Hebrew AI Call System  
בדיקה סופית של מערכת הקריאות עברית
"""

import requests

def test_final_webhook():
    """Test webhook after fix"""
    
    print("🔧 Testing Final Hebrew AI System Fix")
    print("=" * 50)
    
    # Test webhook
    try:
        response = requests.post(
            'https://ai-crmd.replit.app/webhook/incoming_call',
            data={
                'CallSid': 'CA_final_test',
                'From': '+972504294724', 
                'To': '+97233763805',
                'Direction': 'inbound'
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=10
        )
        
        print(f"Webhook Status: {response.status_code}")
        print("Response Content:")
        print(response.text[:500])
        
        # Check for fixes
        success_checks = []
        
        if '<Play>' in response.text:
            success_checks.append("✅ FIXED: Using Play verb")
        else:
            success_checks.append("❌ STILL BROKEN: Using Say verb")
            
        if 'greeting.mp3' in response.text:
            success_checks.append("✅ FIXED: Hebrew greeting MP3 included")
        else:
            success_checks.append("❌ STILL BROKEN: No Hebrew audio")
            
        if '<Record' in response.text:
            success_checks.append("✅ FIXED: Recording setup correct")
        else:
            success_checks.append("❌ STILL BROKEN: No recording")
        
        for check in success_checks:
            print(check)
            
    except Exception as e:
        print(f"❌ Webhook Error: {e}")

    # Test audio file
    print("\nTesting Hebrew Audio File:")
    try:
        audio_response = requests.head('https://ai-crmd.replit.app/static/greeting.mp3', timeout=5)
        if audio_response.status_code == 200:
            size = audio_response.headers.get('Content-Length', 'unknown')
            print(f"✅ Hebrew Audio Accessible: {size} bytes")
        else:
            print(f"❌ Audio Not Found: {audio_response.status_code}")
    except Exception as e:
        print(f"❌ Audio Error: {e}")

    print("\n" + "=" * 50)
    if all('✅' in check for check in success_checks):
        print("🎉 ALL FIXES SUCCESSFUL! System ready for calls!")
        print("📞 Call +97233763805 to test Hebrew AI response!")
    else:
        print("⚠️  Some issues still remain. Check above for details.")

if __name__ == "__main__":
    test_final_webhook()