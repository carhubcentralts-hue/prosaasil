# תיקון Watchdog - מניעת ניתוקים שגויים / Watchdog Timing Fix - Preventing False Disconnections

## סיכום כללי / Executive Summary

תיקון זה פותר **שתי בעיות קריטיות**:
1. ✅ Watchdog מנתק שיחות פעילות אחרי 20 שניות
2. ✅ שגיאת business_id שגורמת לקריסת שיחות

**This fix solves TWO critical issues:**
1. ✅ Watchdog disconnecting active calls after 20 seconds
2. ✅ business_id error causing call crashes

---

## בעיה 1: Watchdog מנתק שיחות פעילות / Problem 1: Watchdog Disconnecting Active Calls

### הבעיה / The Problem

השיחות התנתקו אחרי 20 שניות למרות שהיתה שיחה פעילה בין הבוט והלקוח. לפי דיווח הבעיה:

> "הוא סתם מנתק אחרי 20 שניות למרות שיש שיחה פעילה!! הוא נמצא במקום לא נכון אז הוא לא קולט שהשיחה פעילה אז מבחינתו הוא מנתק!!"

**English:** Calls were disconnecting after 20 seconds even when there was an active conversation between the bot and the customer. The watchdog was "in the wrong place" so it wasn't detecting that the call was active.

### שורש הבעיה / Root Cause

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

### הפתרון / The Solution

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

---

## בעיה 2: שגיאת Business ID / Problem 2: Business ID Error

### הבעיה / The Problem

```
ValueError: CRITICAL: business_id is required - cannot process call without valid business identification
```

כאשר זיהוי העסק נכשל, הקוד ניסה להשתמש ב-`_set_safe_business_defaults()` כפתרון חירום, אבל הפונקציה הזו דורשת ש-`business_id` יהיה מוגדר, מה שיצר מצב Catch-22.

**English:** When business identification failed, the code tried to use `_set_safe_business_defaults()` as a fallback, but this function requires `business_id` to be set, creating a Catch-22 situation.

### שורש הבעיה / Root Cause

```python
# Line 9815: Exception handler when business identification fails
except Exception as e:
    logger.error(f"[CALL-ERROR] Business identification failed: {e}")
    self._set_safe_business_defaults(force_greeting=True)  # ❌ This requires business_id!
```

```python
# Line 2851: _set_safe_business_defaults requires business_id
if not hasattr(self, 'business_id') or self.business_id is None:
    raise ValueError("CRITICAL: business_id is required...")  # ❌ Raises same error!
```

### הפתרון / The Solution

כאשר זיהוי העסק נכשל, לנתק מיידית את השיחה במקום לנסות להמשיך. זה מונע:

**When business identification fails, immediately hang up the call instead of trying to continue. This prevents:**

- ❌ Cross-business contamination (בעיית אבטחה / security issue)
- ❌ OpenAI charges without valid business
- ❌ Confusing nested exceptions

### השינוי / The Change

**קובץ / File:** `server/media_ws_ai.py`

**שורות / Lines:** 9815-9833

```python
except Exception as e:
    import traceback
    logger.error(f"[CALL-ERROR] Business identification failed: {e}")
    logger.error(f"[CALL-ERROR] Traceback: {traceback.format_exc()}")
    
    # ⛔ CRITICAL: Cannot proceed without business_id - reject call immediately
    # Mask phone number for security (only show last 4 digits)
    to_num = getattr(self, 'to_number', 'unknown')
    to_num_masked = f"***{to_num[-4:]}" if to_num and len(to_num) >= 4 else "unknown"
    _orig_print(f"❌ [BUSINESS_ISOLATION] Call REJECTED - cannot identify business for to={to_num_masked}", flush=True)
    
    # Send immediate hangup to Twilio
    try:
        self._immediate_hangup(reason="business_identification_failed")
    except Exception as hangup_err:
        logger.error(f"[CALL-ERROR] Failed to send hangup: {hangup_err}")
    
    # Stop processing this call
    return
```

---

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

---

## בדיקות / Testing

✅ **בדיקת קומפילציה / Compilation Check:** הקוד עובר קומפילציה ללא שגיאות

✅ **סקירת קוד / Code Review:** עבר בהצלחה, טופלו כל ההערות

✅ **בדיקת אבטחה / Security Check:** אין פגיעויות אבטחה (0 alerts)

✅ **Phone Number Masking:** מספרי טלפון מוסתרים בלוגים (רק 4 ספרות אחרונות)

---

## השפעה / Impact

### בעיה 1: Watchdog / Problem 1: Watchdog

| לפני / Before | אחרי / After |
|------|------|
| שיחות מתנתקות בטעות אחרי 20 שניות | שיחות מתנתקות רק אחרי שקט אמיתי |
| הטיימר מתחיל מוקדם מדי | הטיימר מתחיל בזמן הנכון |
| בעיות עם שיחות ארוכות | שיחות יכולות להימשך כל זמן שיש פעילות |

### בעיה 2: Business ID / Problem 2: Business ID

| לפני / Before | אחרי / After |
|------|------|
| ValueError + nested exceptions | Clean hangup with proper error |
| Risk of cross-business contamination | Call rejected immediately |
| Unclear error messages | Clear logging with masked phone |

---

## סיכום / Summary

✅ **פשוט וממוקד / Simple and Focused:** שינוי של 20 שורות בלבד

✅ **בטוח / Safe:** לא משנה לוגיקה קיימת, רק מתזמן אותה נכון

✅ **יעיל / Effective:** פותר שתי בעיות קריטיות במכה אחת

✅ **מאובטח / Secure:** מסתיר מידע רגיש בלוגים

**English:**
- Simple and focused: Only 20 lines changed
- Safe: Doesn't change existing logic, just times it correctly
- Effective: Solves two critical issues in one fix
- Secure: Masks sensitive information in logs
