# Migration Guidelines - ProSaaS Database Migrations

## Overview

This document provides comprehensive guidelines for adding and managing database migrations in the ProSaaS system. Following these guidelines ensures production stability, prevents data loss, and avoids lock-related issues.

## Table of Contents

1. [The Iron Laws of Migrations](#the-iron-laws-of-migrations)
2. [Migration System Architecture](#migration-system-architecture)
3. [When to Add a Migration](#when-to-add-a-migration)
4. [How to Add a New Migration](#how-to-add-a-new-migration)
5. [DDL vs DML - Critical Differences](#ddl-vs-dml---critical-differences)
6. [Batching Large Data Operations](#batching-large-data-operations)
7. [Testing Migrations](#testing-migrations)
8. [Deployment Process](#deployment-process)
9. [Troubleshooting](#troubleshooting)
10. [Common Patterns](#common-patterns)

---

## The Iron Laws of Migrations

**למנוע תקלות בפרודקשן - אלו החוקים שאסור להפר:**

### 1️⃣ NEVER use `db.session.execute()` for migrations

```python
# ❌ BAD - Don't do this!
db.session.execute(text("ALTER TABLE users ADD COLUMN age INTEGER"))

# ✅ GOOD - Always use exec_ddl for schema changes
exec_ddl(migrate_engine, "ALTER TABLE users ADD COLUMN age INTEGER")
```

**Why?** `db.session.execute()` doesn't have proper timeout handling, retry logic, or lock debugging.

### 2️⃣ DDL operations MUST use `exec_ddl()`

Schema changes (structure):
- `CREATE TABLE`, `ALTER TABLE`, `DROP TABLE`
- `CREATE INDEX`, `DROP INDEX`
- `ADD CONSTRAINT`, `DROP CONSTRAINT`

```python
migrate_engine = get_migrate_engine()
exec_ddl(migrate_engine, """
    CREATE TABLE new_feature (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL
    )
""")
```

**Characteristics:**
- `lock_timeout = 5s` (fail fast)
- `statement_timeout = 120s`
- Automatic retry on connection errors
- Lock debugging on failure

### 3️⃣ DML operations MUST use `exec_dml()`

Data changes (content):
- `UPDATE`, `INSERT`, `DELETE`
- Large backfills
- Data transformations

```python
migrate_engine = get_migrate_engine()
exec_dml(migrate_engine, """
    UPDATE users 
    SET status = 'active' 
    WHERE last_login > NOW() - INTERVAL '30 days'
""")
```

**Characteristics:**
- `lock_timeout = 60s` (longer for busy tables)
- `statement_timeout = 0` (unlimited)
- Retries on both connection AND lock errors
- Detects `LockNotAvailable` specifically

### 4️⃣ Always use batching for large updates

**❌ BAD - Single large update:**
```python
exec_dml(migrate_engine, "UPDATE leads SET status = 'new' WHERE status IS NULL")
# Locks entire table for minutes!
```

**✅ GOOD - Batched update:**
```python
batch_size = 1000
for iteration in range(10000):  # Safety limit
    rows_updated = exec_dml(migrate_engine, """
        WITH batch AS (
            SELECT id FROM leads 
            WHERE status IS NULL 
            LIMIT :batch_size
        )
        UPDATE leads l
        SET status = 'new'
        FROM batch b
        WHERE l.id = b.id
    """, params={"batch_size": batch_size})
    
    if rows_updated == 0:
        break  # No more rows
    
    time.sleep(0.1)  # Small delay between batches
```

### 5️⃣ Create supporting indexes BEFORE backfills

```python
# Step 1: Create indexes FIRST
exec_sql(migrate_engine, """
    CREATE INDEX IF NOT EXISTS idx_leads_status_null 
    ON leads(id) 
    WHERE status IS NULL
""", autocommit=True)

# Step 2: Then do the backfill (will be much faster)
# ... batched update code ...
```

### 6️⃣ All operations MUST be idempotent

Every migration must be safe to run multiple times:

```python
# ✅ GOOD - Idempotent patterns
CREATE TABLE IF NOT EXISTS users (...)
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)
ALTER TABLE users ADD COLUMN IF NOT EXISTS age INTEGER

# Check before DROP
IF EXISTS (SELECT 1 FROM information_schema.columns 
           WHERE table_name = 'users' AND column_name = 'old_col')
THEN
    ALTER TABLE users DROP COLUMN old_col;
END IF;
```

---

## Migration System Architecture

### File Structure

```
server/
├── db_migrate.py          # Main migration file
│   ├── exec_ddl()         # For DDL operations (schema changes)
│   ├── exec_dml()         # For DML operations (data changes)
│   ├── exec_sql()         # Lower-level SQL execution
│   ├── fetch_all()        # Query execution with retry
│   └── apply_migrations() # Main migration runner
```

### Migration Execution Flow

```
1. Docker Compose starts
2. migrate service runs FIRST
   ↓
3. Runs: python -m server.db_migrate
   ↓
4. apply_migrations() executes:
   - Checks SERVICE_ROLE (skip if worker)
   - Acquires PostgreSQL advisory lock
   - Runs DB stability checks
   - Applies pending migrations in order
   - Releases lock
   ↓
5. migrate service exits with success
   ↓
6. Other services start (prosaas-api, worker, scheduler)
```

### Lock Policies

| Operation Type | Timeout Policy | Use Case |
|---------------|----------------|----------|
| **DDL** (exec_ddl) | lock_timeout=5s<br>statement_timeout=120s | Schema changes<br>Fail fast on contention |
| **DML** (exec_dml) | lock_timeout=60s<br>statement_timeout=0 | Data operations<br>Handle busy tables |
| **Query** (fetch_all) | AUTOCOMMIT<br>No timeouts | Metadata queries<br>Fast read-only |

---

## When to Add a Migration

Add a migration when you need to:

1. **Schema Changes**
   - Add/remove tables
   - Add/remove columns
   - Add/remove indexes
   - Modify constraints

2. **Data Changes**
   - Backfill new columns with data
   - Transform existing data
   - Clean up/fix corrupted data

3. **Reference Data**
   - Seed initial data
   - Update configuration tables

**Do NOT add migrations for:**
- Application code changes (put in regular code)
- Temporary development changes
- Test data (use fixtures/seeds)

---

## How to Add a New Migration

### Step 1: Identify Migration Number

Find the last migration number in `server/db_migrate.py`:

```bash
grep -n "# Migration [0-9]" server/db_migrate.py | tail -5
```

Your new migration will be the next number (e.g., if last is 118, yours is 119).

### Step 2: Choose the Right Pattern

#### Pattern A: Simple DDL (Add Column/Index)

```python
# Migration 119: Add email_verified column to users
if check_table_exists('users'):
    try:
        migrate_engine = get_migrate_engine()
        
        # Add column using DO block for idempotency
        exec_sql(migrate_engine, """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'users' AND column_name = 'email_verified'
                ) THEN
                    ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT false;
                    RAISE NOTICE 'Added users.email_verified';
                END IF;
            END;
            $$;
        """, autocommit=True)
        
        # Add index
        exec_sql(migrate_engine, """
            CREATE INDEX IF NOT EXISTS idx_users_email_verified 
            ON users(email_verified)
        """, autocommit=True)
        
        migrations_applied.append("add_users_email_verified")
        log.info("✅ Applied migration 119: add_users_email_verified")
    except Exception as e:
        log.error(f"❌ Migration 119 failed: {e}")
        db.session.rollback()
        raise
```

#### Pattern B: Data Backfill (Small Dataset < 10K rows)

```python
# Migration 120: Backfill email_verified from email_confirmations table
if check_table_exists('users') and check_table_exists('email_confirmations'):
    try:
        migrate_engine = get_migrate_engine()
        checkpoint("Backfilling email_verified from email_confirmations...")
        
        # Simple update for small dataset
        rows_updated = exec_dml(migrate_engine, """
            UPDATE users u
            SET email_verified = true
            FROM email_confirmations ec
            WHERE u.id = ec.user_id 
              AND ec.confirmed_at IS NOT NULL
              AND u.email_verified = false
        """)
        
        checkpoint(f"✅ Backfilled {rows_updated} users")
        migrations_applied.append("backfill_email_verified")
        log.info("✅ Applied migration 120: backfill_email_verified")
    except Exception as e:
        log.error(f"❌ Migration 120 failed: {e}")
        db.session.rollback()
        raise
```

#### Pattern C: Large Backfill (> 10K rows) - BATCHED BY BUSINESS

```python
# Migration 121: Backfill lead scores from interactions
if check_table_exists('leads') and check_table_exists('interactions'):
    try:
        migrate_engine = get_migrate_engine()
        
        # Step 1: Create supporting indexes FIRST
        checkpoint("Adding supporting indexes for backfill...")
        exec_sql(migrate_engine, """
            CREATE INDEX IF NOT EXISTS idx_interactions_lead_score 
            ON interactions(lead_id, score) 
            WHERE lead_id IS NOT NULL
        """, autocommit=True)
        
        exec_sql(migrate_engine, """
            CREATE INDEX IF NOT EXISTS idx_leads_score_pending 
            ON leads(tenant_id, id) 
            WHERE total_score IS NULL
        """, autocommit=True)
        
        # Step 2: Backfill by business (batched)
        checkpoint("Backfilling lead scores (batched by business)...")
        
        # Get businesses that need backfill
        with migrate_engine.connect() as conn:
            result = conn.execute(text("""
                SELECT DISTINCT tenant_id 
                FROM leads 
                WHERE total_score IS NULL
                  AND tenant_id IS NOT NULL
                ORDER BY tenant_id
            """))
            tenant_ids = [row[0] for row in result.fetchall()]
        
        if not tenant_ids:
            checkpoint("✅ No leads require backfill")
        else:
            total_updated = 0
            batch_size = 1000
            
            for tenant_id in tenant_ids:
                business_total = 0
                
                for iteration in range(10000):  # Safety limit
                    rows_updated = exec_dml(migrate_engine, """
                        WITH batch AS (
                            SELECT id
                            FROM leads
                            WHERE tenant_id = :tenant_id 
                              AND total_score IS NULL
                            ORDER BY id
                            LIMIT :batch_size
                        ),
                        scores AS (
                            SELECT 
                                i.lead_id,
                                SUM(i.score) as total
                            FROM interactions i
                            JOIN batch b ON b.id = i.lead_id
                            GROUP BY i.lead_id
                        )
                        UPDATE leads l
                        SET total_score = s.total
                        FROM scores s
                        WHERE l.id = s.lead_id
                    """, params={"tenant_id": tenant_id, "batch_size": batch_size})
                    
                    business_total += rows_updated
                    total_updated += rows_updated
                    
                    if rows_updated == 0:
                        break
                    
                    # Log progress every 10 batches
                    if (iteration + 1) % 10 == 0 or rows_updated < batch_size:
                        checkpoint(f"  Business {tenant_id}: {business_total} rows")
                    
                    time.sleep(0.1)  # Small delay
                
                if business_total > 0:
                    checkpoint(f"  ✅ Business {tenant_id}: {business_total} rows")
            
            checkpoint(f"✅ Backfilled {total_updated} total leads")
        
        migrations_applied.append("backfill_lead_scores")
        log.info("✅ Applied migration 121: backfill_lead_scores")
    except Exception as e:
        log.error(f"❌ Migration 121 failed: {e}")
        db.session.rollback()
        raise
```

### Step 3: Test Locally

```bash
# 1. Drop the changes (if already applied)
psql -d your_db -c "ALTER TABLE users DROP COLUMN IF EXISTS email_verified;"
psql -d your_db -c "DROP INDEX IF EXISTS idx_users_email_verified;"

# 2. Run migration
docker compose up migrate

# 3. Verify it worked
psql -d your_db -c "\d users"  # Check column exists

# 4. Test idempotency - run again (should succeed with no changes)
docker compose up migrate

# 5. Check logs
docker compose logs migrate | grep -i "migration 119"
```

---

## DDL vs DML - Critical Differences

### DDL (Data Definition Language) - Schema Changes

**What:** Structure changes
- CREATE/ALTER/DROP TABLE
- CREATE/DROP INDEX
- ADD/DROP CONSTRAINT

**Use:** `exec_ddl()`

**Timeouts:**
- lock_timeout = 5s (fail fast)
- statement_timeout = 120s

**When it fails:**
- Another process is altering the same table
- Long-running query is using the table
- Idle-in-transaction connection holds lock

**What to do:**
1. Check running services: `docker compose ps`
2. Check locks: See troubleshooting section
3. Stop services before migration if needed

### DML (Data Manipulation Language) - Data Changes

**What:** Content changes
- UPDATE/INSERT/DELETE
- Backfills
- Data transformations

**Use:** `exec_dml()` with batching

**Timeouts:**
- lock_timeout = 60s (longer)
- statement_timeout = 0 (unlimited)

**When it fails:**
- Heavy table load
- Lock contention between businesses
- Missing indexes (table scan)

**What to do:**
1. Add supporting indexes FIRST
2. Batch by business (tenant_id)
3. Use smaller batches (500-1000 rows)
4. Add delays between batches

---

## Batching Large Data Operations

### Why Batch?

- ✅ Short-lived locks (1-2 seconds per batch vs minutes for full table)
- ✅ Other queries can proceed between batches
- ✅ Progress visibility
- ✅ Safer - can stop/resume if needed

### Batching Template

```python
def batch_update_template(migrate_engine, table_name, condition, update_expr):
    """Template for batched updates"""
    total_updated = 0
    batch_size = 1000
    max_iterations = 10000
    
    for iteration in range(max_iterations):
        rows_updated = exec_dml(migrate_engine, f"""
            WITH batch AS (
                SELECT id
                FROM {table_name}
                WHERE {condition}
                ORDER BY id
                LIMIT :batch_size
            )
            UPDATE {table_name} t
            SET {update_expr}
            FROM batch b
            WHERE t.id = b.id
        """, params={"batch_size": batch_size})
        
        total_updated += rows_updated
        
        if rows_updated == 0:
            break
        
        if (iteration + 1) % 10 == 0:
            checkpoint(f"  Processed {total_updated} rows...")
        
        time.sleep(0.1)
    
    return total_updated
```

### Batching by Business (Best Practice)

```python
# Get businesses needing update
with migrate_engine.connect() as conn:
    result = conn.execute(text("""
        SELECT DISTINCT tenant_id 
        FROM leads 
        WHERE needs_update = true
          AND tenant_id IS NOT NULL
    """))
    tenant_ids = [row[0] for row in result.fetchall()]

# Process each business separately
for tenant_id in tenant_ids:
    # ... batch update for this business only ...
```

**Why?** Eliminates cross-tenant lock contention.

---

## Testing Migrations

### Local Testing Checklist

- [ ] **Test first run** - Apply migration on clean database
- [ ] **Test idempotency** - Run migration again (should succeed with no changes)
- [ ] **Test with data** - Populate tables with realistic data volumes
- [ ] **Test rollback** - Drop changes and reapply (ensures it can recover)
- [ ] **Check indexes** - Verify indexes were created: `\di` in psql
- [ ] **Check performance** - Time the migration with production-like data
- [ ] **Check logs** - Look for errors, warnings, or unexpected behavior

### Testing Commands

```bash
# 1. Reset migration state
psql -d your_db << EOF
ALTER TABLE your_table DROP COLUMN IF EXISTS new_column;
DROP INDEX IF EXISTS idx_new_index;
EOF

# 2. Run migration
docker compose up migrate

# 3. Check results
docker compose logs migrate | tail -50
psql -d your_db -c "\d your_table"
psql -d your_db -c "SELECT COUNT(*) FROM your_table WHERE new_column IS NOT NULL;"

# 4. Test idempotency
docker compose up migrate  # Should succeed again

# 5. Check timing
time docker compose up migrate
```

---

## Deployment Process

### Docker Compose (Recommended)

```bash
# 1. Stop all services
docker compose down

# 2. Pull/rebuild
docker compose build

# 3. Start (migrations run automatically via migrate service)
docker compose up -d

# 4. Check migration logs
docker compose logs migrate

# 5. Check service health
docker compose ps
```

### Manual / Cloud Run

```bash
# 1. Stop all database-connected services
kill <api-pid> <worker-pid> <scheduler-pid>

# 2. Run migrations
RUN_MIGRATIONS_ON_START=1 python -m server.db_migrate

# 3. Start services
./start_production.sh
```

---

## Troubleshooting

### Problem: Migration fails with LockNotAvailable

**Symptoms:**
```
psycopg2.errors.LockNotAvailable: canceling statement due to lock timeout
```

**Diagnosis:**
```sql
-- Check for blocking queries
SELECT * FROM pg_stat_activity 
WHERE state != 'idle' 
ORDER BY state_change;

-- Check for idle transactions (bad!)
SELECT pid, state, state_change, query 
FROM pg_stat_activity 
WHERE state = 'idle in transaction';
```

**Solutions:**
1. Stop services before migration
2. Terminate idle transactions:
   ```sql
   SELECT pg_terminate_backend(pid) 
   FROM pg_stat_activity 
   WHERE state = 'idle in transaction' 
   AND state_change < now() - interval '30 seconds';
   ```
3. Use DML batching for large updates

### Problem: Migration is too slow

**Symptoms:**
- Takes more than 5 minutes
- Locks tables for extended periods

**Solutions:**
1. Add supporting indexes BEFORE backfill
2. Use smaller batches (500 rows instead of 1000)
3. Batch by business (tenant_id)
4. Consider running backfill as background job after deployment

### Problem: Migration applied but didn't update data

**Check:**
```sql
-- Did the UPDATE actually match any rows?
SELECT COUNT(*) FROM your_table WHERE condition = true;

-- Is there a WHERE clause filtering too aggressively?
-- Review your UPDATE WHERE condition
```

---

## Common Patterns

### Add Column with Index

```python
exec_sql(migrate_engine, """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'users' AND column_name = 'status'
        ) THEN
            ALTER TABLE users ADD COLUMN status VARCHAR(32) DEFAULT 'active';
        END IF;
    END;
    $$;
""", autocommit=True)

exec_sql(migrate_engine, """
    CREATE INDEX IF NOT EXISTS idx_users_status ON users(status)
""", autocommit=True)
```

### Add Foreign Key Constraint

```python
exec_ddl(migrate_engine, """
    ALTER TABLE orders 
    ADD CONSTRAINT fk_orders_user 
    FOREIGN KEY (user_id) REFERENCES users(id)
""")
```

### Create Table with Indexes

```python
exec_ddl(migrate_engine, """
    CREATE TABLE IF NOT EXISTS notifications (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id),
        message TEXT NOT NULL,
        read_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

exec_sql(migrate_engine, """
    CREATE INDEX IF NOT EXISTS idx_notifications_user 
    ON notifications(user_id, created_at)
""", autocommit=True)
```

---

## Summary

✅ **Always use `exec_ddl()` for schema changes**
✅ **Always use `exec_dml()` for data changes**
✅ **Always batch large updates (1000 rows per batch)**
✅ **Always batch by business (tenant_id) when possible**
✅ **Always create indexes BEFORE backfills**
✅ **Always make migrations idempotent**
✅ **Always test locally before production**

❌ **Never use `db.session.execute()` for migrations**
❌ **Never do large UPDATE without batching**
❌ **Never skip indexes for backfills**
❌ **Never assume services are stopped during migration**

---

## Need Help?

- Review: `server/db_migrate.py` - See existing migration patterns
- Review: `MIGRATION_36_DEPLOYMENT_GUIDE.md` - Production-ready example
- Review: This file - Comprehensive guidelines

**When in doubt, ask!** Better to ask than to cause production downtime.
