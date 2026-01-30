# Migration Fixes Summary

## Problem Statement

The migrations had critical issues:

1. **Broken SQL execution**: `exec_ddl`/`execute_with_retry` was running SQL fragments (seeing `ON ...` without `CREATE INDEX`), causing syntax errors
2. **No failure handling**: Migrations continued despite DDL failures, which is forbidden in migrations
3. **Indexes in migrations**: CREATE INDEX statements were in migrations instead of db_indexes.py
4. **Migration 80 bug**: `constraint_row` UnboundLocalError
5. **Migration 113 bug**: `check_constraint_exists()` missing argument

## Changes Made

### 1. Strict DDL Failure Handling ✅

**Added `_is_already_exists_error()` helper function:**
```python
def _is_already_exists_error(e: Exception) -> bool:
    """
    Check if an exception is an 'already exists' error that can be safely ignored.
    
    Safe patterns:
    - already exists
    - duplicate_object  
    - duplicate_table
    - duplicate_column
    """
    msg = str(e).lower()
    safe_patterns = [
        "already exists",
        "duplicate_object",
        "duplicate_table", 
        "duplicate_column",
        "duplicate key",
    ]
    return any(pattern in msg for pattern in safe_patterns)
```

**Updated `exec_ddl()` to fail hard on DDL errors:**
- ✅ DDL failures now STOP migration execution immediately
- ✅ Only "already exists" type errors are allowed to continue
- ✅ SyntaxError, ProgrammingError = FAIL HARD with clear error messages

**Updated `execute_with_retry()` for DDL operations:**
- ✅ Detects DDL operations (ALTER, CREATE, DROP)
- ✅ Applies strict failure handling to DDL only
- ✅ DML operations (SELECT, INSERT, UPDATE, DELETE) continue with existing behavior

### 2. Fixed Migration 80 - constraint_row UnboundLocalError ✅

**Before:**
```python
try:
    result = execute_with_retry(migrate_engine, ...)
    constraint_row = result[0] if result else None
    
    if constraint_row:  # ❌ UnboundLocalError if execute_with_retry fails
        ...
```

**After:**
```python
# Initialize constraint_row before try block
constraint_row = None

try:
    result = execute_with_retry(migrate_engine, ...)
    constraint_row = result[0] if result else None
    
    if constraint_row:  # ✅ Safe - constraint_row is always defined
        ...
```

### 3. Fixed Migration 113 - check_constraint_exists() Signature ✅

**Before:**
```python
if not check_constraint_exists('unique_run_lead'):  # ❌ Missing table_name argument
```

**After:**
```python
if not check_constraint_exists('outbound_call_jobs', 'unique_run_lead'):  # ✅ Correct signature
```

**Function signature:**
```python
def check_constraint_exists(table_name, constraint_name):
    """Check if constraint exists using execute_with_retry"""
```

### 4. Fixed Migration 115 - Removed Broken CREATE INDEX Statements ✅

**Problem:** Migration 115 had incomplete SQL statements that were missing `CREATE INDEX`:

```python
# ❌ BROKEN - Missing CREATE INDEX
exec_ddl(db.engine, """
    ON business_calendars(business_id, is_active)
""")
```

**Solution:** Removed all CREATE INDEX statements from Migration 115 and added them to `db_indexes.py`:

**Removed from db_migrate.py:**
- Lines 6899-6915: `idx_business_calendars_business_active` and `idx_business_calendars_priority`
- Lines 6969-6986: `idx_calendar_routing_business_active` and `idx_calendar_routing_calendar`
- Lines 6999-7003: `idx_appointments_calendar_id`

