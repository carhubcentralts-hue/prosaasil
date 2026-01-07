# n8n PostgreSQL Connection Fix - Deployment Instructions

## Problem Fixed

n8n 2.2.4 was ignoring the `DB_POSTGRESDB_CONNECTION_STRING` environment variable and falling back to localhost (127.0.0.1:5432) instead of connecting to Supabase PgBouncer.

## Solution Applied

Replaced the connection string with individual connection parameters that n8n 2.2.4 properly respects.

### Changes Made

**File Modified:** `docker-compose.yml`

**Before:**
```yaml
environment:
  DB_TYPE: postgresdb
  DB_POSTGRESDB_CONNECTION_STRING: postgresql://postgres.jnawaedtdpiaymavzjra:SV1Stw7wYg7mkfe0@aws-1-ap-northeast-1.pooler.supabase.com:6543/postgres?sslmode=require&pgbouncer=true
```

**After:**
```yaml
environment:
  DB_TYPE: postgresdb
  DB_POSTGRESDB_HOST: aws-1-ap-northeast-1.pooler.supabase.com
  DB_POSTGRESDB_PORT: 6543
  DB_POSTGRESDB_DATABASE: postgres
  DB_POSTGRESDB_USER: postgres.jnawaedtdpiaymavzjra
  DB_POSTGRESDB_PASSWORD: SV1Stw7wYg7mkfe0
  DB_POSTGRESDB_SSL: "true"
```

## Deployment Steps

Run these commands in the exact order specified:

```bash
# 1. Stop and remove n8n container with volumes
docker compose down -v

# 2. Start n8n service
docker compose up -d n8n

# 3. Check logs to verify successful connection
docker logs --tail 100 prosaas-n8n
```

## Expected Results

✅ **Success Indicators:**
- n8n connects to `aws-1-ap-northeast-1.pooler.supabase.com:6543`
- No errors about `127.0.0.1:5432` or `::1` in logs
- n8n service starts and remains stable
- Database migrations complete successfully

❌ **Old Behavior (should NOT see):**
- Connection attempts to `127.0.0.1:5432`
- Connection attempts to `::1`
- "ECONNREFUSED" errors to localhost

## What Was NOT Changed

- ✅ Backend service - unchanged
- ✅ Frontend service - unchanged  
- ✅ Baileys service - unchanged
- ✅ Database passwords - kept the same
- ✅ n8n version - still 2.2.4
- ✅ No env_file added to n8n service

## Verification Command

To verify n8n is connecting to the correct database:

```bash
docker logs prosaas-n8n 2>&1 | grep -i "postgre\|connect\|database"
```

You should see logs indicating successful connection to the Supabase pooler, not localhost.

## Rollback Instructions

If needed, revert the change:

```bash
git revert <commit-hash>
docker compose down -v
docker compose up -d n8n
```

## Technical Notes

- **Why this fix works:** n8n 2.2.4 has a known issue where `DB_POSTGRESDB_CONNECTION_STRING` is not reliably enforced. Using individual parameters (HOST, PORT, USER, PASSWORD, etc.) forces n8n to use the correct connection details.
- **DNS resolution:** The `NODE_OPTIONS: --dns-result-order=ipv4first` flag was already present and helps ensure IPv4 is preferred over IPv6.
- **SSL mode:** Set to `"true"` (quoted string) to enable SSL for the Supabase connection.
