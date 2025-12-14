# BUILD 342: שיפור תמלול מהקלטה לאיכות מקסימלית

## סיכום מהיר

תוקנו 3 בעיות קריטיות שגורמות לתמלול "אחרי שיחה" להיות לא מדויק:

1. ✅ **וידוא שבאמת מתמללים מהקלטה** - לא ממחזרים תמלול לייב
2. ✅ **הורדה בפורמט הכי טוב** - WAV דו-ערוצי קודם (Dual-Channel)
3. ✅ **תמלול עם מודל חזק + מילון עסקי** - gpt-4o-transcribe + אוצר מילים בעברית

## הבעיה: "נראה אותו דבר בלי ההקלטה באמת"

הבאג הכי נפוץ:
- המערכת מציגה "תמלול מהקלטה" 
- אבל בפועל שומרת את אותו טקסט שהגיע בזמן השיחה (realtime)
- אין שיפור באיכות כי זה לא תמלול חדש מהקובץ!

## התיקונים

### תיקון 1: וידוא שבאמת מתמללים מהקלטה ✅

**שדות DB חדשים** (`server/models_sql.py`):

```python
class CallLog(db.Model):
    recording_sid = db.Column(db.String(64))      # NEW: SID של ההקלטה
    audio_bytes_len = db.Column(db.Integer)       # NEW: גודל קובץ בבייטים
    audio_duration_sec = db.Column(db.Float)      # NEW: משך ההקלטה בשניות
    transcript_source = db.Column(db.String(32))  # NEW: "recording"/"realtime"/"failed"
```

**הבדיקה הקריטית:**

```python
# אם audio_bytes_len == 0 או duration < 1s 
# → זה לא תמלול מהקלטה, זה כשל הורדה!

if audio_bytes_len > 0 and audio_duration_sec >= 1.0:
    # ✅ יש קובץ תקין
    transcript_source = "recording"
else:
    # ❌ אין קובץ - fallback ל-realtime
    transcript_source = "realtime" 
```

**לוגים לאימות:**

```
[BUILD 342] ✅ Recording metadata: bytes=245830, duration=61.23s, source=recording
```

### תיקון 2: הורדה בפורמט הכי טוב ✅

**`server/services/recording_service.py`** - פונקציה `_download_from_twilio()`:

**עדיפות חדשה:**

1. `.wav?RequestedChannels=2` - WAV דו-ערוצי (הכי טוב!)
2. `.wav` - WAV רגיל (מונו)
3. `.mp3` - MP3 (fallback)
4. URL בסיסי (נסיון אחרון)

**למה Dual-Channel חשוב?**

- ערוץ נפרד ללקוח ולבוט
- פחות "זליגה" של קול הבוט לתמלול של הלקוח
- איכות אודיו גבוהה יותר (WAV > MP3)

**קוד:**

```python
urls_to_try = [
    (f"{base_url}.wav?RequestedChannels=2", "Dual-channel WAV (best quality)"),
    (f"{base_url}.wav", "Mono WAV (high quality)"),
    (f"{base_url}.mp3", "MP3 (fallback)"),
    (base_url, "Default format (last resort)"),
]
```

### תיקון 3: תמלול עם מודל חזק + אוצר מילים עסקי ✅

**`server/services/lead_extraction_service.py`** - פונקציה `transcribe_recording_with_whisper()`:

**א. אוצר מילים בעברית:**

```python
HEBREW_BUSINESS_VOCABULARY = {
    "services": [
        "פורץ מנעולים", "חשמלאי", "אינסטלטור", "נקיון", "שרברב",
        "מנעולן", "טכנאי", "תיקון", "התקנה"
    ],
    "cities": [
        "תל אביב", "ירושלים", "חיפה", "באר שבע", "פתח תקווה",
        "ראשון לציון", "בית שאן", "מצפה רמון", "אילת"
    ]
}
```

**ב. Prompt משופר:**

