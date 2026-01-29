# Migration Lock Fixes - Complete Implementation

## Problem Statement

Database migrations were experiencing lock issues where DDL operations (CREATE TABLE, ALTER TABLE, CREATE INDEX) would:
1. Get stuck waiting for locks for 2-3 minutes
2. Eventually timeout and fail
3. Continue execution with partial schema changes
4. Result in "relation does not exist" errors for dependent operations

This created a **half-built database state** that was difficult to recover from.

## Root Causes

1. **No lock timeouts**: DDL operations waited indefinitely for locks
2. **No lock visibility**: When timeouts occurred, we couldn't see what was blocking
3. **Soft failures**: Critical DDL failures logged warnings but continued execution
4. **Active connections**: API/worker services held idle transactions that blocked migrations

## Solution Overview

We implemented a **5-point systematic fix** to prevent lock issues:

### 1. ✅ Strengthen exec_ddl() with Lock Timeouts

**File**: `server/db_migrate.py`

Added strict timeouts to every DDL operation:

```python
def exec_ddl(engine, sql: str):
    try:
        with engine.begin() as conn:
            # Set strict timeouts to prevent long waits on locks
            conn.execute(text("SET lock_timeout = '5s'"))
            conn.execute(text("SET statement_timeout = '120s'"))
            conn.execute(text("SET idle_in_transaction_session_timeout = '60s'"))
            # Execute the DDL
            conn.execute(text(sql))
    except Exception as e:
        # ... lock debugging ...
        raise
```

**Impact**:
- DDL operations now **fail within 5 seconds** if they can't acquire a lock
- No more 2-3 minute waits
- Statement timeout of 120s prevents runaway queries
- Idle transaction timeout of 60s kills stuck sessions

### 2. ✅ Add Automatic Lock Debugging

**File**: `server/db_migrate.py`

When a DDL operation fails due to locks, we automatically log **who is blocking**:

```python
LOCK_DEBUG_SQL = """
SELECT
  blocked.pid as blocked_pid,
  blocked.state as blocked_state,
  blocked.query as blocked_query,
  blocking.pid as blocking_pid,
  blocking.state as blocking_state,
  blocking.query as blocking_query
FROM pg_locks bl
JOIN pg_stat_activity blocked ON blocked.pid = bl.pid
JOIN pg_locks kl ON ...
JOIN pg_stat_activity blocking ON blocking.pid = kl.pid
WHERE NOT bl.granted;
"""
```

**Impact**:
- Every lock timeout now shows:
  - Which process is blocked (PID, state, query)
  - Which process is blocking (PID, state, query)
- Makes debugging lock issues **trivial** instead of mysterious

### 3. ✅ Migration 115 Fail-Fast Behavior

**File**: `server/db_migrate.py`

Changed critical DDL failures from soft warnings to **hard failures**:

**Before**:
```python
except Exception as e:
    checkpoint(f"❌ Migration 115 failed: {e}")
    logger.error(f"Migration 115 error: {e}")
    db.session.rollback()  # Just log and continue
```

**After**:
```python
except Exception as e:
    checkpoint(f"❌ Migration 115 CRITICAL FAILURE: {e}")
    logger.error(f"Migration 115 error: {e}", exc_info=True)
    # CRITICAL: Cannot continue without this table - abort migration
    raise RuntimeError(f"Migration 115 FAILED: Could not create table: {e}") from e
```

**Impact**:
- If `CREATE TABLE business_calendars` fails → **migration aborts**
- If `CREATE TABLE calendar_routing_rules` fails → **migration aborts**
- If `ALTER TABLE appointments ADD COLUMN calendar_id` fails → **migration aborts**
- **No more half-built database states**

### 4. ✅ Stop Services Before Migrations

**File**: `scripts/deploy_production.sh`

Added a new step to **stop services before migrations**:

```bash
# Step 2: Stop services to avoid locks during migrations
log_header "Step 2: Stopping Services Before Migration"
log_info "Stopping API, worker, and scheduler to prevent database locks..."

docker compose \
    -f "$BASE_COMPOSE" \
    -f "$PROD_COMPOSE" \
    stop prosaas-api worker scheduler 2>/dev/null || true

log_success "Services stopped, database connections released"

# Step 3: Run migrations
log_header "Step 3: Running Database Migrations"
```

