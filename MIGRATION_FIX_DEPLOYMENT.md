# Database Migration Fix - Deployment Guide

## Problem Summary
The backend logs showed two database errors:
1. `appointments.call_transcript` column does not exist
2. `whatsapp_broadcasts.idempotency_key` column does not exist

## Solution
Added two new migrations to `server/db_migrate.py`:
- **Migration 48**: Adds `call_transcript` column to `appointments` table
- **Migration 49**: Adds `idempotency_key` column to `whatsapp_broadcasts` table with index

## How to Run Migrations

### Option 1: Automatic (Recommended)
The migrations will run automatically when the backend starts. Just restart the backend container:

```bash
docker-compose restart backend
```

Or if running manually:
```bash
python run_server.py
```

### Option 2: Manual Execution
Run migrations explicitly before starting the server:

```bash
# Using the migration script
./run_migrations.sh

# Or using Python module directly
export MIGRATION_MODE=1
export ASYNC_LOG_QUEUE=0
python -m server.db_migrate
```

### Option 3: Docker Container
If the backend is already running in Docker:

```bash
docker exec prosaas-backend python -m server.db_migrate
```

## Verification

After running migrations, verify the columns exist:

```sql
-- Check appointments table
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'appointments' 
AND column_name = 'call_transcript';

-- Check whatsapp_broadcasts table
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'whatsapp_broadcasts' 
AND column_name = 'idempotency_key';

-- Check index was created
SELECT indexname 
FROM pg_indexes 
WHERE tablename = 'whatsapp_broadcasts' 
AND indexname = 'idx_wa_broadcast_idempotency';
```

Expected results:
- `appointments.call_transcript` should be TEXT type
- `whatsapp_broadcasts.idempotency_key` should be VARCHAR(64) type
- Index `idx_wa_broadcast_idempotency` should exist

## Migration Safety

Both migrations are **idempotent** - safe to run multiple times:
- They check if columns exist before adding them
- They use proper transaction handling with rollback on error
- They create indexes with `IF NOT EXISTS` clause

## Testing

Run the test suite to verify migrations:

```bash
python test_migrations_48_49.py
```

Expected output:
```
✅ All checks passed! Migrations 48 and 49 are correctly implemented.
```

## What This Fixes

### Before
- Calendar page crashed with 500 error: "column appointments.call_transcript does not exist"
- WhatsApp broadcasts failed: "column whatsapp_broadcasts.idempotency_key does not exist"

### After
- Calendar appointments load successfully
- WhatsApp broadcast campaigns work properly with duplicate prevention
- Full conversation transcripts can be stored with appointments

## Additional Notes

### About the 403 Error
The 403 error for `/api/admin/businesses` is **expected behavior**:
- This route is restricted to `system_admin` role only
- Users with `owner` role cannot access the global list of all businesses
- This is a security feature, not a bug
- If a frontend component tries to access this route with non-admin role, it should:
  - Either check the user's role first and hide the component
  - Or handle the 403 error gracefully and show appropriate message

### Migration Details

**Migration 48: Appointments Call Transcript**
- Adds `call_transcript TEXT` column to `appointments` table
- Stores full conversation transcript from calls that create appointments
- Complements `call_summary` which stores AI-generated summary

**Migration 49: WhatsApp Broadcast Idempotency**
- Adds `idempotency_key VARCHAR(64)` column to `whatsapp_broadcasts` table
- Creates index `idx_wa_broadcast_idempotency` for efficient lookups
- Prevents duplicate broadcast campaigns from being created

## Rollback (if needed)

If you need to rollback these migrations (not recommended):

```sql
-- Remove Migration 49
DROP INDEX IF EXISTS idx_wa_broadcast_idempotency;
ALTER TABLE whatsapp_broadcasts DROP COLUMN IF EXISTS idempotency_key;

-- Remove Migration 48
ALTER TABLE appointments DROP COLUMN IF EXISTS call_transcript;
```

## Next Steps

After deployment:
1. ✅ Verify migrations ran successfully (check logs for "Migration 48" and "Migration 49")
2. ✅ Test calendar page loads without errors
3. ✅ Test WhatsApp broadcast creation works
4. ✅ Monitor logs for any database-related errors
