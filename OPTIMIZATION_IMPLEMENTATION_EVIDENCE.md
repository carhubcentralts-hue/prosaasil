# System Optimization - Implementation & Verification Guide

## What Was Actually Fixed (With Evidence)

### 1. CRITICAL: asyncio.Queue Instead of Blocking Queue ✅

**Problem**: `asgi.py` used `queue.Queue` (sync) inside async event loop → blocking!

**Fix Applied**:
```python
# OLD (WRONG):
from queue import Queue, Empty
self.recv_queue = Queue(maxsize=500)  # BLOCKS EVENT LOOP!

# NEW (CORRECT):
self.recv_queue = asyncio.Queue(maxsize=500)  # Proper async
await asyncio.wait_for(self.recv_queue.put(data), timeout=1.0)
```

**Evidence**: `git diff asgi.py` lines 18, 105, 225, 260

---

### 2. CRITICAL: Port Separation ✅

**Problem**: Both api and calls on port 5000 → conflict!

**Fix Applied**:
```yaml
# docker-compose.prod.yml
prosaas-api:
  expose: ["5000"]
  
prosaas-calls:
  expose: ["5050"]  # Different port!
  environment:
    PORT: 5050
  command: [..., "--port", "5050"]
```

**Nginx routing**:
```nginx
location /api/ {
    proxy_pass http://prosaas-api:5000/api/;
}

location /ws/ {
    proxy_pass http://prosaas-calls:5050;  # Port 5050!
}

location /webhook {
    proxy_pass http://prosaas-calls:5050;  # Port 5050!
}
```

**Evidence**: 
- `docker-compose.prod.yml` line 158
- `docker/nginx/conf.d/prosaas-ssl.conf` lines 53, 83, 110

---

### 3. CRITICAL: WhatsApp Unique Constraint ✅

**Problem**: No DB constraint → duplicates possible in race conditions

**Fix Applied**:
```sql
-- migration_add_whatsapp_unique_constraint.py
CREATE UNIQUE INDEX idx_whatsapp_message_provider_id_unique
ON whatsapp_message(provider_message_id)
WHERE provider_message_id IS NOT NULL;
```

**Code handling**:
```python
try:
    db.session.add(wa_msg)
    db.session.commit()
except Exception as integrity_err:
    db.session.rollback()
    if 'unique' in str(integrity_err).lower():
        log.info("Message already saved by another process")
        continue
```

**Evidence**:
- `migration_add_whatsapp_unique_constraint.py` (new file)
- `server/routes_whatsapp.py` lines 1085-1095

---

### 4. Service Separation in docker-compose ✅

**What exists**:
```yaml
services:
  redis:              # Queue management
  prosaas-api:        # REST API (port 5000)
  prosaas-calls:      # WebSocket (port 5050)
  prosaas-worker:     # Background jobs
  baileys:            # WhatsApp
  frontend:           # Static files
  nginx:              # Reverse proxy
```

**Evidence**: `docker-compose.prod.yml` lines 70-280

---

### 5. Redis Queue Integration ✅

**What exists**:
```python
# server/routes_receipts.py
try:
    import redis
    from rq import Queue
    redis_conn = redis.from_url(REDIS_URL)
    receipts_queue = Queue('default', connection=redis_conn)
    RQ_AVAILABLE = True
except:
    RQ_AVAILABLE = False  # Fallback to threading
```

**Job enqueue**:
```python
if RQ_AVAILABLE and receipts_queue:
    job = receipts_queue.enqueue(
        sync_gmail_receipts_job,
        business_id=business_id,
        ...
    )
    return jsonify({"job_id": job.id, "status": "queued"}), 202
```

**Evidence**: 
- `server/routes_receipts.py` lines 37-48, 1055-1069
- `server/worker.py` (new file)
- `server/jobs/gmail_sync_job.py` (new file)

---

## What Still Needs Verification (Not Just Claims)

### 1. Worker Actually Processes Jobs ❌ UNVERIFIED

**To verify**:
```bash
# 1. Start services
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 2. Check worker is running
docker ps | grep prosaas-worker

# 3. Trigger sync
curl -X POST https://prosaas.pro/api/receipts/sync \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"mode": "incremental"}'

# Expected response:
# {"success": true, "job_id": "abc123", "status": "queued"}

# 4. Check Redis queue
docker exec prosaas-redis redis-cli LLEN rq:queue:default
# Should show: (integer) 1

# 5. Check worker logs
docker logs prosaas-worker -f
# Should show:
# [INFO] JOB START: Gmail sync for business_id=X
# [INFO] JOB COMPLETE: scanned=Y, saved=Z

# 6. Verify in DB
docker exec prosaas-api python -c "
from server.app_factory import create_app
from server.models_sql import ReceiptSyncRun, db
app = create_app()
with app.app_context():
    runs = ReceiptSyncRun.query.order_by(ReceiptSyncRun.id.desc()).limit(5).all()
    for run in runs:
        print(f'ID={run.id}, status={run.status}, scanned={run.messages_scanned}')
"
```

