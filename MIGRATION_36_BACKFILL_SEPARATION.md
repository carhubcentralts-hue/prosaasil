# Migration 36 Backfill Separation - Complete Guide

## Overview

This document describes the architectural changes made to separate data backfill operations from schema migrations, specifically for Migration 36 (adding `last_call_direction` column to the `leads` table).

## Problem Statement

The original Migration 36 had both schema changes and data backfill in a single migration:

1. **Schema change**: Add `last_call_direction` column to `leads` table
2. **Data backfill**: Update all existing leads with their first call direction from `call_log` table

This approach caused production issues:
- **Lock timeouts**: Large backfill operations (DML) could fail with `lock_timeout` errors
- **Blocking migrations**: Any backfill failure would prevent migration from completing
- **Deployment failures**: Lock contention during backfill caused deployments to fail
- **Race conditions**: Even with services stopped, transient locks from external connections or autovacuum could cause failures

## Solution: Separation of Concerns

We separated migrations into distinct phases:

### Phase 1: Schema Migrations (Critical)
- **What**: DDL operations only (ALTER TABLE, ADD COLUMN)
- **When**: During migration phase (must succeed)
- **Timeout**: Short lock timeout (5s) - fail fast
- **Failure**: Blocks deployment (schema correctness is critical)

### Phase 2: Index Building (Performance)
- **What**: CREATE INDEX CONCURRENTLY operations
- **When**: After migrations, before backfill
- **Timeout**: Longer timeout (60s) with retries
- **Failure**: Warns but doesn't block deployment (performance optimization)

### Phase 3: Data Backfill (Maintenance)
- **What**: DML operations (UPDATE, INSERT)
- **When**: After migrations and indexes
- **Timeout**: Time-boxed execution (10 minutes default)
- **Failure**: Warns but doesn't block deployment (data maintenance)

## Implementation Details

### 1. Migration 36 - Schema Only

**File**: `server/db_migrate.py`

**Changes**:
- Removed all backfill logic (DML operations)
- Kept only schema change (ADD COLUMN)
- Added notice that backfill runs separately

**Code**:
```python
# Migration 36: BUILD 350 - Add last_call_direction (SCHEMA ONLY)
exec_sql(migrate_engine, """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'leads' AND column_name = 'last_call_direction'
        ) THEN
            ALTER TABLE leads ADD COLUMN last_call_direction VARCHAR(16);
            RAISE NOTICE 'Added leads.last_call_direction';
        END IF;
    END;
    $$;
""", autocommit=True)

checkpoint("ℹ️  Backfill will run separately via db_backfill.py after migrations")
```

### 2. Backfill Tool - db_backfill.py

**File**: `server/db_backfill.py`

**Features**:
- **Idempotent**: Safe to run multiple times (only updates NULL values)
- **Batched processing**: Small batches (100 rows) to reduce lock contention
- **SKIP LOCKED**: Uses `FOR UPDATE SKIP LOCKED` to avoid blocking on locked rows
- **Time-boxed**: Default 10-minute execution limit
- **Tenant-based**: Processes by `tenant_id` to reduce cross-tenant lock contention
- **Never fails deployment**: Always exits 0, even on incomplete backfill
- **Progress reporting**: Clear logging of progress and completion status

**SQL Strategy**:
```sql
WITH batch AS (
    SELECT id
    FROM leads
    WHERE tenant_id = :tenant_id 
      AND last_call_direction IS NULL
    ORDER BY id
    LIMIT :batch_size
    FOR UPDATE SKIP LOCKED  -- Key feature: skip locked rows
),
first_calls AS (
    SELECT DISTINCT ON (cl.lead_id) 
        cl.lead_id,
        cl.direction
    FROM call_log cl
    JOIN batch b ON b.id = cl.lead_id
    WHERE cl.direction IN ('inbound', 'outbound')
    ORDER BY cl.lead_id, cl.created_at ASC  -- FIRST call
)
UPDATE leads l
SET last_call_direction = fc.direction
FROM first_calls fc
WHERE l.id = fc.lead_id
```

**Timeout Strategy**:
- `lock_timeout = '5s'`: Fail fast on locked rows (SKIP LOCKED will skip them)
- `statement_timeout = '30s'`: Reasonable timeout for batch operations
- `idle_in_transaction_session_timeout = '60s'`: Prevent stuck transactions

### 3. Docker Compose Service

**File**: `docker-compose.prod.yml`

**Added service**:
```yaml
backfill:
  build:
    context: .
    dockerfile: Dockerfile.backend.light
  restart: "no"  # Run once and exit
  command: ["python", "server/db_backfill.py", "--max-time=600", "--batch-size=100"]
  depends_on:
    migrate:
      condition: service_completed_successfully
```

### 4. Deployment Script Integration

**File**: `scripts/deploy_production.sh`

**Deployment order**:
1. Stop services
2. Run migrations (schema changes) - **MUST succeed**
3. Build indexes - **Can fail (warning only)**
4. **Run backfill - Can fail (warning only)**
5. Start services

**Code**:
```bash
# Step 3.6: Run data backfill (separate from migrations)
log_header "Step 3.6: Running Data Backfill Operations"
docker compose \
    -f "$BASE_COMPOSE" \
    -f "$PROD_COMPOSE" \
    run --rm backfill
log_success "Backfill tool completed (check logs above for any warnings)"
```

## Benefits

