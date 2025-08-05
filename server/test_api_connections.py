#!/usr/bin/env python3
"""
🧪 API Connection Test - בדיקה אוטומטית של כל ה-APIs
בודק באמת איזה endpoints עובדים ואיזה לא
"""
import requests
import json
import sys
from datetime import datetime

# בסיס URL של השרת  
BASE_URL = "http://localhost:5000"

def test_api_endpoint(endpoint, description):
    """בדיקת endpoint בודד"""
    try:
        url = f"{BASE_URL}{endpoint}"
        print(f"🔍 Testing: {endpoint}")
        print(f"   Description: {description}")
        
        response = requests.get(url, timeout=5)
        status = response.status_code
        
        if status == 200:
            try:
                data = response.json()
                print(f"   ✅ Status: {status}")
                print(f"   📊 Response keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
                if isinstance(data, dict) and 'success' in data:
                    print(f"   🎯 Success flag: {data['success']}")
                return True, data
            except json.JSONDecodeError:
                print(f"   ⚠️ Status: {status} but response is not JSON")
                print(f"   📄 Raw response: {response.text[:100]}...")
                return False, None
        else:
            print(f"   ❌ Status: {status}")
            try:
                error_data = response.json()
                print(f"   📄 Error: {error_data}")
            except:
                print(f"   📄 Raw error: {response.text[:100]}...")
            return False, None
            
    except requests.exceptions.ConnectionError:
        print(f"   🔌 Connection Error: Server not running at {BASE_URL}")
        return False, None
    except requests.exceptions.Timeout:
        print(f"   ⏰ Timeout: Server didn't respond within 5 seconds")
        return False, None
    except Exception as e:
        print(f"   💥 Unexpected error: {e}")
        return False, None
    finally:
        print()

def main():
    """בדיקת כל ה-APIs הצפויים"""
    print("🚀 Starting AgentLocator API Connection Test")
    print("=" * 60)
    print(f"🌐 Base URL: {BASE_URL}")
    print(f"🕐 Test time: {datetime.now()}")
    print("=" * 60)
    print()
    
    # רשימת כל ה-APIs שצריכים לעבוד
    api_tests = [
        ("/api/stats/overview", "Stats Overview - סטטיסטיקות כלליות"),
        ("/api/crm/customers", "CRM Customers - רשימת לקוחות"),
        ("/api/crm/tasks", "CRM Tasks - רשימת משימות"),
        ("/api/whatsapp/conversations", "WhatsApp Conversations - שיחות WhatsApp"),
        ("/api/whatsapp/analytics", "WhatsApp Analytics - אנליטיקס WhatsApp"),
        ("/api/signature/signatures", "Digital Signatures - חתימות דיגיטליות"),
        ("/api/proposal/proposals", "Proposals - הצעות מחיר"),
        ("/api/invoice/invoices", "Invoices - חשבוניות"),
        ("/api/status", "System Status - סטטוס מערכת"),
    ]
    
    results = []
    working_count = 0
    
    for endpoint, description in api_tests:
        success, data = test_api_endpoint(endpoint, description)
        results.append((endpoint, success, data))
        if success:
            working_count += 1
    
    # סיכום תוצאות
    print("📋 TEST SUMMARY / סיכום בדיקה")
    print("=" * 60)
    print(f"✅ Working APIs: {working_count}/{len(api_tests)}")
    print(f"❌ Broken APIs: {len(api_tests) - working_count}/{len(api_tests)}")
    print()
    
    print("📊 DETAILED RESULTS:")
    for endpoint, success, data in results:
        status_icon = "✅" if success else "❌"
        print(f"{status_icon} {endpoint}")
        
    print()
    
    if working_count == 0:
        print("🚨 CRITICAL: No APIs are working!")
        print("   Possible causes:")
        print("   1. Flask server not running")
        print("   2. Blueprints not registered in app.py")
        print("   3. Import errors in API files")
        print("   4. Wrong port (should be 5000)")
        return False
    elif working_count < len(api_tests):
        print("⚠️ WARNING: Some APIs are not working")
        print("   Check the failed endpoints above")
        return False
    else:
        print("🎉 SUCCESS: All APIs are working!")
        return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)