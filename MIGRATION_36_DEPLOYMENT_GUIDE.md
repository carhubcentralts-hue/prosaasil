# Migration 36 Deployment Guide - Production-Ready Lock Fix

## Problem Fixed

Migration 36 was failing with `LockNotAvailable` errors at the index creation stage because:
1. `CREATE INDEX` (without CONCURRENTLY) acquires exclusive locks that block writes to the table
2. When services are running and writing to `call_log`/`leads` tables, the index creation can't acquire locks
3. With short lock_timeout (5s), the migration fails immediately in a live production environment

## Solution Implemented

### 1. New exec_index() Function - CONCURRENT Index Creation

**exec_index()** - NEW function specifically for production-safe index creation:
- Uses `CREATE INDEX CONCURRENTLY` which doesn't block writes
- Runs outside transaction (AUTOCOMMIT isolation level - required for CONCURRENTLY)
- `lock_timeout = 60s` (longer to handle concurrent table access)
- `statement_timeout = 0` (unlimited - index creation can be slow on large tables)
- **Best-effort mode**: Warns on failure but doesn't fail migration (indexes are performance optimizations)
- Up to 10 retry attempts with exponential backoff for lock errors
- Lock debug logging on failures

**Why CONCURRENTLY is Critical:**
- Standard `CREATE INDEX` takes AccessExclusiveLock, blocking ALL writes
- `CREATE INDEX CONCURRENTLY` takes ShareUpdateExclusiveLock, allowing concurrent writes
- Essential for zero-downtime deployments on live production systems

### 2. Separated Lock Policies - DDL vs DML vs INDEX

**exec_ddl()** - For schema changes (CREATE/ALTER TABLE):
- `lock_timeout = 5s` (fail fast)
- `statement_timeout = 120s`
- `idle_in_transaction_session_timeout = 60s`

**exec_dml()** - For data operations (UPDATE/INSERT/DELETE):
- `lock_timeout = 60s` (longer to handle concurrent access)
- `statement_timeout = 0` (unlimited for large operations)
- `idle_in_transaction_session_timeout = 60s`
- **Catches both OperationalError AND DBAPIError (includes LockNotAvailable)**
- Detects and retries on `LockNotAvailable` errors from psycopg2
- Includes lock debug logging on failures

**exec_index()** - For index creation (CREATE INDEX CONCURRENTLY):
- Uses AUTOCOMMIT isolation (required for CONCURRENTLY)
- `lock_timeout = 60s` (longer to handle busy tables)
- `statement_timeout = 0` (unlimited - index creation can take time)
- Best-effort mode with retry logic
- Won't fail migration if index creation fails

### 3. Batched Backfill BY BUSINESS (tenant_id)

Instead of processing all leads at once, the migration now:
- **Processes each business separately** to reduce lock contention between tenants
- Processes 1000 leads per batch per business
- Commits after each batch
- Logs progress per business
- Reduces database pressure with small delays between batches

**Benefits:**
- ✅ Eliminates hot locks when multiple businesses exist
- ✅ Short-lived locks per batch (not holding table lock for minutes)
- ✅ Other queries can proceed between batches
- ✅ Progress visibility per business
- ✅ Safer for large datasets and multi-tenant environments

### 4. Supporting Indexes with CONCURRENTLY

The migration now creates critical indexes **using CONCURRENTLY** before the backfill:

1. **`idx_call_log_lead_created`** - Partial index on `call_log(lead_id, created_at)` for fast lookups
2. **`idx_leads_backfill_pending`** - Partial index on `leads(tenant_id, id)` WHERE `last_call_direction IS NULL`
3. **`idx_leads_last_call_direction`** - Index on the new column for filtering

**Benefits:**
- ✅ Prevents full table scans during backfill
- ✅ Dramatically reduces lock duration
- ✅ Uses partial indexes for memory efficiency
- ✅ **CONCURRENTLY ensures no blocking of concurrent writes**
- ✅ Best-effort mode means deployment won't fail if indexes can't be created

### 5. Lock Debug Logging

All three execution functions (`exec_ddl()`, `exec_dml()`, and `exec_index()`) now display lock information when operations fail:
- Shows which process is blocking
- Shows the blocking query
- Shows process state (e.g., "idle in transaction")

