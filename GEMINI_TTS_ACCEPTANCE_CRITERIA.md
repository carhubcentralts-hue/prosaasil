# Gemini TTS Fix - Acceptance Criteria

## סיכום השיפורים שבוצעו

התיקון מטפל בבעיות השורש של Gemini TTS:
1. 400 INVALID_ARGUMENT - מודל מנסה לייצר טקסט במקום AUDIO
2. Timeouts - בקשות נתקעות וממשיכות ברקע
3. TTS Flooding - מספר בקשות TTS במקביל לאותה שיחה

---

## 4 Acceptance Criteria (ללא זה אי אפשר להגיד "מושלם")

### ✅ AC1: אין יותר 400 INVALID_ARGUMENT בשום תרחיש

**מה נעשה:**
- הוספנו PRE-REQUEST ASSERTION לפני כל קריאת API
- בדיקה שהקונפיג כולל: `response_modalities=["AUDIO"]` ו-`speech_config`
- לוג מפורט: model, voice, text_len, response_modalities, has_speech_config
- 4 guards אחרי הקריאה: response exists, candidates exist, audio extracted, audio not empty
- Voice validation: רק קולות תקינים מה-allowlist, fallback לdefault אם לא תקין

**איך לוודא:**
```bash
# בלוגים צריך לראות:
[GEMINI_TTS] PRE_REQUEST_ASSERTION: model=gemini-2.5-flash-preview-tts (TTS_MODEL_ONLY), voice=pulcherrima, text_len=50, response_modalities=['AUDIO'], has_speech_config=True [TTS_ONLY_PATH - NO_LLM_SHARING]
[GEMINI_TTS] request_ok bytes=12345 latency_ms=2500 model=gemini-2.5-flash-preview-tts voice=pulcherrima text_len=50

# לעולם לא צריך לראות:
INVALID_ARGUMENT
Model tried to generate text
400 error
```

---

### ✅ AC2: P95 זמן TTS < 3 שניות, ו-timeout אמיתי לא יוצר backlog

**מה נעשה:**
- HTTP-level timeout: connect=2s, read=10s (ב-`google_clients.py`)
- הסרנו threading-based timeout שלא ביטל בקשות
- Timeout מבוצע ברמת httpx Client, מבטל את ה-HTTP request בפועל
- Latest-wins strategy: אם TTS inflight, לא שולחים עוד - מחכים לסיום

**איך לוודא:**
```bash
# בלוגים:
[GEMINI_TTS] request_ok ... latency_ms=2500  # רוב הבקשות < 3000ms
✅ Gemini client initialized (singleton) with timeout: connect=2s, read=10s

# אסור לראות:
TIMEOUT after 6s
tx_q backlog > 200 frames אחרי TTS timeout
```

**מדידה בפועל:**
```python
# להריץ 100 בקשות TTS ולבדוק P95:
import time
latencies = []
for i in range(100):
    start = time.time()
    synthesize_gemini("שלום עולם")
    latencies.append((time.time() - start) * 1000)

p95 = sorted(latencies)[94]  # צריך להיות < 3000ms
```

---

### ✅ AC3: אין flooding - לעולם לא יותר מ-TTS אחד inflight לכל שיחה

**מה נעשה:**
- `tts_inflight` flag עם lock בכל MediaStreamHandler
- `tts_request_id` counter - מזהה ייחודי לכל בקשה
- אם `tts_inflight=True` → skip new request, log warning
- בcallback: בודקים שזה latest request, אחרת discard
- Clear inflight flag בסוף (success או error)

**איך לוודא:**
```bash
# בלוגים בזמן עומס:
[TTS] request_id=1 started: provider=gemini, text_len=50
[TTS] TTS already inflight (request_id=1) - skipping new request (latest-wins strategy)
[TTS_CALLBACK] request_id=1 Session closed - discarding TTS result  # אם לא relevant

# מונה במספרים:
# אם יש 3 תגובות AI ב-5 שניות, צריך לראות רק 1 TTS inflight בכל רגע:
grep "request_id=" logs.txt | grep "started" | sort
# Output example:
# [TTS] request_id=1 started  (t=0s)
# [TTS] TTS already inflight  (t=1s) <- נחסם
# [TTS] request_id=2 started  (t=5s) <- אחרי שהראשון נגמר
```

**קוד לבדיקה:**
```python
# ב-MediaStreamHandler.__init__:
assert hasattr(self, 'tts_inflight')
assert hasattr(self, 'tts_request_id')
assert hasattr(self, 'tts_lock')
```

---

