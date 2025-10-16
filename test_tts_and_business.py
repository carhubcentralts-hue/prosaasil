#!/usr/bin/env python3
"""
🧪 בדיקת TTS + זיהוי עסק
בודק ש:
1. העסק מזוהה נכון לפי to_number
2. הברכה נטענת נכון עם placeholder
3. TTS משתמש בהגדרות החדשות
"""
import os
import sys

# Set up path
sys.path.insert(0, '/home/runner/workspace')

def test_business_identification():
    """בדיקת זיהוי עסק"""
    print("\n" + "="*60)
    print("🧪 TEST 1: בדיקת זיהוי עסק")
    print("="*60)
    
    from server.app_factory import create_app
    from server.models_sql import Business
    
    app = create_app()
    with app.app_context():
        # בדוק מה יש ב-DB
        businesses = Business.query.all()
        print(f"\n📊 נמצאו {len(businesses)} עסקים:")
        for b in businesses:
            print(f"  ID={b.id}, שם={b.name}, טלפון={b.phone_number}, פעיל={b.is_active}")
        
        # בדיקת זיהוי לפי מספר טלפון
        test_number = "+97233763805"
        print(f"\n🔍 מחפש עסק עם מספר: {test_number}")
        
        from sqlalchemy import or_
        normalized = test_number.replace('-', '').replace(' ', '')
        
        business = Business.query.filter(
            or_(
                Business.phone_number == test_number,
                Business.phone_number == normalized
            )
        ).first()
        
        if business:
            print(f"✅ נמצא! ID={business.id}, שם={business.name}")
            print(f"   ברכה: {business.greeting_message}")
            print(f"   ברכה WhatsApp: {business.whatsapp_greeting}")
            return business
        else:
            print(f"❌ לא נמצא עסק עם מספר {test_number}")
            return None

def test_greeting_loading(business):
    """בדיקת טעינת ברכה"""
    print("\n" + "="*60)
    print("🧪 TEST 2: בדיקת טעינת ברכה")
    print("="*60)
    
    if not business:
        print("❌ אין עסק לבדוק")
        return
    
    greeting = business.greeting_message or "שלום! איך אפשר לעזור?"
    business_name = business.name or "העסק שלנו"
    
    print(f"\n📝 ברכה גולמית: {greeting}")
    print(f"📝 שם עסק: {business_name}")
    
    # החלפת placeholder
    final_greeting = greeting.replace("{{business_name}}", business_name)
    print(f"✅ ברכה סופית: {final_greeting}")
    
    return final_greeting

def test_tts_configuration():
    """בדיקת הגדרות TTS"""
    print("\n" + "="*60)
    print("🧪 TEST 3: בדיקת הגדרות TTS")
    print("="*60)
    
    tts_config = {
        'TTS_VOICE': os.getenv('TTS_VOICE'),
        'TTS_RATE': os.getenv('TTS_RATE'),
        'TTS_PITCH': os.getenv('TTS_PITCH'),
        'ENABLE_TTS_SSML_BUILDER': os.getenv('ENABLE_TTS_SSML_BUILDER'),
        'ENABLE_HEBREW_GRAMMAR_POLISH': os.getenv('ENABLE_HEBREW_GRAMMAR_POLISH'),
        'TTS_CACHE_ENABLED': os.getenv('TTS_CACHE_ENABLED'),
    }
    
    print("\n📋 הגדרות TTS נוכחיות:")
    for key, value in tts_config.items():
        status = "✅" if value else "❌"
        print(f"  {status} {key} = {value}")
    
    # בדוק ערכים צפויים
    expected = {
        'TTS_VOICE': 'he-IL-Wavenet-D',
        'TTS_RATE': '0.96',
        'TTS_PITCH': '-2.0',
        'ENABLE_TTS_SSML_BUILDER': 'true',
        'ENABLE_HEBREW_GRAMMAR_POLISH': 'true',
        'TTS_CACHE_ENABLED': 'true',
    }
    
    print("\n🎯 בדיקת תקינות:")
    all_good = True
    for key, expected_value in expected.items():
        actual = tts_config[key]
        if actual == expected_value:
            print(f"  ✅ {key}: {actual}")
        else:
            print(f"  ❌ {key}: ציפיתי ל-'{expected_value}', קיבלתי '{actual}'")
            all_good = False
    
    return all_good

def test_tts_service():
    """בדיקת שירות TTS"""
    print("\n" + "="*60)
    print("🧪 TEST 4: בדיקת שירות TTS")
    print("="*60)
    
    try:
        from server.services.gcp_tts_live import get_hebrew_tts
        
        print("\n📦 יוצר TTS service...")
        tts_service = get_hebrew_tts()
        
        print(f"✅ TTS service נוצר בהצלחה")
        print(f"   קול: {tts_service.voice_name}")
        print(f"   קצב: {tts_service.speaking_rate}")
        print(f"   גובה: {tts_service.pitch}")
        print(f"   SSML: {tts_service.enable_ssml}")
        print(f"   Cache: {tts_service.cache_enabled}")
        
        # בדיקת סינתזה
        test_text = "שלום! זו בדיקה של המזכירה החדשה."
        print(f"\n🔊 מנסה לסנתז: '{test_text}'")
        
        audio = tts_service.synthesize_hebrew_pcm16_8k(test_text)
        
        if audio and len(audio) > 1000:
            duration = len(audio) / (8000 * 2)
            print(f"✅ TTS הצליח! {len(audio)} bytes ({duration:.2f}s)")
            return True
        else:
            print(f"❌ TTS נכשל או החזיר אודיו קצר מדי")
            return False
            
    except Exception as e:
        print(f"❌ שגיאה ב-TTS service: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("\n" + "="*60)
    print("🚀 בודק TTS + זיהוי עסק")
    print("="*60)
    
    # TEST 1: זיהוי עסק
    business = test_business_identification()
    
    # TEST 2: ברכה
    if business:
        greeting = test_greeting_loading(business)
    
    # TEST 3: הגדרות TTS
    tts_config_ok = test_tts_configuration()
    
    # TEST 4: שירות TTS
    tts_service_ok = test_tts_service()
    
    # סיכום
    print("\n" + "="*60)
    print("📊 סיכום בדיקות")
    print("="*60)
    print(f"  {'✅' if business else '❌'} זיהוי עסק")
    print(f"  {'✅' if business and business.greeting_message else '❌'} טעינת ברכה")
    print(f"  {'✅' if tts_config_ok else '❌'} הגדרות TTS")
    print(f"  {'✅' if tts_service_ok else '❌'} שירות TTS")
    
    if business and tts_config_ok and tts_service_ok:
        print("\n🎉 הכל עובד מצוין! המערכת מוכנה לשיחות!")
    else:
        print("\n⚠️ יש בעיות שצריך לתקן")

if __name__ == "__main__":
    main()
