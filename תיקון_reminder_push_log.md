# תיקון שגיאות reminder_push_log ו-WebPush 410

## הבעיות שתוקנו

### 1. שגיאה: "relation reminder_push_log does not exist"

**הסיבה**: ה-scheduler ניסה למחוק רשומות מטבלה בשם `reminder_push_log`, אבל הטבלה לא קיימת בדאטהבייס כי לא הייתה מיגרציה שיצרה אותה.

**התיקון**:
- ✅ נוספה Migration 66 ב-`server/db_migrate.py` שיוצרת את הטבלה
- ✅ נוספו guards ב-scheduler כדי שלא יקרוס אם הטבלה לא קיימת

### 2. שגיאה: "WebPush failed: 410 Gone"

**הסיבה**: מנוי פוש פג תוקף (המשתמש ביטל הרשאות, החליף דפדפן, או המכשיר מחק את ה-subscription).

**התיקון**:
- ✅ כבר מיושם נכון - הקוד מסמן את ה-subscription כ-`is_active = false` כשמקבל 410/404
- ✅ לא נדרשו שינויים

## מה שונה

### 1. Migration 66 - יצירת טבלת reminder_push_log

נוספה מיגרציה חדשה שיוצרת את הטבלה:

```sql
CREATE TABLE reminder_push_log (
    id SERIAL PRIMARY KEY,
    reminder_id INTEGER NOT NULL REFERENCES lead_reminders(id) ON DELETE CASCADE,
    offset_minutes INTEGER NOT NULL,
    sent_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
)
```

**אינדקסים**:
- `idx_reminder_push_log_reminder_id` על reminder_id
- `idx_reminder_push_log_sent_at` על sent_at

**אילוץ ייחודיות**:
- `uq_reminder_push_log` על (reminder_id, offset_minutes)
- מונע שליחת אותה התראה פעמיים

### 2. Safety Guards ב-reminder_scheduler.py

נוספו בדיקות בטיחות בשתי פונקציות:

**`_cleanup_old_push_logs()`**:
```python
# בודק אם הטבלה קיימת לפני ניקוי
inspector = inspect(db.engine)
if 'reminder_push_log' not in inspector.get_table_names():
    log.debug("reminder_push_log table does not exist yet, skipping cleanup")
    return
```

**`_try_send_with_dedupe()`**:
```python
# בודק אם הטבלה קיימת לפני deduplication
inspector = inspect(db.engine)
if 'reminder_push_log' not in inspector.get_table_names():
    log.debug("reminder_push_log table does not exist yet, sending without deduplication")
    # שולח בלי deduplication (זמני במהלך מיגרציה)
    _send_reminder_push(reminder, lead, offset_minutes)
    return True
```

### 3. WebPush 410 Handling (כבר מיושם)

ב-`server/services/notifications/dispatcher.py`:
```python
# כבר קיים בקוד
if send_result.get("should_deactivate"):
    subscriptions_to_deactivate.append(sub.id)

# ...later...
PushSubscription.query.filter(
    PushSubscription.id.in_(subscriptions_to_deactivate)
).update({PushSubscription.is_active: False}, synchronize_session=False)
```

## סקריפט אימות

נוסף `verify_reminder_push_log_fix.py` שבודק:
- ✅ Migration 66 קיימת עם כל השדות והאילוצים הנדרשים
- ✅ Safety guards קיימים בשתי הפונקציות
- ✅ WebPush 410 handling מיושם נכון

הכל עובר בהצלחה ✅

## פריסה לפרודקשן

כשהקוד יפורס:
1. המיגרציה תרוץ אוטומטית ותיצור את הטבלה `reminder_push_log`
2. ה-scheduler יתחיל לעבוד מיד עם deduplication מלא
3. subscriptions לא תקפים יסומנו כ-inactive אוטומטית
4. הלוגים יהיו נקיים ללא שגיאות חוזרות

**אין צורך בהתערבות ידנית** ✅

## למה זה חשוב

### לפני התיקון:
- ❌ שגיאה "relation does not exist" כל דקה בלוגים
- ❌ מלכלך לוגים ומסתיר בעיות אחרות
- ❌ עם כמה workers זה הופך לרעש רציני

### אחרי התיקון:
- ✅ לוגים נקיים
- ✅ ה-scheduler עובד תקין
- ✅ subscriptions לא תקפים מנוטרלים אוטומטית
- ✅ מערכת יציבה יותר

## שינויים טכניים

**קבצים ששונו**:
1. `server/db_migrate.py` - נוספה Migration 66
2. `server/services/notifications/reminder_scheduler.py` - נוספו safety guards
3. `verify_reminder_push_log_fix.py` - סקריפט אימות

**סה"כ שינויים**: ~100 שורות קוד

**טסטים**: כל הבדיקות עוברות ✅