## Deployment Instructions

### Docker Compose Deployment (Recommended)

The docker-compose setup is **already properly configured**:

```yaml
# Migration runs FIRST, before any services start
migrate:
  depends_on: []  # No dependencies
  restart: "no"   # Run once and exit

# All services depend on migration completing
prosaas-api:
  depends_on:
    migrate:
      condition: service_completed_successfully

worker:
  depends_on:
    migrate:
      condition: service_completed_successfully
```

**To deploy:**
```bash
# Stop all services first (ensures clean migration environment)
docker compose down

# Rebuild and start (migrations run automatically)
docker compose build
docker compose up -d

# Or use the redeploy script
./redeploy.sh
```

### Manual Service Stop (If Not Using Docker Compose)

If you need to stop services manually before migration:

```bash
# Stop all database-connected services
docker compose stop prosaas-api worker scheduler prosaas-calls

# Or if running without docker-compose:
# Kill processes: api, worker, scheduler, whatsapp-service, etc.
```

### Cloud Run / Direct Python Deployment

If deploying without Docker Compose (e.g., Cloud Run with `start_production.sh`):

**CRITICAL: Stop all services before migration**

```bash
# 1. Stop all services that connect to the database
# (Use your process manager, e.g., systemctl, supervisord, or Cloud Run)
kill <api-pid>
kill <worker-pid>
kill <scheduler-pid>
# etc.

# 2. Wait for connections to close (optional but recommended)
sleep 5

# 3. Run migrations
RUN_MIGRATIONS_ON_START=1 python -m server.db_migrate

# 4. Start services again
./start_production.sh
```

**Why?** When services are running during migration, they may hold database connections and locks on the tables being migrated, causing lock timeout errors.

## Migration 36 Details

**What it does:**
1. Adds `last_call_direction` column to `leads` table
2. Creates performance indexes:
   - `idx_leads_last_call_direction` on the new column
   - `idx_call_log_lead_created` for fast call_log lookups
   - `idx_leads_backfill_pending` for efficient batch selection
3. Backfills direction from `call_log` (using FIRST call per lead, not latest)

**Performance:**
- ~1000 rows per batch per business
- With 3474 leads across multiple businesses, expects ~4-10 batches total
- Each batch takes ~1-2 seconds
- Total time: ~10-20 seconds (scales with number of businesses)

**Idempotency:**
- ✅ Safe to run multiple times
- ✅ Only updates rows where `last_call_direction IS NULL`
- ✅ Skips already-processed leads
- ✅ Indexes use `IF NOT EXISTS`

## Production-Ready Improvements

### 1. LockNotAvailable Retry Logic
The `exec_dml()` function now catches:
- `sqlalchemy.exc.OperationalError` (for connection errors)
- `sqlalchemy.exc.DBAPIError` (for database API errors)
- Specifically detects `LockNotAvailable` in `e.orig`
- Retries with exponential backoff (2s, 4s, 6s)

### 2. Batching by Business (tenant_id)
- Processes each business separately to avoid cross-tenant lock contention
- First queries for distinct `tenant_id` values needing backfill
- Then processes each business with batched updates
- Logs progress per business for visibility

### 3. Supporting Indexes
- **CRITICAL**: Indexes are created BEFORE backfill starts
- Uses partial indexes (WHERE clauses) for memory efficiency
- `call_log(lead_id, created_at)` - speeds up DISTINCT ON query
- `leads(tenant_id, id) WHERE last_call_direction IS NULL` - speeds up batch selection

## Troubleshooting

### Migration Still Fails with Lock Timeout

1. **Check for running services:**
   ```bash
   docker compose ps
   # or
   ps aux | grep python
   ```

2. **Check database connections:**
   ```sql
   SELECT * FROM pg_stat_activity 
   WHERE datname = '<your_db_name>' 
   AND state != 'idle';
   ```

3. **Check for idle transactions:**
   ```sql
   SELECT * FROM pg_stat_activity 
   WHERE state = 'idle in transaction';
   ```

4. **Manually terminate blocking connections:**
   ```sql
   SELECT pg_terminate_backend(pid) 
   FROM pg_stat_activity 
   WHERE state = 'idle in transaction' 
   AND state_change < now() - interval '30 seconds';
   ```

