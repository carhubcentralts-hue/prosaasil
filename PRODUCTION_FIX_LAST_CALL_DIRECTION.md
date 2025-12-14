# ✅ PRODUCTION FIX: Missing `last_call_direction` Column

## 🔴 Problem Summary

Production database is missing the `last_call_direction` column in the `leads` table, causing 500 errors on all endpoints that query leads (notifications, leads list, inbound calls, outbound calls).

**Error**: `psycopg2.errors.UndefinedColumn: column leads.last_call_direction does not exist`

## 🔧 Solution Implemented

### 1. Migration Added (Migration 36)
- **File**: `server/db_migrate.py`
- **What it does**:
  - Adds `last_call_direction VARCHAR(16)` column to `leads` table
  - Creates index `idx_leads_last_call_direction` for performance
  - Backfills data from `call_log` table (latest call direction per lead)
  - Fully idempotent (can run multiple times safely)

### 2. Error Handling Added
- **File**: `server/routes_leads.py`
- **What it does**:
  - Wraps `/api/leads` endpoint in try/except
  - Catches `UndefinedColumn` errors gracefully
  - Returns clear error message instead of 500
  - Prevents crashes while migration is pending

## 📋 Deployment Steps

### Step 1: Verify Database Connection

Before running migrations, confirm you're connected to the correct database:

```bash
# In production container/server:
python3 -c "
import os
url = os.getenv('DATABASE_URL', '')
if '@' in url:
    parts = url.split('@')
    print(f'Host: {parts[1].split(':')[0] if ':' in parts[1] else parts[1].split('/')[0]}')
    print(f'Database: {parts[1].split('/')[-1] if '/' in parts[1] else 'unknown'}')
else:
    print('DATABASE_URL not set or invalid')
"
```

**Expected Output**: Should show your production database host and name

### Step 2: Run Migration

#### Option A: Using Docker (Recommended)

```bash
# If backend is running in Docker:
docker exec -it <backend-container-name> /app/run_migrations.sh
```

#### Option B: Direct Python Execution

```bash
# If backend runs directly on server:
cd /app  # or your application directory
export MIGRATION_MODE=1
export ASYNC_LOG_QUEUE=0
python -m server.db_migrate
```

#### Option C: Manual SQL (If migration fails)

If the Python migration fails for any reason, run this SQL directly:

```sql
-- Connect to production database using psql or your preferred client
BEGIN;

-- Add column if it doesn't exist
ALTER TABLE public.leads
ADD COLUMN IF NOT EXISTS last_call_direction VARCHAR(16);

-- Create index for performance
CREATE INDEX IF NOT EXISTS idx_leads_last_call_direction
ON public.leads (last_call_direction);

-- Backfill from call_log (most recent call per lead)
WITH latest_calls AS (
    SELECT DISTINCT ON (cl.lead_id) 
        cl.lead_id,
        cl.direction,
        cl.created_at
    FROM call_log cl
    WHERE cl.lead_id IS NOT NULL 
      AND cl.direction IS NOT NULL
    ORDER BY cl.lead_id, cl.created_at DESC
)
UPDATE leads l
SET last_call_direction = lc.direction
FROM latest_calls lc
WHERE l.id = lc.lead_id
  AND (l.last_call_direction IS NULL OR l.last_call_direction = '');

COMMIT;
```

### Step 3: Verify Migration Success

```sql
-- Verify column exists
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name='leads' AND column_name='last_call_direction';
-- Expected: 1 row with column_name='last_call_direction', data_type='character varying'

-- Verify index exists
SELECT indexname 
FROM pg_indexes 
WHERE schemaname='public' AND indexname='idx_leads_last_call_direction';
-- Expected: 1 row with indexname='idx_leads_last_call_direction'

-- Check backfill results
SELECT 
    COUNT(*) as total_leads,
    COUNT(last_call_direction) as leads_with_direction,
    COUNT(*) FILTER (WHERE last_call_direction = 'inbound') as inbound_leads,
    COUNT(*) FILTER (WHERE last_call_direction = 'outbound') as outbound_leads
FROM leads;
-- Expected: Counts showing distribution of lead directions
```

### Step 4: Restart Backend (if needed)

If you made any code changes, restart the backend:

```bash
# Docker:
docker restart <backend-container-name>

# PM2:
pm2 restart backend

# Systemd:
sudo systemctl restart prosaas-backend
```

