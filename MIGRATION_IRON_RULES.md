# Migration Iron Rules - Database Stability on POOLER

## 🔥 THE PROBLEM

The system doesn't track what migrations have already run, and heavy UPDATE operations in migrations cause failures on connection poolers (POOLER). Every deployment risks:
- Re-running migrations that already executed
- Timeout failures on UPDATE/backfill operations
- Unable to resume after connection drops
- Deployments blocked by data operations

## 🎯 THE SOLUTION

**Single Source of Truth** for migration state + **Strict DDL/DML Separation**

---

## 📋 PART 1: Migration State Tracking

### The schema_migrations Table

```sql
CREATE TABLE IF NOT EXISTS schema_migrations (
    migration_id TEXT PRIMARY KEY,           -- e.g., "096"
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    success BOOLEAN NOT NULL DEFAULT TRUE,
    reconciled BOOLEAN NOT NULL DEFAULT FALSE,  -- auto-detected vs actually run
    notes TEXT
);
```

**Purpose**: Track which migrations have run, prevent re-runs, detect existing schema.

---

## 📋 PART 2: The run_migration() Wrapper

### IRON RULE: All Migrations MUST Use This Wrapper

```python
def run_migration(migration_id, fingerprint_fn, run_fn, engine):
    """
    Enhanced migration wrapper with fingerprint-based reconciliation.
    
    Returns: "SKIP" | "RECONCILE" | "RUN"
    """
```

### How It Works

