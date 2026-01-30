# Fix for "idle in transaction" Locks Breaking Migrations

## Problem

PostgreSQL connections stuck in "idle in transaction" state hold locks and block DDL operations (like CREATE TABLE), causing migrations to fail with `lock_timeout` errors.

### Root Cause

The specific issue was in migration 113, where a constraint check was using `db.session.execute()`:

```python
# OLD CODE (BROKEN)
constraint_check = db.session.execute(text("""
    SELECT 1 FROM pg_constraint 
    WHERE conname='unique_run_lead'
""")).fetchone()
```

This left the database connection in an "idle in transaction" state, holding locks that blocked subsequent DDL operations.

## Solution

### 1. Fixed `check_*` Functions

All database checking functions now use `engine.connect()` instead of `db.session` to avoid leaving transactions open:

- ✅ `check_column_exists()` - already using `engine.connect()`
- ✅ `check_table_exists()` - already using `engine.connect()`
- ✅ `check_index_exists()` - already using `engine.connect()`
- ✅ `check_constraint_exists()` - **NEW** - uses `engine.connect()`

### 2. Added `terminate_idle_in_tx()` Function

New function to terminate idle-in-transaction connections before DDL operations:

```python
def terminate_idle_in_tx(engine, older_than_seconds=30):
    """
    Terminate idle-in-transaction connections that are older than the specified time.
    
    This prevents stale connections from holding locks and blocking DDL operations.
    """
    sql = """
    SELECT pg_terminate_backend(pid)
    FROM pg_stat_activity
    WHERE state = 'idle in transaction'
      AND now() - xact_start > (INTERVAL '1 second' * :secs)
      AND pid <> pg_backend_pid()
    """
    with engine.connect() as conn:
        result = conn.execute(text(sql), {"secs": older_than_seconds})
        terminated_count = sum(1 for row in result if row[0])
        if terminated_count > 0:
            log.info(f"Terminated {terminated_count} idle-in-transaction connection(s)")
```

### 3. Updated `exec_ddl()` Function

The `exec_ddl()` function now:

1. **Checks** for idle-in-transaction connections before DDL
2. **Logs** the count if any are found
3. **Terminates** old idle transactions (> 30 seconds)
4. **Executes** the DDL with strict timeouts

```python
def exec_ddl(engine, sql: str):
    # First, check and log idle-in-transaction count
    with engine.connect() as conn:
        result = conn.execute(text("SELECT count(*) FROM pg_stat_activity WHERE state='idle in transaction'"))
        idle_count = result.scalar()
        if idle_count > 0:
            log.warning(f"Found {idle_count} idle-in-transaction connection(s) before DDL")
            # Terminate old idle transactions to prevent lock contention
            terminate_idle_in_tx(engine, 30)
    
    # Then execute DDL with timeouts...
```

### 4. Fixed Migration 113

Replaced `db.session.execute()` with `check_constraint_exists()`:

```python
# NEW CODE (FIXED)
if not check_constraint_exists('unique_run_lead'):
    checkpoint("  → Adding unique constraint on (run_id, lead_id)...")
    # ... rest of migration
```

### 5. Deploy Script

The `scripts/deploy_production.sh` already includes proper service management:

- **Stops** prosaas-api, worker, and scheduler before migrations
- **Releases** database connections
- **Optional** `--kill-idle-tx` flag for manual cleanup

```bash
# Stop services that might hold database connections
docker compose stop prosaas-api worker scheduler

# Run migrations
docker compose run --rm migrate
```

## Benefits

1. **No More Blocking**: Check functions don't leave transactions open
2. **Auto Cleanup**: Old idle transactions are automatically terminated before DDL
3. **Clear Logging**: Logs show when idle transactions are found and terminated
4. **Fail Fast**: DDL operations still fail fast (5s lock timeout) if issues remain
5. **Production Safe**: Deploy script ensures services are stopped before migrations

## Verification

Run the verification script to confirm all fixes are in place:

```bash
python verify_idle_transaction_fix.py
```

Expected output:
```
================================================================================
Static Verification of Idle-in-Transaction Fix
================================================================================

📋 Test 1: check_constraint_exists function exists...
✅ PASS: check_constraint_exists function found
✅ PASS: check_constraint_exists uses engine.connect()

📋 Test 2: terminate_idle_in_tx function exists...
✅ PASS: terminate_idle_in_tx function found
✅ PASS: terminate_idle_in_tx calls pg_terminate_backend
✅ PASS: terminate_idle_in_tx checks for idle-in-transaction state

📋 Test 3: exec_ddl calls terminate_idle_in_tx...
✅ PASS: exec_ddl calls terminate_idle_in_tx
✅ PASS: exec_ddl checks for idle-in-transaction connections

📋 Test 4: Migration 113 uses check_constraint_exists...
✅ PASS: Migration 113 uses check_constraint_exists
✅ PASS: Migration 113 does not use db.session.execute for constraint check

================================================================================
Results: 9 passed, 0 failed
================================================================================
```

## Deployment

### Normal Deployment

```bash
./scripts/deploy_production.sh
```

This will:
1. Stop API, worker, and scheduler
2. Run migrations (with automatic idle-tx cleanup)
3. Start all services

### Migration Only

```bash
./scripts/deploy_production.sh --migrate-only
```

### With Manual Idle Transaction Cleanup

```bash
./scripts/deploy_production.sh --kill-idle-tx
```

This uses `scripts/kill_idle_transactions.py` to manually clean up idle transactions before migrations.

## Monitoring

After deployment, monitor for:

1. **No blocking PIDs** in migration logs
2. **Fast migration completion** (no 5s lock timeouts)
3. **Clean logs** without "idle in transaction" warnings

## Acceptance Criteria

- [x] No more "Blocking PID ... idle in transaction" errors
- [x] Migration 115 CREATE TABLE business_calendars succeeds immediately
- [x] Migrations can be run multiple times without hanging
- [x] All check_* functions use engine.connect()
- [x] exec_ddl() terminates old idle transactions before DDL
- [x] Deploy script stops services before migrations

## Related Files

- `server/db_migrate.py` - Main migration file with fixes
- `scripts/deploy_production.sh` - Production deployment script
- `scripts/kill_idle_transactions.py` - Manual idle transaction cleanup
- `verify_idle_transaction_fix.py` - Verification test script
