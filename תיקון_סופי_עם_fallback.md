# תיקון סופי - הקלטות עם Fallback וניתוק אוטומטי ✅

## סיכום השינויים

### 1. הקלטה משנייה 0 ✅
**לא השתנה** - נשאר כמו שהיה בתיקון הקודם.

- הקלטה מתחילה מיד כש-CallSid זמין
- משתמשת ב-Twilio REST API
- `recordingChannels=dual` - ערוצים נפרדים
- רץ ב-thread נפרד (לא חוסם)

### 2. תמלול עם Fallback ✅
**שונה** - הוסף fallback ל-realtime transcript.

#### סדר עדיפויות:
```
1. PRIMARY: תמלול מההקלטה המלאה (Whisper - איכות גבוהה)
   ↓ אם נכשל/ריק
2. FALLBACK: תמלול realtime מה-DB (call_log.transcription)
   ↓ אם גם זה לא קיים
3. FAILED: לא נשמר תמלול (אבל לא שובר UI)
```

#### הקוד:
```python
# נסה תמלול מההקלטה
final_transcript = transcribe_recording_with_whisper(audio_file)

# אם נכשל → fallback
if not final_transcript or len(final_transcript) < 10:
    if call_log.transcription:  # Realtime מה-DB
        final_transcript = call_log.transcription
        transcript_source = TRANSCRIPT_SOURCE_REALTIME
        print(f"✅ [FALLBACK] Using realtime transcript")
```

### 3. סיכום מתמלול ✅
**שונה** - משתמש בתמלול הטוב ביותר.

- סיכום נוצר מ-`final_transcript`
- `final_transcript` יכול להיות מהקלטה **או** מ-realtime (fallback)
- אם אין תמלול בכלל → אין סיכום (אבל לא שובר)

### 4. ניתוק אחרי 20 שניות שקט ✅
**שונה** - הורד timeout מ-25 ל-20 שניות.

#### לפני:
```python
self._hard_silence_hangup_sec = 25.0
```

#### אחרי:
```python
self._hard_silence_hangup_sec = 20.0  # 🔥 AUTO-HANGUP: 20 seconds
```

#### לוגיקה:
- מעקב אחרי פעילות אחרונה: `max(last_user_voice, last_ai_audio)`
- אם עברו 20 שניות רצופות בלי פעילות → `request_hangup("hard_silence_timeout")`
- עובד גם עם מענה קולי, גם עם משתמש שקט

### 5. קישור לליד ✅
**לא השתנה** - כבר עובד נכון.

- כל שיחה נקשרת לליד לפי `phone_e164`
- נרמול מספר אחיד לפני שמירה וחיפוש
- UI מציג לפי מספר טלפון

---

## קבצים ששונו

### 1. `/server/tasks_recording.py`
**מה שונה:**
- הוסף fallback logic אחרי ניסיון תמלול מההקלטה
- טוען `call_log.transcription` אם התמלול מההקלטה נכשל
- עדכון לוגים להציג מקור התמלול (recording vs realtime)
- עדכון summary ו-extraction להשתמש בתמלול הטוב ביותר

**שורות מפתח:**
```python
# Line ~357: Fallback logic
if not final_transcript or len(final_transcript.strip()) < 10:
    print(f"🔄 [FALLBACK] Recording transcript empty/failed, checking for realtime transcript")
    if call_log and call_log.transcription and len(call_log.transcription.strip()) > 10:
        realtime_transcript = call_log.transcription
        final_transcript = realtime_transcript
        transcript_source = TRANSCRIPT_SOURCE_REALTIME
```

### 2. `/server/media_ws_ai.py`
**מה שונה:**
- שינוי `_hard_silence_hangup_sec` מ-25.0 ל-20.0
- עדכון ברירת מחדל ב-getattr מ-25.0 ל-20.0

**שורות מפתח:**
```python
# Line 1984
self._hard_silence_hangup_sec = 20.0  # Changed from 25.0

# Line 10801
hard_timeout = float(getattr(self, "_hard_silence_hangup_sec", 20.0))  # Changed from 25.0
```

---

## בדיקות נדרשות

### ✅ תרחיש 1: שיחה רגילה
1. התקשר לעסק
2. דבר עם AI
3. וודא שההקלטה מתחילה מההתחלה (כולל ברכת AI)
4. בדוק שהתמלול מהקלטה (לא realtime)
5. בדוק שיש סיכום

**תוצאה צפויה:**
- Logs: `✅ [OFFLINE_STT] Recording transcription complete`
- UI: נגן + תמלול מלא + סיכום

### ✅ תרחיש 2: תמלול הקלטה נכשל
1. התקשר לעסק
2. דבר עם AI
3. אם תמלול ההקלטה נכשל (נדיר)
4. וודא שמשתמש ב-realtime transcript

**תוצאה צפויה:**
- Logs: `🔄 [FALLBACK] Using realtime transcript`
- UI: נגן + תמלול (מ-realtime) + סיכום

### ✅ תרחיש 3: שקט 20 שניות
1. התקשר לעסק
2. אל תדבר במשך 20 שניות רצופות
3. וודא שהשיחה מתנתקת אוטומטית

**תוצאה צפויה:**
- Logs: `🔇 [HARD_SILENCE] 20.0s inactivity - hanging up`
- השיחה מסתיימת

### ✅ תרחיש 4: מענה קולי
1. התקשר למספר עם מענה קולי
2. המענה מדבר אבל המשתמש לא
3. אחרי 20 שניות → ניתוק

**תוצאה צפויה:**
- השיחה מסתיימת אוטומטית
- לא נשאר "תקוע"

---

## עקרונות חשובים

### ✅ מה כן
1. ✅ הקלטה מהשנייה הראשונה
2. ✅ תמלול ראשי מההקלטה
3. ✅ Fallback ל-realtime (הגנה)
4. ✅ סיכום תמיד אם יש תמלול
5. ✅ ניתוק אחרי 20 שניות שקט

### ❌ מה לא
1. ❌ לא הסרנו את ה-fallback
2. ❌ לא הוספנו מערכות כבדות
3. ❌ לא שיברנו UI
4. ❌ לא שינינו את הקישור לליד

---

## סטטוס

✅ **הכל מיושם ומוכן לבדיקה**

- Recording from second 0: ✅
- Transcription with fallback: ✅
- Summary from transcription: ✅
- 20-second silence hangup: ✅
- Link to lead by phone: ✅

**Commits:**
1. `e832fd0` - Added fallback to realtime transcript
2. `2afa98a` - Set auto-hangup to 20 seconds

**תאריך:** 22/12/2025  
**גרסה:** BUILD_350+  
**סטטוס:** ✅ מוכן לבדיקה
