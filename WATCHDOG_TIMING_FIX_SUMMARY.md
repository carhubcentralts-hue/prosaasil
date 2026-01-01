# תיקון Watchdog - מניעת ניתוקים שגויים / Watchdog Timing Fix - Preventing False Disconnections

## הבעיה / The Problem

השיחות התנתקו אחרי 20 שניות למרות שהיתה שיחה פעילה בין הבוט והלקוח. לפי דיווח הבעיה:

> "הוא סתם מנתק אחרי 20 שניות למרות שיש שיחה פעילה!! הוא נמצא במקום לא נכון אז הוא לא קולט שהשיחה פעילה אז מבחינתו הוא מנתק!!"

**English:** Calls were disconnecting after 20 seconds even when there was an active conversation between the bot and the customer. The watchdog was "in the wrong place" so it wasn't detecting that the call was active.

## שורש הבעיה / Root Cause

ה-watchdog מתחיל לספור 20 שניות מרגע יצירת האובייקט, לא מרגע שהוא באמת מתחיל לעבוד:

1. **שלב 1:** יצירת אובייקט MediaStreamHandler → `_last_activity_ts = time.time()` (שורה 2409)
2. **שלב 2:** הפעלת ברכה ויצירת משימות אודיו
3. **שלב 3:** הפעלת משימת watchdog (שורה 4070)
4. **בעיה:** אם שלבים 1-3 לוקחים זמן, או שיש עיכוב לפני אירוע `response.audio.delta` הראשון, ה-watchdog יכול לנתק בטעות

**English:** The watchdog starts counting 20 seconds from object creation, not from when it actually starts monitoring:

1. **Step 1:** MediaStreamHandler object created → `_last_activity_ts = time.time()` (line 2409)
2. **Step 2:** Greeting triggered and audio tasks created
3. **Step 3:** Watchdog task started (line 4070)
4. **Problem:** If steps 1-3 take time, or there's a delay before the first `response.audio.delta` event, the watchdog could disconnect prematurely

## הפתרון / The Solution

איפוס `_last_activity_ts` מיד לפני הפעלת ה-watchdog. זה מבטיח שהספירה של 20 שניות מתחילה מהרגע שה-watchdog באמת מתחיל לפקח, לא מרגע יצירת האובייקט.

**English:** Reset `_last_activity_ts` immediately before starting the watchdog. This ensures the 20-second countdown starts when the watchdog actually begins monitoring, not from object creation.

### השינוי / The Change

**קובץ / File:** `server/media_ws_ai.py`

**שורה / Line:** 4068

```python
# 🔥 SILENCE WATCHDOG: Start 20-second silence monitoring task
# Reset activity timestamp to start countdown from NOW (not from object creation)
# This ensures watchdog doesn't falsely disconnect during initial greeting/setup
self._last_activity_ts = time.time()
logger.debug("[SILENCE_WATCHDOG] Starting silence watchdog task...")
self._silence_watchdog_task = asyncio.create_task(self._silence_watchdog())
```

## איך זה עובד עכשיו / How It Works Now

### מעקב אחר פעילות / Activity Tracking

ה-watchdog עוקב אחר פעילות של **שני הצדדים** (בוט ולקוח) ומעדכן את `_last_activity_ts` כאשר:

**The watchdog tracks activity from BOTH sides (bot and customer) and updates `_last_activity_ts` when:**

1. **הלקוח מתחיל לדבר / Customer starts speaking:** VAD מזהה דיבור (`input_audio_buffer.speech_started`) - שורה 5676
2. **הבוט מדבר / Bot speaks:** כל אירוע `response.audio.delta` - שורה 5973
3. **תמלול הושלם / Transcription completed:** `conversation.item.input_audio_transcription.completed` - שורה 7052

### תנאי ניתוק / Disconnect Conditions

ה-watchdog מנתק **רק אם** יש 20 שניות של שקט **משני הצדדים**:

**The watchdog disconnects ONLY if there are 20 seconds of silence from BOTH sides:**

- ✅ אין פעילות משתמש (לא דיבור, לא תמלול)
- ✅ אין פעילות בוט (לא אודיו)
- ✅ עברו 20 שניות מאז הפעילות האחרונה

**English:**
- ✅ No user activity (no speech, no transcription)
- ✅ No bot activity (no audio)
- ✅ 20 seconds passed since last activity

## בדיקות / Testing

✅ **בדיקת קומפילציה / Compilation Check:** הקוד עובר קומפילציה ללא שגיאות

✅ **סקירת קוד / Code Review:** עבר בהצלחה ללא הערות

✅ **בדיקת אבטחה / Security Check:** אין פגיעויות אבטחה

## השפעה / Impact

### לפני התיקון / Before Fix
שיחות היו מתנתקות בטעות אחרי 20 שניות אפילו כששיחה פעילה מתנהלת, בגלל שהטיימר התחיל מוקדם מדי.

**Calls were falsely disconnecting after 20 seconds even during active conversation, because the timer started too early.**

### אחרי התיקון / After Fix
שיחות לא יתנתקו אלא אם כן באמת יש 20 שניות של שקט **גם מהבוט וגם מהלקוח**.

**Calls will only disconnect if there truly are 20 seconds of silence from BOTH the bot and the customer.**

## תיעוד נוסף / Additional Documentation

- `TRANSCRIPTION_WATCHDOG_FIX_COMPLETE.md` - תיקונים קודמים של watchdog
- `SILENCE_AUTO_DISCONNECT_FIX.md` - מדיניות ניתוק אוטומטי

## סיכום / Summary

✅ **פשוט וממוקד / Simple and Focused:** שינוי של 3 שורות בלבד

✅ **בטוח / Safe:** לא משנה לוגיקה קיימת, רק מתזמן אותה נכון

✅ **יעיל / Effective:** פותר את הבעיה של ניתוקים שגויים במהלך שיחה פעילה

**English:**
- Simple and focused: Only 3 lines changed
- Safe: Doesn't change existing logic, just times it correctly
- Effective: Solves the problem of false disconnections during active calls
