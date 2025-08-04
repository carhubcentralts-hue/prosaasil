#!/usr/bin/env python3
"""
🔍 Debug script for admin dashboard business viewing issue

הבעיה: המשתמש לוחץ על "צפה כעסק" ותמיד מועבר לעסק #6
הפתרון: נבדוק מה קורה בממשק ונתקן את הבעיה
"""

import requests
import json

def test_admin_api():
    """בדיקת API המנהל"""
    try:
        # Get businesses list
        response = requests.get('http://localhost:5000/api/admin/businesses')
        businesses = response.json()
        
        print("📋 עסקים במערכת:")
        for business in businesses:
            print(f"  #{business['id']}: {business['name']} ({'פעיל' if business['is_active'] else 'לא פעיל'})")
        
        # Test impersonation for each business
        print("\n🚀 בדיקת השתלטות:")
        for business in businesses:
            business_id = business['id']
            print(f"  בדיקה לעסק #{business_id}: {business['name']}")
            
            # Test impersonation API
            try:
                imp_response = requests.post(
                    f'http://localhost:5000/api/admin/impersonate/{business_id}',
                    headers={'Authorization': 'Bearer fake_admin_token'}
                )
                if imp_response.status_code == 200:
                    print(f"    ✅ השתלטות עובדת")
                else:
                    print(f"    ❌ השתלטות נכשלת: {imp_response.status_code}")
            except Exception as e:
                print(f"    ❌ שגיאה: {e}")
        
        return businesses
        
    except Exception as e:
        print(f"❌ שגיאה בבדיקת API: {e}")
        return []

if __name__ == "__main__":
    businesses = test_admin_api()
    
    print(f"\n💡 סיכום: נמצאו {len(businesses)} עסקים במערכת")
    print("אם המשתמש תמיד מועבר לעסק #6, יש לבדוק:")
    print("1. האם בממשק מוצג עסק #6 כראשון ברשימה")
    print("2. האם יש בעיה בפונקציית handleDirectBusinessTakeover")
    print("3. האם יש בעיה בהפניית הכפתור")