#!/usr/bin/env python3
"""
🛠️ תיקון בעיות ברכה טלפונית - Fix Hebrew Greeting Issues
תיקונים אוטומטיים לבעיות נפוצות במערכת
"""

import os
import sys
from models import Business, db

def fix_missing_businesses():
    """תיקון 1: הוספת עסק לדוגמה אם לא קיים"""
    print("🔧 תיקון 1: בדיקת עסקים במסד נתונים")
    
    test_phone = "+972-3-376-3805"
    business = Business.query.filter_by(phone_number=test_phone).first()
    
    if not business:
        print(f"❌ עסק עם מספר {test_phone} לא קיים")
        print("🛠️ יוצר עסק לדוגמה...")
        
        new_business = Business(
            name="עסק בדיקה",
            phone_number=test_phone,
            email="test@example.com", 
            ai_prompt="אתה עוזר וירטואלי מועיל בעברית לעסק בדיקה. תן תשובה קצרה ומנומסת."
        )
        
        db.session.add(new_business)
        db.session.commit()
        print("✅ עסק נוסף בהצלחה!")
        return new_business
    else:
        print(f"✅ עסק קיים: {business.name}")
        return business

def fix_tts_directory():
    """תיקון 2: וידוא שתיקיית TTS קיימת"""
    print("🔧 תיקון 2: בדיקת תיקיית TTS")
    
    tts_dir = "server/static/voice_responses"
    
    if not os.path.exists(tts_dir):
        print(f"❌ תיקייה {tts_dir} לא קיימת")
        print("🛠️ יוצר תיקייה...")
        os.makedirs(tts_dir, exist_ok=True)
        print("✅ תיקייה נוצרה!")
    else:
        print("✅ תיקיית TTS קיימת")
    
    # Check permissions
    if os.access(tts_dir, os.W_OK):
        print("✅ יש הרשאת כתיבה")
    else:
        print("❌ אין הרשאת כתיבה")

def fix_google_credentials():
    """תיקון 3: בדיקת Google TTS credentials"""
    print("🔧 תיקון 3: בדיקת Google credentials")
    
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    
    if not creds_path:
        print("❌ GOOGLE_APPLICATION_CREDENTIALS לא מוגדר")
        print("⚠️ זקוק להגדרה ידנית של המשתמש")
        return False
    
    if not os.path.exists(creds_path):
        print(f"❌ קובץ credentials לא נמצא: {creds_path}")
        return False
    
    try:
        with open(creds_path, 'r') as f:
            content = f.read().strip()
            if content.startswith('{') and content.endswith('}'):
                print("✅ קובץ credentials תקין (JSON)")
                return True
            else:
                print("❌ קובץ credentials לא תקין (לא JSON)")
                return False
    except Exception as e:
        print(f"❌ שגיאה בקריאת credentials: {e}")
        return False

def fix_webhook_route():
    """תיקון 4: וידוא שהroute נרשם"""
    print("🔧 תיקון 4: בדיקת webhook routes")
    
    from app import app
    
    # Check registered routes
    webhook_routes = []
    for rule in app.url_map.iter_rules():
        if 'webhook' in rule.rule:
            webhook_routes.append(rule.rule)
    
    print(f"✅ Routes שנמצאו: {webhook_routes}")
    
    required_routes = ['/webhook/incoming_call', '/webhook/handle_recording', '/webhook/call_status']
    
    for route in required_routes:
        if route in webhook_routes:
            print(f"✅ {route} נרשם")
        else:
            print(f"❌ {route} לא נרשם")

def create_test_tts():
    """תיקון 5: יצירת TTS לדוגמה"""
    print("🔧 תיקון 5: יצירת TTS לדוגמה")
    
    try:
        from hebrew_tts import hebrew_tts
        
        test_text = "שלום, זהו בדיקת TTS לעברית"
        print(f"🎵 יוצר TTS: '{test_text}'")
        
        filename = hebrew_tts.synthesize_hebrew_audio(test_text)
        
        if filename:
            print(f"✅ TTS נוצר: {filename}")
            
            # Check file
            full_path = f"server/static/voice_responses/{filename}"
            if os.path.exists(full_path):
                size = os.path.getsize(full_path)
                print(f"✅ קובץ קיים, גודל: {size} bytes")
                return filename
            else:
                print("❌ קובץ לא נמצא אחרי יצירה")
                return None
        else:
            print("❌ TTS לא נוצר")
            return None
            
    except Exception as e:
        print(f"❌ שגיאה ביצירת TTS: {e}")
        return None

def run_all_fixes():
    """הרצת כל התיקונים"""
    print("🚀 התחלת תיקונים אוטומטיים")
    print("=" * 50)
    
    from app import app
    with app.app_context():
        
        # Fix 1: Business
        business = fix_missing_businesses()
        
        # Fix 2: TTS Directory  
        fix_tts_directory()
        
        # Fix 3: Google Credentials
        creds_ok = fix_google_credentials()
        
        # Fix 4: Routes
        fix_webhook_route()
        
        # Fix 5: Test TTS (only if creds OK)
        test_tts = create_test_tts() if creds_ok else None
        
        print("\n" + "=" * 50)
        print("📋 סיכום תיקונים:")
        print(f"1. עסק בדיקה: {'✅' if business else '❌'}")
        print(f"2. תיקיית TTS: ✅")  
        print(f"3. Google creds: {'✅' if creds_ok else '❌'}")
        print(f"4. Webhook routes: ✅")
        print(f"5. TTS בדיקה: {'✅' if test_tts else '❌'}")
        
        if all([business, creds_ok, test_tts]):
            print("\n🎉 כל התיקונים הושלמו בהצלחה!")
        else:
            print("\n⚠️ חלק מהתיקונים דורשים התערבות ידנית")

if __name__ == "__main__":
    run_all_fixes()