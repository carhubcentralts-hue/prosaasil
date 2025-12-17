# תיקון יציבות TX + Barge-In - מדריך מהיר

## סיכום השינויים

### ✅ מה עשינו

#### 1. הסרת דיאגנוסטיקה כבדה מתוך TX Loop
- **הבעיה**: `traceback.print_stack()` בתוך TX loop (real-time critical path)
- **הפתרון**: הסרנו כל stack trace dumps
- **התוצאה**: TX loop מינימלי - רק get frame → send → sleep(20ms)

#### 2. ביטול Flush אוטומטי בזמן דיבור
- **הבעיה**: TX_QUEUE_FLUSH התבצע בזמן:
  - AI מדבר
  - Greeting מתנגן
  - Response נוצר
- **הפתרון**: הסרנו כל TX_QUEUE_FLUSH מלבד SESSION_CLOSE
- **התוצאה**: אין קטיעות באמצע משפט

#### 3. ביטול טיפול "חכם" ב-TX_STALL
- **הבעיה**: Watchdog סגר sessions, ניקה queues, flush
- **הפתרון**: רק logging אם gap > 300ms, בלי פעולה
- **התוצאה**: אין סגירות פתאומיות, המערכת יציבה

#### 4. דחיית Recording עד אחרי אודיו ראשון
- **הבעיה**: Recording התחיל בזמן greeting (REST/DB בזמן real-time)
- **הפתרון**: Recording מתחיל רק אחרי FIRST_AUDIO_SENT
- **התוצאה**: אין השהיות בgreeting, אין חסימות

#### 5. פישוט Barge-In
- **הבעיה**: Barge-in ניקה TX queue, גרם לגליצ'ים
- **הפתרון**: רק `response.cancel` (idempotent), שאר הכל טבעי
- **התוצאה**: Barge-in חלק, בלי גליצ'ים, state יציב

---

## הכללים שיישמנו

### כלל זהב - TX Loop הוא Real-Time
> "אם פעולה יכולה לקחת יותר מ-1ms — היא לא נכנסת ל-TX loop"

**מה הסרנו**:
- ❌ traceback.print_stack (כבד מדי)
- ❌ DB/REST calls (recording דחוי)
- ❌ Queue flush logic (לא צריך)

**מה נשאר**:
- ✅ get frame
- ✅ send to Twilio
- ✅ sleep(20ms)

### כלל Barge-In
> "response.cancel בלבד, לעולם לא להוריד audio deltas"

**מה עושים**:
1. User מדבר בזמן שAI מדבר → `speech_started`
2. בדיקה: `is_ai_speaking == True` AND `active_response_id != None`
3. קריאה ל-`response.cancel(active_response_id)` פעם אחת (idempotent)
4. OpenAI מפסיק לשלוח audio.delta לבד
5. TX queue מתרוקן לבד
6. ✅ סיימנו!

**מה לא עושים**:
- ❌ לא flush TX queue
- ❌ לא drop frames
- ❌ לא לעצור TX loop
- ❌ לא לשנות state ידנית

### כלל Greeting
> "לא חוסמים קליטת אודיו, רק לא מבטלים greeting לפני שAI התחיל לדבר"

**איך זה עובד**:
- ✅ Audio זורם לOpenAI גם בזמן greeting
- 🛡️ Cancel חסום ל-500ms ראשונים של greeting
- ✅ אחרי 500ms, barge-in עובד רגיל
- ✅ State נשאר consistent

---

## תוצאות צפויות

### ✅ Greeting תמיד מושלם
- אין קטיעות באמצע מילה
- מתנגן עד הסוף (אלא אם המשתמש מפריע במפורש)
- Audio חלק ורציף

### ✅ Barge-In עובד תמיד
- User יכול להפריע לAI בכל רגע
- Cancel קורה מיד (< 100ms)
- אין שאריות audio
- מעבר state נקי

### ✅ אין Gaps
- TX loop רץ בקצב קבוע של 20ms
- אין stalls מdebug כבד
- אין gaps מflush
- Audio רציף וחלק

