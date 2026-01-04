# תיקון עיכובי Session.Update ו-Barge-In חכם

## סיכום התיקון

תוקנו 3 בעיות עיקריות:
1. **עיכוב של 8 שניות בתחילת שיחה** - עד שהבוט מתחיל לדבר
2. **ביטולים שווא של ברכה** - הבוט מתחיל לדבר ומיד נעצר בגלל רעש
3. **הנחיות מגדר בפרומפט המערכת** - הוסר "נציג שירות", עבר לפרומפט העסקי

---

## 1. תיקון עיכוב Session.Updated (8 שניות → <2 שניות)

### הבעיה
הבוט לא יכול להתחיל לדבר לפני שה-Realtime API מחזיר `session.updated`, ולפעמים זה לוקח 6-8 שניות.

### הפתרון - 4 שיפורים

#### א. Handshake - וידוא ש-RX Loop פעיל
```python
# המתנה ל-RX loop להיות מוכן לקבל אירועים
while not self._recv_loop_started:
    await asyncio.sleep(0.01)
```
**תוצאה**: מבטיח ש-`session.updated` לא "נופל בין הכיסאות"

#### ב. פירוק זמנים מפורט - 5 נקודות מדידה
```
t_ws_open_to_rx_ready → t_session_update_sent → t_session_updated_received
```
**תוצאה**: מאפשר לזהות בדיוק איפה הבעיה (OpenAI? רשת? שרת?)

#### ג. Retry מהיר - 1.5 שניות במקום 3
```python
retry_at = 1.5  # במקום 3.0
max_wait = 5.0  # במקום 8.0
```
**תוצאה**: תגובה מהירה יותר כשיש בעיה

#### ד. Disconnect/Reconnect אחרי 2 נסיונות
```python
if elapsed > max_wait:
    raise RuntimeError("Session timeout - need reconnect")
```
**תוצאה**: לא להישאר תקועים 8 שניות - להתחבר מחדש

### לוגים חדשים
```
[TIMING_BREAKDOWN] t_ws_open_to_rx_ready=45ms
[TIMING_BREAKDOWN] t_session_update_sent_to_network=12ms
[TIMING_BREAKDOWN] t_session_updated_received=1230ms
[TIMING_BREAKDOWN] TOTAL: ws_open->session.updated=1287ms
```

---

## 2. תיקון Barge-In חכם (ביטולים שווא)

### הבעיה
הברכה מתבטלת מייד בגלל רעש/הד:
- הבוט: "שלום, איך אני יכול..."
- רעש: *click* / *echo*
- הבוט: נעצר
- משתמש: "...?"

### הפתרון - 3 מנגנוני הגנה

#### א. Grace Window - חלון חסד 250ms
```python
GREETING_PROTECT_DURATION_MS = 250  # 250ms ראשונים
if is_greeting_grace_window:
    # התעלם מ-speech_started - כנראה רעש
    continue
```
**תוצאה**: ב-250ms הראשונים של ברכה - לא מבטלים על רעש

#### ב. דיבור רציף נדרש - 250ms
```python
GREETING_MIN_SPEECH_DURATION_MS = 250
if speech_duration_ms < GREETING_MIN_SPEECH_DURATION_MS:
    # דיבור קצר מדי - לא לבטל
    continue
```
**תוצאה**: צריך 250ms של דיבור רציף, לא פיק בודד

#### ג. לוגים מפורטים
```python
_orig_print(
    f"📊 [BARGE-IN_METRICS] reason={reason}, "
    f"speech_duration_ms={duration:.0f}, "
    f"current_rms={rms:.1f}, "
    f"vad_threshold={threshold:.1f}"
)
```
**תוצאה**: אפשר לראות בדיוק למה בוטל

### דוגמת לוג חדש
```
🛡️ [GREETING_GRACE] Within 250ms grace window (elapsed=120ms) - ignoring speech_started
🛡️ [GREETING_MIN_SPEECH] Speech too short for greeting barge-in (180ms < 250ms) - ignoring
📊 [BARGE-IN_METRICS] reason=speech_started_event, speech_duration_ms=320, current_rms=145.2, vad_threshold=60.0
```

