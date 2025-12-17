# הרצת מיגרציות - תיקון כפילות שיחות

## ✅ המיגרציות כבר ב-db_migrate.py

המיגרציות כבר קיימות בקובץ `server/db_migrate.py`:
- **Migration 41a**: הוספת `parent_call_sid` ל-call_log
- **Migration 41b**: הוספת `twilio_direction` ל-call_log

## 🚀 איך להריץ?

### אופציה 1: אוטומטי בהפעלת שרת (מומלץ ✅)

הוסף למשתנה סביבה:
```bash
export RUN_MIGRATIONS_ON_START=1
python3 run_server.py
```

או בקובץ `.env`:
```
RUN_MIGRATIONS_ON_START=1
```

המיגרציות ירוצו **אוטומטית** בפעם הראשונה שהשרת יעלה!

### אופציה 2: הרצה ידנית

```bash
python3 run_call_fix_migration.py
```

### אופציה 3: דרך מודול מיגרציה

```bash
python3 -m server.db_migrate
```

### אופציה 4: דרך API endpoint

אחרי שהשרת רץ:
```bash
curl -X POST http://localhost:5000/api/admin/run-migrations
```

## ✅ בדיקה שהמיגרציה רצה

```sql
-- בדוק שהשדות נוספו
SELECT column_name 
FROM information_schema.columns 
WHERE table_name = 'call_log' 
  AND column_name IN ('parent_call_sid', 'twilio_direction');

-- צפוי לראות:
-- parent_call_sid
-- twilio_direction
```

## 📊 מה המיגרציות עושות?

### Migration 41a: parent_call_sid
```sql
ALTER TABLE call_log ADD COLUMN parent_call_sid VARCHAR(64);
CREATE INDEX idx_call_log_parent_call_sid ON call_log(parent_call_sid);
```

**מטרה**: מעקב אחרי קשרי הורה-ילד בשיחות Twilio (parent call + child leg).

### Migration 41b: twilio_direction
```sql
ALTER TABLE call_log ADD COLUMN twilio_direction VARCHAR(32);
CREATE INDEX idx_call_log_twilio_direction ON call_log(twilio_direction);
```

**מטרה**: שמירת הערך המקורי של Direction מ-Twilio (outbound-api, outbound-dial, וכו').

## 🔧 מה אם המיגרציה נכשלת?

אם המיגרציה נכשלת, היא לא תשבור כלום:
- הקוד בודק אם השדות כבר קיימים
- אם כן - מדלג על המיגרציה
- אם לא - מוסיף אותם

זה **idempotent** - בטוח להריץ כמה פעמים.

## 🎯 סיכום

✅ המיגרציות **כבר בקוד** - לא צריך להוסיף כלום  
✅ הן **ירוצו אוטומטית** בהפעלת השרת (אם `RUN_MIGRATIONS_ON_START=1`)  
✅ בטוח להריץ **כמה פעמים** (idempotent)  
✅ לא **משבר כלום** אם נכשל  

**פשוט הפעל את השרת והמיגרציות ירוצו מאליהן!**
