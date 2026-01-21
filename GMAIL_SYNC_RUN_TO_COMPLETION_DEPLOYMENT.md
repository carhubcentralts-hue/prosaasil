# Gmail Sync Run-to-Completion - מדריך פריסה

## סקירה
שדרוג מערכת סנכרון Gmail שמאפשר חילוץ מלא של כל המיילים בטווח תאריכים נתון, עם תמיכה במצבים:
1. **מצב רציף** - RUN_TO_COMPLETION=true - רץ עד סיום מלא
2. **מצב מנומס** - RUN_TO_COMPLETION=false - משהה אחרי זמן מוגדר ומאפשר המשך

## שינויים במסד נתונים

### Migration 89 - שדות חדשים ב-receipt_sync_runs

```sql
-- שדות למעקב אחר טווח התאריכים
ALTER TABLE receipt_sync_runs ADD COLUMN from_date DATE;
ALTER TABLE receipt_sync_runs ADD COLUMN to_date DATE;
ALTER TABLE receipt_sync_runs ADD COLUMN months_back INTEGER;

-- שדות למצב ריצה
ALTER TABLE receipt_sync_runs ADD COLUMN run_to_completion BOOLEAN DEFAULT FALSE;
ALTER TABLE receipt_sync_runs ADD COLUMN max_seconds_per_run INTEGER;
ALTER TABLE receipt_sync_runs ADD COLUMN skipped_count INTEGER DEFAULT 0;

-- עדכון constraint למצב 'paused'
ALTER TABLE receipt_sync_runs DROP CONSTRAINT IF EXISTS chk_receipt_sync_status;
ALTER TABLE receipt_sync_runs ADD CONSTRAINT chk_receipt_sync_status 
  CHECK (status IN ('running', 'paused', 'completed', 'failed', 'cancelled'));
```

## משתני סביבה

### חדש
```bash
# מצב ריצה עד סיום (ברירת מחדל: false)
RUN_TO_COMPLETION=true    # ימשיך עד חילוץ כל המיילים
RUN_TO_COMPLETION=false   # ישהה אחרי MAX_SECONDS_PER_RUN

# זמן מקסימלי לריצה (רק כאשר RUN_TO_COMPLETION=false)
MAX_SECONDS_PER_RUN=120   # ברירת מחדל: 120 שניות (2 דקות)
MAX_SECONDS_PER_RUN=300   # דוגמה: 5 דקות
```

### קיים (ללא שינוי)
```bash
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
ENCRYPTION_KEY=...
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
```

## הוראות פריסה

### 1. גיבוי מסד נתונים
```bash
# לפני כל שינוי - גיבוי!
pg_dump $DATABASE_URL > backup_before_migration_89.sql
```

### 2. הרצת Migration
```bash
cd /home/runner/work/prosaasil/prosaasil

# בדיקה - האם Python environment מוכן
source .venv/bin/activate  # או venv אחר

# הרצת migrations
python -m server.db_migrate
```

### 3. אימות Migration
```bash
# בדיקה שהשדות נוספו
psql $DATABASE_URL -c "\d receipt_sync_runs"

# צריך לראות:
# - from_date | date
# - to_date | date
# - months_back | integer
# - run_to_completion | boolean
# - max_seconds_per_run | integer
# - skipped_count | integer

# בדיקת constraint
psql $DATABASE_URL -c "
  SELECT conname, pg_get_constraintdef(oid) 
  FROM pg_constraint 
  WHERE conname = 'chk_receipt_sync_status';
"
# צריך לכלול: 'paused' ברשימת הסטטוסים
```

### 4. הפעלת השרת

#### אופציה א': מצב ריצה עד סיום (מומלץ לסנכרונים גדולים)
```bash
export RUN_TO_COMPLETION=true
python run_server.py
# או
docker-compose up -d
```

#### אופציה ב': מצב משהה (ברירת מחדל)
```bash
export RUN_TO_COMPLETION=false
export MAX_SECONDS_PER_RUN=120
python run_server.py
```

### 5. אימות פעולה

#### בדיקה 1: sync קצר
```bash
# API call עם טווח קטן
curl -X POST "http://localhost:8000/api/receipts/sync" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "from_date": "2024-01-01",
    "to_date": "2024-01-31",
    "mode": "incremental"
  }'

# בדיקת סטטוס
curl "http://localhost:8000/api/receipts/sync/status?run_id=XXX" \
  -H "Authorization: Bearer $TOKEN"
```

#### בדיקה 2: sync ארוך (36 חודשים)
```bash
curl -X POST "http://localhost:8000/api/receipts/sync" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "months_back": 36,
    "mode": "full_backfill"
  }'
```

