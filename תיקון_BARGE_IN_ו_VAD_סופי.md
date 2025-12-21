# תיקון Barge-In ו-VAD - סיכום שינויים (מעודכן)

## תיאור הבעיה המקורית

הייתה בעיה כפולה במערכת:

1. **Barge-in לא עוצר תמיד** - כשהלקוח מדבר, ה-AI ממשיך לדבר לפעמים
2. **התמלול רגיש מדי** - VAD גבוה מדי גורם להתמלול להתחיל על רעשי רקע

## הפתרון שיושם (גרסה מעודכנת - גישה מאוזנת)

### 1. תיקון Barge-In - כלל הזהב 🔥

**העיקרון החדש: speech_started => ביטול מיידי**

#### מה השתנה:
- **לפני**: נדרש שהן `active_response_id` והן `ai_response_active` יהיו true כדי לבטל
- **אחרי**: אם קיים `active_response_id` - מבטלים מיד, ללא תנאים נוספים

#### הגנות שהוספו:
1. ✅ **Idempotency**: `_should_send_cancel()` מונע ביטול כפול
2. ✅ **State tracking**: `_mark_response_cancelled_locally()` עוקב אחר responses שבוטלו
3. ✅ **Exception handling**: טיפול חכם בשגיאות "already_cancelled"

#### קוד אחרי:
```python
# 🔥 GOLDEN RULE: If active_response_id exists, cancel it NOW
if has_active_response and self.realtime_client and barge_in_allowed_now:
    # Step 1: Cancel (with idempotency protection)
    if self._should_send_cancel(self.active_response_id):
        await self.realtime_client.cancel_response(self.active_response_id)
        self._mark_response_cancelled_locally(self.active_response_id, "barge_in")
    
    # Step 2: Clear Twilio queue
    # Step 3: Flush TX queue  
    # Step 4: Reset state
```

#### השפעות:
1. ✅ ביטול מיידי כשהלקוח מדבר
2. ✅ אין ביטול כפול (הגנת idempotency)
3. ✅ ניקוי מיידי של תור האודיו (Twilio + TX queue)

### 2. הפחתת רגישות VAD 📉 (גישה הדרגתית)

**שינינו את הגישה לפי המלצות מומחה - עדיף להתחיל באמצע ולכוונן:**

| פרמטר | לפני | ניסיון 1 | **אחרי (מאוזן)** | השפעה |
|--------|------|----------|-------------------|--------|
| `SERVER_VAD_THRESHOLD` | 0.50 | 0.91 | **0.82** | איזון: פחות רעש, עדיין תופס דיבור שקט |
| `SERVER_VAD_SILENCE_MS` | 500ms | 650ms | **650ms** | יותר סבלני, לא חותך באמצע |
| `SERVER_VAD_PREFIX_PADDING_MS` | 300ms | 300ms | **300ms** | ללא שינוי (מתאים לעברית) |
| `BARGE_IN_VOICE_FRAMES` | 8 (160ms) | 3 (60ms) | **4 (80ms)** | איזון: מהיר אך לא רגיש מדי |

#### הסבר השינויים:

**VAD Threshold (0.82 במקום 0.91):**
- 0.91 היה גבוה מדי → יכול לפספס דיבור שקט
- 0.50 היה נמוך מדי → רגיש מדי לרעש
- **0.82 = נקודת איזון** (בטווח 0.75-0.85 המומלץ)

**Barge-in Frames (4 במקום 3):**
- 3 frames (60ms) היה מהיר מדי → סיכון לביטול שגוי על רעש/נשימות
- 8 frames (160ms) היה איטי מדי → חוויה פחות רספונסיבית
- **4 frames (80ms) = איזון** בין מהירות לדיוק

#### תוצאות צפויות:
1. ✅ פחות התחלות תמלול שגויות על רעש
2. ✅ עדיין תופס דיבור בעוצמה רגילה/שקטה
3. ✅ פחות חיתוך של משפטים באמצע
4. ✅ barge-in מהיר אך לא רגיש מדי

### 3. מעקב ניטור נדרש ⚠️

**חשוב לבדוק בייצור ולכוונן לפי הצורך:**

#### אם רואים יותר מדי false triggers (רעש מפעיל תמלול):
```python
SERVER_VAD_THRESHOLD = 0.85  # העלה ל-0.85-0.88
BARGE_IN_VOICE_FRAMES = 5    # העלה ל-5 frames (100ms)
```

#### אם מפספסים דיבור שקט:
```python
SERVER_VAD_THRESHOLD = 0.75  # הורד ל-0.75-0.78
```

#### אם המערכת לא מרגישה רספונסיבית:
```python
SERVER_VAD_SILENCE_MS = 550  # הורד ל-550-600ms
```

#### אם barge-in מפריע ללא סיבה:
```python
BARGE_IN_VOICE_FRAMES = 5    # העלה ל-5 frames (100ms)
```

### 4. קוד מפורט - Barge-In Handler

#### מיקום: `server/media_ws_ai.py` - שורות 4300-4380

התוספות העיקריות (עם הגנות):

