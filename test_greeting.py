#!/usr/bin/env python3
import sys
import os
sys.path.append('server')
"""
🔍 בדיקת מערכת הברכה הטלפונית - Hebrew TTS Greeting Test
בודק את כל השלבים: עסק → ברכה → TTS → TwiML
"""

import os
import sys
import requests
from models import Business, db
from hebrew_tts import hebrew_tts

def test_business_lookup():
    """בדיקה 1: האם נמצא עסק לפי מספר טלפון"""
    print("\n🔍 בדיקה 1: חיפוש עסק לפי מספר")
    
    test_numbers = [
        "+972-3-376-3805", 
        "+972-3-376-3805",  # Without dashes
        "+9723376-3805"     # Different format
    ]
    
    for number in test_numbers:
        business = Business.query.filter_by(phone_number=number).first()
        print(f"📞 {number}: {business.name if business else '❌ לא נמצא'}")
        
        if business:
            print(f"   ✅ עסק נמצא: {business.name}")
            print(f"   📋 AI Prompt: {business.ai_prompt[:50]}..." if business.ai_prompt else "   ⚠️ אין AI prompt")
            return business
    
    print("❌ לא נמצא עסק באף מספר!")
    return None

def test_greeting_generation(business):
    """בדיקה 2: יצירת ברכה בעברית"""
    print("\n🔍 בדיקה 2: יצירת ברכה")
    
    if not business:
        print("❌ אין עסק - לא ניתן לבדוק ברכה")
        return None
        
    # Generate greeting like in the webhook
    business_name = business.name
    greeting = f"שלום, התקשרתם אל {business_name}. אנא השאירו הודעה אחרי הצפצוף."
    
    print(f"✅ ברכה נוצרה: '{greeting}'")
    print(f"📏 אורך: {len(greeting)} תווים")
    
    # Check for problematic characters
    problematic_chars = ['"', "'", "&", "<", ">"]
    for char in problematic_chars:
        if char in greeting:
            print(f"⚠️ תו בעייתי נמצא: {char}")
    
    return greeting

def test_tts_generation(greeting_text):
    """בדיקה 3: יצירת קובץ TTS"""
    print("\n🔍 בדיקה 3: יצירת TTS")
    
    if not greeting_text:
        print("❌ אין ברכה - לא ניתן לבדוק TTS")
        return None
    
    try:
        # Check Google credentials
        google_creds = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        print(f"🔑 Google Credentials: {'✅ קיים' if google_creds else '❌ חסר'}")
        
        if google_creds:
            print(f"   📄 נתיב: {google_creds}")
            print(f"   📁 קובץ קיים: {'✅' if os.path.exists(google_creds) else '❌'}")
        
        # Try to create TTS file
        print(f"🎵 מנסה ליצור TTS עבור: '{greeting_text[:30]}...'")
        tts_filename = hebrew_tts.synthesize_hebrew_audio(greeting_text)
        
        if tts_filename:
            print(f"✅ TTS נוצר: {tts_filename}")
            
            # Check if file exists
            full_path = f"server/static/voice_responses/{tts_filename}"
            file_exists = os.path.exists(full_path)
            print(f"📁 קובץ קיים: {'✅' if file_exists else '❌'} - {full_path}")
            
            if file_exists:
                file_size = os.path.getsize(full_path)
                print(f"📊 גודל קובץ: {file_size} bytes")
                
            return tts_filename
        else:
            print("❌ TTS לא נוצר")
            return None
            
    except Exception as e:
        print(f"❌ שגיאה ביצירת TTS: {e}")
        return None

def test_twiml_generation(tts_filename, greeting_text):
    """בדיקה 4: יצירת TwiML תקין"""
    print("\n🔍 בדיקה 4: יצירת TwiML")
    
    if tts_filename:
        # TTS file route
        response_url = f"https://ai-crmd.replit.app/server/static/voice_responses/{tts_filename}"
        twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{response_url}</Play>
    <Record maxLength="30" transcribe="false" recordingStatusCallback="https://ai-crmd.replit.app/webhook/handle_recording" recordingStatusCallbackMethod="POST"/>
    <Hangup/>
