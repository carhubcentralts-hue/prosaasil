# ✅ Checklist QA - Receipt Sync + Push Notifications Fix
# ═══════════════════════════════════════════════════════════════

## 🔧 לפני Deploy (Development/Staging)

### 1. בדיקת Migration
```bash
# הרצת migrations במצב test
MIGRATION_MODE=1 python -c "from server.db_migrate import apply_migrations; apply_migrations()"
```

**תוצאה מצופה:**
- ✅ "Migration 89 complete: from_date, to_date, months_back, run_to_completion, max_seconds_per_run, skipped_count added"
- ✅ "Schema validation passed - all required columns exist"
- ❌ אם יש שגיאה - המערכת תיפול מיד עם הסבר ברור

### 2. בדיקת Schema Validation
```bash
# וידוא שהולידציה עובדת
python -c "
from server.app_factory import create_minimal_app
app = create_minimal_app()
with app.app_context():
    from server.environment_validation import validate_database_schema
    from server.db import db
    validate_database_schema(db)
"
```

**תוצאה מצופה:**
- ✅ "Database schema validation passed - all critical columns exist"
- ❌ אם חסרות עמודות - המערכת תיפול מיד

### 3. בדיקת Push Service Validation
```bash
# וידוא שהולידציה של Push עובדת
python test_push_service_validation.py
```

**תוצאה מצופה:**
- ✅ "ALL TESTS PASSED"
- ❌ אם DATABASE_URL חסר - RuntimeError מיידי

---

## 🚀 אחרי Deploy (Production)

### 1. בדיקת Startup Logs
חפש בלוגים:
```
✅ "Migration 89 complete"
✅ "Database schema validation passed"
✅ "Reminder notification scheduler started"
```

**סימני אזהרה:**
- ❌ "Missing column: receipt_sync_runs.X" → המערכת תיפול
- ❌ "DATABASE_URL is not set" → Push לא יעבוד
- ❌ "DATABASE_URL mismatch detected" → צריך restart

### 2. בדיקת Receipt Sync
```bash
# נסה לסנכרן קבלות
curl -X POST https://your-domain.com/api/receipts/sync \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"mode": "incremental"}'
```

**תוצאה מצופה:**
- ✅ {"success": true, "sync_run_id": X}
- ❌ אם יש UndefinedColumn → הבעיה לא תוקנה

### 3. בדיקת Push Notifications
1. רשום מכשיר לקבלת התראות (דרך UI)
2. צור תזכורת ל-30 דקות מעכשיו
3. חכה ל-notification

**תוצאה מצופה:**
- ✅ לוג: "Sent X reminder push notification(s)"
- ✅ התראה מגיעה למכשיר
- ❌ אם יש DNS error → בדוק DATABASE_URL
- ⚠️ אם יש 410 Gone → זה subscription מת (תקין)

---

## 🔍 Sanity Checks מהירים

### Query ישיר ל-DB
```sql
-- וידוא שהעמודות קיימות
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'receipt_sync_runs' 
AND column_name IN ('from_date', 'to_date', 'months_back', 
                    'run_to_completion', 'max_seconds_per_run', 'skipped_count');
```

**תוצאה מצופה:** 6 שורות עם כל העמודות

### בדיקת Health Endpoint
```bash
curl https://your-domain.com/health
```

**תוצאה מצופה:**
- ✅ 200 OK
- ❌ אם 500 → בדוק logs

---

## ⚠️ מה לעשות אם משהו נכשל

### אם Receipt Sync נכשל
1. בדוק logs: `grep "receipt_sync_runs" /var/log/app.log`
2. אם יש UndefinedColumn → הרץ migrations שוב
3. אם זה לא עוזר → rollback ל-commit הקודם

### אם Push לא עובד
1. בדוק logs: `grep "REMINDER_SCHEDULER\|Push" /var/log/app.log`
2. אם יש DATABASE_URL error → בדוק .env
3. אם subscription expired (410) → זה תקין, המנגנון מנטרל אותו
4. אם אין לוגים בכלל → בדוק ש-ENABLE_SCHEDULERS=true

### אם המערכת לא עולה בכלל
1. זה **תכנון מכוון** - fail-fast
2. בדוק את השגיאה המדויקת בלוגים
3. תקן את הבעיה (חסרות עמודות / DATABASE_URL)
4. לא להוסיף try/except או workarounds

---

## ✅ Success Criteria

הכל תקין אם:
- ✅ Receipt sync עובד בלי UndefinedColumn errors
- ✅ Push notifications מגיעות (או 410 אם subscription מת)
- ✅ המערכת עולה בהצלחה או נופלת עם שגיאה ברורה
- ✅ אין DNS errors בלוגים של Push services
- ✅ Validation logs מופיעים בהצלחה

---

## 📝 Notes

- לא להסיר את ה-validation גם אם הכל עובד
- לא להוסיף try/except סביב השגיאות
- אם יש בעיה חדשה - זו בעיה אמיתית אחרת, לא אותו סיפור
