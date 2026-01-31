# Gmail Receipts Migration and Worker Resilience Fix

## Overview

This PR implements Migration 119 to create the `gmail_receipts` table and makes the worker more resilient by adding a `STRICT_SCHEMA_CHECK` environment variable.

## Problem Statement

The worker was crashing on startup when the `gmail_receipts` table didn't exist. In production environments, this causes queues to die and services to fail. The original requirements (in Hebrew) specified:

1. Add a real migration that creates the `gmail_receipts` table with indexes and deduplication
2. Make the worker not crash by default (but still allow strict mode when needed)
3. Ensure the table is checked but allows graceful degradation

## Changes Made

### 1. Migration 119: gmail_receipts Table

**File**: `server/db_migrate.py`

Added a new migration that creates the `gmail_receipts` table with:

#### Table Schema
- `id BIGSERIAL PRIMARY KEY` - Auto-incrementing primary key
- `business_id BIGINT NOT NULL` - Links to business (multi-tenant)
- `provider TEXT NOT NULL DEFAULT 'gmail'` - Receipt provider (gmail, etc.)
- `external_id TEXT NOT NULL` - Unique ID from provider (Gmail messageId)
- `subject TEXT` - Email subject
- `merchant TEXT` - Merchant/vendor name
- `amount NUMERIC(12,2)` - Receipt amount
- `currency CHAR(3)` - Currency code (ISO 4217)
- `receipt_date TIMESTAMPTZ` - Receipt date with timezone
- `raw_payload JSONB` - Raw JSON from parsing
- `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()` - Creation timestamp
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()` - Update timestamp

#### Indexes

**UNIQUE Index (Deduplication)**:
```sql
CREATE UNIQUE INDEX ux_gmail_receipts_business_provider_external
  ON gmail_receipts (business_id, provider, external_id)
```

This prevents duplicate receipts from being inserted. The combination of `(business_id, provider, external_id)` ensures each receipt is stored only once per business.

**Performance Indexes**:
```sql
-- For list queries sorted by creation date
CREATE INDEX ix_gmail_receipts_business_created_at
  ON gmail_receipts (business_id, created_at DESC)

-- For filtering by receipt date
CREATE INDEX ix_gmail_receipts_business_receipt_date
  ON gmail_receipts (business_id, receipt_date DESC)

-- For merchant filtering
CREATE INDEX ix_gmail_receipts_merchant
  ON gmail_receipts (merchant)
```

#### Idempotency

The migration uses:
- `IF NOT EXISTS` for table creation
- `IF NOT EXISTS` for all indexes
- Table existence check before running

This ensures the migration can be run multiple times safely without errors.

### 2. Worker Resilience: STRICT_SCHEMA_CHECK

**File**: `server/worker.py`

#### New Environment Variable

```bash
STRICT_SCHEMA_CHECK=0  # Default: non-strict mode (continues on missing tables)
STRICT_SCHEMA_CHECK=1  # Strict mode (exits on missing tables)
```

#### Behavior

**Non-Strict Mode (Default - `STRICT_SCHEMA_CHECK=0` or unset)**:
- Worker logs error messages about missing tables
- Worker continues startup
- Allows services to remain operational even if some features are unavailable
- Recommended for production to prevent total service outage

**Strict Mode (`STRICT_SCHEMA_CHECK=1`)**:
- Worker logs error messages about missing tables
- Worker exits with status code 1
- Forces migration to be run before worker starts
- Recommended for development and staging environments

#### Implementation

```python
STRICT_SCHEMA_CHECK = os.getenv("STRICT_SCHEMA_CHECK", "0") == "1"

def quick_schema_check():
    """Check for missing critical tables. Returns list of missing tables (empty if all present)."""
    # ... checks for critical tables ...
    return missing_tables  # Returns [] if all tables present

missing = quick_schema_check()
if missing:
    logger.error("❌ CRITICAL: DB schema appears outdated!")
    logger.error(f"❌ Missing tables: {missing}")
    logger.error("❌ Please run migrations first:")
    logger.error("❌   docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm migrate")
    
    if STRICT_SCHEMA_CHECK:
        sys.exit(1)
    
    logger.warning("⚠️ Continuing worker startup (non-strict mode).")
else:
    logger.info("✅ Schema check passed - all critical tables present")
```

### 3. Critical Tables List

The worker checks for these critical tables:
- `business` - Core tenant table
- `leads` - CRM data
- `receipts` - Existing receipts table
- `gmail_receipts` - **NEW** - Gmail receipts tracking

## Usage

### Running the Migration

```bash
# Run all pending migrations (including Migration 119)
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm migrate
```

### Worker Configuration

**Production (Recommended)**:
```bash
# Don't set STRICT_SCHEMA_CHECK or set to 0
# Worker will continue even if gmail_receipts is missing
docker compose up worker
```

**Development/Staging (Optional)**:
```bash
# Set STRICT_SCHEMA_CHECK=1 to enforce schema checks
STRICT_SCHEMA_CHECK=1 docker compose up worker
```

## Upsert Pattern for Future Code

When inserting receipts into the `gmail_receipts` table, use the upsert pattern to prevent duplicates:

### Option 1: Ignore Duplicates
```python
from sqlalchemy import text

db.session.execute(text("""
    INSERT INTO gmail_receipts (
        business_id, provider, external_id, 
        subject, merchant, amount, currency, receipt_date, raw_payload
    ) VALUES (
        :business_id, :provider, :external_id,
        :subject, :merchant, :amount, :currency, :receipt_date, :raw_payload
    )
    ON CONFLICT (business_id, provider, external_id) DO NOTHING
"""), {
    'business_id': business_id,
    'provider': 'gmail',
    'external_id': message_id,
    # ... other fields ...
})
```

### Option 2: Update on Conflict
```python
db.session.execute(text("""
    INSERT INTO gmail_receipts (
        business_id, provider, external_id, 
        subject, merchant, amount, currency, receipt_date, raw_payload
    ) VALUES (
        :business_id, :provider, :external_id,
        :subject, :merchant, :amount, :currency, :receipt_date, :raw_payload
    )
    ON CONFLICT (business_id, provider, external_id) 
    DO UPDATE SET 
        raw_payload = EXCLUDED.raw_payload, 
        updated_at = NOW()
"""), {
    # ... parameters ...
})
```

## Testing

Two test files were created to validate the changes:

1. **test_migration_119_gmail_receipts.py** - Validates SQL syntax and upsert patterns
2. **test_worker_strict_schema_check.py** - Validates worker behavior

Run tests:
```bash
python test_migration_119_gmail_receipts.py
python test_worker_strict_schema_check.py
```

## Verification Checklist

- [x] Migration 119 SQL syntax is valid
- [x] UNIQUE index prevents duplicates
- [x] Performance indexes support common queries
- [x] Migration is idempotent
- [x] Worker defaults to non-strict mode
- [x] Worker respects STRICT_SCHEMA_CHECK=1
- [x] gmail_receipts is in critical tables list
- [x] Upsert patterns are documented

## Deployment Notes

1. **Run Migration First**: Ensure Migration 119 is run before deploying worker changes
2. **Zero Downtime**: Migration can run while services are running (uses IF NOT EXISTS)
3. **Worker Rollout**: New worker version is backward compatible (non-strict mode allows operation without table)
4. **Production Safety**: Default non-strict mode prevents worker crashes

## Related Files

- `server/db_migrate.py` - Migration 119 implementation
- `server/worker.py` - STRICT_SCHEMA_CHECK implementation
- `test_migration_119_gmail_receipts.py` - Migration tests
- `test_worker_strict_schema_check.py` - Worker behavior tests