#### בדיקה 3: מצב paused והמשך
```bash
# עם RUN_TO_COMPLETION=false, אחרי 120 שניות צריך לראות:
curl "http://localhost:8000/api/receipts/sync/status?run_id=XXX"
# תגובה:
# {
#   "status": "paused",
#   "checkpoint": {
#     "has_next": true,
#     "last_page_token": "..."
#   }
# }

# המערכת תמשיך אוטומטית בריצה הבאה
```

## API Response - שדות חדשים

### GET /api/receipts/sync/status

```json
{
  "success": true,
  "sync_run": {
    "id": 123,
    "mode": "full_backfill",
    "status": "running",  // או "paused", "completed", "failed", "cancelled"
    "progress": {
      "messages_scanned": 1500,
      "saved_receipts": 45,
      "skipped_count": 1420,  // ← חדש!
      "errors_count": 35
    },
    "config": {  // ← חדש!
      "from_date": "2021-01-01",
      "to_date": "2024-01-01",
      "months_back": 36,
      "run_to_completion": true,
      "max_seconds_per_run": null
    },
    "checkpoint": {  // ← חדש!
      "has_next": true,
      "last_page_token": "CAIQ...",
      "current_month": "2023-06"
    }
  }
}
```

## זרימת עבודה

### מצב A: RUN_TO_COMPLETION=true
```
1. משתמש מפעיל sync עם 36 חודשים
2. המערכת רצה ללא הפסקה
3. מעבדת כל דף אחר דף
4. שומרת progress ב-DB כל 20 הודעות
5. סטטוס: running → completed
6. משך: כמה דקות עד שעה (תלוי בכמות מיילים)
```

### מצב B: RUN_TO_COMPLETION=false
```
1. משתמש מפעיל sync עם 36 חודשים
2. המערכת רצה 120 שניות
3. שומרת checkpoint (page_token, current_month)
4. סטטוס: running → paused
5. [המשך אוטומטי] job חדש מתחיל
6. ממשיך מה-checkpoint
7. חוזר על 2-6 עד completed
```

## טיפול בבעיות

### בעיה: Migration נכשל
```bash
# בדיקת שגיאה
tail -f /var/log/app.log | grep -i migration

# rollback ידני אם צריך
psql $DATABASE_URL << EOF
BEGIN;
-- הסר שדות שנוספו
ALTER TABLE receipt_sync_runs DROP COLUMN IF EXISTS from_date;
ALTER TABLE receipt_sync_runs DROP COLUMN IF EXISTS to_date;
-- וכו'
COMMIT;
EOF

# שחזר מגיבוי
psql $DATABASE_URL < backup_before_migration_89.sql
```

### בעיה: Sync תקוע ב-paused
```bash
# בדיקה
psql $DATABASE_URL -c "
  SELECT id, status, messages_scanned, last_heartbeat_at, updated_at
  FROM receipt_sync_runs
  WHERE status = 'paused'
  ORDER BY updated_at DESC
  LIMIT 5;
"

# אם צריך לאפס ידנית
psql $DATABASE_URL -c "
  UPDATE receipt_sync_runs
  SET status = 'completed'
  WHERE id = <run_id> AND status = 'paused';
"
```

### בעיה: Worker לא מריץ המשך אוטומטי
```bash
# בדיקת Redis Queue
redis-cli -u $REDIS_URL
> KEYS *sync*
> LLEN default

# בדיקת worker
ps aux | grep rq
# אם אין - הפעל worker
rq worker default --url $REDIS_URL
```

## ניטור

### Logs חשובים
```bash
# התחלת sync
grep "🔍 RUN_START" /var/log/app.log

# התקדמות
grep "📊 RUN_PROGRESS" /var/log/app.log

# השהיה
grep "⏸️ Reached MAX_SECONDS_PER_RUN" /var/log/app.log

# השלמה
grep "🔔 JOB_DONE" /var/log/app.log
```

### מדדי ביצועים
```sql
-- ביצועי sync
SELECT 
  id,
  mode,
  status,
  messages_scanned,
  saved_receipts,
  EXTRACT(EPOCH FROM (finished_at - started_at)) as duration_seconds,
  messages_scanned / NULLIF(EXTRACT(EPOCH FROM (finished_at - started_at)), 0) as messages_per_second
FROM receipt_sync_runs
WHERE finished_at IS NOT NULL
ORDER BY started_at DESC
LIMIT 10;
```

## Rollback Plan

אם יש בעיה קריטית:

### שלב 1: עצור workers
```bash
# עצור את כל ה-workers
pkill -f "rq worker"
docker-compose stop worker
```

### שלב 2: Rollback code
```bash
git checkout <previous_commit>
docker-compose build
docker-compose up -d
```

### שלב 3: Rollback DB (אם צריך)
```bash
psql $DATABASE_URL < backup_before_migration_89.sql
```

## תמיכה

בעיות? פתח issue ב-GitHub עם:
1. Logs מה-sync
2. מצב ה-receipt_sync_runs table
3. משתני סביבה (ללא סודות!)
4. גרסת קוד (commit hash)
