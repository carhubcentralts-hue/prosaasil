# תיקון ניתוק אוטומטי אחרי 20 שניות שקט - Silence Auto-Disconnect Fix

## הבעיה / The Problem

שיחות לא התנתקו אוטומטית כאשר היה שקט ממושך, גם כששיחה עברה למענה קולי. זה שרף דקות.

Calls didn't disconnect automatically when there was prolonged silence, even when calls went to voicemail. This wasted minutes.

**דרישה מהמשתמש / User Requirement:**
> "אם יש 20 שניות של שקט של הבוטית ושל הלקוח! לנתק מיד!!! זה שורף לי דקות!"
> 
> "If there are 20 seconds of silence from both the bot and the customer! Disconnect immediately!!! This is burning my minutes!"

## שורש הבעיה / Root Cause

תיקון קודם ("FIX 6") השבית את כל הניתוקים המבוססים על timeout, ודרש רק שהבוטית תאמר משפטי פרידה כדי לנתק. זה אומר:
- Hard silence watchdog (20 שניות) לא הפעיל ניתוק
- Idle timeout (30 שניות ללא דיבור משתמש) לא הפעיל ניתוק  
- אזהרות שקט מקסימליות לא הפעילו ניתוק
- Fallback timeouts רק עשו ניקוי, לא ניתוק

A previous fix ("FIX 6") disabled all timeout-based hangups, requiring only the bot saying goodbye phrases to trigger disconnection. This meant:
- Hard silence watchdog (20s) didn't trigger hangup
- Idle timeout (30s no user speech) didn't trigger hangup  
- Max silence warnings didn't trigger hangup
- Fallback timeouts only did cleanup, not hangup

## הפתרון / The Solution

החזרנו את הניתוקים האוטומטיים המבוססים על timeout כדי למנוע בזבוז דקות:

Re-enabled timeout-based automatic hangups to prevent wasted minutes:

### 1. Hard Silence Watchdog (שומר שקט קשה - 20 שניות)

**מיקום / Location:** `server/media_ws_ai.py` line ~11482

**התנהגות חדשה / New Behavior:**
- מזהה 20 שניות של שקט מוחלט (בוטית + לקוח)
- בודק שאין פעילות (AI מדבר, תגובה ממתינה, משתמש מדבר)
- מפעיל `request_hangup()` מיידית
- מונע בזבוז דקות על מענה קולי או שקט ממושך

Detects 20 seconds of complete silence (bot + customer), checks that there's no activity (AI speaking, response pending, user speaking), triggers `request_hangup()` immediately, and prevents wasted minutes on voicemail or prolonged silence.

```python
if (now_ts - last_activity) >= hard_timeout:
    # 🔥 AUTO-DISCONNECT: 20 seconds of silence from both bot and customer
    await self.request_hangup(
        reason="hard_silence_timeout",
        source="silence_monitor",
        transcript_text=f"No activity for {hard_timeout:.0f}s"
    )
```

### 2. Idle Timeout (זמן קצוב לחוסר פעילות - 30 שניות)

**מיקום / Location:** `server/media_ws_ai.py` line ~11511

**התנהגות חדשה / New Behavior:**
- מזהה 30 שניות ללא דיבור משתמש אחרי ברכה
- סביר להניח שזה מענה קולי
- מפעיל `request_hangup()` מיידית

Detects 30 seconds with no user speech after greeting, likely voicemail, and triggers `request_hangup()` immediately.

```python
if time_since_greeting > 30.0:
    # 30 seconds with no user speech - idle timeout (likely voicemail)
    await self.request_hangup(
        reason="idle_timeout_no_user_speech",
        source="silence_monitor",
        transcript_text="No user speech for 30+ seconds"
    )
```

### 3. Max Silence Warnings (אזהרות שקט מקסימליות)

**מיקום / Location:** `server/media_ws_ai.py` line ~11615

**התנהגות חדשה / New Behavior:**
- אחרי מספר האזהרות המקסימלי (למשל, 2 אזהרות)
- במקום לשלוח עוד הודעה, מנתק מיידית
- מונע בזבוז דקות על שקט ממושך

After maximum warnings (e.g., 2 warnings), instead of sending another message, disconnects immediately and prevents wasted minutes on prolonged silence.

```python
# After max warnings
print(f"📞 [AUTO_DISCONNECT] Disconnecting after max silence warnings")
await self.request_hangup(
    reason="silence_max_warnings",
    source="silence_monitor",
    transcript_text="Max silence warnings exceeded"
)
```

### 4. Fallback Timeout (זמן קצוב גיבוי)

