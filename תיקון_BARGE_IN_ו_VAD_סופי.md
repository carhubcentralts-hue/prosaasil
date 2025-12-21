# תיקון Barge-In ו-VAD - סיכום שינויים

## תיאור הבעיה המקורית

הייתה בעיה כפולה במערכת:

1. **Barge-in לא עוצר תמיד** - כשהלקוח מדבר, ה-AI ממשיך לדבר לפעמים
2. **התמלול רגיש מדי** - VAD גבוה מדי גורם להתמלול להתחיל על רעשי רקע

## הפתרון שיושם

### 1. תיקון Barge-In - כלל הזהב 🔥

**העיקרון החדש: speech_started => ביטול מיידי**

#### מה השתנה:
- **לפני**: נדרש שהן `active_response_id` והן `ai_response_active` יהיו true כדי לבטל
- **אחרי**: אם קיים `active_response_id` - מבטלים מיד, ללא תנאים נוספים

#### קוד לפני:
```python
ai_can_be_cancelled = bool(ai_response_active) or is_ai_speaking
if has_active_response and ai_can_be_cancelled and ...:
    # Cancel only if both conditions met
```

#### קוד אחרי:
```python
# 🔥 GOLDEN RULE: If active_response_id exists, cancel it NOW
if has_active_response and self.realtime_client and barge_in_allowed_now:
    # Cancel immediately - no additional checks
```

#### השפעות:
1. ✅ ביטול מיידי כשהלקוח מדבר
2. ✅ פחות החמצות של barge-in
3. ✅ ניקוי מיידי של תור האודיו (Twilio + TX queue)

### 2. הפחתת רגישות VAD 📉

שינינו את הפרמטרים של turn_detection כדי להפחית רגישות:

| פרמטר | לפני | אחרי | השפעה |
|--------|------|------|--------|
| `SERVER_VAD_THRESHOLD` | 0.50 | **0.91** | פחות רגיש לרעש רקע |
| `SERVER_VAD_SILENCE_MS` | 500ms | **650ms** | יותר סבלני, לא חותך באמצע משפט |
| `SERVER_VAD_PREFIX_PADDING_MS` | 300ms | **300ms** | ללא שינוי (מתאים לעברית) |
| `BARGE_IN_VOICE_FRAMES` | 8 (160ms) | **3 (60ms)** | תגובה מהירה יותר |

#### תוצאות צפויות:
1. ✅ פחות התחלות תמלול שגויות על רעש
2. ✅ פחות חיתוך של משפטים באמצע
3. ✅ התמלול יתחיל רק על דיבור אמיתי
4. ✅ סביבה רועשת לא תפריע

### 3. קוד מפורט - Barge-In Handler

#### מיקום: `server/media_ws_ai.py` - שורות 4250-4380

התוספות העיקריות:

```python
# Step 1: Cancel response
await self.realtime_client.cancel_response(self.active_response_id)
logger.info(f"[BARGE-IN] ✅ GOLDEN RULE: Cancelled response {self.active_response_id} on speech_started")

# Step 2: Clear Twilio buffer immediately
if self.stream_sid:
    clear_event = {"event": "clear", "streamSid": self.stream_sid}
    self._ws_send(json.dumps(clear_event))

# Step 3: Flush TX queue (both OpenAI→TX and TX→Twilio)
self._flush_tx_queue()

# Step 4: Reset state
self.is_ai_speaking_event.clear()
self.active_response_id = None
self.ai_response_active = False

# Step 5: Set barge-in flag
self.barge_in_active = True
self._barge_in_started_ts = time.time()
```

### 4. קוד מפורט - VAD Configuration

#### מיקום: `server/config/calls.py` - שורות 45-65

```python
# UPDATED VALUES (per requirements):
SERVER_VAD_THRESHOLD = 0.91         # Less sensitive (was 0.50)
SERVER_VAD_SILENCE_MS = 650         # Longer wait (was 500)
SERVER_VAD_PREFIX_PADDING_MS = 300  # Unchanged

# BARGE-IN TUNING:
BARGE_IN_VOICE_FRAMES = 3   # Faster response - 60ms (was 8/160ms)
BARGE_IN_DEBOUNCE_MS = 350  # Unchanged
```

## בדיקות שנדרשות

### בדיקה 1: Barge-In עובד באופן עקבי
- [ ] לקוח מדבר באמצע תשובת AI - האודיו נעצר מיד
- [ ] לא נשמע המשך של התשובה הישנה אחרי ההפסקה
- [ ] ה-AI מתחיל תשובה חדשה על בסיס הדיבור החדש

### בדיקה 2: VAD לא רגיש מדי
- [ ] רעש רקע לא מתחיל תמלול
- [ ] דיבור אמיתי עדיין מזוהה
- [ ] משפטים לא נחתכים באמצע
- [ ] הפסקות טבעיות מאפשרות דיבור מלא

### בדיקה 3: ברכה עדיין מוגנת
- [ ] greeting_lock עדיין פועל
- [ ] ברכה לא נקטעת על ידי רעשים קצרים
- [ ] משתמש אמיתי עדיין יכול להפריע לברכה

## השוואה: לפני ואחרי

### לפני התיקון:
```
❌ Barge-in: נדרש ai_response_active=True
❌ VAD: 0.50 threshold - רגיש מדי
❌ Voice frames: 8 frames (160ms delay)
❌ Silence: 500ms - חותך מהר
```

### אחרי התיקון:
```
✅ Barge-in: ביטול מיידי על כל active_response_id
✅ VAD: 0.91 threshold - פחות רגיש
✅ Voice frames: 3 frames (60ms delay)
✅ Silence: 650ms - יותר סבלני
```

## קבצים ששונו

1. **server/config/calls.py**
   - עדכון SERVER_VAD_THRESHOLD: 0.50 → 0.91
   - עדכון SERVER_VAD_SILENCE_MS: 500 → 650
   - עדכון BARGE_IN_VOICE_FRAMES: 8 → 3

2. **server/media_ws_ai.py**
   - הסרת תנאי `ai_can_be_cancelled`
   - תיעוד מפורט של "Golden Rule"
   - הדגשת ניקוי מיידי של תורי אודיו

## ערכים מומלצים (מתוך הדרישות המקוריות)

```python
# Per requirements:
threshold: 0.91               # ✅ Implemented
silence_duration_ms: 650      # ✅ Implemented  
prefix_padding_ms: 300        # ✅ Already at 300
barge-in: cancel on speech_started  # ✅ Implemented
```

## תמיכה והבהרות

אם יש צורך לכוונן יותר:
- להגביר threshold → פחות רגיש (אבל יותר קשה לדבר)
- להגביר silence_duration_ms → פחות חיתוכים (אבל יותר לאט)
- להפחית prefix_padding_ms → פחות רעשים לפני (אבל יכול לחתוך התחלות)

כרגע הערכים הם **מאוזנים** בין רגישות לבין יציבות.
