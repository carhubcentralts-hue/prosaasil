# ONE SOURCE OF TRUTH - Complete Separation Architecture

## Overview

This document defines the **IRON RULE** of database operations in this project:
**NO DUPLICATIONS - Each type of operation has exactly ONE place where it belongs.**

## The Three Pillars

```
┌─────────────────────────────────────────────────────────────────┐
│                    DATABASE OPERATIONS                           │
│                                                                   │
│  1. MIGRATIONS        2. INDEXES         3. BACKFILLS           │
│  (Schema Only)        (Performance)      (Data Only)             │
│                                                                   │
│  db_migrate.py   │   db_indexes.py   │   db_backfills.py       │
│                  │   db_build_indexes│   db_run_backfills.py   │
│                  │                   │                           │
└─────────────────────────────────────────────────────────────────┘
```

## 1. Migrations = Schema Only

**Location**: `server/db_migrate.py`

**Allowed**:
- ✅ `CREATE TABLE`
- ✅ `ALTER TABLE ADD COLUMN`
- ✅ `ALTER TABLE DROP COLUMN`
- ✅ `ALTER TABLE ADD CONSTRAINT` (UNIQUE, FOREIGN KEY, CHECK)
- ✅ `DROP TABLE`
- ✅ Metadata operations (small tables only)

**FORBIDDEN**:
- ❌ `CREATE INDEX` → Goes to `db_indexes.py`
- ❌ `UPDATE` on hot tables → Goes to `db_backfills.py`
- ❌ `INSERT INTO ... SELECT` → Goes to `db_backfills.py`
- ❌ `DELETE` on hot tables → Goes to `db_backfills.py`
- ❌ Any data backfill operations
- ❌ Any performance index creation

**Hot Tables** (NEVER backfill in migrations):
- `leads`
- `call_log`
- `receipts`
- `messages`
- `appointments`
- `whatsapp_message`

## 2. Indexes = Performance Only

**Location**: 
- `server/db_indexes.py` - Index definitions (registry)
- `server/db_build_indexes.py` - Index builder (runner)

**Allowed**:
- ✅ `CREATE INDEX CONCURRENTLY`
- ✅ `CREATE UNIQUE INDEX CONCURRENTLY` (for performance, not constraints)
- ✅ Partial indexes with `WHERE` clauses
- ✅ Multi-column indexes

**FORBIDDEN**:
- ❌ `ALTER TABLE` → Goes to `db_migrate.py`
- ❌ `UPDATE/INSERT/DELETE` → Goes to `db_backfills.py`
- ❌ Schema changes of any kind
- ❌ Data operations

**Key Properties**:
- Never fails deployment (exits 0 even on errors)
- Uses `CONCURRENTLY` to avoid table locks
- Retries on lock conflicts
- Can run while services are online

## 3. Backfills = Data Only

**Location**:
- `server/db_backfills.py` - Backfill definitions (registry)
- `server/db_run_backfills.py` - Backfill runner
- `server/db_backfill.py` - Wrapper (backward compat)

**Allowed**:
- ✅ `UPDATE` to populate existing columns
- ✅ `INSERT INTO` for data migration
- ✅ Batch processing with `FOR UPDATE SKIP LOCKED`
- ✅ Data transformations

**FORBIDDEN**:
- ❌ `ALTER TABLE` → Goes to `db_migrate.py`
- ❌ `CREATE INDEX` → Goes to `db_indexes.py`
- ❌ Schema changes
- ❌ Index creation

**Key Properties**:
- Never fails deployment (exits 0 even on errors)
- Idempotent (safe to run multiple times)
- Small batches (100 rows default)
- Uses `SKIP LOCKED` to avoid blocking
- Time-boxed execution (10 minutes default)
- Per-tenant processing to reduce contention

## Deployment Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    DEPLOYMENT SEQUENCE                           │
└─────────────────────────────────────────────────────────────────┘

1. Stop Services
   └─> Release database connections

2. Run Migrations (db_migrate.py)
   ├─> Schema changes ONLY
   ├─> MUST succeed (critical)
   └─> 5s lock timeout (fail fast)

3. Build Indexes (db_build_indexes.py)
   ├─> CREATE INDEX CONCURRENTLY
   ├─> Can warn but doesn't fail
   └─> 60s lock timeout with retries

4. Run Backfills (db_run_backfills.py)
   ├─> UPDATE/INSERT data operations
   ├─> Can warn but doesn't fail
   ├─> FOR UPDATE SKIP LOCKED
   └─> 5s lock timeout + skip locked rows

5. Start Services
   └─> All schema and indexes are ready