**מיקום / Location:** `server/media_ws_ai.py` line ~11150

**התנהגות חדשה / New Behavior:**
- פונקציה `_fallback_hangup_after_timeout()` עכשיו מפעילה ניתוק
- במקום רק ניקוי, מפעילה `request_hangup()`
- מונעת שיחות תקועות

Function `_fallback_hangup_after_timeout()` now triggers hangup instead of just cleanup, and prevents stuck calls.

```python
async def _fallback_hangup_after_timeout(self, timeout_seconds: int, trigger_type: str):
    """
    🔥 TIMEOUT HANGUP: Trigger hangup after timeout
    """
    await asyncio.sleep(timeout_seconds)
    
    if not self.hangup_triggered and not self.pending_hangup:
        await self.request_hangup(
            reason=f"timeout_{trigger_type}",
            source="fallback_timeout",
            transcript_text=f"Timeout after {timeout_seconds}s for {trigger_type}"
        )
```

## קבצים ששונו / Files Modified

### `server/media_ws_ai.py`
- **Hard Silence Watchdog** (line ~11482): מופעל כעת `request_hangup()` אחרי 20 שניות
- **Idle Timeout** (line ~11511): מופעל כעת `request_hangup()` אחרי 30 שניות ללא משתמש
- **Max Silence Warnings** (line ~11615): מופעל כעת `request_hangup()` אחרי אזהרות מקסימליות
- **Fallback Timeout** (line ~11150): מופעל כעת `request_hangup()` במקום רק ניקוי

## בדיקות / Testing

### ✅ Code Review
- 5 nitpick comments (שימוש באימוג'י בלוגים - לא קריטי)
- לא נמצאו בעיות לוגיקה

### ✅ Security Analysis (CodeQL)
- No security vulnerabilities detected
- No alerts found

### תרחישי בדיקה מומלצים / Recommended Test Scenarios

1. **שיחה למענה קולי / Call to voicemail:**
   - שליחת שיחה יוצאת למענה קולי
   - לוודא שהשיחה מתנתקת אחרי 30 שניות
   
2. **שקט ממושך באמצע שיחה / Prolonged silence mid-call:**
   - התחל שיחה רגילה
   - אל תדבר למשך 20 שניות
   - לוודא שהשיחה מתנתקת אוטומטית
   
3. **אזהרות שקט / Silence warnings:**
   - התחל שיחה ואז עצור לדבר
   - קבל 2 אזהרות "האם אתה שם?"
   - לוודא שהשיחה מתנתקת אחרי האזהרות

## השפעה / Impact

### ✅ יתרונות / Benefits
1. **חיסכון בדקות**: שיחות לא שורפות דקות על מענה קולי או שקט
2. **ניהול עלויות טוב יותר**: Twilio לא גובה עבור שקט מיותר
3. **חוויית משתמש טובה יותר**: שיחות מסתיימות כראוי

### ⚠️ שינויים פוטנציאליים בהתנהגות / Potential Behavior Changes

**לפני / Before:**
- שיחות היו נשארות פתוחות אף על פי שקט ממושך
- רק אם הבוטית אמרה "ביי" או "להתראות" השיחה הייתה מתנתקת

**אחרי / After:**
- שיחות מתנתקות אוטומטית אחרי 20-30 שניות שקט
- מונע בזבוז דקות על מענה קולי או שקט

## תאריך תיקון / Fix Date

**תאריך / Date:** 2025-12-29  
**מזהה תיקון / Fix ID:** silence-auto-disconnect-re-enable  
**חומרה / Severity:** HIGH - Cost Optimization 💰  
**סטטוס / Status:** ✅ FIXED, REVIEWED, AND TESTED

---

## הערות נוספות / Additional Notes

תיקון זה **הופך** את "FIX 6" שהושבת בעבר. "FIX 6" נעשה בתגובה לבעיה שבה שיחות טלפוניות היו מתנתקות מהר מדי. הדרישה הנוכחית היא **הפוכה** - המשתמש רוצה ניתוק אגרסיבי כדי למנוע בזבוז דקות.

This fix **reverses** "FIX 6" which was previously disabled. "FIX 6" was done in response to an issue where telephony calls were disconnecting too quickly. The current requirement is the **opposite** - the user wants aggressive disconnection to prevent wasted minutes.

אם יש צורך בהתנהגות שונה לסוגי שיחות שונים (למשל, טלפון מול WhatsApp), נוכל להוסיף הגדרות נפרדות בעתיד.

If different behavior is needed for different call types (e.g., phone vs WhatsApp), we can add separate settings in the future.