**Added to db_indexes.py (5 new indexes):**
```python
{
    "name": "idx_business_calendars_business_active",
    "table": "business_calendars",
    "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_business_calendars_business_active ON business_calendars(business_id, is_active)",
    "critical": False,
    "description": "Index on business_calendars for filtering active calendars by business"
},
{
    "name": "idx_business_calendars_priority",
    "table": "business_calendars",
    "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_business_calendars_priority ON business_calendars(business_id, priority)",
    "critical": False,
    "description": "Index on business_calendars for ordering calendars by priority"
},
{
    "name": "idx_calendar_routing_business_active",
    "table": "calendar_routing_rules",
    "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_calendar_routing_business_active ON calendar_routing_rules(business_id, is_active)",
    "critical": False,
    "description": "Index on calendar_routing_rules for filtering active routing rules by business"
},
{
    "name": "idx_calendar_routing_calendar",
    "table": "calendar_routing_rules",
    "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_calendar_routing_calendar ON calendar_routing_rules(calendar_id)",
    "critical": False,
    "description": "Index on calendar_routing_rules for looking up rules by calendar"
},
{
    "name": "idx_appointments_calendar_id",
    "table": "appointments",
    "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_appointments_calendar_id ON appointments(calendar_id)",
    "critical": False,
    "description": "Index on appointments for looking up appointments by calendar"
}
```

### 5. Schema Migrations Marking ✅

**Verification:**
- ✅ `migrations_applied.append()` is called only after successful operations
- ✅ DDL failures now raise exceptions immediately, preventing further execution
- ✅ Partial progress is NOT marked if migration fails mid-execution
- ✅ Each migration step is properly wrapped in try-catch blocks

## Testing

Created `test_migration_fixes.py` to verify all changes:

```bash
python test_migration_fixes.py
```

**Test Results:**
```
✅ All calendar indexes correctly added to db_indexes.py
✅ _is_already_exists_error logic is correct
✅ Migration 80 fix: constraint_row initialized before try block
✅ Migration 113 fix: check_constraint_exists called with correct signature
✅ Migration 115 fix: CREATE INDEX statements removed and documented
✅ Added _is_already_exists_error helper function
✅ Added FAIL HARD logic for DDL errors
✅ No broken CREATE INDEX statements found
```

## Impact

### Before Fixes:
- ❌ Migration 115 crashes with "syntax error near ON"
- ❌ Migrations continue despite DDL failures
- ❌ Migration 80 crashes with UnboundLocalError
- ❌ Migration 113 crashes with missing argument
- ❌ Partial migrations marked as complete even when failed

### After Fixes:
- ✅ Migration 115 runs without index creation (indexes built separately)
- ✅ DDL failures stop migration immediately
- ✅ Migration 80 handles constraint checks safely
- ✅ Migration 113 calls check_constraint_exists correctly
- ✅ Failed migrations are NOT marked as applied

## Deployment

### Running Migrations:
```bash
# Migrations run automatically during API server startup
# Or manually:
python -m server.db_migrate
```

### Building Indexes:
```bash
# Run separately from migrations (safe to run multiple times)
python server/db_build_indexes.py

# Or via Docker:
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm indexer
```

## Files Modified

1. **server/db_migrate.py**
   - Added `_is_already_exists_error()` helper
   - Updated `exec_ddl()` with strict error handling
   - Updated `execute_with_retry()` with DDL error checking
   - Fixed Migration 80 (constraint_row initialization)
   - Fixed Migration 113 (check_constraint_exists signature)
   - Removed broken CREATE INDEX from Migration 115

2. **server/db_indexes.py**
   - Added 5 calendar-related indexes to INDEX_DEFS_MISC
   - Total indexes: 82 → 87

3. **test_migration_fixes.py** (new)
   - Verification tests for all fixes

## Architecture Compliance

✅ **IRON RULE: Migrations = DDL Only**
- Migrations now contain ONLY schema changes (CREATE TABLE, ALTER TABLE, ADD CONSTRAINT)
- All CREATE INDEX moved to db_indexes.py
- Performance indexes built separately via db_build_indexes.py

✅ **IRON RULE: DDL Failures = Fail Hard**
- DDL errors now stop execution immediately
- Only "already exists" errors are allowed
- Clear error messages indicate what went wrong

✅ **IRON RULE: No Partial Success**
- Migrations marked as applied only after full success
- Failed migrations do not mark partial progress
- Next run will retry from beginning of failed migration
