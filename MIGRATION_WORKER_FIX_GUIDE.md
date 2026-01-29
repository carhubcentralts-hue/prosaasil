# Migration and Worker Fixes - Complete Guide

## תיקון מיגרציות ו-Worker (עברית)

### בעיות שתוקנו

#### 1. מיגרציות לא אידמפוטנטיות (Migrations 115-117)
**הבעיה:** 
- מיגרציות 115-117 השתמשו רק ב-`if not check_table_exists()` לפני יצירת טבלאות
- אם טבלה הייתה קיימת חלקית (מניסיון כושל קודם), המיגרציה דילגה לחלוטין
- זה הותיר סכמה שבורה עם עמודות/אינדקסים חסרים

**הפתרון:**
- כעת המיגרציות בודקות גם כאשר טבלה קיימת:
  - בודקות עמודות קריטיות שעשויות להיות חסרות
  - מוסיפות עמודות חסרות עם `ALTER TABLE` (רק עמודות שנוספו מאוחר יותר)
  - יוצרות אינדקסים חסרים גם אם הטבלה קיימת
- מדפיסות דיווח ברור על מה חסר ומה נתקן
- **הערה:** המיגרציות מתקנות רק עמודות שנוספו בשלבים מאוחרים. אם עמודות בסיס חסרות (id, business_id וכו'), זו בעיה חמורה שדורשת התערבות ידנית.

#### 2. חוסר לוגים בתהליך המיגרציה
**הבעיה:**
- לא היה ברור איפה המיגרציה נכשלת או מדלגת

**הפתרון:**
- השארנו את פונקציית `checkpoint()` הקיימת שמדפיסה לוגים
- הוספנו קריאות נוספות לאחר כל שלב במיגרציה
- כעת רואים בדיוק איזו טבלה/עמודה חסרה

#### 3. Worker ללא אבחון סכמת DB
**הבעיה:**
- ה-worker עלה על DB ישן בלי אזהרה
- "נראה שבור" אבל לא היה ברור למה

**הפתרון:**
- הוספנו בדיקת סכמה מהירה בהפעלת ה-worker
- בודקים שטבלאות קריטיות קיימות: `business`, `leads`, `receipts`, `gmail_receipts`
- אם חסרות - יציאה ברורה עם הודעה: "DB schema outdated, run migrate"
- לוגים משופרים:
  - `DATABASE_URL` (ממוסך)
  - `REDIS_URL` (ממוסך)
  - `SERVICE_ROLE`
  - `FLASK_ENV`

#### 4. תיקיית worker/ מיותרת
**הבעיה:**
- קיימת תיקייה `worker/` עם Dockerfile ישן
- עלולה לגרום לבלבול - איזה worker להשתמש?

**הפתרון:**
- הוספנו `worker/README.md` עם אזהרה ברורה: **DO NOT USE**
- מסבירים שה-worker הנכון הוא `server/worker.py`
- שומרים את התיקייה להיסטוריה בלבד

#### 5. חוסר סקריפט deployment מסודר
**הבעיה:**
- אין דרך פשוטה להריץ migrations ולאחר מכן להעלות services
- קל לשכוח להריץ migrations

**הפתרון:**
- יצרנו `scripts/deploy_production.sh` - סקריפט מושלם לפריסה:
  1. בונה images (אופציונלי: `--rebuild`)
  2. מריץ migrations תחילה
  3. מחכה שיסתיימו בהצלחה
  4. רק אז מעלה את כל ה-services
  5. מאמת שהם רצים
  6. מדפיס פקודות שימושיות

---

## English Guide

### Problems Fixed

#### 1. Non-Idempotent Migrations (115-117)
**Problem:**
- Migrations 115-117 only used `if not check_table_exists()` before creating tables
- If a table existed partially (from a previous failed attempt), the migration skipped entirely
- This left a broken schema with missing columns/indexes

**Solution:**
- Migrations now check even when tables exist:
  - Check critical columns that might be missing
  - Add missing columns with `ALTER TABLE` (only columns added in later phases)
  - Create missing indexes even if table exists
- Print clear reports about what's missing and what was fixed
- **Note:** Migrations only fix columns that were added in later phases. If base columns are missing (id, business_id, etc.), that's a serious problem requiring manual intervention.

#### 2. Lack of Migration Checkpoint Logging
**Problem:**
- Unclear where migration fails or skips

**Solution:**
- Kept existing `checkpoint()` function that logs to stderr
- Added more checkpoint calls after each migration step
- Now see exactly which table/column is missing

#### 3. Worker Without DB Schema Diagnostics
**Problem:**
- Worker starts on old DB without warning
- "Looks broken" but unclear why

**Solution:**
- Added quick schema check on worker startup
- Checks critical tables exist: `business`, `leads`, `receipts`, `gmail_receipts`
- If missing - clear exit with message: "DB schema outdated, run migrate"
- Enhanced logging:
  - `DATABASE_URL` (masked)
  - `REDIS_URL` (masked)
  - `SERVICE_ROLE`
  - `FLASK_ENV`

#### 4. Redundant worker/ Directory
**Problem:**
- `worker/` directory exists with old Dockerfile
- Could cause confusion - which worker to use?

**Solution:**
- Added `worker/README.md` with clear warning: **DO NOT USE**
- Explains correct worker is `server/worker.py`
- Keep directory for history only

#### 5. No Proper Deployment Script
**Problem:**
- No simple way to run migrations then start services
- Easy to forget running migrations

**Solution:**
- Created `scripts/deploy_production.sh` - perfect deployment script:
  1. Builds images (optional: `--rebuild`)
  2. Runs migrations first
  3. Waits for successful completion
  4. Only then starts all services
  5. Verifies they're running
  6. Prints useful commands

---

## How to Use (כיצד להשתמש)

### Production Deployment (פריסה לפרודקשן)

```bash
# Full deployment with migrations
./scripts/deploy_production.sh

# Force rebuild all images
./scripts/deploy_production.sh --rebuild

# Only run migrations (don't start services)
./scripts/deploy_production.sh --migrate-only
```

### Manual Migration Run (הרצת migrations ידנית)

```bash
# Run migrations manually
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm migrate

# Or using dcprod wrapper
./scripts/dcprod.sh run --rm migrate
```

### View Logs (צפייה בלוגים)

```bash
# View all logs
./scripts/dcprod.sh logs -f

# View specific service
./scripts/dcprod.sh logs -f worker
./scripts/dcprod.sh logs -f prosaas-api
./scripts/dcprod.sh logs -f migrate
```

### Check Service Status (בדיקת סטטוס)

```bash
./scripts/dcprod.sh ps
```

---

## Migration Checkpoint Examples

When running migrations, you'll now see detailed checkpoints:

```
🔧 MIGRATION CHECKPOINT: Migration 115: Adding business calendars and routing rules system
🔧 MIGRATION CHECKPOINT:   ℹ️ business_calendars table already exists - verifying schema...
🔧 MIGRATION CHECKPOINT:   ✅ All required columns present in business_calendars
🔧 MIGRATION CHECKPOINT:   ✅ Index idx_business_calendars_business_active created
🔧 MIGRATION CHECKPOINT:   ℹ️ calendar_routing_rules table already exists - verifying schema...
🔧 MIGRATION CHECKPOINT:   ⚠️ Missing columns in calendar_routing_rules: ['question_text']
🔧 MIGRATION CHECKPOINT:   ✅ Added missing columns to calendar_routing_rules: ['question_text']
🔧 MIGRATION CHECKPOINT: ✅ Migration 115 complete: Business calendars and routing rules system added
```

---

## Worker Startup Examples

When worker starts, you'll see diagnostics:

```
================================================================================
🔧 WORKER BOOT DIAGNOSTICS
================================================================================
📍 DATABASE_URL: postgresql://postgres:***@aws-1-ap-northeast-1.pooler.supabase.com:6543/postgres
📍 REDIS_URL: redis://redis:6379/0
📍 SERVICE_ROLE: worker
📍 FLASK_ENV: production
🔍 Performing quick schema check...
✅ Schema check passed - all critical tables present
================================================================================
```

If schema is outdated:

```
================================================================================
❌ CRITICAL: DB schema appears outdated!
❌ Missing tables: ['business_calendars', 'scheduled_message_rules']
❌ Please run migrations first:
❌   docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm migrate
================================================================================
```

---

## Files Changed

1. **server/db_migrate.py** - Made migrations 115-117 truly idempotent
2. **server/worker.py** - Added boot diagnostics and schema check
3. **worker/README.md** - Documented that worker/ directory is deprecated
4. **scripts/deploy_production.sh** - New comprehensive deployment script

---

## Important Notes (הערות חשובות)

### ⚠️ Always Run Migrations First

```bash
# ✅ CORRECT ORDER:
# 1. Run migrations
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm migrate

# 2. Start services
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# ✅ OR USE THE DEPLOYMENT SCRIPT (does both automatically):
./scripts/deploy_production.sh
```

### ⚠️ Never Skip Migrations

The worker will now refuse to start if critical tables are missing. This is by design to prevent broken deployments.

### ⚠️ Use Correct Worker

- **✅ CORRECT:** `server/worker.py` (started by docker-compose)
- **❌ WRONG:** `worker/` directory (deprecated)

---

## Testing the Fixes

### Test Migration Idempotency

```bash
# Run migrations twice - second run should be safe
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm migrate
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm migrate

# Check logs - should see "already exists - verifying schema"
```

### Test Worker Schema Check

```bash
# Start worker (will check schema)
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d worker

# View logs
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs worker

# Should see boot diagnostics with schema check
```

---

## Troubleshooting (פתרון בעיות)

### Problem: Worker exits with "DB schema outdated"
**Solution:** Run migrations:
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm migrate
```

### Problem: Migration says "table already exists" but worker still fails
**Solution:** This is now fixed! The migrations are idempotent and will add missing columns.

### Problem: Not sure which worker is running
**Solution:** Check docker-compose.yml - it should use `command: ["python", "-m", "server.worker"]`

---