**Impact**:
- API, worker, and scheduler are **stopped before migrations run**
- Eliminates "idle in transaction" connections that cause locks
- Services only start **after migrations succeed**
- If migrations fail, services stay down (safe state)

### 5. ✅ Optional Kill Idle Transactions

**File**: `scripts/kill_idle_transactions.py`

Created a new script to **forcefully clear stuck transactions**:

```python
# Kill transactions that are:
# - In "idle in transaction" state
# - Older than 60 seconds
# - Not the current session
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle in transaction'
  AND now() - xact_start > interval '60 seconds'
  AND pid <> pg_backend_pid();
```

**Usage**:
```bash
# Manual cleanup
python scripts/kill_idle_transactions.py --dry-run  # Preview
python scripts/kill_idle_transactions.py            # Execute

# During deployment
./scripts/deploy_production.sh --kill-idle-tx
```

**Impact**:
- Can clear stuck transactions **before migrations run**
- Safe: only kills idle transactions > 60s old
- Safe: excludes the current session
- Optional: only runs when `--kill-idle-tx` flag is used

## Testing

Created comprehensive test suite in `test_migration_lock_fixes.py`:

```bash
python test_migration_lock_fixes.py
```

**Tests**:
1. ✅ exec_ddl() sets all three lock timeouts
2. ✅ exec_ddl() logs lock debugging on failure
3. ✅ LOCK_DEBUG_SQL is properly defined
4. ✅ Migration 115 raises RuntimeError on critical failures
5. ✅ Deployment script stops services before migrations
6. ✅ kill_idle_transactions.py exists and is correct

All tests pass! ✅

## Acceptance Criteria

From the original problem statement:

| Requirement | Status | How |
|------------|--------|-----|
| Migration 115 doesn't wait 2-3 minutes | ✅ | 5s lock timeout |
| Fast failure with LOCK DEBUG on locks | ✅ | exec_ddl() exception handler |
| Log shows who is blocking | ✅ | LOCK_DEBUG_SQL query |
| Deploy doesn't continue if migrate fails | ✅ | Exit code check in deploy script |
| Rerun on clean system works smoothly | ✅ | Fail-fast prevents half-built state |

## Deployment Instructions

### Standard Deployment

```bash
# Full deployment with lock fixes
./scripts/deploy_production.sh
```

### With Idle Transaction Cleanup

```bash
# If you suspect stuck transactions
./scripts/deploy_production.sh --kill-idle-tx
```

### Migration Only

```bash
# Just run migrations, don't start services
./scripts/deploy_production.sh --migrate-only
```

## Rollback Plan

If issues occur, revert these changes:
1. `server/db_migrate.py` - revert exec_ddl() and Migration 115
2. `scripts/deploy_production.sh` - revert service stopping logic

Original behavior (without lock protection) will be restored.

## Monitoring

After deployment, monitor migration logs for:

1. **Lock timeouts** (should see within 5s):
   ```
   ❌ DDL failed: ...
   LOCK DEBUG - Processes blocking this migration:
     Blocked PID: 1234, State: active
     Blocking PID: 5678, State: idle in transaction
   ```

2. **Critical failures** (should abort):
   ```
   ❌ Migration 115 CRITICAL FAILURE: ...
   RuntimeError: Migration 115 FAILED: Could not create business_calendars table
   ```

3. **Successful migrations** (no locks):
   ```
   ✅ Migration 115 complete: Business calendars and routing rules system added
   ```

## Benefits

1. **Fast Failure**: 5s instead of 2-3 minutes
2. **Visibility**: Always know who is blocking
3. **Safety**: No half-built databases
4. **Prevention**: Services stopped before migrations
5. **Recovery**: Optional cleanup script for stuck transactions

## Related Files

- `server/db_migrate.py` - Core migration logic with lock fixes
- `scripts/deploy_production.sh` - Deployment with service stopping
- `scripts/kill_idle_transactions.py` - Optional cleanup script
- `test_migration_lock_fixes.py` - Comprehensive test suite

## Summary

This is a **complete, systematic fix** for PostgreSQL lock issues in migrations. The solution prevents locks from occurring (stop services), fails fast when they do (5s timeout), logs diagnostic information (lock debugging), and prevents half-built states (fail-fast on critical DDL).

**שלא יהיו locks במיגרציות, ושהכל יעבור בשלום!** ✅
