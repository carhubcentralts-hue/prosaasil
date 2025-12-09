# תיקון 404 - הורדת הקלטות מ-Twilio

## 🎯 הבעיה
הקוד ניסה להוריד הקלטות מ-Twilio ונכשל עם **404 Not Found** כי:
1. Twilio מחזיר URL יחסי המסתיים ב-`.json` (לדוגמה: `/2010-04-01/.../Recordings/RExxxxx.json`)
2. הקוד הישן היה מוסיף `.mp3` אחד והולך - אם זה נכשל, הוא מוותר
3. לא היו ניסיונות מרובים של פורמטים שונים

## ✅ הפתרון

### 1. תיקון `download_recording` ב-`server/tasks_recording.py`
```python
def download_recording(recording_url: str, call_sid: str) -> Optional[str]:
    # 1) הסרת .json אם קיים
    if base_url.endswith(".json"):
        base_url = base_url[:-5]
    
    # 2) ניסיון של 3 קנדידטים:
    candidates = [
        base_url,              # בלי סיומת (ברירת מחדל של Twilio)
        base_url + ".mp3",
        base_url + ".wav",
    ]
    
    # 3) לולאה על כל הקנדידטים
    for url in candidates:
        resp = session.get(url, timeout=15)
        if resp.status_code == 200 and resp.content:
            # הצלחה! שמור ותחזיר
            return save_to_disk(resp.content)
        if resp.status_code == 404:
            continue  # נסה קנדידט הבא
```

**שינויים עיקריים:**
- הסרת `.json` לפני הניסיון להוריד
- לולאה על 3 וריאציות של URL
- המשך לקנדידט הבא במקרה של 404
- לוגים מפורטים לכל ניסיון

### 2. תיקון `routes_twilio.py` - שימוש ב-`recording.uri`
```python
# לפני:
recording_mp3_url = f"https://api.twilio.com/.../Recordings/{recording.sid}.mp3"

# אחרי:
form_data = {
    'CallSid': call_sid,
    'RecordingUrl': recording.uri,  # ✅ כמו שהוא, עם .json
}
```

**למה?** `recording.uri` הוא ה-URI המקורי מ-Twilio, והפונקציה `download_recording` תטפל בנורמליזציה.

### 3. תיקון `routes_calls.py` - endpoint להורדה
```python
# לפני:
urls_to_try = [
    f"{call.recording_url}.mp3",  # ❌ מוסיף .mp3 על .json
    call.recording_url,
]

# אחרי:
base_url = call.recording_url
if base_url.endswith(".json"):
    base_url = base_url[:-5]

urls_to_try = [
    base_url,              # בלי סיומת
    f"{base_url}.mp3",
    f"{base_url}.wav",
]
```

## 🔍 מה לבדוק אחרי השינוי

### בלוגים של שיחה אחת:
```bash
# צריך לראות:
[OFFLINE_STT] Original recording_url for CAxxxx: /2010-04-01/.../RExxxx.json
[OFFLINE_STT] Trying download for CAxxxx: https://api.twilio.com/.../RExxxx
[OFFLINE_STT] Download status for CAxxxx: 404 (https://api.twilio.com/.../RExxxx)
[OFFLINE_STT] Trying download for CAxxxx: https://api.twilio.com/.../RExxxx.mp3
[OFFLINE_STT] Download status for CAxxxx: 200 (https://api.twilio.com/.../RExxxx.mp3)
[OFFLINE_STT] ✅ Download OK for CAxxxx, bytes=123456 from https://...
[OFFLINE_STT] ✅ Recording saved to disk: server/recordings/CAxxxx.mp3 (123456 bytes)
[OFFLINE_STT] ✅ Transcript obtained: 543 chars for CAxxxx
[OFFLINE_STT] ✅ Saved final_transcript (543 chars) for CAxxxx
[WEBHOOK] ✅ Using OFFLINE transcript (543 chars)
```

### בUI:
- התמלול צריך להיות **מלא ואיכותי** גם אם realtime היה חלש
- השדה "תמלול" בכרטיס השיחה יהיה מלא
- הסיכום יהיה מבוסס על offline transcript

## 🎯 עדיפות Offline על Realtime

הקוד ב-`media_ws_ai.py` כבר מטפל בזה נכון:

```python
# שורות 9981-9986
if call_log and call_log.final_transcript:
    final_transcript = call_log.final_transcript  # ← OFFLINE תמיד בעדיפות!
    print(f"✅ [WEBHOOK] Using OFFLINE transcript ({len(final_transcript)} chars)")
else:
    final_transcript = full_conversation  # realtime fallback
    print(f"ℹ️ [WEBHOOK] Offline transcript missing → using realtime")
```

## 📋 סטטוס תיקונים

- ✅ `server/tasks_recording.py` - `download_recording()` מתוקן
- ✅ `server/routes_twilio.py` - שימוש ב-`recording.uri` כמו שהוא
- ✅ `server/routes_calls.py` - endpoint הורדה מתוקן
- ✅ `server/media_ws_ai.py` - עדיפות offline כבר קיימת
- ✅ טסטים - `test_recording_url_fix.py` עובר בהצלחה

## 🚀 דפלוי

לאחר השינויים, כדי לבדוק:
1. עשה שיחת טסט
2. בדוק בלוגים שההורדה מצליחה (200)
3. בדוק בUI שהתמלול מופיע מלא
4. בדוק שה-webhook מקבל offline transcript

אם עדיין 404 - זה בעיה של Twilio (הרשאות/פורמט), לא של הקוד.
