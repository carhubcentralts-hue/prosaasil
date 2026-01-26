# Google STT & Gemini Client Optimization - Complete Implementation

## מטרה
למנוע אתחול מחדש של Google STT ו-Gemini clients בכל שיחה, ולוודא ש-Gemini עובד תמיד כשבוחרים אותו.

## מה עשינו

### Phase 1: תיקון Docker Configuration (Commits 1-3)
✅ הוספת `GOOGLE_APPLICATION_CREDENTIALS` environment variable  
✅ Mount של service account JSON עם read-only  
✅ עדכון docker-compose.yml ו-docker-compose.prod.yml  
✅ החלה על כל השירותים הרלוונטיים: backend, worker, prosaas-api, prosaas-calls

### Phase 2: Singleton Pattern Implementation (Commit 4)
✅ נוצר מודול חדש: `server/services/providers/google_clients.py`
- Thread-safe singleton ל-Google Cloud STT client
- Thread-safe singleton ל-Gemini client
- Double-checked locking pattern
- Cache של failures למניעת ניסיונות חוזרים

✅ עודכנו 7 קבצים להשתמש ב-singleton:
1. `server/services/tts_provider.py` - Gemini TTS
2. `server/services/ai_service.py` - Gemini LLM
3. `server/routes_live_call.py` - Gemini chat
4. `server/services/gcp_stt_stream.py` - Google STT streaming
5. `server/services/gcp_stt_stream_optimized.py` - Google STT optimized
6. `server/media_ws_ai.py` - Google STT batch
7. `server/app_factory.py` - warmup

### Phase 3: תיקוני באגים קריטיים (Commits 5-6)
✅ **תיקון באג חמור**: `DISABLE_GOOGLE` היה חוסם את Gemini
- תוקן `server/services/gemini_voice_catalog.py`
- הוסר `DISABLE_GOOGLE` check מ-`is_gemini_available()`
- הוסר `DISABLE_GOOGLE` check מ-`discover_voices_via_api()`

✅ **תיקון singleton pattern**: טיפול נכון ב-cached failures
- Fast path בודק אם ה-value הוא `False` (failure) או client אמיתי
- Double-check pattern מטפל נכון ב-failures

## ארכיטקטורה סופית

### כשבוחרים `business.ai_provider = 'gemini'`:
```
STT:  Google Cloud Speech-to-Text (google.cloud.speech)
      ↓ משתמש ב-GOOGLE_APPLICATION_CREDENTIALS
      ↓ Singleton - אתחול פעם אחת בלבד
      
LLM:  Gemini API (gemini-2.0-flash-exp)
      ↓ משתמש ב-GEMINI_API_KEY
      ↓ Singleton - אתחול פעם אחת בלבד
      
TTS:  Gemini Native Speech
      ↓ משתמש ב-GEMINI_API_KEY
      ↓ Singleton - אתחול פעם אחת בלבד
```

### כשבוחרים `business.ai_provider = 'openai'`:
```
STT:  OpenAI Realtime API (built-in)
LLM:  OpenAI GPT
TTS:  OpenAI TTS
```

## התנהגות DISABLE_GOOGLE

### ❌ **מה ש-DISABLE_GOOGLE חוסם** (רק שירותים ישנים):
- Google Cloud TTS הישן (deprecated)
- Google Cloud STT הישן (deprecated, כשלא משתמשים ב-Gemini)

### ✅ **מה ש-DISABLE_GOOGLE לא חוסם** (חשוב!):
- ❌ לא חוסם Gemini API (TTS, LLM, STT)
- ❌ לא חוסם Google Cloud STT כש-`ai_provider='gemini'`

## יתרונות

### 1. ביצועים
- ✅ **אין bottleneck** - לא יוצרים client חדש בכל שיחה
- ✅ **אתחול מהיר** - warmup בהפעלת שרת, לא באמצע שיחה
- ✅ **Thread-safe** - בטוח לשימוש concurrent

### 2. אמינות
- ✅ **Early failure detection** - בעיות נתפסות בהפעלה
- ✅ **Cache failures** - לא מנסים אתחול שוב ושוב
- ✅ **Clean separation** - כל provider מנותק לחלוטין

### 3. נכונות
- ✅ **Gemini תמיד עובד** כשיש GEMINI_API_KEY
- ✅ **Google Cloud STT עובד** כש-ai_provider='gemini'
- ✅ **אין hardcoded disabling** של שירותים

## אימות

נוצרו סקריפטים לאימות:
1. `verify_google_clients.py` - בדיקות מקיפות
2. `test_google_clients_singleton.py` - unit tests

**כל הבדיקות עוברות:**
```
✅ Module structure is correct
✅ DISABLE_GOOGLE only affects Google Cloud STT
✅ DISABLE_GOOGLE does NOT affect Gemini
✅ Thread-safe singleton pattern implemented
✅ gemini_voice_catalog works with DISABLE_GOOGLE=true
```

## פריסה

```bash
# עצור קונטיינרים
docker compose down

# הפעל מחדש עם force-recreate (חובה!)
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --force-recreate
```

**חשוב:** `--force-recreate` חובה כי:
- Environment variables מוגדרים רק בעת יצירת קונטיינר
- Volume mounts מוגדרים רק בעת יצירת קונטיינר

## סיכום טכני

| תכונה | לפני | אחרי |
|-------|------|------|
| Google STT init | בכל שיחה | פעם אחת (singleton) |
| Gemini client init | בכל request | פעם אחת (singleton) |
| DISABLE_GOOGLE חוסם Gemini | ✅ כן (באג!) | ❌ לא (תוקן) |
| Warmup בעליית שרת | ❌ לא | ✅ כן |
| Thread-safe | ❓ unclear | ✅ כן (double-checked locking) |
| Cache failures | ❌ לא | ✅ כן |

## קבצים שונו

### קבצים חדשים:
- `server/services/providers/google_clients.py` - singleton module
- `server/services/providers/__init__.py` - package init
- `verify_google_clients.py` - verification script
- `test_google_clients_singleton.py` - unit tests
- `GOOGLE_STT_DEPLOYMENT_GUIDE.md` - deployment guide
- `תיקון_Google_STT_סיכום.md` - Hebrew summary

### קבצים מעודכנים:
- `docker-compose.yml` - ENV + volume mounts
- `docker-compose.prod.yml` - ENV + volume mounts  
- `server/app_factory.py` - warmup call
- `server/services/tts_provider.py` - use singleton
- `server/services/ai_service.py` - use singleton
- `server/routes_live_call.py` - use singleton
- `server/services/gcp_stt_stream.py` - use singleton
- `server/services/gcp_stt_stream_optimized.py` - use singleton
- `server/media_ws_ai.py` - use singleton
- `server/services/gemini_voice_catalog.py` - remove DISABLE_GOOGLE check

## מה הלאה?

כל התיקונים הושלמו ומאומתים. המערכת מוכנה לפרודקשן:

1. ✅ Docker configuration תקין
2. ✅ Singleton pattern מיושם
3. ✅ Gemini עובד תמיד כשבוחרים אותו
4. ✅ Google Cloud STT עובד עם Gemini
5. ✅ אין bottlenecks
6. ✅ כל הבדיקות עוברות

**המערכת מוכנה לפריסה!**
