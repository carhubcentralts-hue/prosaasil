# Migration 109 Deployment Guide

## Overview
This guide explains how to deploy the production-safe fixes for Migration 109.

## Problem
Migration 109 was failing because it attempted to ALTER TABLE `call_log` while the system was running, causing:
- Lock contention (Postgres couldn't acquire exclusive lock)
- Statement timeout errors
- Migration failures in production

## Solution
We've implemented a production-safe migration pattern:

### 1. Migration 109 Changes (db_migrate.py)
- ✅ Added `IF NOT EXISTS` to all ALTER TABLE statements for idempotency
- ✅ Set `statement_timeout = 0` (no timeout for DDL when system is down)
- ✅ Set `lock_timeout = '5s'` (fail fast if table is locked - shouldn't happen)
- ✅ Removed heavy backfill operations from migration (deferred to background job)

### 2. Docker Compose Changes
- ✅ Added dedicated `migrate` service that runs once before all other services
- ✅ Set `restart: "no"` for migrate service (runs once and exits)
- ✅ All services (api, calls, worker) depend on `migrate` completing successfully
- ✅ Disabled `RUN_MIGRATIONS_ON_START` in API service

### 3. Production Docker Compose Changes
- ✅ Same pattern applied to docker-compose.prod.yml
- ✅ Uses Dockerfile.backend.light for production

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