1. **Check tracking table**: If already applied → **SKIP**
2. **Check fingerprint**: If schema exists in DB → **RECONCILE** (mark as applied, don't re-run)
3. **Otherwise**: **RUN** the migration

### Example: Migration 96

```python
# Step 1: Define fingerprint function
def fp_96():
    """Check if migration 96 schema already exists"""
    return (
        check_column_exists("leads", "name") and
        check_column_exists("leads", "name_source") and
        check_column_exists("leads", "name_updated_at") and
        check_column_exists("business", "whatsapp_system_prompt") and
        check_column_exists("business", "whatsapp_temperature") and
        check_column_exists("business", "whatsapp_model") and
        check_column_exists("business", "whatsapp_max_tokens")
    )

# Step 2: Define DDL-only migration function
def run_96():
    """Execute migration 96 DDL - schema changes only"""
    if check_table_exists('business'):
        if not check_column_exists('business', 'whatsapp_system_prompt'):
            exec_ddl(migrate_engine, """
                ALTER TABLE business 
                ADD COLUMN IF NOT EXISTS whatsapp_system_prompt TEXT
            """)
        # ... more DDL only ...
    
    if check_table_exists('leads'):
        if not check_column_exists('leads', 'name'):
            exec_ddl(migrate_engine, """
                ALTER TABLE leads 
                ADD COLUMN IF NOT EXISTS name VARCHAR(255)
            """)
        # ... more DDL only ...

# Step 3: Run with wrapper
run_migration("096", fp_96, run_96, migrate_engine)
```

**Key Points**:
- ✅ Fingerprint checks ALL columns the migration adds
- ✅ DDL only - no UPDATE/INSERT/DELETE
- ✅ Uses `exec_ddl()` helper (proper timeouts, retries)
- ✅ Idempotent - safe to run multiple times

---

## 📋 PART 3: DDL vs DML - The Iron Law

### ✅ ALLOWED in Migrations (DDL)

```sql
-- Add columns
ALTER TABLE leads ADD COLUMN name VARCHAR(255);

-- Create indexes (but prefer db_indexes.py for performance indexes)
CREATE UNIQUE INDEX IF NOT EXISTS idx_leads_email ON leads(email);

-- Add constraints (NOT VALID for heavy tables)
ALTER TABLE leads ADD CONSTRAINT chk_status 
CHECK (status IN ('new', 'contacted')) NOT VALID;

-- Validate constraints (separate step)
ALTER TABLE leads VALIDATE CONSTRAINT chk_status;
```

### ❌ FORBIDDEN in Migrations (DML)

```sql
-- NO UPDATE statements
UPDATE leads SET name = first_name || ' ' || last_name;  -- ❌ FORBIDDEN

-- NO INSERT for backfilling
INSERT INTO logs SELECT * FROM old_logs;  -- ❌ FORBIDDEN

-- NO DELETE for cleanup
DELETE FROM leads WHERE created_at < '2020-01-01';  -- ❌ FORBIDDEN
```

**Why?** These operations:
- Lock tables for long periods
- Cause timeouts on POOLER
- Cannot resume if connection drops
- Block deployment if they fail

---

## 📋 PART 4: Backfills - For Data Operations

### All DML Goes to db_backfills.py

```python
def backfill_96_lead_name(engine, batch_size=200, max_time_seconds=600):
    """
    Backfill lead names for Migration 96.
    
    POOLER-SAFE:
    - Uses batches of 200 rows
    - FOR UPDATE SKIP LOCKED
    - Commits per batch
    - Retry logic for connection errors
    """
    while iteration < max_iterations:
        try:
            with engine.begin() as conn:
                # POOLER-SAFE timeout policy
                conn.execute(text("SET lock_timeout = '15s'"))
                conn.execute(text("SET statement_timeout = '120s'"))
                
                # Batch update with SKIP LOCKED
                result = conn.execute(text("""
                    WITH batch AS (
                        SELECT id
                        FROM leads
                        WHERE name IS NULL
                          AND (first_name IS NOT NULL OR last_name IS NOT NULL)
                        LIMIT :batch_size
                        FOR UPDATE SKIP LOCKED
                    )
                    UPDATE leads
                    SET name = first_name || ' ' || last_name,
                        name_source = 'manual',
                        name_updated_at = NOW()
                    FROM batch
                    WHERE leads.id = batch.id
                """), {"batch_size": batch_size})
                
                rows_updated = result.rowcount
            
            # Success - continue to next batch
            if rows_updated == 0:
                return total_updated, True  # Complete
                
        except OperationalError as e:
            # Handle connection errors - retry
            if 'ssl connection' in str(e).lower():
                time.sleep(2.0)
                continue  # Retry this batch
            
            if 'lock_timeout' in str(e).lower():
                time.sleep(1.0)
                continue  # Skip and continue
```

### Register in BACKFILL_DEFS

```python
BACKFILL_DEFS = [
    {
        'key': 'migration_96_lead_name',
        'migration_number': '96',
        'description': 'Migrate first_name + last_name to unified name field',
        'tables': ['leads'],
        'batch_size': 200,
        'max_runtime_seconds': 600,
        'priority': 'HIGH',
        'safe_to_run_online': True,
        'function': backfill_96_lead_name,
        'status': 'active',
    },
]
```

### Run Backfills

```bash
# Run all active backfills
python server/db_run_backfills.py --all

# Run specific backfill
python server/db_run_backfills.py --only migration_96_lead_name

# Run with time limit
python server/db_run_backfills.py --all --max-minutes=10
```

**Key Features**:
- ✅ Exit 0 always (never fails deployment)
- ✅ Resume-safe (idempotent, continues from where it left off)
- ✅ POOLER-safe (batching, SKIP LOCKED, timeouts)
- ✅ Retry logic for connection errors

---

## 📋 PART 5: Connection Management

### Single Engine Throughout Migration Run

The system already implements this correctly:

```python
def apply_migrations():
    # 1. Create engine ONCE at start
    migrate_engine = get_migrate_engine()
    
    # 2. Use SAME engine for ALL operations
    ensure_migration_tracking_table(migrate_engine)
    reconcile_existing_state(migrate_engine)
    
    # 3. Pass SAME engine to all migrations
    run_migration("096", fp_96, run_96, migrate_engine)
    
    # ❌ NEVER call get_migrate_engine() again during run
```

**Why?** Connection choice (DIRECT vs POOLER) is made once and locked. Creating multiple engines causes:
- Inconsistent connection handling
- Lock conflicts
- Timeout issues

---

## 📋 PART 6: Deployment Safety

### Backfills and Indexes Never Fail Deployment

Both systems already implement this:

```python
# db_run_backfills.py - always exits 0
if results['failed']:
    logger.warning("⚠️  Some backfills failed, but deployment will continue")
    sys.exit(0)  # Always 0

# db_build_indexes.py - always exits 0
except Exception as e:
    logger.error(f"❌ Failed: {e}")
    sys.exit(0)  # Always 0
```

**Result**: Deployment succeeds even if backfills/indexes fail. They'll retry on next deployment.

---

## 📋 PART 7: Future Migration Checklist

When creating a new migration:

- [ ] Define fingerprint function that checks ALL added schema
- [ ] Define run function with ONLY DDL operations
- [ ] Use `run_migration(id, fingerprint_fn, run_fn, engine)` wrapper
- [ ] Use `exec_ddl()` for schema changes (proper timeouts)
- [ ] Move any UPDATE/INSERT/DELETE to db_backfills.py
- [ ] Register backfill in BACKFILL_DEFS
- [ ] Test idempotency (run twice, second run should SKIP/RECONCILE)
- [ ] Test on POOLER connection

### Migration Template

```python
# In apply_migrations() function:

# Define fingerprint
def fp_XXX():
    """Check if migration XXX schema exists"""
    return (
        check_column_exists("table", "column1") and
        check_column_exists("table", "column2")
    )

# Define DDL function
def run_XXX():
    """Execute migration XXX DDL - schema only"""
    if check_table_exists('table'):
        if not check_column_exists('table', 'column1'):
            exec_ddl(migrate_engine, """
                ALTER TABLE table 
                ADD COLUMN IF NOT EXISTS column1 VARCHAR(255)
            """)
        # More DDL...

# Run with wrapper
run_migration("XXX", fp_XXX, run_XXX, migrate_engine)
```

---

## 🎯 Summary: The Four Guarantees

1. **No Re-runs**: schema_migrations table tracks what's applied
2. **No Failures on POOLER**: DDL in migrations, DML in backfills
3. **Resume-Safe**: Backfills use batching + SKIP LOCKED
4. **No Blocked Deployments**: Backfills/indexes always exit 0

---

## 📚 References

- **Migrations**: `server/db_migrate.py` - Schema changes only
- **Backfills**: `server/db_backfills.py` - Data operations registry
- **Backfill Runner**: `server/db_run_backfills.py` - Execute backfills
- **Index Builder**: `server/db_build_indexes.py` - Build indexes
- **Index Definitions**: `server/db_indexes.py` - Index registry

---

## ⚠️ Breaking These Rules = Production Failure

- Re-running migrations → Duplicate constraints, "already exists" errors
- UPDATE in migrations → Timeout on POOLER, blocked deployment
- No fingerprint → Can't detect existing state, will fail on re-run
- No batching in backfills → Locks entire table, timeout on POOLER
- Failing deployments on backfill errors → Cannot deploy until data operation completes

**Follow these rules and migrations will be stable, resumable, and never block deployment.**
