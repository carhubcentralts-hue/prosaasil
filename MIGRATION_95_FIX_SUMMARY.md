# Migration 95 Constraint Fix - Summary

## Problem Statement

Migration 95 was failing in production with `LockNotAvailable` errors when trying to modify the CHECK constraint on the `receipts` table. The migration used a DO $$ block which:

1. Requires AccessExclusive lock on the `receipts` table
2. Has a short lock_timeout (5s) that's insufficient for busy production environments
3. Cannot retry properly when wrapped in a DO block
4. Doesn't provide adequate debugging when locks are held

## Root Cause

The issue occurs because:
- The receipts table can have active queries from various services (n8n, cron jobs, manual queries, etc.)
- Even simple SELECT queries can hold locks that conflict with AccessExclusive lock requirements
- The 5-second timeout is too aggressive for production where brief lock contention is normal
- The DO $$ block wraps both operations, preventing granular retry control

## Solution

### 1. Added `exec_ddl_heavy()` Function

A new function specifically designed for heavy DDL operations that require AccessExclusive locks:

```python
def exec_ddl_heavy(engine, sql: str, params=None, retries=10):
    """
    Execute heavy DDL operations that require AccessExclusive locks.
    
    Key differences from exec_ddl():
    - Longer lock_timeout (120s instead of 5s)
    - statement_timeout = 0 (unlimited)
    - More retries (10 instead of 4) with exponential backoff
    - Lock debugging on failures
    """
```

**Configuration:**
- `lock_timeout = 120s` - Allows more time to acquire locks in busy environments
- `statement_timeout = 0` - Unlimited execution time (waiting for locks is expected)
- `idle_in_transaction_session_timeout = 60s` - Prevents stuck transactions
- **10 retries** with exponential backoff (2s → 30s)
- Detailed lock debugging on failures

### 2. Refactored Migration 95

**Before:**
```python
exec_sql(migrate_engine, """
    DO $$ 
    BEGIN
        ALTER TABLE receipts DROP CONSTRAINT IF EXISTS chk_receipt_status;
        ALTER TABLE receipts 
        ADD CONSTRAINT chk_receipt_status 
        CHECK (status IN ('pending_review', 'approved', 'rejected', 'not_receipt', 'incomplete'));
    END $$;
""", autocommit=True)
```

**After:**
```python
# Step 1: Drop existing constraint (if exists)
exec_ddl_heavy(migrate_engine, """
    ALTER TABLE receipts DROP CONSTRAINT IF EXISTS chk_receipt_status
""")

# Step 2: Add new constraint with 'incomplete' status
exec_ddl_heavy(migrate_engine, """
    ALTER TABLE receipts 
    ADD CONSTRAINT chk_receipt_status 
    CHECK (status IN ('pending_review', 'approved', 'rejected', 'not_receipt', 'incomplete'))
""")
```

**Benefits:**
- Each operation is separate, allowing independent retry
- Proper timeout configuration for production
- Automatic retry with backoff on lock contention
- Maintains idempotency with `IF EXISTS`

### 3. Comprehensive Test Suite

Created `test_migration_95_constraint_fix.py` with 7 tests:

1. ✅ `exec_ddl_heavy()` function exists
2. ✅ Lock timeouts are correctly configured (120s, 0, 60s)
3. ✅ Retry logic with exponential backoff (10 retries, 2s → 30s)
4. ✅ Lock debugging implementation
5. ✅ Migration 95 uses `exec_ddl_heavy()` (not DO $$ block)
6. ✅ Split into two separate ALTER statements
7. ✅ Proper documentation

## Why This Works in Production

1. **Longer Timeouts**: 120s lock_timeout gives adequate time to acquire locks during normal operations
2. **Automatic Retry**: 10 retries with exponential backoff (2s → 30s) handle transient lock contention
3. **Lock Debugging**: When failures occur, detailed information about blocking processes is logged
4. **Idempotent**: The `IF EXISTS` clause allows safe re-runs
5. **No Transaction Pollution**: Each ALTER runs in its own transaction via `engine.begin()`

## Production Deployment

The migration is now production-safe and handles:
- Brief lock contention from active queries
- Idle-in-transaction connections (killed after 60s)
- Long-running queries (migration waits up to 120s × 10 retries)
- Failed attempts with detailed debugging output

## Testing

All tests pass:
- ✅ `test_migration_95_constraint_fix.py`: 7/7 tests pass
- ✅ `test_migration_lock_fixes.py`: All related tests still pass
- ✅ Python syntax validation passes
- ✅ Code review feedback addressed

## Files Modified

1. **server/db_migrate.py**:
   - Added `exec_ddl_heavy()` function (lines 749-847)
   - Refactored Migration 95 (lines 5208-5253)

2. **test_migration_95_constraint_fix.py** (new):
   - Comprehensive test suite with 7 tests

## Migration Execution Example

When Migration 95 runs, you'll see:
```
🔧 Running Migration 95: Add 'incomplete' status to receipts
   ⚠️  This is a heavy DDL operation - may take time to acquire lock
   → Step 1: Dropping existing constraint (if exists)
   → Step 2: Adding new constraint with 'incomplete' status
✅ Migration 95 completed - 'incomplete' status added to receipts
```

If lock contention occurs:
```
⚠️ Lock error on heavy DDL (attempt 1/10), retrying in 2.0s: ...
⚠️ Lock error on heavy DDL (attempt 2/10), retrying in 3.0s: ...
```

If all retries fail:
```
❌ Heavy DDL failed (attempt 10/10): ...
================================================================================
LOCK DEBUG - Processes blocking this DDL:
================================================================================
  Blocked PID: 12345, State: active
    Query: ALTER TABLE receipts DROP CONSTRAINT...
  Blocking PID: 67890, State: idle in transaction
    Query: SELECT * FROM receipts WHERE...
--------------------------------------------------------------------------------
```

## Summary

This fix transforms Migration 95 from a fragile operation that fails in production to a robust, production-ready DDL operation that:
- ✅ Handles lock contention gracefully
- ✅ Provides automatic retry with backoff
- ✅ Gives detailed debugging on failures
- ✅ Maintains idempotency for safe re-runs
- ✅ Uses appropriate timeouts for heavy DDL

The migration is now ready for production deployment with confidence.
