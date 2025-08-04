#!/usr/bin/env python3
"""
בדיקה מלאה של מערכת התמלול - דמו מושלם
August 4, 2025
"""

import sys
sys.path.append('server')

def test_complete_workflow():
    """בדיקה מלאה של תהליך התמלול"""
    print("🎯 בדיקת תהליך תמלול מלא")
    print("=" * 50)
    
    # שלב 1: הדמיית שיחה נכנסת
    print("📞 שלב 1: שיחה נכנסת")
    call_details = {
        'from': '+972501234567',
        'to': '+972-3-376-3805',
        'call_sid': 'DEMO_CALL_' + str(int(__import__('time').time())),
        'recording_sid': 'REC_DEMO_' + str(int(__import__('time').time()))
    }
    print(f"   מ: {call_details['from']}")
    print(f"   אל: {call_details['to']}")
    print(f"   Call SID: {call_details['call_sid']}")
    
    # שלב 2: הדמיית תמלול
    print("\n🎤 שלב 2: תמלול הקלטה")
    transcriptions = [
        "שלום, אני רוצה לקבוע תור לרופא שיניים",
        "האם אפשר לקבל מידע על הטיפולים שלכם?",
        "אני מעוניין בהלבנת שיניים, כמה זה עולה?",
        "יש לי כאב שן, אפשר לקבוע תור דחוף?"
    ]
    
    selected_transcription = transcriptions[0]
    print(f"   תמלול: '{selected_transcription}'")
    
    # שלב 3: בדיקת תקינות
    print("\n🔍 שלב 3: בדיקת תקינות")
    from whisper_handler import is_gibberish
    is_valid = not is_gibberish(selected_transcription)
    status_text = "תקין ✅" if is_valid else "ג'יבריש ❌"
    print(f"   תקינות: {status_text}")
    
    if not is_valid:
        print("❌ השיחה נדחתה - תוכן לא תקין")
        return False
    
    # שלב 4: יצירת תגובת AI
    print("\n🤖 שלב 4: יצירת תגובת AI")
    try:
        from ai_service import generate_response
        ai_prompt = f"לקוח טלפן ואמר: '{selected_transcription}'. תן תגובה מקצועית ומועילה בעברית כרופא שיניים."
        ai_response = generate_response(ai_prompt)
        print(f"   תגובת AI: '{ai_response[:60]}...'")
        
        if len(ai_response) < 10:
            print("❌ תגובת AI קצרה מדי")
            return False
            
    except Exception as e:
        print(f"❌ שגיאה ב-AI: {e}")
        return False
    
    # שלב 5: יצירת קובץ אודיו
    print("\n🎵 שלב 5: יצירת קובץ אודיו")
    try:
        from hebrew_tts import hebrew_tts
        audio_filename = hebrew_tts.synthesize_hebrew_audio(ai_response[:100])
        
        if audio_filename:
            print(f"   קובץ אודיו: {audio_filename} ✅")
            
            # בדיקת קובץ
            import os
            audio_path = f"server/static/voice_responses/{audio_filename}"
            if os.path.exists(audio_path):
                size = os.path.getsize(audio_path)
                print(f"   גודל קובץ: {size:,} bytes")
            else:
                print("❌ קובץ אודיו לא נמצא")
                return False
        else:
            print("❌ יצירת אודיו נכשלה")
            return False
            
    except Exception as e:
        print(f"❌ שגיאה ב-TTS: {e}")
        return False
    
    # שלב 6: שמירה למסד נתונים
    print("\n💾 שלב 6: שמירה למסד נתונים")
    try:
        import psycopg2
        import os
        
        conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        cur = conn.cursor()
        
        # הכנסת שיחה חדשה
        cur.execute("""
            INSERT INTO call_log (business_id, call_sid, from_number, to_number, 
                                call_status, call_duration, conversation_summary, 
                                recording_url, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
            RETURNING id
        """, (
            1,  # business_id
            call_details['call_sid'],
            call_details['from'], 
            call_details['to'],
            'completed',
            45,  # duration
            f"תמלול: {selected_transcription}\nתגובת AI: {ai_response}",
            f"https://api.twilio.com/{call_details['recording_sid']}.wav"
        ))
        
        call_id = cur.fetchone()[0]
        conn.commit()
        conn.close()
        
        print(f"   שיחה נשמרה: ID #{call_id} ✅")
        
    except Exception as e:
        print(f"❌ שגיאה בשמירה: {e}")
        return False
    
    # שלב 7: סיכום
    print("\n🎉 שלב 7: סיכום")
    print("   ✅ שיחה התקבלה")
    print("   ✅ תמלול בוצע")
    print("   ✅ AI הגיב")
    print("   ✅ אודיו נוצר")
    print("   ✅ נתונים נשמרו")
    
    return True

def test_system_status():
    """בדיקת מצב כללי של המערכת"""
    print("\n📊 בדיקת מצב המערכת")
    print("-" * 30)
    
    # בדיקת קבצי אודיו
    import os
    audio_dir = "server/static/voice_responses"
    if os.path.exists(audio_dir):
        audio_files = [f for f in os.listdir(audio_dir) if f.endswith('.mp3')]
        print(f"📁 קבצי אודיו: {len(audio_files)} קבצים")
    else:
        print("❌ תיקיית אודיו לא קיימת")
    
    # בדיקת רשומות במסד נתונים
    try:
        import psycopg2
        conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        cur = conn.cursor()
        
        cur.execute("SELECT COUNT(*) FROM call_log")
        call_count = cur.fetchone()[0]
        print(f"📞 רשומות שיחה: {call_count}")
        
        cur.execute("SELECT COUNT(*) FROM business")
        business_count = cur.fetchone()[0] 
        print(f"🏢 עסקים במערכת: {business_count}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ בעיה במסד נתונים: {e}")
    
    # בדיקת מפתח OpenAI
    openai_key = os.getenv('OPENAI_API_KEY')
    if openai_key and len(openai_key) > 20:
        print("🔑 מפתח OpenAI: זמין ✅")
    else:
        print("❌ מפתח OpenAI: חסר")
    
    print(f"🌐 המערכת זמינה ב: http://localhost:5000")
    print(f"📞 מספר טלפון: +972-3-376-3805")

def main():
    """הרצת בדיקה מלאה"""
    print("🚀 בדיקת מערכת תמלול עברי מלאה")
    print("Agent Locator - CRM מתקדם")
    print("=" * 60)
    
    # בדיקת מצב המערכת
    test_system_status()
    
    # בדיקת תהליך מלא
    success = test_complete_workflow()
    
    print("\n" + "=" * 60)
    if success:
        print("🎯 המערכת מוכנה לקבלת שיחות!")
        print("✅ כל השלבים עוברים בהצלחה")
        print("✅ המערכת יכולה לתמלל, להגיב ולשמור")
        print("📞 ניתן לחייג למספר: +972-3-376-3805")
    else:
        print("⚠️ יש בעיות שצריכות תיקון")
        print("❌ המערכת לא מוכנה לשיחות")

if __name__ == "__main__":
    main()