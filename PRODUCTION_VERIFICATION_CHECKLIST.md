# Production Deployment Verification Checklist

## ⚠️ CRITICAL CHECKS - Must Pass Before Production

These checks prevent the two most common production failures:
1. Worker crashes due to missing `rq` package
2. Service discovery issues due to incorrect compose file usage

### Check 1: Verify RQ is Installed in Worker Container ✋

**Why This Matters**: Having `rq` in `pyproject.toml` doesn't guarantee it's installed in the container. If it's missing, worker will crash with:
```
rq package not installed
```

**How to Check**:
```bash
./scripts/dcprod.sh exec worker python -c "import rq; print('rq ok')"
```

**Expected Output**:
```
rq ok
```

**If It Fails**:
- Check that `Dockerfile.backend` line 39 runs: `pip install --no-cache-dir .`
- Verify `pyproject.toml` includes `rq>=2.0.0` in dependencies (line 57)
- Rebuild the worker image: `./scripts/dcprod.sh build --no-cache worker`

**Root Cause Prevention**:
- ✅ `Dockerfile.backend` line 34: Copies `pyproject.toml`
- ✅ `Dockerfile.backend` line 39: Runs `pip install .` to install all dependencies
- ✅ `pyproject.toml` line 57: Includes `rq>=2.0.0`

---

### Check 2: Verify Backend is NOT Running in Production ✋

**Why This Matters**: If backend is running alongside prosaas-api/prosaas-calls, it can cause:
- Confusion about which service handles requests
- Wrong traffic routing if NGINX points to backend by mistake
- Wasted resources

**How to Check**:
```bash
./scripts/dcprod.sh ps
```

**Expected Output** (8 services, NO backend):
```
NAME                IMAGE               STATUS
prosaas-nginx       ...                 Up
prosaas-api         ...                 Up
prosaas-calls       ...                 Up
prosaas-worker      ...                 Up
prosaas-baileys     ...                 Up
prosaas-frontend    ...                 Up
prosaas-n8n         ...                 Up
prosaas-redis       ...                 Up
```

**If Backend Appears**:
- You're running compose with wrong profile or old command
- Stop all services: `./scripts/dcprod.sh down`
- Start only with new script: `./scripts/dcprod.sh up -d --build`

**Verify Service List**:
```bash
./scripts/dcprod.sh config --services
```

**Expected Output** (backend should NOT be in list):
```
redis
prosaas-api
worker
baileys
frontend
n8n
prosaas-calls
nginx
```

**Root Cause Prevention**:
- ✅ `docker-compose.prod.yml` line 102: Backend has `profiles: [legacy]`
- ✅ `scripts/dcprod.sh`: Always uses correct compose files

---

## 🟢 Additional Production Checks (Recommended)

### Check 3: Verify Worker Logs are Clean

```bash
./scripts/dcprod.sh logs --tail 120 worker
```

**Should NOT see**:
- ❌ `rq package not installed`
- ❌ `Logger._log() got an unexpected keyword argument 'file'`
- ❌ `Migration failed`

**Should see**:
- ✅ `RQ worker started`
- ✅ `Listening on queues: high,default,low,receipts,receipts_sync`

---

### Check 4: Verify NGINX Logs are Clean

```bash
./scripts/dcprod.sh logs --tail 80 nginx
```

**Should NOT see**:
- ❌ `502 Bad Gateway`
- ❌ `upstream not found`
- ❌ `connect() failed`

**Should see**:
- ✅ Successful proxying to prosaas-api:5000
- ✅ Successful proxying to prosaas-calls:5050

---

### Check 5: Verify Service Health

```bash
./scripts/dcprod.sh ps --format json | grep -i health
```

All services should show `(healthy)` status.

---

## 📋 Quick Verification Script

Run all checks at once:

```bash
#!/bin/bash
echo "=== Check 1: RQ Package ==="
./scripts/dcprod.sh exec worker python -c "import rq; print('✅ rq ok')" 2>&1

echo ""
echo "=== Check 2: Services Running ==="
./scripts/dcprod.sh ps --format table

echo ""
echo "=== Check 3: Service List (backend should NOT appear) ==="
./scripts/dcprod.sh config --services

echo ""
echo "=== Check 4: Worker Logs (last 20 lines) ==="
./scripts/dcprod.sh logs --tail 20 worker

echo ""
echo "=== Check 5: NGINX Logs (last 20 lines) ==="
./scripts/dcprod.sh logs --tail 20 nginx
```

Save this as `scripts/verify_production.sh` and run:
```bash
chmod +x scripts/verify_production.sh
./scripts/verify_production.sh
```

---

## ✅ Success Criteria

Production is ready when:
1. ✅ `import rq` succeeds in worker container
2. ✅ Backend does NOT appear in `ps` output
3. ✅ Worker logs show no errors
4. ✅ NGINX logs show no 502 errors
5. ✅ All 8 services are running and healthy

---

## 🔥 If Production is Already Running with Old Method

**Migrate to new script**:
```bash
# Stop current deployment (whatever method was used)
docker compose down

# Start with new script (ensures correct configuration)
./scripts/dcprod.sh up -d --build --force-recreate

# Verify
./scripts/dcprod.sh ps
```

---

## 📞 Support

If any check fails, provide these 3 outputs:
```bash
./scripts/dcprod.sh ps
./scripts/dcprod.sh logs --tail 80 nginx
./scripts/dcprod.sh logs --tail 120 worker
```