### 1. Production Stability
- Migrations never fail due to lock timeouts on data operations
- Schema changes are separate from data maintenance
- Deployment continues even if backfill is incomplete

### 2. Lock Contention Handling
- `FOR UPDATE SKIP LOCKED` skips locked rows instead of waiting
- Small batches (100 rows) reduce lock duration
- Per-tenant processing reduces cross-tenant contention
- Short lock timeout (5s) with retry on next run

### 3. Idempotency
- Safe to run multiple times
- Only updates NULL values
- Incomplete backfill continues on next deployment

### 4. Observability
- Clear progress logging per tenant
- Time tracking and completion status
- Warning when incomplete (but doesn't fail)

## Usage

### Manual Backfill Run

```bash
# Run with defaults (600s, batch size 100)
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm backfill

# Run with custom parameters
docker compose run --rm backfill python server/db_backfill.py --max-time=300 --batch-size=50

# Run locally
python server/db_backfill.py --max-time=600 --batch-size=100
```

### Monitoring Progress

Check logs during deployment:
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs backfill
```

Expected output:
```
Starting backfill of last_call_direction column
Found 3 business(es) with leads requiring backfill:
Total pending leads: 15000
  • Business 1: 5000 leads
  • Business 2: 8000 leads
  • Business 3: 2000 leads

Processing business 1 (5000 pending leads)
  Progress: Batch 10, 1000 rows updated so far (elapsed: 12.3s)
  ✅ Business 1 complete: 5000 rows updated
...
✅ Backfill completed successfully!
```

## Testing

Run the test suite:
```bash
python test_migration_36_backfill_separation.py
```

This verifies:
1. Migration 36 is schema-only
2. Backfill tool exists and is executable
3. Backfill uses FOR UPDATE SKIP LOCKED
4. Backfill is idempotent
5. Docker Compose has backfill service
6. Deploy script runs backfill
7. Backfill SQL correctness

## Troubleshooting

### Backfill Incomplete After Deployment

**Symptom**: Logs show "Partial completion" or time limit reached

**Cause**: Large dataset or high lock contention

**Solution**:
1. This is normal behavior - backfill will continue on next deployment
2. Or run manually: `docker compose run --rm backfill`
3. Or increase time limit: `--max-time=1200` (20 minutes)

### Lock Timeout Warnings

**Symptom**: "Lock timeout on batch N - skipping"

**Cause**: Row is locked by another transaction

**Solution**:
- This is expected - row will be processed on next run
- SKIP LOCKED prevents blocking
- No action needed

### No Progress

**Symptom**: 0 rows updated repeatedly

**Possible causes**:
1. All leads already have `last_call_direction` set (✅ good)
2. No calls in `call_log` table for any leads
3. Database connectivity issues

**Check**:
```sql
-- Count pending leads
SELECT COUNT(*) FROM leads WHERE last_call_direction IS NULL;

-- Check call_log data
SELECT COUNT(*) FROM call_log WHERE direction IN ('inbound', 'outbound');
```

## Migration from Old to New Approach

### Before (Problematic)
```
Migration 36:
  1. ADD COLUMN last_call_direction
  2. Backfill all leads (could fail on lock timeout)
  3. If backfill fails → migration fails → deployment fails
```

### After (Stable)
```
Migration 36:
  1. ADD COLUMN last_call_direction
  2. Log message: "Backfill runs separately"
  ✅ Migration always succeeds

Separate backfill tool:
  1. Run after migration
  2. Use SKIP LOCKED to avoid blocking
  3. Time-boxed execution
  ⚠️ Can fail but doesn't block deployment
```

## Production Deployment Checklist

- [ ] Stop all services that connect to database
- [ ] Run migrations (schema changes) - must succeed
- [ ] Build indexes (performance) - can warn
- [ ] Run backfill (data maintenance) - can warn
- [ ] Start services
- [ ] Monitor backfill logs for completion status
- [ ] If incomplete, backfill will continue on next deployment

## Best Practices for Future Migrations

When adding new migrations that include data operations:

1. **Separate schema from data**:
   - Migration N: Schema changes only (DDL)
   - Backfill tool: Data operations (DML)

2. **Use small batches**:
   - 100-200 rows per batch
   - Reduces lock duration

3. **Use SKIP LOCKED**:
   - Prevents blocking on locked rows
   - Fails fast with short timeout

4. **Make it idempotent**:
   - Check conditions (e.g., IS NULL)
   - Safe to run multiple times

5. **Time-box execution**:
   - Don't run forever
   - Continue on next deployment

6. **Process by tenant/business**:
   - Reduces cross-tenant lock contention
   - Better progress visibility

7. **Always exit 0 for backfill**:
   - Never block deployment
   - Log warnings instead

## References

- **Original issue**: Migration 36 lock timeout in production
- **Solution**: Separate backfill from migrations
- **Pattern**: Similar to index building (db_build_indexes.py)
- **Deployment**: deploy_production.sh

## Summary

This architectural change brings production-grade stability to data backfill operations by:
- ✅ Separating critical schema changes from non-critical data maintenance
- ✅ Using production-tested patterns (SKIP LOCKED, batching, time limits)
- ✅ Never blocking deployments on data operations
- ✅ Providing idempotent, retry-safe backfill operations
- ✅ Following the same pattern as index building

The system is now more resilient to lock contention and provides a clear path for handling large-scale data migrations in production environments.
