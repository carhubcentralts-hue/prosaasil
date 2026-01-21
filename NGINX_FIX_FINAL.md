# NGINX Upstream Fix - Complete Guide

## Critical Issue Fixed

**Problem**: NGINX 521 error - "host not found in upstream"

**Root Cause**: Production uses **split architecture** with separate services:
- `prosaas-api:5000` for REST API
- `prosaas-calls:5050` for WebSocket/Twilio

But NGINX was incorrectly configured or cached with wrong upstream values.

## Production Architecture

### Actual Running Services
```
✅ prosaas-api          (REST API on port 5000)
✅ prosaas-calls        (WebSocket/Calls on port 5050)
✅ prosaas-worker       (Background jobs)
✅ prosaas-redis        (Queue management)
✅ prosaas-nginx        (Reverse proxy)
✅ prosaas-frontend     (Static files)
✅ prosaas-baileys      (WhatsApp integration)
✅ prosaas-n8n          (Automation platform)
```

### Services NOT in Production
```
❌ backend              (dev only - uses profile)
❌ prosaas-backend      (legacy monolith)
```

## Changes Made

### 1. docker-compose.prod.yml
```yaml
nginx:
  build:
    args:
      API_UPSTREAM: prosaas-api:5000     # ✅ Correct
      CALLS_UPSTREAM: prosaas-calls:5050  # ✅ Correct
      USE_SSL: "true"
  depends_on:
    prosaas-api:
      condition: service_healthy
    prosaas-calls:
      condition: service_healthy

worker:
  depends_on:
    prosaas-api:  # ✅ Points to correct service
      condition: service_healthy

backend:
  profiles:
    - legacy  # ✅ Disabled in production
```

### 2. docker-compose.yml
```yaml
backend:
  profiles:
    - dev  # ✅ Only runs in dev, not production
```

### 3. Deployment Scripts

**scripts/deploy-prod.sh**:
- Rebuilds nginx with `--no-cache` to bust cache
- Deploys correct services: prosaas-api, prosaas-calls
- Verifies proxy_pass configuration
- Shows clear error messages

**scripts/force-rebuild.sh** (NEW):
- Nuclear option for complete rebuild
- Removes all images and rebuilds from scratch
- Use when cache issues persist

### 4. Other Fixes (Still Applied)

- DNS resilience for backend and worker (1.1.1.1, 8.8.8.8)
- Concise DNS error logging in reminder_scheduler
- Receipts sync returns 202 (not 503)
- Worker configured with all queues

## Deployment Instructions

### Option 1: Normal Deployment (Fast)
```bash
./scripts/deploy-prod.sh
```
**Time**: ~5 minutes  
**When**: Config is correct, just need code updates

### Option 2: Force NGINX Rebuild
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml build --no-cache nginx
docker compose -f docker-compose.yml -f docker-compose.prod.yml build --pull prosaas-api prosaas-calls
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --force-recreate
```
**Time**: ~7 minutes  
**When**: NGINX not picking up new build args

### Option 3: Nuclear Option (Slow)
```bash
./scripts/force-rebuild.sh
```
**Time**: ~10-15 minutes  
**When**: Everything is broken, start fresh

## Verification Steps

### 1. Check Services Running
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

Expected:
```
NAME              STATUS
prosaas-api       Up (healthy)
prosaas-calls     Up (healthy)
prosaas-nginx     Up (healthy)
prosaas-worker    Up (healthy)
```

### 2. Verify NGINX Configuration
```bash
docker exec prosaas-nginx nginx -T | grep proxy_pass
```

Expected:
```
proxy_pass http://prosaas-api:5000/api/;
proxy_pass http://prosaas-calls:5050;
```

❌ **If you see backend:5000** - rebuild with `--no-cache`!

### 3. Check NGINX Logs
```bash
docker logs prosaas-nginx --tail 50
```

Expected:
```
✅ nginx started successfully
✅ configuration ok
```

❌ **If you see "host not found"** - config didn't update!

### 4. Test Health Endpoints
```bash
curl http://localhost/health
# Should return: ok