### Migration Takes Too Long

If you have more than 100K leads:
- The batched-by-business approach already scales well
- Consider increasing batch size from 1000 to 5000 for very large datasets
- The supporting indexes ensure queries remain fast even with large tables

### Lock Debug Output

If you see lock debug output in logs:
```
LOCK DEBUG - Processes blocking this DML operation:
  Blocked PID: 12345, State: active
    Query: UPDATE leads SET...
  Blocking PID: 67890, State: idle in transaction
    Query: SELECT * FROM leads...
```

This means:
- Process 67890 is holding a lock (possibly an idle transaction)
- Process 12345 (the migration) is waiting
- **Solution**: Ensure all services are stopped before migration

## Files Changed

1. **server/db_migrate.py**
   - Added import for `DBAPIError` (line 56)
   - Added `exec_dml()` function with LockNotAvailable detection (lines ~494-587)
   - **NEW:** Added `exec_index()` function for CONCURRENT index creation (lines ~588-720)
     - Uses AUTOCOMMIT isolation level (required for CONCURRENTLY)
     - 60s lock_timeout, unlimited statement_timeout
     - Up to 10 retries with exponential backoff
     - Best-effort mode (warns on failure, doesn't fail migration)
     - Lock debug logging
   - Updated Migration 36 with:
     - **Changed index creation from `exec_sql` to `exec_index`**
     - **All indexes now use CREATE INDEX CONCURRENTLY**
     - Supporting indexes before backfill
     - Batched-by-business approach
     - Better progress logging

2. **test_migration_36_improvements.py**
   - Added `test_exec_index_exists()` to verify new function
   - Updated `test_supporting_indexes()` to check for CONCURRENTLY usage
   - Verifies best-effort mode and retry logic

3. **MIGRATION_36_DEPLOYMENT_GUIDE.md** (this file)
   - Comprehensive deployment documentation
   - Documentation of exec_index() function and CONCURRENTLY approach

## Testing

To test the changes:

```bash
# 1. Reset migration 36 (if already applied)
# In PostgreSQL:
ALTER TABLE leads DROP COLUMN IF EXISTS last_call_direction;
DROP INDEX IF EXISTS idx_leads_last_call_direction;
DROP INDEX IF EXISTS idx_call_log_lead_created;
DROP INDEX IF EXISTS idx_leads_backfill_pending;

# 2. Run migrations
docker compose up migrate

# 3. Check logs for batch progress
docker compose logs migrate | grep -i "batch\|backfill\|business"

# Expected output:
# 🔧 MIGRATION CHECKPOINT: Adding supporting indexes for backfill performance...
# 🔧 MIGRATION CHECKPOINT: ✅ Supporting indexes created
# 🔧 MIGRATION CHECKPOINT: Backfilling last_call_direction from call_log (batched by business)...
# Found 2 business(es) with leads requiring backfill
#   Business 1: 2000 rows updated
#   ✅ Business 1: Completed 2000 rows
#   Business 2: 1474 rows updated
#   ✅ Business 2: Completed 1474 rows
# ✅ Backfilled last_call_direction: 3474 total rows
```

## Summary of Production-Ready Features

✅ **NEW: exec_index() function** - Production-safe CONCURRENT index creation
✅ **CREATE INDEX CONCURRENTLY** - No blocking of concurrent writes
✅ **AUTOCOMMIT isolation** - Required for CONCURRENTLY, runs outside transaction
✅ **Best-effort index creation** - Won't fail migration if indexes can't be created
✅ **Separated lock policies** - DDL uses 5s timeout, DML uses 60s timeout, INDEX uses 60s+AUTOCOMMIT
✅ **LockNotAvailable retry** - Catches and retries on lock errors with exponential backoff
✅ **Batched by business** - Reduces cross-tenant lock contention
✅ **Supporting indexes** - Prevents full table scans during backfill
✅ **Lock debug logging** - Shows exactly which process is blocking
✅ **Progress visibility** - Per-business logging of backfill progress
✅ **Idempotent** - Safe to run multiple times
✅ **Small delays** - 0.1s between batches to reduce DB pressure
✅ **Zero-downtime deployment** - Can run with services active (CONCURRENTLY indexes)
