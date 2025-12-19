# סיכום תיקון - בדיקות אבחון ל-TX Audio Silence

## מטרה

למצוא למה יש "שקט מוחלט" למרות `response.audio.delta` - TX נשאר על 1.

## 4 הבדיקות שהוספנו

### 🔍 בדיקה 1: TX Liveness Probe (פעימות לב)

**מיקום:** `_tx_loop()` בקובץ `server/media_ws_ai.py`

**מה זה עושה:**
- מדפיס פעימת לב כל שנייה
- מראה: qsize, is_ai_speaking, active_response_id, frames_sent

**דוגמה ללוג:**
```
[TX_HEARTBEAT] alive=True, qsize=0, is_ai_speaking=True, active_response_id=resp_abc123, frames_sent=42
```

**איך לאבחן:**
- ✅ יש פעימות לב בזמן שקט → TX loop חי (לא קרס)
- ❌ אין פעימות לב → TX thread מת

---

### 🚨 בדיקה 2: TX Crash Probe (תפיסת קריסות)

**מיקום:** `_tx_loop()` עטוף ב-try/except

**מה זה עושה:**
- תופס כל Exception ב-TX loop
- מדפיס `[TX_CRASH]` עם traceback מלא

**דוגמה ללוג:**
```
[TX_CRASH] TX loop crashed with exception:
Traceback (most recent call last):
  File "server/media_ws_ai.py", line 11720, in _tx_loop
    ...
[TX_CRASH] Exception type: ValueError
```

**איך לאבחן:**
- ✅ אין TX_CRASH → לא קרס
- ❌ יש TX_CRASH → ראה traceback למציאת הבאג

---

### ⏱️ בדיקה 3: Send Blocking Probe (חסימת שליחה)

**מיקום:** סביב כל קריאה ל-`_ws_send()`

**מה זה עושה:**
- מודד זמן של כל `ws.send()`
- לוג אם >50ms
- stacktrace של כל threads אם >500ms (פעם אחת)

**דוגמה ללוג:**
```
[TX_SEND_SLOW] type=media, send_ms=127.3, qsize=45
```

או במקרה חמור:
```
[TX_SEND_SLOW] CRITICAL: send blocked for 1523ms! Dumping all thread stacks:
  Thread: MainThread (id=139876543210)
  ...
```

**איך לאבחן:**
- ✅ אין TX_SEND_SLOW → ws.send מהיר
- ❌ יש TX_SEND_SLOW → WebSocket חוסם את TX loop

---

### 📥 בדיקה 4: Queue Flow Probe (קצב הכנסה לתור)

**מיקום:** 
- צד הכנסה: איפה שקוראים `realtime_audio_out_queue.put_nowait()`
- צד הוצאה: `_realtime_audio_out_loop()`

**מה זה עושה:**
- ספירת frames שנכנסים לתור בשנייה
- לוג כל שנייה עם גודל תור

**דוגמה ללוג:**
```
[ENQ_RATE] frames_enqueued_per_sec=50, qsize=12
```

**איך לאבחן:**
- ✅ ENQ_RATE > 0 בזמן שקט → אודיו נכנס לתור (הבעיה downstream)
- ❌ ENQ_RATE = 0 למרות delta → הבעיה ב-bridge (לא מכניס לתור)

---

## איך לאבחן במקרה של שקט

### שלב 1: בדוק אם TX חי
```bash
grep "TX_HEARTBEAT" logs.txt
```
- יש פעימות? → TX חי, עבור לשלב 2
- אין פעימות? → TX מת, בדוק שלב 4

### שלב 2: בדוק קצב הכנסה לתור
```bash
grep "ENQ_RATE" logs.txt | tail -20
```
- frames_enqueued_per_sec > 0? → אודיו נכנס, עבור לשלב 3
- frames_enqueued_per_sec = 0? → **זה הבאג** - bridge לא מכניס

### שלב 3: בדוק חסימת send
```bash
grep "TX_SEND_SLOW" logs.txt
```
- יש TX_SEND_SLOW? → **זה הבאג** - ws.send חוסם
- אין? → בדוק qsize ב-heartbeat

### שלב 4: בדוק קריסה
```bash
grep "TX_CRASH" logs.txt
```
- יש TX_CRASH? → **זה הבאג** - ראה traceback

---

## מה להכין לדיווח

אחרי שיחה עם הבעיה:

1. **30 שורות לוג** מסביב לאירוע
2. **שורת מסקנה אחת:**
   - "TX crashed: [exception]"
   - "ws.send blocked: [ms]"
   - "Audio not enqueued despite delta"
3. **מיקום בקוד** (מספר שורה)

דוגמה:
```
Call SID: CA123abc
בעיה: Audio not enqueued despite delta events
מיקום: server/media_ws_ai.py שורה 3928 (pre-user guard)
ראיה: ENQ_RATE=0 בזמן שמגיעים chunks מ-OpenAI

לוגים:
[ENQ_RATE] frames_enqueued_per_sec=0, qsize=0
[AI_TALK] Audio chunk from OpenAI: chunk#1, bytes=160
[GUARD] Blocking AI audio response...
```

---

## התחייבות למינימום שינויים

✅ רק לוגים לאבחון - בלי שינויי לוגיקה  
✅ בלי פיצ'רים חדשים  
✅ בלי ריפקטור  
✅ משתמש ב-`_orig_print()` כדי לעקוף DEBUG mode  
✅ דטרמיניסטי - תמיד לוג, בלי דגימה  

הבדיקות יעזרו למצוא את הנקודה המדויקת של הכשל בלי לשנות התנהגות.

---

## קבצי תיעוד

- **TX_DIAGNOSTIC_PROBES.md** - פירוט הבדיקות, תבניות לוג, זרימת אבחון (אנגלית)
- **TX_PROBE_TESTING_GUIDE.md** - מדריך בדיקה, דוגמאות, פורמט דיווח (אנגלית)
- **TX_PROBE_SUMMARY_HE.md** - הקובץ הזה (עברית)

---

## הצלחה מובטחת

הבדיקות מכריחות את הבאג "להודות" איפה הוא:
1. TX loop מת? → TX_CRASH
2. ws.send חוסם? → TX_SEND_SLOW  
3. לא מכניסים לתור? → ENQ_RATE=0

**אחת מהשלוש תהיה התשובה. מובטח.**