```

## Guard Tests

**Test**: `test_guard_no_backfills_in_migrations.py`

**Purpose**: Prevent violations of the ONE SOURCE OF TRUTH rule

**What it checks**:
- ❌ No `UPDATE/INSERT/DELETE` in migrations
- ❌ No `exec_dml()` calls in migrations
- ❌ No backfill comments in migrations
- ✅ Allows grandfathered migrations (to be migrated)

**When to run**: 
- Before every commit
- In CI/CD pipeline
- Before production deployment

## File Structure

```
server/
├── db_migrate.py              # 1. MIGRATIONS (Schema Only)
│   └─> exec_ddl()             # DDL operations with 5s timeout
│
├── db_indexes.py              # 2. INDEXES (Registry)
│   └─> INDEX_DEFS = [...]     # Index definitions
│
├── db_build_indexes.py        # 2. INDEXES (Runner)
│   └─> Runs INDEX_DEFS        # Creates indexes CONCURRENTLY
│
├── db_backfills.py            # 3. BACKFILLS (Registry)
│   └─> BACKFILL_DEFS = [...]  # Backfill definitions
│
├── db_run_backfills.py        # 3. BACKFILLS (Runner)
│   └─> Runs BACKFILL_DEFS     # Executes backfills
│
└── db_backfill.py             # 3. BACKFILLS (Wrapper - compat)
    └─> Calls db_run_backfills # Backward compatibility
```

## Examples

### ❌ WRONG - Backfill in Migration

```python
# In db_migrate.py (WRONG!)
def migration_99():
    # Add column
    exec_ddl(engine, "ALTER TABLE leads ADD COLUMN status VARCHAR(20)")
    
    # ❌ WRONG - Backfill in migration
    exec_dml(engine, "UPDATE leads SET status = 'active' WHERE status IS NULL")
```

### ✅ CORRECT - Separated

```python
# In db_migrate.py (Schema Only)
def migration_99():
    # Add column ONLY
    exec_ddl(engine, "ALTER TABLE leads ADD COLUMN status VARCHAR(20)")
    log.info("✅ Schema change complete. Backfill runs separately.")

# In db_backfills.py (Data Only)
def backfill_lead_status(engine, batch_size=100, max_time_seconds=600):
    """Populate status column on leads."""
    # Batched UPDATE with SKIP LOCKED
    # ...
    
BACKFILL_DEFS.append({
    'key': 'migration_99_lead_status',
    'migration_number': '99',
    'description': 'Populate status on leads',
    'tables': ['leads'],
    'function': backfill_lead_status,
})
```

### ❌ WRONG - Index in Migration

```python
# In db_migrate.py (WRONG!)
def migration_100():
    # Add column
    exec_ddl(engine, "ALTER TABLE leads ADD COLUMN last_activity_at TIMESTAMP")
    
    # ❌ WRONG - Index in migration
    exec_ddl(engine, "CREATE INDEX idx_leads_activity ON leads(last_activity_at)")
```

### ✅ CORRECT - Separated

```python
# In db_migrate.py (Schema Only)
def migration_100():
    # Add column ONLY
    exec_ddl(engine, "ALTER TABLE leads ADD COLUMN last_activity_at TIMESTAMP")
    log.info("✅ Schema change complete. Index built separately.")

# In db_indexes.py (Performance Only)
INDEX_DEFS.append({
    'name': 'idx_leads_activity',
    'table': 'leads',
    'sql': 'CREATE INDEX CONCURRENTLY idx_leads_activity ON leads(last_activity_at)',
    'priority': 'MEDIUM',
})
```

## Benefits of ONE SOURCE OF TRUTH

1. **Predictability**: Each operation type has one home
2. **Debuggability**: Easy to find where operations are defined
3. **Safety**: Migrations never fail due to lock timeouts on data
4. **Flexibility**: Backfills can be run independently
5. **Performance**: Indexes built separately with CONCURRENTLY
6. **Idempotency**: Each system is idempotent on its own
7. **Monitoring**: Clear separation for observability
8. **Testing**: Guard tests prevent violations

## Audit Reports

- `BACKFILL_AUDIT_REPORT.md` - Lists all existing backfills to migrate
- `audit_backfills.py` - Tool to scan for violations

## References

- `MIGRATION_GUIDELINES.md` - Detailed migration rules
- `INDEXING_GUIDE.md` - Index creation guidelines
- `MIGRATION_36_BACKFILL_SEPARATION.md` - Backfill separation example

## Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                    REMEMBER THE RULE                             │
│                                                                   │
│  ONE SOURCE OF TRUTH - NO DUPLICATIONS - NO EXCEPTIONS          │
│                                                                   │
│  Migrations  → Schema                                            │
│  Indexes     → Performance                                       │
│  Backfills   → Data                                              │
│                                                                   │
│  VIOLATION = PRODUCTION FAILURE                                  │
└─────────────────────────────────────────────────────────────────┘
```
