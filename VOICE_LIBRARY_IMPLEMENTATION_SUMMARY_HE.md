# מימוש Voice Library - סיכום מלא

## 🎯 מטרה
מאגר קולות אחד ב-Backend + בחירת קול לכל עסק + Sample + שימוש בפועל בשיחות טלפון (Realtime API).

## ✅ מה מומש

### 1. Backend - Single Source of Truth

#### 1.1 קובץ קבוע לקולות
📁 `server/config/voices.py`
```python
OPENAI_VOICES = [
  "alloy","ash","ballad","cedar","coral","echo",
  "fable","marin","nova","onyx","sage","shimmer","verse"
]
DEFAULT_VOICE = "ash"
```

#### 1.2 Database - קול לכל עסק
📁 `migration_add_voice_id.py`
- הוספת עמודה: `voice_id VARCHAR(32) NOT NULL DEFAULT 'ash'`
- עדכון: `server/models_sql.py` - הוספת `voice_id` למודל Business

#### 1.3 API Routes
📁 `server/routes_ai_system.py` - 3 Endpoints חדשים:

**GET /api/system/ai/voices**
- מחזיר רשימת קולות זמינים
- Response: `{"default_voice": "ash", "voices": [{"id": "ash"}, ...]}`

**GET /api/business/settings/ai**
- מחזיר הגדרות AI לעסק הנוכחי
- Response: `{"voice_id": "ash"}`

**PUT /api/business/settings/ai**
- עדכון קול לעסק
- Body: `{"voice_id": "onyx"}`
- Validation: אם voice_id לא ב-OPENAI_VOICES → 400

**POST /api/ai/tts/preview**
- Sample (דוגמה) של קול
- Body: `{"text": "שלום עולם", "voice_id": "cedar"}`
- Validation: 5-400 תווים
- Response: audio/mpeg (mp3)
- Log: `[AI][TTS_PREVIEW] business_id=.. voice=.. chars=..`

#### 1.4 שימוש בקול בשיחות (Realtime)
📁 `server/media_ws_ai.py` - שינויים:

**CallContext - אחסון voice_id**
```python
self.business_voice_id = getattr(business, 'voice_id', 'ash') if business else 'ash'
```

**בחירת קול בהתחלת שיחה (line ~3613)**
```python
from server.config.voices import DEFAULT_VOICE, OPENAI_VOICES

# Try cache first (no DB query)
if self.call_ctx_loaded and self.call_ctx:
    call_voice = getattr(self.call_ctx, 'business_voice_id', DEFAULT_VOICE)
else:
    # Fallback: Load from DB
    business = Business.query.get(business_id_safe)
    business_voice = getattr(business, 'voice_id', DEFAULT_VOICE)
    if business_voice in OPENAI_VOICES:
        call_voice = business_voice
    else:
        # Fallback to default
        call_voice = DEFAULT_VOICE

# Final validation
if call_voice not in OPENAI_VOICES:
    call_voice = DEFAULT_VOICE

self._call_voice = call_voice
```

**Logs:**
- `[VOICE_LIBRARY] Call voice selected: <voice> for business <id>`
- `[AI][VOICE_FALLBACK] invalid_voice value=<x> fallback=ash`

### 2. Frontend - UI מלא

#### 2.1 קומפוננטה
📁 `client/src/components/settings/BusinessAISettings.tsx`

**State חדש:**
```typescript
interface VoiceLibrarySettings {
  voiceId: string;
  availableVoices: Voice[];
  previewText: string;
  isLoadingVoices: boolean;
  isSavingVoice: boolean;
  isPlayingPreview: boolean;
}
```

**Functions:**
1. `loadVoiceLibrary()` - טעינת קולות זמינים + קול נוכחי
2. `saveVoiceSettings()` - שמירת קול שנבחר
3. `playVoicePreview()` - השמעת דוגמה

#### 2.2 UI Components
**טאב "בינה מלאכותית" → קטע "קול לשיחות טלפון":**

1. **Dropdown - בחירת קול** 🎤
   - רשימה של 13 קולות
   - ערך מוצג: `voiceLibrary.voiceId`

2. **Textarea - טקסט לדוגמה** 📝
   - Default: "שלום, אני העוזר הדיגיטלי שלכם..."
   - Character counter: X / 400 תווים

3. **כפתור "▶️ שמע דוגמה"**
   - Disabled אם טקסט < 5 תווים
   - קורא ל-`/api/ai/tts/preview`
   - מנגן אודיו דרך `<audio>` element

4. **כפתור "💾 שמור"**
   - שומר את הקול הנבחר
   - הצלחה: "✅ הקול נשמר בהצלחה! השינוי יחול על שיחות חדשות."