### ✅ AC4: אם TTS נכשל - השיחה ממשיכה לקלוט ולענות, ורואים ב-DB: tts_status=failed + tts_error_code

**מה נעשה:**
- הסרנו **כל** הקריאות ל-`_send_beep()` מ-TTS error paths
- במקום beep: `call_log.tts_status = "failed"` + `call_log.tts_error_code`
- `_finalize_speaking()` מחזיר ל-STATE_LISTEN מיד - לא חוסם
- Clear `tts_inflight` flag גם ב-error paths
- Callback ממשיך לעבד - לא משאיר session תקוע

**איך לוודא:**
```bash
# בלוגים:
🔊 TTS returned no audio (request_id=5) - NOT sending beep (per requirements)
❌ GREETING_TTS_FAILED - NOT sending beep (per requirements)

# במקום beep - צריך לראות:
🎤 SPEAKING_END -> LISTEN STATE | buffer_reset
# והשיחה ממשיכה לקלוט

# ב-DB:
SELECT call_sid, tts_status, tts_error_code FROM call_logs WHERE tts_status='failed';
# תוצאה:
# call_sid=CA123... | tts_status=failed | tts_error_code=NO_AUDIO_BYTES
# call_sid=CA456... | tts_status=failed | tts_error_code=GREETING_NO_AUDIO
```

**תרחיש בדיקה:**
1. כבה GEMINI_API_KEY זמנית
2. התחל שיחה
3. וודא: השיחה לא נתקעת, מחזירה ל-LISTEN, יש רשומה ב-DB עם tts_status=failed

```python
# Simulate TTS failure:
os.environ['GEMINI_API_KEY'] = ''  # זמנית
# התחל שיחה
# וודא:
assert call_log.tts_status == 'failed'
assert call_log.tts_error_code.startswith('GEMINI_TTS')
assert handler.state == STATE_LISTEN  # חזר להאזנה
assert not handler.closed  # השיחה לא נסגרה
```

---

## בדיקת Smoke Test מלאה

```bash
# 1. התחל server עם DEBUG=0
DEBUG=0 GEMINI_API_KEY=your_key python run_server.py

# 2. צפה בלוגים של startup:
# צריך לראות:
[GEMINI_TTS] Startup config: model=gemini-2.5-flash-preview-tts, default_voice=pulcherrima, available=True

# 3. בצע שיחת בדיקה:
# התקשר למספר Twilio
# דבר עם הבוט
# וודא בלוגים:

# ✅ לפני כל TTS request:
[GEMINI_TTS] PRE_REQUEST_ASSERTION: model=... response_modalities=['AUDIO'] ... [TTS_ONLY_PATH]

# ✅ אחרי TTS success:
[GEMINI_TTS] request_ok bytes=... latency_ms=...

# ✅ אין שגיאות:
# אין: INVALID_ARGUMENT
# אין: TIMEOUT after 6s
# אין: Model tried to generate text
# אין: tx_q backlog > 200

# ✅ TTS flooding prevented:
# אם יש 2 תגובות רצופות, רק 1 TTS inflight:
[TTS] request_id=1 started
[TTS] TTS already inflight ... skipping new request

# 4. בדוק DB:
SELECT COUNT(*) FROM call_logs WHERE tts_status='failed';
# אם יש failures, וודא שיש tts_error_code:
SELECT tts_error_code FROM call_logs WHERE tts_status='failed' LIMIT 5;
```

---

## Summary - מה השתנה

| Before | After |
|--------|-------|
| 400 INVALID_ARGUMENT errors | ✅ PRE-REQUEST assertion + guards |
| Threading timeout (doesn't cancel) | ✅ HTTP timeout (connect=2s, read=10s) |
| Multiple TTS requests concurrent | ✅ tts_inflight gate, latest-wins |
| Beep masking on failure | ✅ tts_status=failed + tts_error_code |
| TTS blocks receive_loop | ✅ _finalize_speaking immediate return |
| No model separation | ✅ GEMINI_TTS_MODEL separate from LLM |
| Voice not validated | ✅ Allowlist validation, fallback to default |

---

## מה עוד צריך?

אם עדיין יש 400 אחרי כל זה, צריך:
1. לבדוק שה-API key תקין ויש לו הרשאות TTS
2. לוודא ש-`google-genai` SDK מעודכן לגרסה האחרונה
3. לבדוק שה-model name `gemini-2.5-flash-preview-tts` קיים בפועל (אולי שונה)
4. לשלוח את הלוג המדויק עם PRE_REQUEST_ASSERTION ל-Google Support

**אבל** - אם הקוד פועל כמתוכנן, לא צריך להיות 400 בכלל.