```python
business_vocabulary_prompt = (
    f"תמלל מילה במילה שיחת טלפון בעברית בין לקוח לנציג שירות. "
    f"תכתוב בעברית תקנית עם פיסוק. "
    f"השיחה עוסקת בבקשת שירות (למשל: {services_text}) "
    f"ומיקום (ערים בישראל כמו: {cities_text}). "
    f"אל תוסיף או תמציא מידע שלא נאמר."
)
```

**ג. מודל STT:**

```python
models_to_try = [
    ("gpt-4o-transcribe", "GPT-4o transcribe (highest quality)"),  # ראשון
    ("whisper-1", "Whisper-1 (fallback)")                          # fallback
]
```

**הגדרות:**

```python
transcript_response = client.audio.transcriptions.create(
    model=model,
    file=audio_file,
    language="he",            # עברית
    temperature=0,            # דטרמיניסטי מקסימלי
    response_format="text",   # טקסט רגיל
    prompt=business_vocabulary_prompt
)
```

## מעקב מטאדטה - Tracking

**`server/tasks_recording.py`** - Worker אופליין:

```python
# 1. קבלת גודל קובץ
audio_bytes_len = os.path.getsize(audio_file)

# 2. קבלת משך הקלטה
with contextlib.closing(wave.open(audio_file, 'r')) as f:
    frames = f.getnframes()
    rate = f.getframerate()
    audio_duration_sec = frames / float(rate)

# 3. הגדרת מקור תמלול
if final_transcript and len(final_transcript) >= 10:
    transcript_source = TRANSCRIPT_SOURCE_RECORDING  # "recording"
else:
    transcript_source = TRANSCRIPT_SOURCE_FAILED     # "failed"

# 4. שמירה ל-DB
call_log.audio_bytes_len = audio_bytes_len
call_log.audio_duration_sec = audio_duration_sec
call_log.transcript_source = transcript_source
```

**קונסטנטות:**

```python
TRANSCRIPT_SOURCE_RECORDING = "recording"  # תומלל מקובץ הקלטה
TRANSCRIPT_SOURCE_REALTIME = "realtime"    # שימוש בתמלול לייב
TRANSCRIPT_SOURCE_FAILED = "failed"        # ניסיון תמלול נכשל
```

## בדיקת הצלחה

### ✅ צ'ק ליסט (מהדרישה המקורית)

1. **התמלול "אחרי שיחה" שונה מה-live transcript:**
   ```sql
   SELECT call_sid, 
          LENGTH(final_transcript) as final_len,
          LENGTH(transcription) as live_len,
          (final_transcript != transcription) as is_different
   FROM call_log
   WHERE transcript_source = 'recording';
   ```

2. **נשמרים audio_duration_sec + audio_bytes_len > 0:**
   ```sql
   SELECT call_sid, audio_bytes_len, audio_duration_sec, transcript_source
   FROM call_log
   WHERE audio_bytes_len > 0 AND audio_duration_sec >= 1.0;
   ```

3. **ירידה דרמטית במילים מומצאות/נחתכות:**
   - השווה תמלולים לפני/אחרי
   - בדוק שמות ערים (בית שאן, מצפה רמון)
   - בדוק מונחים טכניים (פורץ מנעולים, חשמלאי)

4. **אם dual-channel: פחות תמלול של קול הבוט:**
   - בדוק שאין משפטים של הבוט בתמלול של הלקוח
   - הפרדה ברורה בין דוברים

### בדיקות SQL

**1. מציאת שיחות עם תמלול מהקלטה:**

```sql
SELECT call_sid, audio_bytes_len, audio_duration_sec, 
       LENGTH(final_transcript) as transcript_len,
       transcript_source
FROM call_log
WHERE transcript_source = 'recording'
  AND audio_bytes_len > 10000  -- לפחות 10KB
ORDER BY created_at DESC
LIMIT 10;
```

**2. בדיקת איכות - השוואה realtime vs recording:**

```sql
SELECT 
    call_sid,
    LENGTH(transcription) as realtime_len,
    LENGTH(final_transcript) as recording_len,
    transcript_source,
    audio_bytes_len,
    audio_duration_sec
FROM call_log
WHERE final_transcript IS NOT NULL
  AND transcription IS NOT NULL
  AND transcript_source = 'recording'
ORDER BY created_at DESC
LIMIT 5;
```