**Current status**: Code exists, but NOT DEPLOYED/TESTED

---

### 2. Date Filtering Works End-to-End ❌ UNVERIFIED

**Backend claims to support both formats**:
```python
from_date = request.args.get('from_date') or request.args.get('fromDate')
to_date = request.args.get('to_date') or request.args.get('toDate')
```

**But logs show**:
```
Filtering - from_date=None, to_date=None
```

**To verify**:
```bash
# 1. Check what frontend actually sends
# Open browser DevTools → Network tab
# Filter receipts → Look at request query params

# 2. Check backend logs
docker logs prosaas-api | grep "list_receipts.*PARSED"
# Should show actual date values, not None

# 3. Test manually
curl "https://prosaas.pro/api/receipts?from_date=2024-01-01&to_date=2024-01-31" \
  -H "Authorization: Bearer $TOKEN"

# 4. Verify results are actually filtered
# Compare total count with and without date filter
```

**Current status**: Code exists, but LOGS SHOW IT'S NOT WORKING

---

### 3. Load Capacity ❌ UNVERIFIED

**Claims removed**: "100+ concurrent calls" (false promise)

**Reality**: Single Uvicorn worker + asyncio.Queue

**To measure actual capacity**:
```bash
# NOT with fake tools (wscat, curl)
# Use real Twilio Media Stream simulator

# 1. Create test script that simulates Twilio
python test_twilio_load.py --concurrent 10 --duration 60

# 2. Monitor metrics
docker stats prosaas-calls
# Watch: CPU%, MEM%, NET I/O

# 3. Check logs for errors
docker logs prosaas-calls | grep -E "ERROR|Ghost session|Memory"

# 4. Measure latency
# Time from START event to first audio frame
```

**Current status**: Unknown, needs real load test

---

## Deployment Checklist

Before deploying to production:

- [x] Fix asyncio.Queue (done)
- [x] Fix port separation (done)
- [x] Add unique constraint migration (done)
- [x] IntegrityError handling (done)
- [ ] **RUN MIGRATION**: `python migration_add_whatsapp_unique_constraint.py`
- [ ] **Test worker locally**: Start worker, queue job, verify logs
- [ ] **Test date filter**: Frontend → Backend with DevTools
- [ ] **Load test**: Real Twilio simulator, measure capacity
- [ ] Set all env vars (REDIS_URL, etc.)
- [ ] Deploy with docker-compose prod
- [ ] Monitor logs for 24h

---

## What to Tell the Agent

**DO:**
- Show actual code diffs
- Show logs proving it works
- Show measurements (CPU, RAM, latency)
- Show Redis queue length
- Show DB query results

**DON'T:**
- Claim "already works" without proof
- Promise "100+ concurrent X" without load test
- Show fake load test examples (wscat, curl)
- Write "documentation" before testing

---

## Known Limitations

1. **Single worker**: No multi-process Uvicorn (causes state issues)
2. **Capacity unknown**: Needs real load test to measure
3. **Worker unverified**: Code exists but not deployed
4. **Date filter**: Backend ready, frontend may not be sending correctly
5. **No graceful restart**: WebSocket connections will drop on restart

---

## Files Changed

1. `asgi.py` - Fixed asyncio.Queue (CRITICAL)
2. `docker-compose.prod.yml` - Port separation + services
3. `docker/nginx/conf.d/prosaas-ssl.conf` - Routing to correct ports
4. `server/routes_receipts.py` - RQ integration
5. `server/routes_whatsapp.py` - Unique constraint handling
6. `server/worker.py` - Worker process (NEW)
7. `server/jobs/gmail_sync_job.py` - Job handler (NEW)
8. `migration_add_whatsapp_unique_constraint.py` - DB migration (NEW)
9. `pyproject.toml` - Added redis, rq dependencies

Total: 9 files changed, 3 new files

---

## Summary

**What's PROVEN (code + can verify)**:
- ✅ asyncio.Queue instead of blocking Queue
- ✅ Port separation (5000 vs 5050)
- ✅ Unique constraint migration ready
- ✅ IntegrityError handling in code
- ✅ Service separation in docker-compose
- ✅ Redis queue integration in code

**What's NOT PROVEN (needs deployment test)**:
- ❌ Worker actually processes jobs
- ❌ Date filtering works end-to-end
- ❌ Load capacity (how many concurrent WS?)
- ❌ No memory leaks under sustained load
- ❌ Stale run recovery works

**Next step**: Deploy and TEST each claim with evidence.