curl http://localhost/api/health  
# Should return: JSON with status
```

## Troubleshooting

### Issue 1: "host not found in upstream"

**Cause**: NGINX still has old config (cached build)

**Solution**:
```bash
# Option A - Rebuild just nginx
docker compose -f docker-compose.yml -f docker-compose.prod.yml build --no-cache nginx
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --force-recreate nginx

# Option B - Force rebuild everything
./scripts/force-rebuild.sh
```

### Issue 2: prosaas-api won't start

**Check**:
```bash
docker logs prosaas-api
```

**Common Causes**:
- Missing environment variables in .env
- Invalid DATABASE_URL
- Redis not available

**Solution**:
```bash
# Check Redis
docker logs prosaas-redis

# Check environment
cat .env | grep DATABASE_URL
```

### Issue 3: Worker not processing jobs

**Check**:
```bash
docker logs prosaas-worker | grep RQ_QUEUES
```

Expected:
```
RQ_QUEUES=high,default,low,receipts,receipts_sync
```

**Solution**:
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart worker
```

### Issue 4: 521 from Cloudflare

**Possible Causes**:
1. NGINX not listening on 80/443
2. SSL not configured correctly
3. Origin server down

**Check**:
```bash
# Test locally - should work
curl http://localhost/health

# If local works but Cloudflare doesn't - SSL issue
ls -la docker/nginx/ssl/
```

## Why Previous Commit Was Wrong

**My Mistake**: I incorrectly assumed production used a monolith `backend` service.

**Reality**: Production uses split architecture with `prosaas-api` and `prosaas-calls`.

**The Confusion**: 
- Base `docker-compose.yml` defines `backend` for dev
- Production `docker-compose.prod.yml` overrides with split services
- I saw `backend` in base file and assumed it was used in prod

**Lesson**: Always check `docker compose ps` to see actual running services!

## Configuration Summary

### NGINX Build Args (Correct)
```yaml
API_UPSTREAM: prosaas-api:5000
CALLS_UPSTREAM: prosaas-calls:5050
FRONTEND_UPSTREAM: frontend
USE_SSL: "true"
```

### Service Dependencies (Correct)
```yaml
nginx → prosaas-api, prosaas-calls, frontend
worker → prosaas-api, redis
baileys → prosaas-api
```

### Disabled Services
```yaml
backend:
  profiles: [legacy]  # Won't start in production
```

## Files Modified

1. `docker-compose.prod.yml` - Corrected to use prosaas-api/prosaas-calls
2. `docker-compose.yml` - backend kept in dev profile
3. `scripts/deploy-prod.sh` - Updated for correct services + --no-cache
4. `scripts/force-rebuild.sh` - NEW: Nuclear option rebuild
5. `scripts/verify-nginx-fix.sh` - NEW: Verification script
6. `server/routes_receipts.py` - Remove worker check (Phase 5)
7. `server/services/notifications/reminder_scheduler.py` - DNS logging (Phase 4)
8. `הנחיות_תיקון_סופי.md` - NEW: Hebrew deployment guide

## Quick Reference

### Pre-Deployment Checklist
- [ ] .env file exists with all variables
- [ ] SSL certificates in `docker/nginx/ssl/`
- [ ] Latest code pulled
- [ ] No conflicting containers running

### Post-Deployment Checklist
- [ ] All services Up and healthy
- [ ] NGINX proxy_pass points to prosaas-api:5000
- [ ] No "host not found" in logs
- [ ] `/health` returns ok
- [ ] `/api/health` returns JSON
- [ ] Worker listening to all queues

## Support

If still not working after all this:

1. Run: `./scripts/force-rebuild.sh`
2. Collect logs:
   ```bash
   docker logs prosaas-nginx --tail 100 > nginx.log
   docker exec prosaas-nginx nginx -T > nginx-config.txt
   docker compose ps > services-status.txt
   ```
3. Share the logs for debugging

## Summary

**The Fix**: 
- NGINX → prosaas-api:5000 (not backend:5000)
- NGINX → prosaas-calls:5050 (not backend:5000)
- Force rebuild with --no-cache to bust Docker cache

**The Proof**:
```bash
docker exec prosaas-nginx nginx -T | grep proxy_pass | grep -E "(prosaas-api|prosaas-calls)"
```

If both commands return results - **IT WORKS!** ✅
