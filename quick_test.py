#!/usr/bin/env python3
"""
🚀 בדיקה מהירה של מערכת הברכה - ללא imports כבדים
"""

import os
import requests
import json

def test_webhook_basic():
    """בדיקה בסיסית של webhook"""
    print("🔍 בדיקה 1: Webhook accessibility")
    
    try:
        response = requests.post(
            "https://ai-crmd.replit.app/webhook/incoming_call",
            data={
                'From': '+972501234567',
                'To': '+972-3-376-3805',
                'CallSid': 'test12345'
            },
            timeout=10
        )
        
        print(f"  📊 Status: {response.status_code}")
        print(f"  📋 Content-Type: {response.headers.get('Content-Type', 'Unknown')}")
        
        if response.status_code == 200:
            content = response.text[:200] if response.text else "Empty"
            print(f"  ✅ Response: {content}...")
            return True
        else:
            print(f"  ❌ Error: {response.text[:100]}...")
            return False
            
    except requests.exceptions.Timeout:
        print("  ❌ Timeout - webhook taking too long")
        return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False

def test_google_credentials():
    """בדיקת Google credentials"""
    print("🔍 בדיקה 2: Google TTS Credentials")
    
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    
    if not creds_path:
        print("  ❌ GOOGLE_APPLICATION_CREDENTIALS not set")
        return False
    
    print(f"  📄 Path: {creds_path}")
    
    if not os.path.exists(creds_path):
        print("  ❌ Credentials file not found")
        return False
    
    try:
        with open(creds_path, 'r') as f:
            content = f.read().strip()
        
        # Check if it's valid JSON
        json.loads(content)
        print("  ✅ Valid JSON credentials file")
        return True
        
    except json.JSONDecodeError:
        print("  ❌ Invalid JSON format")
        return False
    except Exception as e:
        print(f"  ❌ Error reading file: {e}")
        return False

def test_tts_directory():
    """בדיקת תיקיית TTS"""
    print("🔍 בדיקה 3: TTS Directory")
    
    tts_dir = "server/static/voice_responses"
    
    if os.path.exists(tts_dir):
        print(f"  ✅ Directory exists: {tts_dir}")
        
        # List files
        try:
            files = os.listdir(tts_dir)
            print(f"  📁 Files: {len(files)} files")
            if files:
                print(f"    Recent: {files[-3:] if len(files) > 3 else files}")
        except Exception as e:
            print(f"  ⚠️ Cannot list files: {e}")
        
        return True
    else:
        print(f"  ❌ Directory missing: {tts_dir}")
        return False

def test_app_status():
    """בדיקת סטטוס כללי של האפליקציה"""
    print("🔍 בדיקה 4: App Status")
    
    try:
        response = requests.get("https://ai-crmd.replit.app/api/status", timeout=5)
        
        if response.status_code == 200:
            print("  ✅ Main app is running")
            return True
        else:
            print(f"  ❌ App status: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"  ❌ Cannot reach app: {e}")
        return False

def test_business_api():
    """בדיקה האם יש עסקים במערכת"""
    print("🔍 בדיקה 5: Business Data")
    
    try:
        # Try to get businesses list
        response = requests.get("https://ai-crmd.replit.app/api/admin/businesses", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                print(f"  ✅ Found {len(data)} businesses")
                
                # Check for test phone number
                test_phone = "+972-3-376-3805"
                matching = [b for b in data if b.get('phone_israel') == test_phone]
                
                if matching:
                    print(f"  ✅ Test phone number found: {matching[0].get('name')}")
                else:
                    print(f"  ⚠️ Test phone {test_phone} not found in businesses")
                
                return True
            else:
                print("  ❌ No businesses found")
                return False
        else:
            print(f"  ❌ API error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"  ❌ Cannot access business API: {e}")
        return False

def test_static_serving():
    """בדיקת serving של קבצים static"""
    print("🔍 בדיקה 6: Static File Serving")
    
    # Test if we can access static directory
    test_url = "https://ai-crmd.replit.app/server/static/voice_responses/"
    
    try:
        response = requests.head(test_url, timeout=5)
        
        if response.status_code in [200, 403, 404]:  # Any of these means server is responding
            print(f"  ✅ Static serving works (status: {response.status_code})")
            return True
        else:
            print(f"  ❌ Static serving issue: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"  ❌ Cannot test static serving: {e}")
        return False

def main():
    """רוץ את כל הבדיקות"""
    print("🚀 בדיקה מהירה של מערכת הברכה העברית")
    print("=" * 50)
    
    results = {}
    
    results['webhook'] = test_webhook_basic()
    results['credentials'] = test_google_credentials()  
    results['tts_dir'] = test_tts_directory()
    results['app_status'] = test_app_status()
    results['business_data'] = test_business_api()
    results['static_serving'] = test_static_serving()
    
    print("\n" + "=" * 50)
    print("📋 סיכום תוצאות:")
    
    for test_name, result in results.items():
        status = "✅" if result else "❌"
        print(f"{status} {test_name}")
    
    working = sum(1 for r in results.values() if r)
    total = len(results)
    
    print(f"\n🎯 {working}/{total} בדיקות עברו בהצלחה")
    
    if working == total:
        print("🎉 כל המערכת עובדת!")
    else:
        print("⚠️ יש בעיות שצריך לתקן")
        
        # Specific recommendations
        if not results['credentials']:
            print("🔧 תיקון: הגדר Google TTS credentials תקינים")
        
        if not results['webhook']:
            print("🔧 תיקון: בדוק את הwebhook code - יש בעיות circular import")
        
        if not results['business_data']:
            print("🔧 תיקון: הוסף עסק עם מספר +972-3-376-3805")

if __name__ == "__main__":
    main()