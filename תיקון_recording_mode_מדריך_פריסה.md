# תיקון בעיית recording_mode - מדריך פריסה

## 📋 סיכום הבעיה

**שגיאה:** `PostgreSQL: column call_log.recording_mode does not exist`

### מה קרה?
הקוד/ORM מצפה לעמודה `recording_mode` בטבלת `call_log`, אבל המיגרציה לא רצה או לא נפרסה.

### איפה זה משפיע?
השגיאה פוגעת במערכות הבאות:
- ✅ `finalize_in_background` (media_ws_ai.py)
- ✅ call_status webhook
- ✅ stream_ended webhook
- ✅ REC_CB (recording callback)
- ✅ tasks.recording (offline_stt)
- ✅ כל ה-API שמביא Calls (calls_in_range, calls_last7d וכו')

---

## 🛠️ הפתרון - 3 שלבים

### שלב 1️⃣: הרצת המיגרציה

**אפשרות א': הרצה ישירה של סקריפט המיגרציה**
```bash
python migration_add_recording_mode.py
```

**אפשרות ב': הרצה דרך Flask app context**
```bash
python -m server.db_migrate
```

**אפשרות ג': הרצה דרך Python**
```python
from server.app_factory import create_minimal_app
from server.db_migrate import apply_migrations

app = create_minimal_app()
with app.app_context():
    apply_migrations()
```

### שלב 2️⃣: אימות התיקון

לאחר הרצת המיגרציה, בדוק שהעמודות נוספו:

```sql
\d+ call_log;
```

חפש את העמודות הבאות:
- ✅ `recording_mode VARCHAR(32)`
- ✅ `stream_started_at TIMESTAMP`
- ✅ `stream_ended_at TIMESTAMP`
- ✅ `stream_duration_sec DOUBLE PRECISION`
- ✅ `stream_connect_count INTEGER`
- ✅ `webhook_11205_count INTEGER`
- ✅ `webhook_retry_count INTEGER`
- ✅ `recording_count INTEGER`
- ✅ `estimated_cost_bucket VARCHAR(16)`

### שלב 3️⃣: הפעלה מחדש של השרת

```bash
# עצור את השרת הקיים
kill $(cat server.pid)  # או: pkill -f "python.*run_server"

# הפעל מחדש
python run_server.py
```

---

## 🔍 בדיקת תקינות (2 דקות)

לאחר ההפעלה מחדש, בדוק:

### 1. לוגים נקיים
```bash
tail -f logs/app.log | grep -i "recording_mode\|UndefinedColumn"
```
**צפוי:** אין שגיאות של `UndefinedColumn`

### 2. שיחה חדשה
בצע שיחה אחת ווודא:
- ✅ אין שגיאות `UndefinedColumn recording_mode`
- ✅ דף שיחות אחרונות נטען בהצלחה
- ✅ REC_CB שומר את recording_url
- ✅ OFFLINE_STT מצליח למשוך הקלטה

### 3. API Endpoints
בדוק endpoints:
```bash
# שיחות אחרונות
curl http://localhost:5000/api/calls/last7d

# טווח שיחות
curl http://localhost:5000/api/calls/range?start=2025-01-01&end=2025-12-31
```

---

## 🔒 הקשחת Deploy (למנוע תקלות עתידיות)

### שלב א': הוספת בדיקת Startup

הקוד כבר כולל בדיקת startup אוטומטית ב-`server/environment_validation.py`:
- בודק שכל העמודות הקריטיות קיימות
- נכשל ב-boot אם חסרות עמודות → מונע "חצי עובד"
- מציג הודעת שגיאה ברורה עם הוראות תיקון

### שלב ב': CI/CD Pipeline

הוסף לסקריפט ה-Deploy:

```bash
#!/bin/bash
# deploy.sh

echo "🔄 Running database migrations..."
python -m server.db_migrate

if [ $? -ne 0 ]; then
    echo "❌ Migrations failed - aborting deploy"
    exit 1
fi

echo "✅ Migrations completed successfully"
echo "🚀 Starting application..."
python run_server.py
```

### שלב ג': בדיקה בהרצת CI

הוסף ל-`.github/workflows/deploy.yml`:

```yaml
- name: Run Database Migrations
  run: |
    python -m server.db_migrate
    
- name: Validate Database Schema
  run: |
    python -c "from server.environment_validation import validate_database_schema; from server.db import db; from server.app_factory import create_minimal_app; app=create_minimal_app(); app.app_context().push(); validate_database_schema(db)"
```

---

## 📊 מה השתנה?

### עמודות חדשות ב-`call_log`:

| עמודה | סוג | ברירת מחדל | תיאור |
|-------|-----|------------|-------|
| `recording_mode` | VARCHAR(32) | NULL | אופן הקלטה: TWILIO_CALL_RECORD / RECORDING_API / OFF |
| `stream_started_at` | TIMESTAMP | NULL | זמן התחלת WebSocket stream |
| `stream_ended_at` | TIMESTAMP | NULL | זמן סיום WebSocket stream |
| `stream_duration_sec` | DOUBLE PRECISION | NULL | משך Stream בשניות |
| `stream_connect_count` | INTEGER | 0 | מספר reconnections (>1 = בעיית עלות) |
| `webhook_11205_count` | INTEGER | 0 | ספירת שגיאות Twilio 11205 |
| `webhook_retry_count` | INTEGER | 0 | ספירת ניסיונות webhook חוזרים |
| `recording_count` | INTEGER | 0 | מספר הקלטות שנוצרו (צריך להיות 0 או 1) |
| `estimated_cost_bucket` | VARCHAR(16) | NULL | סיווג עלות: LOW/MED/HIGH |

### קבצים ששונו:

1. **server/db_migrate.py** - הוספת Migration 51
   - מוסיף את כל עמודות cost metrics
   - idempotent - בודק קיום לפני הוספה

2. **server/environment_validation.py** - הוספת בדיקת schema
   - בודק קיום עמודות קריטיות בהפעלה
   - נכשל מיד אם חסר משהו

3. **server/app_factory.py** - קריאה לבדיקת schema
   - מריץ `validate_database_schema` אחרי migrations
   - מונע הפעלה של מערכת שבורה

4. **migration_add_recording_mode.py** - סקריפט standalone
   - ניתן להריץ ישירות ללא Flask app
   - מוסיף רק את העמודות החסרות

---

## ❓ שאלות ותשובות נפוצות

**ש: מה אם המיגרציה נכשלת?**
ת: המיגרציה idempotent - ניתן להריץ מחדש בבטחה. היא תדלג על עמודות קיימות.

**ש: האם צריך להוריד את השרת לפני המיגרציה?**
ת: מומלץ, אבל לא חובה. המיגרציה מוסיפה עמודות בלבד (לא מוחקת).

**ש: מה קורה אם יש שיחות פעילות בזמן המיגרציה?**
ת: השיחות ימשיכו לעבוד. השגיאות ייפסקו רק אחרי הפעלה מחדש של השרת.

**ש: איך אני יודע שהתיקון עבד?**
ת: בצע שיחה חדשה ובדוק שאין שגיאות `UndefinedColumn` בלוגים.

---

## 📞 תמיכה

אם יש בעיות:
1. בדוק logs: `tail -f logs/app.log`
2. אמת schema: `\d+ call_log` ב-psql
3. הרץ מיגרציה שוב: `python migration_add_recording_mode.py`

---

**✅ הכל מוכן! המערכת תעבוד בצורה תקינה אחרי הרצת המיגרציה.**
