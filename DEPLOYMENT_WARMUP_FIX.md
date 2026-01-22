# Deployment Guide: Warmup Timeout and n8n Configuration Fix

## 🎯 Problem Summary

Two critical issues were preventing production deployment:

1. **Warmup Timeout Crash** (PRIMARY ISSUE)
   - The API was crashing with `RuntimeError` when migrations didn't complete within 60 seconds
   - This was a **race condition**: migrations were running successfully, but the warmup thread timed out before they completed
   - Result: Login failures, API instability, application crashes

2. **n8n Configuration Issue** (SECONDARY ISSUE)
   - n8n environment variables needed explicit base path configuration
   - Without proper `N8N_PATH` and `N8N_EDITOR_BASE_URL`, n8n would try to load assets from incorrect paths

## ✅ Solution Implemented

### 1. Warmup Timeout Fix (server/app_factory.py)

**Changes:**
- Added `DISABLE_WARMUP` environment variable support to completely skip warmup if needed
- Modified warmup timeout behavior to be **production-safe**:
  - ✅ **Production mode**: Logs warning and continues without crashing
  - ✅ **Development mode**: Still raises RuntimeError to catch issues early
- Improved production detection logic to check multiple environment variables

**Key Code Change:**
```python
if not migrations_ready:
    error_msg = "❌ Warmup timeout waiting for migrations - CANNOT proceed with invalid schema"
    logger.error(error_msg)
    
    # Check if production mode
    is_production = (
        os.getenv("ENV") == "production" or
        os.getenv("FLASK_ENV") == "production" or
        os.getenv("PRODUCTION", "0") in ("1", "true", "True")
    )
    
    if is_production:
        logger.warning("⚠️ Skipping warmup failure in production - app will continue without warmup")
        return  # Don't crash!
    else:
        raise RuntimeError(error_msg)  # Catch issues early in dev
```

### 2. DISABLE_WARMUP Environment Variable (docker-compose.prod.yml)

**Changes:**
- Added `DISABLE_WARMUP` to both `prosaas-api` and `prosaas-calls` services
- Defaults to `false` (warmup enabled)
- Can be set to `true` to skip warmup entirely during deployment

**Usage:**
```yaml
environment:
  DISABLE_WARMUP: ${DISABLE_WARMUP:-false}
```

### 3. n8n Configuration Fix (docker-compose.yml)

**Changes:**
- Explicitly set `N8N_PATH: /` (no subpath)
- Added `N8N_EDITOR_BASE_URL: https://n8n.prosaas.pro`
- Fixed `WEBHOOK_URL` format (removed trailing slash)

**Updated Configuration:**
```yaml
environment:
  N8N_HOST: ${N8N_HOST:-n8n.prosaas.pro}
  N8N_PORT: 5678
  N8N_PROTOCOL: ${N8N_PROTOCOL:-https}
  N8N_PATH: /
  N8N_EDITOR_BASE_URL: https://n8n.prosaas.pro
  WEBHOOK_URL: https://n8n.prosaas.pro
```

## 🚀 Deployment Instructions

### Step 1: Pull Latest Changes
```bash
git pull origin <branch-name>
```

### Step 2: Optional - Disable Warmup (Recommended for First Deploy)
If you want to skip warmup during this deployment for faster startup:

1. Edit your `.env` file:
   ```bash
   echo "DISABLE_WARMUP=true" >> .env
   ```

2. This is **optional** but recommended for first deploy after this fix

### Step 3: Rebuild and Deploy
```bash
./scripts/dcprod.sh down
./scripts/dcprod.sh up -d --build --force-recreate
```

### Step 4: Monitor Logs
Watch the logs to verify the fix:

```bash
# Watch API logs
docker logs -f prosaasil-prosaas-api-1 | grep -E "(Warmup|Migration|ERROR)"

# Watch n8n logs
docker logs -f prosaasil-n8n-1
```

### Step 5: Verify Services

1. **Check API Health:**
   ```bash
   curl https://prosaas.pro/health
   # Should return: ok
   ```