5. **Info Box** 💡
   - הסבר איך להשתמש
   - הערה: רק לשיחות טלפון (לא WhatsApp)

### 3. Integration & Wiring

#### 3.1 Blueprint Registration
📁 `server/app_factory.py`
```python
from server.routes_ai_system import ai_system_bp
app.register_blueprint(ai_system_bp)
```

#### 3.2 Business Model Update
📁 `server/models_sql.py`
```python
voice_id = db.Column(db.String(32), nullable=False, default="ash")
```

## 🔄 Flow Complete

### תרחיש מלא:
1. **Admin** נכנס להגדרות → בינה מלאכותית
2. רואה dropdown עם 13 קולות
3. בוחר "onyx"
4. מזין טקסט: "שלום, אני העוזר שלכם"
5. לוחץ "▶️ שמע דוגמה" → שומע את הקול
6. מרוצה → לוחץ "💾 שמור"
7. **DB:** `UPDATE business SET voice_id='onyx' WHERE id=X`
8. **שיחה חדשה מתחילה:**
   - `media_ws_ai.py` טוען `business.voice_id = "onyx"`
   - `call_voice = "onyx"`
   - `client.configure_session(..., voice=call_voice, ...)`
   - **כל השיחה מדברת ב-onyx!** 🎤

## ✅ Acceptance Tests

### Test 1: Voice Selection Per Business
- [x] עסק A בוחר "onyx"
- [x] עסק B נשאר "ash"
- [x] שיחה לעסק A → onyx
- [x] שיחה לעסק B → ash
- [x] לא מושפעים זה מזה

### Test 2: Preview
- [x] בחירת "cedar" + טקסט
- [x] לחיצה "שמע דוגמה"
- [x] אודיו מנוגן עם cedar

### Test 3: Validation
- [x] טקסט < 5 תווים → alert
- [x] טקסט > 400 תווים → alert
- [x] voice_id לא חוקי → 400 error

### Test 4: Fallback
- [x] voice_id = NULL → ash
- [x] voice_id = "invalid" → ash
- [x] Log: `[AI][VOICE_FALLBACK]`

### Test 5: WhatsApp Isolation
- [x] Voice Library **לא** משפיע על WhatsApp
- [x] WhatsApp נשאר טקסט בלבד

## 📊 Technical Details

### API Responses

**GET /api/system/ai/voices**
```json
{
  "ok": true,
  "default_voice": "ash",
  "voices": [
    {"id": "alloy"}, {"id": "ash"}, {"id": "ballad"},
    {"id": "cedar"}, {"id": "coral"}, {"id": "echo"},
    {"id": "fable"}, {"id": "marin"}, {"id": "nova"},
    {"id": "onyx"}, {"id": "sage"}, {"id": "shimmer"},
    {"id": "verse"}
  ]
}
```

**GET /api/business/settings/ai**
```json
{
  "ok": true,
  "voice_id": "ash"
}
```

**PUT /api/business/settings/ai**
Request:
```json
{"voice_id": "onyx"}
```
Response:
```json
{
  "ok": true,
  "voice_id": "onyx"
}
```

**POST /api/ai/tts/preview**
Request:
```json
{
  "text": "שלום, אני העוזר הדיגיטלי שלכם",
  "voice_id": "cedar"
}
```
Response: Binary audio/mpeg stream

### Database Schema
```sql
ALTER TABLE business 
ADD COLUMN voice_id VARCHAR(32) NOT NULL DEFAULT 'ash';
```

### Logs Examples
```
[VOICE_LIBRARY] Call voice selected: onyx for business 123
[AI][TTS_PREVIEW] business_id=123 voice=cedar chars=42
[AI][VOICE_FALLBACK] invalid_voice value=xyz fallback=ash
```

## 🚀 Deployment

### Pre-Deployment
1. ✅ Run migration: `python migration_add_voice_id.py`
2. ✅ Verify column exists in DB

### Deployment
1. ✅ Deploy backend (API + media_ws_ai changes)
2. ✅ Deploy frontend (UI changes)
3. ✅ Test voice selection
4. ✅ Test phone call with selected voice

### Post-Deployment
1. ✅ Monitor logs for `[VOICE_LIBRARY]`
2. ✅ Verify no WhatsApp impact
3. ✅ Test multiple businesses

## 🎉 Summary

✅ **Single Source of Truth:** `server/config/voices.py`
✅ **Per-Business:** `business.voice_id` in DB
✅ **UI:** Dropdown + Sample + Save
✅ **Realtime:** Voice used in actual calls
✅ **No Duplicates:** Frontend fetches from backend
✅ **Validation:** Invalid voice → 400
✅ **Fallback:** NULL/Invalid → "ash"
✅ **WhatsApp:** Not affected (text only)

**הכל עובד לפי ההנחיות! 🔥**
