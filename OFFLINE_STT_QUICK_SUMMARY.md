# תיקון Offline STT - סיכום מהיר

## 🎯 הבעיה
```
[OFFLINE_STT] Recording fetched ... duration=-1s
[OFFLINE_STT] Downloading recording via Twilio client: https://api.twilio.com/.../RE...mp3
[OFFLINE_STT] Download status: 404, bytes=363
```

**duration=-1** = ההקלטה עדיין בעיבוד (לא מוכנה)
**404** = הקובץ עדיין לא זמין להורדה
**המערכת ויתרה מיד** = לא היה retry mechanism

## ✅ הפתרון (מה תוקן)

### 1. Retry עבור duration=-1
```python
# ממתין עד 5 ניסיונות עם backoff: 3s, 5s, 5s, 10s, 10s
if duration is None or duration == -1:
    log: "Recording not ready yet, will retry in Xs (attempt N/5)"
    time.sleep(wait_time)
    continue
```

### 2. העתקת לוגיקת ההורדה מה-UI
```python
# מנסה מספר פורמטים (כמו ב-routes_calls.py)
urls_to_try = [
    base_url,      # ללא סיומת
    base_url.mp3,  # עם .mp3
    base_url.wav,  # עם .wav
]
```

### 3. טיפול ב-404
```python
if response.status_code == 404:
    time.sleep(5)  # ממתין 5 שניות לפני format הבא
    continue
```

### 4. עדיפות transcript (כבר הייתה נכונה)
```python
# media_ws_ai.py - שורות 9981-9986
if call_log and call_log.final_transcript:
    final_transcript = call_log.final_transcript  # ✅ OFFLINE
else:
    final_transcript = full_conversation  # fallback לrealtime
```

## 📋 לוגים צפויים אחרי התיקון

```
[OFFLINE_STT] Recording not ready yet (duration=-1), will retry in 3s (attempt 1/5)
[OFFLINE_STT] Recording not ready yet (duration=-1), will retry in 5s (attempt 2/5)
[OFFLINE_STT] Recording fetched: RE..., duration=42s
[OFFLINE_STT] Trying recording URL (format 1/3)...
[OFFLINE_STT] Download status: 200, bytes=524288
[OFFLINE_STT] ✅ Successfully downloaded 524288 bytes
[OFFLINE_STT] ✅ Recording saved to disk: server/recordings/CA....mp3
[OFFLINE_STT] Starting Whisper transcription for CA...
[OFFLINE_STT] ✅ Transcript obtained: 1234 chars
[OFFLINE_STT] ✅ Saved final_transcript (1234 chars)
...
✅ [WEBHOOK] Using OFFLINE transcript (1234 chars)
```

## 📁 קבצים ששונו

- **`server/tasks_recording.py`** - פונקציה `download_recording()` נכתבה מחדש

## 🧪 בדיקה

1. בצע שיחת טסט
2. בדוק logs שמופיעים הניסיונות עם retry
3. ודא שרואים: `✅ [WEBHOOK] Using OFFLINE transcript`

---
**סטטוס**: ✅ התיקון הושלם ומוכן לטסט