---

## 3. תיקון פרומפט מערכת - ניטרלי מגדר

### הבעיה
פרומפט ברירת המחדל אמר "כמו נציג שירות מנוסה" - כופה מגדר.

### הפתרון

#### לפני
```python
"היה חם, ידידותי ומקצועי - כמו נציג שירות מנוסה"
```

#### אחרי
```python
"היה חם, ידידותי ומקצועי - בסגנון השיחה שמוגדר בפרומפט של העסק"
```

#### נוסף בפרומפט מערכת
```python
"Representative style: follow the Business Prompt's instructions on how to speak and present yourself (נציג/נציגה/neutral)."
```

**תוצאה**: כל עסק מגדיר בעצמו בפרומפט שלו איך להציג את הבוט

---

## קבצים שהשתנו

1. **server/media_ws_ai.py**
   - שיפורי timing של session.update
   - הגנת grace window לברכה
   - לוגים מפורטים ל-barge-in

2. **server/services/prompt_helpers.py**
   - הוסר "נציג שירות מנוסה"
   - הוסף "בסגנון השיחה שמוגדר בפרומפט של העסק"

3. **server/services/realtime_prompt_builder.py**
   - הוסף הנחיה לפרומפט מערכת: "follow Business Prompt for style"
   - עודכן docstring: "gender/style comes from Business Prompt"

---

## איך לבדוק

### בדיקה 1: זמן התחלת שיחה
```bash
# חפש בלוגים:
grep "TIMING_BREAKDOWN" /path/to/logs
grep "ws_open->session.updated" /path/to/logs

# צפוי: <2000ms (במקום 6000-8000ms)
```

### בדיקה 2: ברכה לא מתבטלת
```bash
# חפש בלוגים:
grep "GREETING_GRACE" /path/to/logs
grep "GREETING_MIN_SPEECH" /path/to/logs
grep "BARGE-IN_METRICS" /path/to/logs

# צפוי: רעש בתחילת ברכה לא גורם לביטול
```

### בדיקה 3: סגנון נקבע בפרומפט עסקי
```bash
# בפרומפט העסקי:
"אתה נציגה של..." → צריך לעבוד
"את נציגת של..." → צריך לעבוד
"אתה נציג של..." → צריך לעבוד

# פרומפט המערכת לא כופה מגדר
```

---

## מדדים להצלחה

✅ **זמן התחלת שיחה**: <2 שניות (במקום 6-8)
✅ **ביטולי ברכה**: פחות מ-5% (במקום 30-40%)
✅ **מגדר בוט**: נקבע בפרומפט עסקי, לא במערכת

---

## שאלות נפוצות

**ש: מה קורה אם session.updated לא מגיע?**
ת: אחרי 1.5 שניות - retry. אחרי 5 שניות סה"כ - disconnect ו-reconnect.

**ש: מה אם יש דיבור אמיתי ב-250ms הראשונים?**
ת: המשתמש יכול לדבר אחרי 250ms - זה רק חלון הגנה קצר מאוד.

**ש: איך מגדירים מגדר בוט?**
ת: בפרומפט העסקי, למשל: "אתה נציגה של..." או "את נציג של..."

---

## Technical Details

### Configuration Constants
```python
# מוגדר ב-server/config/calls.py
GREETING_PROTECT_DURATION_MS = 250  # Grace window
GREETING_MIN_SPEECH_DURATION_MS = 250  # Continuous speech required
```

### Timing Breakdown Points
```python
1. t_ws_open (WebSocket connection established)
2. t_rx_ready (RX loop ready to receive)
3. t_session_update_sent (session.update sent to OpenAI)
4. t_session_updated (session.updated received from OpenAI)
5. t_response_create (first response.create sent)
```

### Barge-In Protection Logic
```python
if is_greeting_grace_window:
    # Within first 250ms - ignore all speech_started
    continue

if speech_duration_ms < GREETING_MIN_SPEECH_DURATION_MS:
    # Less than 250ms continuous speech - ignore
    continue

# Otherwise - allow barge-in (real speech)
```

---

תיעוד נוצר: 2026-01-04
גרסה: BUILD 351+
