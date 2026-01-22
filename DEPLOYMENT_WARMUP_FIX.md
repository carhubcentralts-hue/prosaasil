# Deployment Guide: Production Startup Race Condition Fix

## 🎯 Problem Summary

The production deployment was failing due to a **race condition during startup**:

1. **The Real Issue** (NOT what I initially thought)
   - Migrations ARE completing successfully
   - The database IS accessible
   - The problem is **timing**: The app tries to warm up agents before migrations signal completion
   - Agent warmup queries the database (Business.query), so it needs the schema to be ready
   - When warmup times out, it was crashing the entire app

2. **What Was Wrong With My Initial Fix**
   - I made `DISABLE_WARMUP` skip waiting for migrations entirely
   - This would allow the app to start with an invalid schema
   - Agent warmup QUERIES THE DATABASE, so it MUST wait for migrations
   - This was hiding the symptom, not fixing the root cause

## ✅ Correct Solution Implemented

### 1. Separate TTS Warmup from Agent Warmup

**TTS Warmup** (Optional - Does NOT query DB):
- Initializes Google Cloud TTS client
- Can be safely skipped with `DISABLE_TTS_WARMUP=true`
- Non-critical optimization

**Agent Warmup** (Queries DB - Must wait for migrations):
- Queries `Business.query` to get active businesses
- Pre-creates AI agents to eliminate cold starts
- MUST wait for migrations to complete or it will fail

### 2. Production-Safe Timeout Handling

**Key Changes in server/app_factory.py:**
- Agent warmup still waits for migrations (60 second timeout)
- If timeout occurs in production:
  - ✅ Logs warning but does NOT crash
  - ✅ App continues to start
  - ✅ Agent warmup has built-in retry logic anyway
- If timeout occurs in development:
  - ❌ Still raises RuntimeError (fail-fast to catch issues early)

**Why this is safe:**
- The timeout means the signal didn't arrive, NOT that migrations failed
- Migrations are likely still running (or completed but signal was delayed)
- Agent warmup has built-in retry logic (5 attempts with exponential backoff)
- First requests may be slower, but app stays up

### 3. Health Check Validates DB Readiness

**`/api/health` endpoint:**
- Returns 503 (Service Unavailable) while migrations are running
- Returns 200 (OK) only after migrations complete
- Docker healthcheck uses this, so dependent services wait

**`/readyz` endpoint:**
- Validates actual DB connectivity with `SELECT 1`
- Checks Baileys service connectivity
- Returns 200 only when all dependencies are healthy

## 📦 Changes Made

### server/app_factory.py
- Separated TTS warmup (optional) from agent warmup (must wait for DB)
- Added `DISABLE_TTS_WARMUP` environment variable
- Made agent warmup timeout non-blocking in production
- Improved logging to distinguish between warmup types

### docker-compose.prod.yml
- Changed `DISABLE_WARMUP` to `DISABLE_TTS_WARMUP`
- Clarified that this only affects TTS, not DB-dependent warmup
- Added clear comments about what can/cannot be disabled

### docker-compose.yml
- Fixed n8n environment configuration:
  - Explicit `N8N_PATH: /` (no subpath)
  - Added `N8N_EDITOR_BASE_URL: https://n8n.prosaas.pro`
  - Fixed `WEBHOOK_URL` format

## 🚀 Deployment Instructions

### Step 1: Pull Latest Changes
```bash
git pull origin <branch-name>
```

### Step 2: (Optional) Disable TTS Warmup Only
If you want to skip TTS client warmup for faster startup (does NOT affect DB):

```bash
echo "DISABLE_TTS_WARMUP=true" >> .env
```

**Note:** This only skips TTS client initialization. Agent warmup still runs.

### Step 3: Deploy
```bash
./scripts/dcprod.sh down
./scripts/dcprod.sh up -d --build --force-recreate
```

### Step 4: Monitor Startup
Watch the logs to see migrations and warmup:

```bash
# Watch API logs
docker logs -f prosaasil-prosaas-api-1 | grep -E "(Migration|Agent warmup|ERROR)"

# Check health status
watch -n 2 'curl -s https://prosaas.pro/api/health | jq'
```

