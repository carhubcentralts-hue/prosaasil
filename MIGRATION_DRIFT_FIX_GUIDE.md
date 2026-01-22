# Migration Drift Fix - Documentation

## בעיה שתוקנה

הדאטהבייס היה חסר את העמודה `leads.phone_raw` שקיימת במודל הקוד.
זה גרם לשגיאות 500 ב-`/api/notifications` ועוד נקודות קצה שמבצעות שאילתות על Lead.

## הפתרון

### 1. Migration 93 - הוספת העמודה החסרה

נוספה מיגרציה חדשה (`Migration 93`) ב-`server/db_migrate.py` שמוסיפה:
- `leads.phone_raw` - VARCHAR(64), nullable
- מטרה: שמירת הטלפון המקורי לפני נורמליזציה (לצורך debugging)

### 2. כלי אודיט סכמה - `db_schema_audit.py`

נוצר סקריפט חדש: `server/scripts/db_schema_audit.py`

**שימוש:**
```bash
# בדיקה מקומית
python -m server.scripts.db_schema_audit

# בדיקה ב-Docker
docker compose run --rm prosaas-api python -m server.scripts.db_schema_audit
```

**Exit codes:**
- `0` - הסכמה תקינה
- `1` - יש drift או מיגרציות חסרות
- `2` - שגיאה קריטית (חיבור ל-DB נכשל וכו')

### 3. Guardrail - מניעת startup עם schema drift

השרת בודק את הסכמה בזמן startup דרך `validate_database_schema()`.

**נשלט על ידי ENV variable:**

```bash
# Production (מומלץ) - fail-fast אם יש drift
MIGRATIONS_ENFORCE=true

# Local/Debug - התר startup עם אזהרות
MIGRATIONS_ENFORCE=false
```

**התנהגות:**
- `MIGRATIONS_ENFORCE=true`: השרת לא יעלה אם חסרות עמודות קריטיות
- `MIGRATIONS_ENFORCE=false`: השרת יעלה עם אזהרות בלוג

### 4. Fail-soft ב-/api/notifications (בונוס בלבד)

⚠️ **חשוב**: זה לא פתרון אמיתי - רק מונע 500 errors!

אם יש UndefinedColumn error ב-`/api/notifications`:
- מחזיר 200 עם מערך ריק + אזהרה
- כותב בלוג הוראות ברורות להרצת מיגרציות
- **אבל** - הבעיה משפיעה על כל ה-Lead flow, לא רק notifications!

## הרצת מיגרציות

### אופציה 1: מקומית (Python)

```bash
python -m server.db_migrate
```

### אופציה 2: דרך Docker Compose

```bash
# הרצה חד-פעמית
docker compose run --rm prosaas-api python -m server.db_migrate

# או אם השירות כבר רץ
docker compose exec prosaas-api python -m server.db_migrate
```

### אופציה 3: בתוך Flask App Context

```python
from server.db_migrate import apply_migrations
with app.app_context():
    migrations = apply_migrations()
print(f"Applied {len(migrations)} migrations")
```

## אימות שהתיקון עבד

### 1. בדיקת DB ישירה

```sql
SELECT column_name 
FROM information_schema.columns 
WHERE table_name='leads' AND column_name='phone_raw';
```

צריך להחזיר שורה אחת.

### 2. בדיקת API

```bash
curl -X GET https://your-domain.com/api/notifications \
  -H "Authorization: Bearer YOUR_TOKEN"
```

צריך להחזיר 200 (לא 500).

### 3. בדיקת לוגים

```bash
docker compose logs prosaas-api | grep "phone_raw"
```

לא צריך לראות שגיאות UndefinedColumn.

### 4. הרצת סקריפט האודיט

```bash
python -m server.scripts.db_schema_audit
# Exit code צריך להיות 0
echo $?
```

## חוקים חדשים - מניעת drift בעתיד

### ✅ חובה: שינויי schema רק דרך מיגרציות

**אסור:**
- `db.create_all()` בפרודקשן (מותר רק לבוטסטראפ של DB ריק)
- שינויי schema ידניים (ALTER TABLE ישירות ב-psql)
- הוספת עמודות במודל בלי מיגרציה מתאימה

**מותר ונכון:**
- כל שינוי schema = מיגרציה חדשה ב-`server/db_migrate.py`
- בדיקה עם `check_column_exists()` לפני הוספה
- Rollback אוטומטי אם מיגרציה נכשלת

### ✅ חובה: תמיד להריץ את סקריפט האודיט

**ב-CI/CD:**
```yaml
- name: Audit Database Schema
  run: python -m server.scripts.db_schema_audit
```

**לפני deploy:**
```bash
# 1. בדיקה שהסכמה תקינה
python -m server.scripts.db_schema_audit

# 2. הרצת מיגרציות
python -m server.db_migrate

# 3. בדיקה שוב שהכל תקין
python -m server.scripts.db_schema_audit
```

### ✅ חובה: MIGRATIONS_ENFORCE=true בפרודקשן

```bash
# docker-compose.prod.yml או .env
MIGRATIONS_ENFORCE=true
```

זה מבטיח:
- השרת לא יעלה עם schema drift
- שגיאות ברורות במקום cascading failures
- אי אפשר לשכוח להריץ מיגרציות

## Troubleshooting

### בעיה: השרת לא עולה - "Missing critical column"

**גורם:** `MIGRATIONS_ENFORCE=true` והסכמה לא מעודכנת.

**פתרון:**
```bash
# אופציה 1: הרץ מיגרציות מחוץ ל-container
docker compose run --rm prosaas-api python -m server.db_migrate

# אופציה 2: אפשר startup זמנית
MIGRATIONS_ENFORCE=false docker compose up prosaas-api
# ואז הרץ מיגרציות ידנית
docker compose exec prosaas-api python -m server.db_migrate
# ואז restart עם MIGRATIONS_ENFORCE=true
```

### בעיה: "Migration 93 already applied"

זה תקין! המיגרציה בודקת אם העמודה כבר קיימת.

```
✅ Migration 93: phone_raw column already exists - skipping
```

### בעיה: nginx מחזיר 502 בגלל שה-API לא עולה

```bash
# 1. בדוק לוגים של ה-API
docker compose logs prosaas-api --tail=100

# 2. אם יש schema drift, הרץ מיגרציות
docker compose run --rm prosaas-api python -m server.db_migrate

# 3. Restart
docker compose restart prosaas-api
```

## קבצים שהשתנו

1. `server/db_migrate.py` - Migration 93 נוספה
2. `server/scripts/db_schema_audit.py` - סקריפט אודיט חדש
3. `server/environment_validation.py` - CRITICAL_COLUMNS עודכנה, MIGRATIONS_ENFORCE נוסף
4. `server/app_factory.py` - גם dev mode משתמש במיגרציות עכשיו
5. `server/routes_leads.py` - fail-soft ב-/api/notifications

## Security Summary

✅ **No vulnerabilities introduced**
- Migration adds nullable column (no data loss)
- Fail-soft only affects one endpoint (graceful degradation)
- Guardrail prevents broken deployments
- All changes are backwards compatible

✅ **Security improvements**
- Better error handling (no stack traces to client)
- Clear logging for debugging
- Production-safe defaults (MIGRATIONS_ENFORCE)
