# Indexing Guide - Best Practices for Database Indexes

## Overview

This guide explains how database indexes are managed in the ProSaaS system to ensure reliable production deployments.

## The Problem We're Solving

Previously, migrations included `CREATE INDEX` statements. This caused problems:

- **Deployment failures**: Index creation could fail due to locks, blocking the entire deployment
- **Long migration times**: Heavy tables could take many minutes to index, holding locks
- **Duplicate definitions**: Indexes were scattered across migration files, making them hard to track
- **No retry mechanism**: If an index failed, the whole migration failed

## The Solution: Separate Index Building

We now separate index creation from schema migrations:

1. **Migrations** handle only schema changes (DDL) and critical data updates (DML)
2. **Index Builder** handles all performance indexes separately, after migrations complete
3. **Single Registry** defines all indexes in one place (`server/db_indexes.py`)

## Architecture

```
Deployment Flow:
┌──────────────────┐
│ Stop Services    │  ← Release DB connections
└────────┬─────────┘
         │
┌────────▼─────────┐
│ Run Migrations   │  ← Schema + Data only (no indexes)
└────────┬─────────┘
         │
┌────────▼─────────┐
│ Build Indexes    │  ← Separate, idempotent, non-blocking
└────────┬─────────┘
         │
┌────────▼─────────┐
│ Start Services   │  ← Deployment continues even if indexes fail
└──────────────────┘
```

## File Structure

- **`server/db_indexes.py`** - Single source of truth for all performance indexes
- **`server/db_build_indexes.py`** - Index builder script (idempotent, safe)
- **`server/db_migrate.py`** - Schema migrations only (no performance indexes)

## How to Add a New Index

### Step 1: Add to Index Registry

Edit `server/db_indexes.py` and add your index to the `INDEX_DEFS` list:

```python
INDEX_DEFS = [
    # ... existing indexes ...
    {
        "name": "idx_your_new_index",
        "sql": """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_your_new_index 
            ON your_table(your_column)
            WHERE your_condition  -- Optional: partial index
        """,
        "critical": False,  # True only if required for basic app functionality
        "description": "Brief description of what this index optimizes"
    },
]
```

### Step 2: Deploy

The index will be automatically built during the next deployment:

```bash
./scripts/deploy_production.sh --rebuild
```

If the index fails to build, deployment continues with a warning. You can retry later:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm indexer
```

## Index Definition Guidelines

### Always Use These Features

1. **`CONCURRENTLY`** - Never blocks table writes
   ```sql
   CREATE INDEX CONCURRENTLY IF NOT EXISTS ...
   ```

2. **`IF NOT EXISTS`** - Makes it idempotent (safe to run multiple times)
   ```sql
   CREATE INDEX CONCURRENTLY IF NOT EXISTS ...
   ```

3. **Partial Indexes** - Smaller, faster indexes when you have a WHERE clause
   ```sql
   ON table(column) WHERE condition
   ```

### Critical vs Non-Critical

- **Critical** (`critical: True`): Required for basic app functionality
  - Example: UNIQUE constraints needed for data integrity
  - Example: Indexes required for authentication/authorization queries
  
- **Non-Critical** (`critical: False`): Performance optimization only
  - Example: Indexes for filtering/sorting in UI
  - Example: Indexes for background job queries
  
Most indexes should be `critical: False`.

## What NOT to Do

### ❌ DO NOT Add Indexes to Migrations

```python
# ❌ BAD - Do not do this in db_migrate.py
exec_index(migrate_engine, """
    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_something
    ON some_table(some_column)
""")
```

### ✅ DO Add Indexes to Registry

```python
# ✅ GOOD - Do this in db_indexes.py
INDEX_DEFS = [
    {
        "name": "idx_something",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_something ON some_table(some_column)",
        "critical": False,
        "description": "Optimizes something queries"
    }
]
```

## Exception: When to Include Indexes in Migrations

**Only** in these rare cases:

1. **UNIQUE constraints** - These are schema constraints, not performance indexes
   ```sql
   ALTER TABLE users ADD CONSTRAINT unique_email UNIQUE (email);
   ```

2. **Foreign key constraints** - PostgreSQL automatically creates indexes for these
   ```sql
   ALTER TABLE orders ADD CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id);
   ```

3. **Primary keys** - These are structural, not performance indexes
   ```sql
   ALTER TABLE items ADD PRIMARY KEY (id);
   ```

## Running the Index Builder Manually

During development or troubleshooting:

```bash
# Run in development
python server/db_build_indexes.py

# Run in production (via Docker)
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm indexer
```

The script:
- ✅ Checks if each index exists before creating it
- ✅ Uses `CONCURRENTLY` to avoid blocking writes
- ✅ Retries on lock conflicts (10 attempts with backoff)
- ✅ Logs progress clearly
- ✅ Never fails deployment (exit 0 even on errors)

## Monitoring Index Build

During deployment, you'll see output like:

```
==================================================
Database Index Builder
==================================================

Connecting to database...
✅ Database connection successful

Found 3 index(es) to process

[1/3] Processing: idx_leads_last_call_direction
    Description: Index for filtering leads by call direction
    Critical: False
    🔨 Creating index (this may take a while)...
    ✅ Created index idx_leads_last_call_direction

[2/3] Processing: idx_call_log_lead_created
    Description: Partial index for call_log lookups
    Critical: False
    ⏭️  Already exists, skipping

[3/3] Processing: idx_leads_backfill_pending
    Description: Partial index for backfill operations
    Critical: False
    🔨 Creating index (this may take a while)...
    ✅ Created index idx_leads_backfill_pending

==================================================
Index Build Summary
==================================================
Total indexes:  3
Created:        2
Skipped:        1 (already existed)
Failed:         0

🎉 All indexes processed successfully!
```

## Troubleshooting

### Index Build Times Out

If index building times out due to locks:

1. **Wait for low traffic** - Run indexer during maintenance window
2. **Stop more services** - Ensure all DB-writing services are stopped
3. **Increase timeout** - Edit `lock_timeout` in `db_build_indexes.py` (default: 5 minutes)

### Index Build Fails

The deployment will continue anyway. To retry:

```bash
# Check which indexes are missing
psql $DATABASE_URL -c "\di"

# Retry index builder
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm indexer
```

### Performance Issues Without Indexes

If indexes aren't built yet, queries may be slower but will still work. The system is designed to function without these performance indexes, just not optimally.

## Summary

**The Golden Rules:**

1. ✅ All performance indexes go in `server/db_indexes.py`
2. ✅ Migrations handle schema + data only
3. ✅ Index builder runs separately after migrations
4. ✅ Deployment never fails due to index issues
5. ✅ Indexes can be retried independently

**Result:** Reliable deployments with clean, maintainable index management.

---

For questions or issues, see the deployment logs or check:
- `server/db_indexes.py` - Index definitions
- `server/db_build_indexes.py` - Index builder implementation
- `scripts/deploy_production.sh` - Deployment flow