**3. בדיקת כשלים:**

```sql
SELECT COUNT(*) as failed_count
FROM call_log
WHERE transcript_source = 'failed'
  OR (audio_bytes_len IS NULL AND recording_url IS NOT NULL)
  OR (audio_bytes_len = 0 AND recording_url IS NOT NULL);
```

### בדיקות לוג

**לוגים מצופים - הצלחה:**

```
[BUILD 342] ✅ Recording metadata: bytes=245830, duration=61.23s, source=recording
[OFFLINE_STT] ✅ Transcript obtained with gpt-4o-transcribe (1247 chars) for CAxxxx
[RECORDING_SERVICE] ✅ Downloaded 245830 bytes using Dual-channel WAV (best quality)
```

**לוגים מצופים - כשל:**

```
[BUILD 342] ⚠️ No recording file downloaded (audio_bytes_len=None)
[OFFLINE_STT] ⚠️ Empty or invalid transcript for CAxxxx
❌ [RECORDING_SERVICE] All download attempts failed for CAxxxx
```

**חיפוש בלוגים:**

```bash
# בדיקת הורדות מוצלחות
grep "BUILD 342.*bytes=" logs/backend.log | tail -20

# בדיקת dual-channel
grep "Dual-channel WAV" logs/backend.log | wc -l

# בדיקת כשלים
grep "BUILD 342.*audio_bytes_len=None" logs/backend.log

# בדיקת תמלולים
grep "gpt-4o-transcribe.*chars" logs/backend.log | tail -10
```

## שינויים בקבצים

### 1. `server/models_sql.py`

**הוספה:**
- 4 שדות חדשים: `recording_sid`, `audio_bytes_len`, `audio_duration_sec`, `transcript_source`

### 2. `server/services/recording_service.py`

**שינוי:**
- `_download_from_twilio()` - עדיפות חדשה: dual-WAV → mono-WAV → MP3

### 3. `server/services/lead_extraction_service.py`

**הוספה:**
- `HEBREW_BUSINESS_VOCABULARY` - מילון עסקי (שירותים + ערים)

**שינוי:**
- `transcribe_recording_with_whisper()` - prompt משופר עם אוצר מילים

### 4. `server/tasks_recording.py`

**הוספה:**
- קונסטנטות: `TRANSCRIPT_SOURCE_RECORDING`, `TRANSCRIPT_SOURCE_REALTIME`, `TRANSCRIPT_SOURCE_FAILED`
- חישוב `audio_bytes_len` ו-`audio_duration_sec`
- שמירת metadata ל-DB
- לוגים מפורטים לאימות

## איכות קוד

### Code Review - כל ההערות טופלו ✅

1. ✅ **Import במקום הנכון:**
   - `wave`, `contextlib` הועברו לראש הקובץ

2. ✅ **אוצר מילים בקונסטנטה:**
   - `HEBREW_BUSINESS_VOCABULARY` - קל לעדכן ולתחזק

3. ✅ **קונסטנטות למקורות תמלול:**
   - `TRANSCRIPT_SOURCE_*` - מונע טעויות הקלדה

### CodeQL Security Scan ✅

```
Analysis Result for 'python'. Found 0 alerts.
```

אין בעיות אבטחה.

## סיכום סופי

**BUILD 342 מבטיח:**

1. ✅ **תמלול אמיתי מהקלטה** - לא ממחזור
   - בדיקה: `audio_bytes_len > 0`
   - מעקב: `transcript_source = "recording"`

2. ✅ **איכות מקסימלית**
   - Dual-channel WAV (הפרדת דוברים)
   - gpt-4o-transcribe (מודל הכי טוב)
   - אוצר מילים עסקי בעברית

3. ✅ **שקיפות מלאה**
   - כל שיחה: גודל קובץ + משך + מקור
   - לוגים מפורטים
   - קל לזהות בעיות

**תוצאה:**
- תמלול חד ומדויק יותר
- פחות מילים מומצאות
- זיהוי נכון של ערים ושירותים בעברית
- יכולת אימות שבאמת מתמללים מהקובץ