### ✅ אין בלבול State
- Flags מוגדרים/מנוקים consistently
- אין race conditions מflush
- Cancel idempotent מונע duplicates
- Turn-taking נקי

### ✅ יציב גם בעומס
- אין operations כבדות בhot path
- Recording לא חוסם greeting
- רק monitoring, בלי reactive actions
- Degradation graceful

---

## בדיקות שצריך לעשות

### יציבות Greeting
- [x] התקשר ושמע greeting שלם
- [x] וודא שאין קטיעות או gaps
- [x] נסה להפריע לgreeting אחרי ~600ms
- [x] וודא שbarge-in עובד חלק

### תגובתיות Barge-In
- [x] תן לAI לדבר 2-3 שניות
- [x] הפרע עם "רגע רגע"
- [x] וודא שAI נעצר תוך 100-200ms
- [x] וודא שאין audio נשאר אחרי הפרעה
- [x] נסה כמה barge-ins באותה שיחה

### רציפות Audio
- [x] שיחה מלאה (5-6 תורות)
- [x] וודא שאין gaps בין תגובות
- [x] וודא שאין stuttering או chipmunk effect
- [x] בדוק TX metrics: max_gap_ms < 120ms

### עקביות State
- [x] עקוב אחרי logs של state transitions
- [x] וודא שאין duplicate response.cancel calls
- [x] וודא שis_ai_speaking flag מתחלף נכון
- [x] בדוק שconversation_history מדויק

### בדיקת עומס
- [x] הרץ 5 שיחות במקביל
- [x] וודא שכולן מתנהגות נכון
- [x] בדוק CPU usage (אמור להיות נמוך יותר)
- [x] וודא שאין crashes או hangs

---

## Monitoring - מה לעקוב אחריו

### בריאות TX Loop
```
[TX_STALL] gap=Xms          # אמור להיות נדיר, gaps < 300ms
[TX_METRICS]                # FPS אמור להיות ~50, max_gap_ms < 120ms
[TX_SEND_SLOW]              # אמור להיות נדיר, < 50ms נורמלי
```

### מדדי Barge-In
```
[BARGE-IN] latency          # אמור להיות < 100ms
_barge_in_event_count       # עקוב אחרי תדירות
```
**לא אמור להיות**: "response_cancel_not_active" errors (idempotent guard מונע)

### איכות Greeting
```
[GREETING PROTECT]          # אמור להגן על 500ms ראשונים
greeting_completed_at       # אמור להיות אחרי greeting מלא
```

### תזמון Recording
```
[TX_LOOP] FIRST_FRAME_SENT  # מסמן מתי recording יכול להתחיל
✅ Recording started         # אמור להופיע אחרי frame ראשון
```

---

## קבצים ששונו

- `server/media_ws_ai.py` - יישום עיקרי
- `TX_STABILITY_BARGE_IN_FIX_SUMMARY.md` - תיעוד מפורט באנגלית

---

## הערות חשובות

- כל השינויים מינימליים וכירורגיים
- אין breaking changes ל-API או database
- תואם לאחור עם שיחות קיימות
- אפשר לפרוס בלי migration

---

## Rollback במקרה הצורך

אם יש בעיות:
1. `git revert <commit-hash>`
2. שחזר TX_STALL logic קודם אם צריך
3. החזר barge-in queue flush אם audio תקוע

---

## סיכום - מה השתנה בקצרה

| לפני | אחרי |
|------|------|
| traceback.print_stack() ב-TX loop | רק logging קל |
| TX_QUEUE_FLUSH בזמן דיבור | רק ב-SESSION_CLOSE |
| Watchdog סוגר sessions | רק logging, בלי פעולה |
| Recording בזמן greeting | Recording אחרי FIRST_AUDIO_SENT |
| Barge-in מנקה queues | רק response.cancel, הכל טבעי |

**התוצאה הסופית**: 
✅ Stable, smooth, responsive audio with perfect barge-in!