</Response>'''
        print("✅ TwiML עם TTS:")
        print(twiml)
        print(f"\n🔗 קישור לקובץ: {response_url}")
        
    else:
        # Fallback TwiML
        twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna" language="he-IL">{greeting_text}</Say>
    <Record maxLength="30" transcribe="false" recordingStatusCallback="https://ai-crmd.replit.app/webhook/handle_recording" recordingStatusCallbackMethod="POST"/>
    <Hangup/>
</Response>'''
        print("⚠️ TwiML fallback (without TTS file):")
        print(twiml)
    
    return twiml

def test_url_accessibility(tts_filename):
    """בדיקה 5: האם הקובץ נגיש מהאינטרנט"""
    print("\n🔍 בדיקה 5: נגישות קובץ מהאינטרנט")
    
    if not tts_filename:
        print("❌ אין קובץ TTS לבדיקה")
        return False
    
    url = f"https://ai-crmd.replit.app/server/static/voice_responses/{tts_filename}"
    
    try:
        print(f"🌐 בודק: {url}")
        response = requests.head(url, timeout=10)
        
        print(f"📊 סטטוס: {response.status_code}")
        print(f"📋 Content-Type: {response.headers.get('Content-Type', 'לא מוגדר')}")
        
        if response.status_code == 200:
            print("✅ קובץ נגיש!")
            return True
        else:
            print(f"❌ קובץ לא נגיש - קוד {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ שגיאה בגישה לקובץ: {e}")
        return False

def test_webhook_endpoint():
    """בדיקה 6: האם endpoint הוא בריא"""
    print("\n🔍 בדיקה 6: בדיקת webhook endpoint")
    
    webhook_url = "https://ai-crmd.replit.app/webhook/incoming_call"
    
    try:
        # Simulate Twilio POST
        test_data = {
            'From': '+972501234567',
            'To': '+972-3-376-3805',
            'CallSid': 'test12345'
        }
        
        print(f"🎯 שולח POST ל: {webhook_url}")
        response = requests.post(webhook_url, data=test_data, timeout=10)
        
        print(f"📊 סטטוס: {response.status_code}")
        print(f"📋 Content-Type: {response.headers.get('Content-Type', 'לא מוגדר')}")
        
        if response.status_code == 200:
            print("✅ Webhook פועל!")
            print("📄 תגובה:")
            print(response.text[:200] + "..." if len(response.text) > 200 else response.text)
            return True
        else:
            print(f"❌ Webhook כשל - קוד {response.status_code}")
            print("📄 שגיאה:")
            print(response.text[:200] + "..." if len(response.text) > 200 else response.text)
            return False
            
    except Exception as e:
        print(f"❌ שגיאה בקריאה ל-webhook: {e}")
        return False

def run_full_test():
    """הרצת כל הבדיקות"""
    print("🚀 התחלת בדיקה מלאה של מערכת הברכה")
    print("=" * 50)
    
    # Initialize Flask app context
    from app import app
    with app.app_context():
        
        # Step 1: Find business
        business = test_business_lookup()
        
        # Step 2: Generate greeting  
        greeting = test_greeting_generation(business)
        
        # Step 3: Generate TTS
        tts_filename = test_tts_generation(greeting)
        
        # Step 4: Generate TwiML
        twiml = test_twiml_generation(tts_filename, greeting)
        
        # Step 5: Check URL accessibility
        url_accessible = test_url_accessibility(tts_filename)
        
        # Step 6: Test webhook
        webhook_works = test_webhook_endpoint()
        
        # Summary
        print("\n" + "=" * 50)
        print("📋 סיכום תוצאות:")
        print(f"1. עסק נמצא: {'✅' if business else '❌'}")
        print(f"2. ברכה נוצרה: {'✅' if greeting else '❌'}")
        print(f"3. TTS נוצר: {'✅' if tts_filename else '❌'}")
        print(f"4. TwiML תקין: {'✅' if twiml else '❌'}")
        print(f"5. קובץ נגיש: {'✅' if url_accessible else '❌'}")
        print(f"6. Webhook פועל: {'✅' if webhook_works else '❌'}")
        
        if all([business, greeting, tts_filename, twiml, url_accessible, webhook_works]):
            print("\n🎉 כל הבדיקות עברו בהצלחה!")
            print("📞 המערכת מוכנה לקבלת שיחות!")
        else:
            print("\n⚠️ נמצאו בעיות שצריך לתקן")

if __name__ == "__main__":
    run_full_test()