### Step 5: Test All Affected Endpoints

Run these tests to verify everything works:

#### Backend API Tests

```bash
# Test 1: Get all leads (should return 200)
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "https://your-domain.com/api/leads?page=1&pageSize=25"

# Test 2: Filter by inbound calls (should return 200)
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "https://your-domain.com/api/leads?direction=inbound"

# Test 3: Filter by outbound calls (should return 200)
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "https://your-domain.com/api/leads?direction=outbound"

# Test 4: Get notifications (should return 200, not 500)
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "https://your-domain.com/api/notifications"
```

#### UI Tests

1. **Leads Page** (`/leads`)
   - ✅ Page loads without errors
   - ✅ Lead count displays correctly
   - ✅ Direction filter dropdown works
   - ✅ Filtering by "נכנסות" (inbound) shows only inbound leads
   - ✅ Filtering by "יוצאות" (outbound) shows only outbound leads

2. **Inbound Calls Page** (`/inbound-calls`)
   - ✅ Page loads without errors
   - ✅ Only shows leads with inbound calls
   - ✅ Lead cards display correctly

3. **Outbound Calls Page** (`/outbound-calls`)
   - ✅ Page loads without errors
   - ✅ Only shows leads with outbound calls
   - ✅ Lead cards display correctly

## 📊 What This Fix Does

### Before Fix:
- ❌ `/api/leads` returns 500 error
- ❌ `/api/notifications` crashes on JOIN with leads
- ❌ UI shows "Internal server error"
- ❌ Lead counts don't display
- ❌ Cannot filter by call direction

### After Fix:
- ✅ All endpoints return 200
- ✅ Leads query works with/without direction filter
- ✅ UI displays lead counts correctly
- ✅ Direction filtering works (inbound/outbound/all)
- ✅ Graceful error handling if column still missing

## 🔍 Root Cause Analysis

**Why This Happened**: Code was deployed that references `leads.last_call_direction` column, but the database migration was never added to `db_migrate.py`. This is a classic "code ahead of schema" deployment issue.

**Prevention**: Always ensure database migrations are committed and deployed BEFORE code that uses new columns.

## 📝 Files Changed

1. `server/db_migrate.py` - Added Migration 36 for `last_call_direction` column
2. `server/routes_leads.py` - Added error handling for missing column scenarios
3. `PRODUCTION_FIX_LAST_CALL_DIRECTION.md` - This deployment guide

## 🚨 Rollback Plan (if needed)

If the migration causes issues:

```sql
-- Remove the column (data loss - use with caution)
ALTER TABLE leads DROP COLUMN IF EXISTS last_call_direction;

-- Remove the index
DROP INDEX IF EXISTS idx_leads_last_call_direction;
```

**Note**: Removing the column will cause the same errors as before. Only rollback if migration itself fails.

## ✅ Success Criteria

- [ ] Migration runs without errors
- [ ] Column `last_call_direction` exists in `leads` table
- [ ] Index `idx_leads_last_call_direction` exists
- [ ] `GET /api/leads` returns 200 (not 500)
- [ ] `GET /api/leads?direction=inbound` returns 200
- [ ] `GET /api/leads?direction=outbound` returns 200
- [ ] Leads page in UI loads without errors
- [ ] Inbound calls page shows correct leads
- [ ] Outbound calls page shows correct leads
- [ ] Lead count displays in UI
- [ ] Direction filter works in UI

## 🆘 Troubleshooting

### Migration fails with "relation already exists"
**Solution**: Migration is idempotent, this is safe to ignore. Verify column exists with verification query.

### Still getting UndefinedColumn error after migration
**Solution**: 
1. Verify column was actually created: `\d leads` in psql
2. Restart backend application
3. Check you ran migration on correct database

### Backfill updated 0 rows
**Solution**: This is normal if:
- No leads have calls yet
- `call_log` table doesn't have `direction` column (older schema)
- All leads already have `last_call_direction` populated

Future calls will populate this field automatically via `tasks_recording.py`.

### API still returns 500
**Solution**:
1. Check backend logs for exact error
2. Verify migration completed successfully
3. Restart backend to clear any cached schema information
4. Check database connection is to correct database

## 📞 Support

If issues persist after following this guide:
1. Check backend application logs
2. Check database query logs
3. Verify migration was applied: `SELECT * FROM information_schema.columns WHERE table_name='leads' AND column_name='last_call_direction'`
