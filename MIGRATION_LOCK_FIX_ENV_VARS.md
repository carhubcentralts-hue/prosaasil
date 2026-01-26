# Migration Lock Timeout Fix - Environment Variables

This document describes the new environment variables introduced to fix migration lock timeout issues.

## New Environment Variables

### `RUN_MIGRATIONS`
**Purpose**: Controls which container is allowed to run database migrations.

**Values**: 
- `"1"` - Container will run migrations on startup
- `"0"` (default) - Container will skip migrations

**Recommended Setup**:
```yaml
services:
  prosaas-api:
    environment:
      RUN_MIGRATIONS: "1"  # Only API runs migrations
  
  worker:
    environment:
      RUN_MIGRATIONS: "0"  # Worker never runs migrations
  
  prosaas-calls:
    environment:
      RUN_MIGRATIONS: "0"  # Calls service never runs migrations
```

**Why**: Prevents multiple containers from trying to run migrations simultaneously, which causes lock conflicts and timeouts.

---

### `MIGRATION_LOCK_WAIT_SECONDS`
**Purpose**: Maximum time (in seconds) to wait for the migration lock before giving up.

**Default**: `30` seconds

**Range**: Any positive integer

**Example**:
```bash
MIGRATION_LOCK_WAIT_SECONDS=60  # Wait up to 60 seconds for lock
```

**When to Change**:
- Increase if migrations typically take longer than 30 seconds
- Decrease for faster startup when migrations are already running elsewhere

---

### `MIGRATION_STATEMENT_TIMEOUT`
**Purpose**: PostgreSQL statement timeout for the migration connection.

**Default**: `"120s"` (120 seconds)

**Format**: PostgreSQL interval format (e.g., `"120s"`, `"2min"`, `"0.5h"`)

**Example**:
```bash
MIGRATION_STATEMENT_TIMEOUT="180s"  # 3 minute timeout
```

**Why**: Prevents PostgreSQL from killing the lock acquisition query if it takes too long. The default database `statement_timeout` may be too low for migration operations.

---

## Migration Behavior

### With RUN_MIGRATIONS=1
1. Container checks if another container is running migrations (tries `pg_try_advisory_lock`)
2. If lock acquired immediately → runs migrations
3. If lock busy → retries for `MIGRATION_LOCK_WAIT_SECONDS` seconds
4. If lock still busy after timeout → **skips migrations gracefully** (doesn't crash)

### With RUN_MIGRATIONS=0
Container immediately skips migrations without trying to acquire the lock.

### Graceful Skip
When migrations are skipped (due to lock timeout or RUN_MIGRATIONS=0):
- Container continues to start normally
- Logs clearly indicate migrations were skipped
- **System does NOT crash** - this is safe because migrations will run in another container

---

## Logging

### Migration Lock Logs
```
🔧 MIGRATION CHECKPOINT: Starting apply_migrations()
✅ Set statement_timeout to 120s for migration connection
✅ Acquired migration lock
... migrations run ...
✅ Released migration lock
```

### Graceful Skip Logs
```
⚠️ MIGRATION CHECKPOINT: Could not acquire lock in time -> skipping migrations
   Waited 30s but another process is running migrations
   This is SAFE - migrations will run in another container
```

### Disabled Logs
```
🚫 MIGRATIONS_DISABLED: RUN_MIGRATIONS is not set to '1'
   Migrations are disabled for this service
```

---

## Worker Logging

New structured logs for recording worker help debug the "recording loop" issue:

- `[WORKER_PICKED]` - Job pulled from queue
- `[WORKER_SLOT_ACQUIRED]` - Per-business slot acquired
- `[WORKER_DOWNLOAD_DONE]` - Recording downloaded successfully
- `[WORKER_RELEASE_SLOT]` - Slot released for next job
- `[WORKER_JOB_FAILED]` - Job failed with error

Example:
```
🎯 [WORKER_PICKED] job_type=download_only call_sid=CA123... business_id=42
✅ [WORKER_SLOT_ACQUIRED] call_sid=CA123... business_id=42
✅ [WORKER_DOWNLOAD_DONE] call_sid=CA123... file=CA123.mp3 bytes=1234567
🔓 [WORKER_RELEASE_SLOT] call_sid=CA123... business_id=42 reason=success
```

---

## Troubleshooting

### Issue: Container crashes on startup with "Migration failed"
**Solution**: Check logs for lock timeout. Increase `MIGRATION_LOCK_WAIT_SECONDS` or ensure only one container has `RUN_MIGRATIONS=1`.

### Issue: Migrations never run
**Solution**: Ensure at least one container (typically `prosaas-api`) has `RUN_MIGRATIONS=1`.

### Issue: Multiple containers trying to run migrations
**Solution**: Set `RUN_MIGRATIONS=0` for all containers except the designated one (usually `prosaas-api`).

### Issue: Statement timeout error during migrations
**Solution**: Increase `MIGRATION_STATEMENT_TIMEOUT` to a higher value (e.g., `"180s"`).

---

## Migration Safety

All changes maintain existing safety guarantees:
- ✅ No data loss - FAQs and leads are never deleted
- ✅ Lock prevents concurrent migrations
- ✅ Graceful skip doesn't crash the system
- ✅ Only one container runs migrations (configured via RUN_MIGRATIONS)
- ✅ Lock timeout doesn't cause system-wide failure

---

## Backward Compatibility

The legacy `RUN_MIGRATIONS_ON_START` variable is still supported but **RUN_MIGRATIONS takes precedence**:
- If `RUN_MIGRATIONS` is set, it controls migration behavior
- If `RUN_MIGRATIONS` is not set, falls back to checking `SERVICE_ROLE`

This ensures existing deployments continue to work while new deployments can use the more explicit `RUN_MIGRATIONS` variable.