```python
# Step 1: Cancel response (WITH IDEMPOTENCY PROTECTION)
if self._should_send_cancel(self.active_response_id):
    await self.realtime_client.cancel_response(self.active_response_id)
    self._mark_response_cancelled_locally(self.active_response_id, "barge_in")
    logger.info(f"[BARGE-IN] ✅ GOLDEN RULE: Cancelled {self.active_response_id}")
else:
    logger.debug("[BARGE-IN] Skipped duplicate cancel")  # ← הגנה!

# Step 2: Clear Twilio buffer
if self.stream_sid:
    clear_event = {"event": "clear", "streamSid": self.stream_sid}
    self._ws_send(json.dumps(clear_event))

# Step 3: Flush TX queue
self._flush_tx_queue()

# Step 4: Reset state (אחרי cancel בלבד!)
self.active_response_id = None
self.ai_response_active = False
```

### 5. קוד מפורט - VAD Configuration

#### מיקום: `server/config/calls.py` - שורות 45-125

```python
# BALANCED VALUES (per expert feedback):
SERVER_VAD_THRESHOLD = 0.82         # Balanced (was 0.50, tried 0.91)
SERVER_VAD_SILENCE_MS = 650         # Longer wait (was 500)
SERVER_VAD_PREFIX_PADDING_MS = 300  # Unchanged

# BARGE-IN TUNING:
BARGE_IN_VOICE_FRAMES = 4   # Balanced: 80ms (was 8, tried 3)
BARGE_IN_DEBOUNCE_MS = 350  # Unchanged
```

## בדיקות שנדרשות

### בדיקה 1: Barge-In עובד באופן עקבי
- [ ] לקוח מדבר באמצע תשובת AI - האודיו נעצר תוך 80-200ms
- [ ] לא נשמע המשך של התשובה הישנה אחרי ההפסקה
- [ ] ה-AI מתחיל תשובה חדשה על בסיס הדיבור החדש
- [ ] **רעש/נשימות/קליקים לא גורמים לbiarge-in שגוי**

### בדיקה 2: VAD לא רגיש מדי (אך עדיין תופס)
- [ ] רעש רקע לא מתחיל תמלול
- [ ] דיבור אמיתי (כולל שקט!) עדיין מזוהה
- [ ] משפטים לא נחתכים באמצע
- [ ] הפסקות טבעיות מאפשרות דיבור מלא

### בדיקה 3: ברכה עדיין מוגנת
- [ ] greeting_lock עדיין פועל
- [ ] ברכה לא נקטעת על ידי רעשים קצרים
- [ ] משתמש אמיתי עדיין יכול להפריע לברכה

### בדיקה 4: תרחישים ספציפיים (מההמלצות)
1. **לקוח קוטע באמצע משפט** → עוצר תוך <200ms?
2. **רעש רקע קבוע** → אין false speech_started?
3. **לקוח מדבר חלש** → מזהה בכלל?
4. **"הלו" קצר** → לא מתפספס?
5. **greeting_lock** → barge-in עובד מיד אחרי?
6. **שקט 20-30 שניות** → מתנתק כרגיל?

## השוואה: לפני ואחרי (מעודכן)

### לפני התיקון:
```
❌ Barge-in: נדרש ai_response_active=True
❌ VAD: 0.50 threshold - רגיש מדי
❌ Voice frames: 8 frames (160ms delay)
❌ Silence: 500ms - חותך מהר
```

### אחרי התיקון (גרסה מאוזנת):
```
✅ Barge-in: ביטול מיידי על כל active_response_id + הגנת idempotency
✅ VAD: 0.82 threshold - מאוזן (לא רגיש מדי, לא מפספס)
✅ Voice frames: 4 frames (80ms delay) - מהיר אך בטוח
✅ Silence: 650ms - יותר סבלני
```

## קבצים ששונו

1. **server/config/calls.py**
   - עדכון SERVER_VAD_THRESHOLD: 0.50 → 0.82 (לא 0.91!)
   - עדכון SERVER_VAD_SILENCE_MS: 500 → 650
   - עדכון BARGE_IN_VOICE_FRAMES: 8 → 4 (לא 3!)

2. **server/media_ws_ai.py**
   - הסרת תנאי `ai_can_be_cancelled`
   - תיעוד מפורט של "Golden Rule"
   - הדגשת ניקוי מיידי של תורי אודיו
   - הגנת idempotency כבר קיימת ב-`_should_send_cancel()`

## ערכים מומלצים (מעודכן לפי משוב מומחה)

```python
# Per expert feedback - balanced approach:
threshold: 0.82               # ✅ Implemented (was 0.91, too high)
silence_duration_ms: 650      # ✅ Implemented  
prefix_padding_ms: 300        # ✅ Already at 300
barge_in_frames: 4 (80ms)     # ✅ Implemented (was 3, too fast)

# Monitor and adjust based on production data:
# - Too many false triggers → increase threshold to 0.85-0.88
# - Missing quiet speech → decrease threshold to 0.75-0.78
# - Feel unresponsive → decrease silence_ms to 550-600
```

## תמיכה והבהרות

אם יש צורך לכוונן יותר:
- להגביר threshold (0.85-0.88) → פחות רגיש (אבל יותר קשה לדבר)
- להוריד threshold (0.75-0.78) → יותר רגיש (אבל יותר רעש)
- להגביר silence_duration_ms → פחות חיתוכים (אבל יותר לאט)
- להגביר barge_in_frames (5) → פחות false barge-in (אבל יותר לאט)

כרגע הערכים הם **מאוזנים** בין רגישות, יציבות ומהירות.

**חשוב**: בדקו בשיחות אמיתיות וכווננו לפי הנתונים מהשטח!
