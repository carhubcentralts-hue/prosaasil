# Fix Summary: NGINX Upstream Mismatch & Production Issues

## Problem

The production deployment was failing with these critical issues:

1. **NGINX 521 Error**: "host not found in upstream prosaas-api"
   - docker-compose.prod.yml referenced `prosaas-api:5000` and `prosaas-calls:5050`
   - These services don't exist - actual services are `backend` and `worker`

2. **Receipts Sync 503 Error**: Endpoint returned "worker not online" error
   - Worker availability check blocked the endpoint
   - Jobs couldn't be queued even when Redis was available

3. **DB DNS Spam**: Reminder scheduler logged full stack traces for transient DNS errors
   - Every 5 minutes: huge error messages
   - Normal transient failures treated as critical errors

4. **No Deployment Automation**: Manual steps required for production updates
   - Developers had to remember: build, up, force-recreate
   - Config changes not picked up automatically

## Solutions Implemented

### Phase 1: Fix NGINX Upstream Mismatch ✅

**Files Changed:**
- `docker-compose.prod.yml`: Updated nginx build args and dependencies
- `docker-compose.yml`: Removed dev profile restriction from backend

**Changes:**
```yaml
# docker-compose.prod.yml - BEFORE
nginx:
  build:
    args:
      API_UPSTREAM: prosaas-api:5000
      CALLS_UPSTREAM: prosaas-calls:5050
  depends_on:
    prosaas-api:
      condition: service_healthy

# docker-compose.prod.yml - AFTER
nginx:
  build:
    args:
      API_UPSTREAM: backend:5000
      CALLS_UPSTREAM: backend:5000
  depends_on:
    backend:
      condition: service_healthy
```

**Result:**
- NGINX now correctly proxies to `backend:5000` (actual service name)
- No more "host not found" errors
- Both API and calls routes go to same backend service (monolith)

### Phase 2: Verify Build-Time Config ✅

**Status:** Already correctly implemented

Verified that `Dockerfile.nginx`:
- Uses `envsubst` at BUILD TIME (lines 35-43)
- No runtime template processing
- Config is "baked" into the image
- Fail-fast validation catches errors during build

### Phase 3: Deployment Automation ✅

**New File:** `scripts/deploy-prod.sh`

Automated deployment script that:
1. Pulls latest code (optional)
2. Rebuilds images with `--pull` flag
3. Recreates containers with `--force-recreate`
4. Cleans up old images
5. Validates NGINX logs for errors
6. Provides clear success/failure feedback

**Usage:**
```bash
./scripts/deploy-prod.sh
```

### Phase 4: Fix DB DNS Error Spam ✅

**File Changed:** `server/services/notifications/reminder_scheduler.py`

**Change:**
```python
# BEFORE - Always logged full stack trace
except Exception as e:
    log.error(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

# AFTER - Check if it's expected DNS error first
except Exception as e:
    if _is_dns_error(e):
        log.warning(f"[REMINDER_SCHEDULER] DB connection issue (likely DNS). Skipping this cycle. err={e}")
    else:
        log.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
```

**Result:**
- Transient DNS errors: Single line warning (no stack trace)
- Retry logic already present (3 attempts with exponential backoff)
- Legitimate errors still get full stack traces for debugging

### Phase 5: Fix Receipts Sync 503 Error ✅

**File Changed:** `server/routes_receipts.py`

**Change:**
```python
# BEFORE - Blocked request if no worker detected
if not _has_worker_for_queue(redis_conn, queue_name="default"):
    return jsonify({
        "success": False,
        "error": "Receipt sync worker is not online. Please try again later."
    }), 503

# AFTER - Log warning but allow job to queue
if not _has_worker_for_queue(redis_conn, queue_name="default"):
    logger.warning("⚠️ No RQ workers currently listening - job will queue until worker starts")
# Continue to enqueue job...
```

**Result:**
- Endpoint always returns 202 Accepted (not 503)
- Jobs queue successfully in Redis
- Workers process jobs when available
- Handles worker restarts gracefully

## Service Name Clarification

**Actual Running Services** (verified with `docker compose ps`):
```
backend         (prosaas-backend)     - Main API service
worker          (prosaas-worker)      - Background job processor
redis           (prosaas-redis)       - Queue management
baileys         (prosaas-baileys)     - WhatsApp integration
frontend        (prosaas-frontend)    - Static files / SPA
nginx           (prosaas-nginx)       - Reverse proxy
n8n             (prosaas-n8n)         - Automation platform
```

**Non-existent Services** (removed from config):
- ❌ `prosaas-api` - Was referenced but never defined
- ❌ `prosaas-calls` - Was referenced but never defined

**Current Architecture:**
- **Monolith**: Single `backend` service handles both API and calls
- **Not Split**: No separate API/calls services currently deployed
- **Future**: Can add split services later, but need to define them first

## Deployment Instructions

### First-Time Setup

1. **Ensure SSL certificates exist** (if USE_SSL=true):
   ```bash
   ls docker/nginx/ssl/prosaas-origin.crt
   ls docker/nginx/ssl/prosaas-origin.key
   ```