## 📊 Expected Log Output

### ✅ Success Case 1: Migrations Complete, Agent Warmup Runs
```
🔒 Migrations complete - warmup can now proceed
🔥 Agent warmup waiting for migrations to complete...
✅ Migrations complete - starting agent warmup
🔥 WARMUP: Pre-creating agents for active businesses...
📊 Found 10 businesses to warm up
✅ Warmed up 10 agents in 5.2s
```

### ✅ Success Case 2: Timeout in Production (Non-Blocking)
```
🔥 Agent warmup waiting for migrations to complete...
❌ Agent warmup timeout waiting for migrations
⚠️ Skipping agent warmup in production due to timeout
⚠️ Note: Migrations may still be running. First requests may be slower.
[App continues normally - no crash!]
```

### ✅ Success Case 3: TTS Warmup Disabled
```
⚠️ TTS warmup disabled by DISABLE_TTS_WARMUP environment variable
🔥 Agent warmup waiting for migrations to complete...
✅ Migrations complete - starting agent warmup
```

## 🔧 Environment Variables

### New Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `DISABLE_TTS_WARMUP` | `false` | Skip TTS client warmup (does NOT skip agent warmup) |

### Existing Variables (No Changes)

| Variable | Purpose |
|----------|---------|
| `RUN_MIGRATIONS_ON_START` | Run DB migrations on startup (always 1 in production) |
| `ENV` / `FLASK_ENV` / `PRODUCTION` | Detect production mode |

## ⚠️ What NOT To Do

❌ **DO NOT** try to skip agent warmup entirely
- Agent warmup queries the database
- It has built-in retry logic
- Skipping it doesn't solve any problem

❌ **DO NOT** bypass migration completion checks
- Migrations MUST complete before agent warmup
- The health check ensures this
- Bypassing it could cause 500 errors on first requests

## ✅ What This Fix Actually Does

1. **Prevents app crashes** when agent warmup times out waiting for migrations
2. **Maintains DB safety** - migrations still run and must complete
3. **Allows optional TTS skip** - for faster deployment without affecting DB
4. **Better logging** - clearly shows what's happening during startup
5. **Production-friendly** - degrades gracefully instead of crashing

## 🆘 Troubleshooting

### If Login Still Fails

1. **Check migrations completed:**
   ```bash
   docker logs prosaasil-prosaas-api-1 | grep "Migrations complete"
   ```

2. **Check DB connectivity:**
   ```bash
   curl https://prosaas.pro/api/health
   # Should return {"status": "ok"} not {"status": "initializing"}
   ```

3. **Check for actual migration errors:**
   ```bash
   docker logs prosaasil-prosaas-api-1 | grep "MIGRATION FAILED"
   ```

### If n8n Doesn't Load

1. **Check n8n container:**
   ```bash
   docker logs prosaasil-n8n-1 | tail -50
   ```

2. **Test direct connectivity:**
   ```bash
   docker exec -it prosaasil-n8n-1 curl -I http://localhost:5678
   ```

3. **Check nginx routing:**
   ```bash
   docker exec -it prosaasil-nginx-1 curl -H "Host: n8n.prosaas.pro" http://n8n:5678
   ```

## 🔒 Security Summary

- ✅ CodeQL scan: 0 vulnerabilities
- ✅ No sensitive data exposed
- ✅ No new dependencies added
- ✅ Maintains backward compatibility
- ✅ DB migrations still required and blocking

## 📝 Key Takeaways

1. **The timeout is a symptom, not the root cause** - Migrations ARE running
2. **Agent warmup needs DB** - It cannot be completely disabled
3. **Production must be resilient** - Timeouts shouldn't crash the app
4. **TTS warmup is optional** - It doesn't query DB and can be skipped
5. **Health checks matter** - They ensure proper startup ordering

---

**Updated by:** GitHub Copilot Agent (Corrected Fix)  
**Date:** 2026-01-22  
**PR:** Fix production startup race condition with proper DB/warmup separation
