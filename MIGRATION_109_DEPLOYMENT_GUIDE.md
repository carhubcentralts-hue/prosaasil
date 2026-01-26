# Migration 109 Deployment Guide

## Overview
This guide explains the production-safe implementation for Migration 109, including the critical fix for failure handling.

## Problem
Migration 109 was experiencing two issues:
1. **Lock contention**: Attempting to ALTER TABLE `call_log` while the system was running caused timeouts
2. **Silent failures**: When migration failed, the system would continue and report "Migration completed successfully", leading to `UndefinedColumn` errors when applications started

## Solution
We've implemented a production-safe migration pattern with fail-hard error handling:

### 1. Migration 109 Changes (db_migrate.py)
- ✅ Added `IF NOT EXISTS` to all ALTER TABLE statements for idempotency
- ✅ Set `statement_timeout = 0` (no timeout for DDL when system is down)
- ✅ Set `lock_timeout = '5s'` (fail fast if table is locked - shouldn't happen)
- ✅ Removed heavy backfill operations from migration (deferred to background job)
- ✅ **NEW: Fail-hard error handling** - Migration raises exception on ANY failure
- ✅ **NEW: Column existence validation** - Fails if columns don't exist after DDL
- ✅ **NEW: Exit code 1 on failure** - Docker won't start dependent services

### 2. Docker Compose Changes
- ✅ Added dedicated `migrate` service that runs once before all other services
- ✅ Set `restart: "no"` for migrate service (runs once and exits)
- ✅ All services (api, calls, worker) depend on `migrate` completing successfully
- ✅ Disabled `RUN_MIGRATIONS_ON_START` in all services except migrate

### 3. Production Docker Compose Changes
- ✅ Same pattern applied to docker-compose.prod.yml
- ✅ Uses Dockerfile.backend.light for production

## Key Fix: Fail-Hard Error Handling

**Before the fix:**
```
❌ Migration 109 failed: statement timeout
⚠️ Migration 109 incomplete - check logs for details
Migration 110: Adding summary_status...
✅ Migration completed successfully!
Exit code: 0  ← Docker thinks migration succeeded
```

**After the fix:**
```
❌ Migration 109 failed: statement timeout
🚫 STOPPING: Migration 109 is critical - cannot continue with failed migration
❌ MIGRATION FAILED: Critical migration 109 failed: statement timeout
Exit code: 1  ← Docker will NOT start dependent services
```

This ensures that if Migration 109 fails for ANY reason (timeout, lock, partial success), the migrate container exits with code 1 and dependent services won't start with broken schema.

## Deployment Steps

### Option A: Using Docker Compose (Recommended)

```bash
# Stop all services first
docker compose down

# Start services (migrations run automatically before app starts)
docker compose up -d

# Check migration logs
docker compose logs migrate

# Verify services are healthy
docker compose ps
```

### Option B: Manual Migration (if needed)

```bash
# 1. Stop all services
docker compose down

# 2. Run migrations manually
docker compose run --rm migrate

# 3. Verify migration succeeded
# Check logs for "✅ Migration 109 complete"

# 4. Start services
docker compose up -d
```

### Production Deployment

```bash
# Stop services
docker compose -f docker-compose.yml -f docker-compose.prod.yml down

# Start with production config
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Check logs
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs migrate
```

## Verification

After deployment, verify that migration 109 completed successfully:

```sql
-- Check that columns were added
SELECT column_name
FROM information_schema.columns
WHERE table_name = 'call_log'
AND column_name IN ('started_at','ended_at','duration_sec');

-- Should return 3 rows
```

Expected output:
```
 column_name  
--------------
 started_at
 ended_at
 duration_sec
```

## What Changed in the Fix

### Investigation Findings:
1. ✅ **No duplicates found** - Migration 109 columns are defined only once
2. ✅ **Already idempotent** - Uses `IF NOT EXISTS` (can be run multiple times safely)
3. ✅ **Only migrate service runs migrations** - All other services have `RUN_MIGRATIONS=0`
4. ❌ **Bug found: Silent failures** - Migration could fail but system would continue

### The Fix:
- **Fail-hard on DDL errors**: If `exec_ddl` throws exception, migration immediately stops
- **Fail-hard on validation**: If columns don't exist after DDL, migration immediately stops
- **Fail-hard on partial success**: If any of the 3 columns fails to add, migration stops
- **Exception propagation**: Exceptions bubble up to `if __name__ == '__main__'` which calls `sys.exit(1)`

### Why This Matters:
Without fail-hard logic, the system could:
1. Fail Migration 109 (timeout, lock, etc.)
2. Continue to Migration 110, 111...
3. Print "✅ Migration completed successfully!"
4. Exit with code 0
5. Docker starts all services
6. Application fails with `UndefinedColumn: column call_log.started_at does not exist`

With fail-hard logic:
1. Fail Migration 109
2. Raise exception immediately
3. Print "❌ MIGRATION FAILED"
4. Exit with code 1
5. Docker does NOT start dependent services
6. System stays down until migration is fixed

## Verification

After deployment, verify that migration 109 completed successfully:

```sql
-- Check that columns were added
SELECT column_name
FROM information_schema.columns
WHERE table_name = 'call_log'
AND column_name IN ('started_at','ended_at','duration_sec');

-- Should return 3 rows
```

Expected output:
```
 column_name  
--------------
 started_at
 ended_at
 duration_sec
```

## Service Startup Order

With the new configuration, services start in this order:

1. **redis** - Starts and becomes healthy
2. **migrate** - Runs migrations and completes successfully  
3. **prosaas-api**, **prosaas-calls**, **worker** - Start after migration completes

This ensures:
- ✅ Migrations run before any API traffic
- ✅ No lock contention
- ✅ Clean, predictable startup

## Troubleshooting

### Migration fails with lock timeout
**Cause**: Another process is accessing the database  
**Solution**: Ensure all services are stopped before running migrations

### Migration service keeps restarting
**Cause**: `restart` policy is not set to "no"  
**Solution**: Verify `restart: "no"` in docker-compose.yml for migrate service

### Services start before migration completes
**Cause**: Missing or incorrect `depends_on` configuration  
**Solution**: Verify all services have:
```yaml
depends_on:
  migrate:
    condition: service_completed_successfully
```

## Rollback

If you need to rollback:

```bash
# Stop services
docker compose down

# Revert to previous version
git checkout <previous-commit>

# Start services
docker compose up -d
```

## Testing

Run the validation script to verify the implementation:

```bash
python validate_migration_109.py
```

Expected output: All checks should pass ✅

## Security Summary

No security vulnerabilities introduced:
- Migration only adds columns (no data deletion)
- Uses production-safe timeouts
- Idempotent (can be run multiple times safely)
- No backfill in migration (avoids long locks)

## Notes

- Migration 109 adds 3 columns: `started_at`, `ended_at`, `duration_sec`
- Backfill of existing data is deferred to a background job (not part of migration)
- Migration is idempotent - safe to run multiple times
- All changes follow Postgres best practices for production DDL
