# 🔥 HOTFIX: lead_tabs_config Column Missing

## הבעיה
טבלת `business` חסרה את העמודה `lead_tabs_config`, מה שגורם ל-API להיכשל בעת startup.

## הפתרון המהיר (Production)

### שיטה 1: הרצת הסקריפט Standalone (מומלץ)

```bash
# 1. התחבר לסרבר הפרודקשן
ssh user@production-server

# 2. הגדר את DATABASE_URL
export DATABASE_URL="postgresql://user:password@host:5432/database"

# 3. הרץ את הסקריפט
cd /path/to/prosaasil
python3 migration_add_lead_tabs_config.py
```

הסקריפט:
- ✅ בודק אם העמודה כבר קיימת
- ✅ מוסיף את העמודה עם timeout של 10 דקות
- ✅ מעדכן שורות קיימות
- ✅ מוסיף NOT NULL constraint
- ✅ מאמת שהעמודה נוספה בהצלחה

### שיטה 2: SQL ישיר (אם הסקריפט נכשל)

```sql
-- התחבר ל-PostgreSQL
psql $DATABASE_URL

-- הגדל timeout
SET statement_timeout = '600000';  -- 10 minutes

-- בדוק אם העמודה קיימת
SELECT column_name 
FROM information_schema.columns 
WHERE table_name = 'business' 
AND column_name = 'lead_tabs_config';

-- אם לא קיימת, הוסף אותה:
ALTER TABLE business ADD COLUMN lead_tabs_config JSONB;
ALTER TABLE business ALTER COLUMN lead_tabs_config SET DEFAULT '{}'::jsonb;
UPDATE business SET lead_tabs_config = '{}'::jsonb WHERE lead_tabs_config IS NULL;
ALTER TABLE business ALTER COLUMN lead_tabs_config SET NOT NULL;

-- אמת
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns 
WHERE table_name = 'business' 
AND column_name = 'lead_tabs_config';
```

## למה זה קורה?

המיגרציה (Migration 112) בקוד נכשלת בגלל אחד מהסיבות הבאות:

1. **Statement Timeout** - ה-ALTER TABLE לוקח יותר מדי זמן על טבלה גדולה
2. **Table Lock** - יש lock אחר על הטבלה
3. **Connection Issues** - בעיית תקשורת עם ה-DB

## איך למנוע את זה בעתיד?

הקוד עודכן עם התיקונים הבאים:

1. ✅ **Increased Timeout** - המיגרציה עכשיו מגדילה את ה-statement_timeout ל-10 דקות
2. ✅ **Post-Migration Verification** - המערכת מאמתת שהעמודה קיימת ונכשלת אם לא
3. ✅ **Fail Fast** - ה-API לא עולה אם חסרה עמודה קריטית (בפרודקשן)

## וריפיקציה

אחרי שתריץ את ההוטפיקס, בדוק:

```bash
# 1. וודא שהעמודה קיימת
psql $DATABASE_URL -c "SELECT column_name FROM information_schema.columns WHERE table_name = 'business' AND column_name = 'lead_tabs_config';"

# 2. וודא שה-API עולה
docker compose logs prosaas-api | grep "lead_tabs_config"

# 3. בדוק שה-API healthy
curl http://localhost:5000/api/health
```

## תמיכה

אם ההוטפיקס נכשל, בדוק:
- יש locks על הטבלה: `SELECT * FROM pg_locks WHERE relation = 'business'::regclass;`
- גודל הטבלה: `SELECT pg_size_pretty(pg_total_relation_size('business'));`
- זמן הרצה משוער: `~1-2 שניות לכל 10,000 שורות`