2. **Set environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with production values
   ```

3. **Deploy**:
   ```bash
   chmod +x scripts/deploy-prod.sh
   ./scripts/deploy-prod.sh
   ```

### Updating Production

Just run the deployment script:
```bash
./scripts/deploy-prod.sh
```

The script will:
- Pull latest code
- Rebuild images
- Recreate containers
- Validate deployment
- Show any errors

### Manual Deployment (if script fails)

```bash
# 1. Build images
docker compose -f docker-compose.yml -f docker-compose.prod.yml build --pull \
  nginx backend worker frontend baileys

# 2. Recreate containers
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --force-recreate

# 3. Check status
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps

# 4. Check nginx logs
docker logs prosaas-nginx --tail 50

# 5. Check backend logs
docker logs prosaas-backend --tail 50
```

## Verification Steps

### 1. Check NGINX Started Successfully
```bash
docker logs prosaas-nginx 2>&1 | grep -i "host not found"
# Should return nothing (no errors)

docker logs prosaas-nginx 2>&1 | tail -20
# Should show nginx started successfully
```

### 2. Verify Service Dependencies
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
# All services should be "Up" and healthy
```

### 3. Test Health Endpoint
```bash
curl http://localhost/health
# Should return: ok

curl http://localhost/api/health
# Should return JSON health status
```

### 4. Test Receipts Sync
```bash
# Should return 202 Accepted (not 503)
curl -X POST http://localhost/api/receipts/sync \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json"
```

### 5. Check Worker Processing
```bash
docker logs prosaas-worker -f
# Should show worker listening to queues: high,default,low,receipts,receipts_sync
```

## Configuration Reference

### Environment Variables (Required)

Production `.env` must include:
```env
# Database
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# API Keys
OPENAI_API_KEY=sk-...
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...

# Storage
R2_ACCOUNT_ID=...
R2_BUCKET_NAME=...
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_ENDPOINT=https://...

# Security
ATTACHMENT_SECRET=...
INTERNAL_SECRET=...

# Application
PUBLIC_BASE_URL=https://prosaas.pro
PRODUCTION=1
```

### Docker Compose Files

- **Base**: `docker-compose.yml` - Shared config for all environments
- **Production**: `docker-compose.prod.yml` - Production overrides
- **Usage**: `docker compose -f docker-compose.yml -f docker-compose.prod.yml [command]`

### Service Ports

- **nginx**: 80 (HTTP), 443 (HTTPS) - External
- **backend**: 5000 - Internal only
- **worker**: No port - Internal only
- **redis**: 6379 - Internal only
- **baileys**: 3300 - External (can be internal)
- **frontend**: 80 - Internal only
- **n8n**: 5678 - Internal only (accessed via nginx at n8n.prosaas.pro)

## Troubleshooting

### NGINX shows "host not found in upstream"

**Cause:** Service name mismatch

**Fix:**
1. Check running services: `docker compose ps`
2. Verify nginx build args match actual services:
   ```bash
   docker compose config | grep -A 5 "API_UPSTREAM"
   ```
3. Rebuild nginx: `docker compose build --no-cache nginx`

### Worker not processing receipts jobs

**Cause:** Worker not listening to correct queues

**Fix:**
1. Check worker queues:
   ```bash
   docker logs prosaas-worker | grep RQ_QUEUES
   ```
2. Should show: `high,default,low,receipts,receipts_sync`
3. If not, check docker-compose.prod.yml worker environment

### DB DNS errors in logs

**Status:** Fixed in this PR

If still seeing errors:
1. Check DNS config in docker-compose files
2. Verify `dns:` section includes: `1.1.1.1`, `8.8.8.8`
3. Check `dns_opt` includes: `ndots:0`, `timeout:2`

## Files Modified

1. `docker-compose.prod.yml` - Fixed service names and dependencies
2. `docker-compose.yml` - Removed dev profile from backend
3. `server/routes_receipts.py` - Removed worker check that caused 503
4. `server/services/notifications/reminder_scheduler.py` - Reduced DNS error spam
5. `scripts/deploy-prod.sh` - NEW: Automated deployment script

## Testing Checklist

Before considering this fix complete:

- [ ] NGINX starts without "host not found" errors
- [ ] All services show as healthy in `docker compose ps`
- [ ] Health endpoint responds: `curl http://localhost/health`
- [ ] API health responds: `curl http://localhost/api/health`
- [ ] Receipts sync returns 202 (not 503)
- [ ] Worker shows correct queues in logs
- [ ] No DNS error spam in logs
- [ ] Deployment script runs successfully
- [ ] SSL works (if USE_SSL=true)
- [ ] Frontend loads correctly
- [ ] WhatsApp (baileys) service connects

## Summary

This fix addresses the root cause of production deployment failures:

✅ **NGINX 521 fixed**: Correct service names (backend:5000)
✅ **Receipts 503 fixed**: Removed blocking worker check
✅ **DNS spam fixed**: Concise logging for transient errors
✅ **Deployment automated**: Single script for reliable deploys
✅ **Config validated**: Docker compose syntax verified

**Result:** Production system should now start successfully and handle all traffic correctly.