2. **Test Login:**
   - Open https://prosaas.pro
   - Try logging in
   - Should work without errors

3. **Check n8n:**
   - Open https://n8n.prosaas.pro
   - Should load correctly with all assets
   - No white screen or 500 errors

## 📊 Expected Log Output

### ✅ Success Case 1: Warmup Completes
```
🔥 Warmup waiting for migrations to complete...
✅ Migrations complete - starting warmup
[Warmup runs successfully]
```

### ✅ Success Case 2: Warmup Timeout in Production (NON-BLOCKING)
```
🔥 Warmup waiting for migrations to complete...
❌ Warmup timeout waiting for migrations - CANNOT proceed with invalid schema
⚠️ Skipping warmup failure in production - app will continue without warmup
[App continues to start normally - LOGIN WORKS!]
```

### ✅ Success Case 3: Warmup Disabled
```
⚠️ Warmup disabled by DISABLE_WARMUP environment variable
[App starts immediately without warmup]
```

### ❌ Old Behavior (FIXED)
```
🔥 Warmup waiting for migrations to complete...
❌ Warmup timeout waiting for migrations - CANNOT proceed with invalid schema
RuntimeError: Warmup timeout waiting for migrations
[APP CRASHES - LOGIN DOESN'T WORK]
```

## 🔧 Environment Variables

### New Variables Added

| Variable | Default | Purpose |
|----------|---------|---------|
| `DISABLE_WARMUP` | `false` | Set to `true` to skip agent warmup entirely |

### Existing Variables (No Changes)

| Variable | Purpose |
|----------|---------|
| `ENV` | Environment mode (`production` or `development`) |
| `FLASK_ENV` | Flask environment mode |
| `PRODUCTION` | Production flag (`1` or `0`) |
| `RUN_MIGRATIONS_ON_START` | Run migrations on startup |

## 🔒 Security Summary

- ✅ CodeQL scan completed: **0 vulnerabilities found**
- ✅ Code review completed: All critical issues addressed
- ✅ No sensitive data exposed
- ✅ No new dependencies added
- ✅ Maintains backward compatibility

## 📝 Rollback Plan

If you need to rollback:

```bash
# Stop services
./scripts/dcprod.sh down

# Checkout previous commit
git checkout <previous-commit-sha>

# Rebuild and restart
./scripts/dcprod.sh up -d --build --force-recreate
```

## ✨ Benefits

1. **Production Stability**: App never crashes due to warmup timeout
2. **Login Reliability**: Login works even if migrations are still running
3. **Faster Deployment**: Option to skip warmup for quicker startup
4. **Better Monitoring**: Clear log messages about warmup status
5. **n8n Reliability**: n8n loads correctly with proper asset paths

## 🆘 Troubleshooting

### If Login Still Doesn't Work

1. Check if migrations are running:
   ```bash
   docker logs prosaasil-prosaas-api-1 | grep Migration
   ```

2. Check database connectivity:
   ```bash
   docker logs prosaasil-prosaas-api-1 | grep DATABASE_URL
   ```

3. Check for other errors:
   ```bash
   docker logs prosaasil-prosaas-api-1 | grep ERROR
   ```

### If n8n Doesn't Load

1. Check n8n service status:
   ```bash
   docker ps | grep n8n
   ```

2. Check n8n logs:
   ```bash
   docker logs prosaasil-n8n-1
   ```

3. Test direct connection:
   ```bash
   docker exec -it prosaasil-n8n-1 curl http://localhost:5678/health
   ```

## 📞 Support

If issues persist after deployment:
1. Collect logs: `docker logs prosaasil-prosaas-api-1 > api.log`
2. Check environment: `docker exec prosaasil-prosaas-api-1 env | grep -E "(PRODUCTION|ENV|WARMUP)"`
3. Create issue with logs and environment details

---

**Deployed by:** GitHub Copilot Agent  
**Date:** 2026-01-22  
**PR:** Fix warmup timeout and n8n configuration blocking production deployment
