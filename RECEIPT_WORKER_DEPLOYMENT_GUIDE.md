# Gmail Receipts Worker - Deployment Guide

## Overview

The Gmail receipts sync system uses a background worker architecture:
- **API Service** (prosaas-api): Enqueues sync jobs to Redis queue
- **Redis**: Message queue for job coordination
- **Worker Service** (prosaas-worker): Processes jobs from the queue

## Production Deployment

### 1. Verify Environment Variables

Ensure these are set in your `.env` file:

```bash
# Redis connection
REDIS_URL=redis://redis:6379/0

# Database
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# Gmail OAuth (if using Gmail sync)
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=https://prosaas.pro/api/gmail/oauth/callback

# Encryption key for storing refresh tokens
ENCRYPTION_KEY=your-fernet-key-here
```

### 2. Start Services

The worker is already configured in `docker-compose.prod.yml`. To start all services:

```bash
# Start with production overrides
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Or use the production script
./start_production.sh
```

### 3. Verify Worker is Running

Check that all services are running:

```bash
docker ps
```

You should see:
- `prosaas-redis` - Redis message queue
- `prosaas-worker` - Background worker
- `prosaas-api` - API service
- `prosaas-calls` - WebSocket/calls service
- Other services...

### 4. Check Worker Logs

View worker logs to ensure it's processing jobs:

```bash
# Follow worker logs
docker logs -f prosaas-worker

# You should see:
# ============================================================
# ProSaaS Background Worker Starting
# ============================================================
# Redis URL: redis://redis:6379/0
# Service Role: worker
# Environment: production
# Worker PID: 1
# ============================================================
# ✓ Redis connection successful
#   → Queue 'high': 0 job(s) pending
#   → Queue 'default': 0 job(s) pending
#   → Queue 'low': 0 job(s) pending
# ✓ Flask app context initialized
# ✓ Worker created: prosaas-worker-1
# Listening on queues: high, default, low (in priority order)
# ------------------------------------------------------------
# Worker is now ready to process jobs...
# Waiting for jobs to be enqueued...
# ------------------------------------------------------------
```

### 5. Test the Sync

Trigger a sync from the UI or API:

```bash
# Via API (replace with your auth token)
curl -X POST https://prosaas.pro/api/receipts/sync \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"mode": "incremental"}'
```

### 6. Monitor Job Execution

When a job runs, you should see these logs in the worker:

```
============================================================
🔔 JOB START: Gmail receipts sync
  → business_id: 123
  → mode: incremental
  → from_date: None
  → to_date: None
  → max_messages: None
  → months_back: 36
============================================================
✓ Created sync run record: run_id=45
... processing messages ...
============================================================
🔔 JOB DONE: Gmail sync completed
  → business_id: 123
  → run_id: 45
  → duration: 12.3s
  → messages_scanned: 150
  → saved_receipts: 12
  → errors_count: 0
============================================================
```

### 7. Check Sync Status

Use the new status endpoint:

```bash
# Get latest sync status
curl https://prosaas.pro/api/receipts/sync/latest \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Response:
```json
{
  "success": true,
  "status": "completed",
  "last_run": {
    "id": 45,
    "mode": "incremental",
    "status": "completed",
    "started_at": "2024-01-21T10:00:00Z",
    "finished_at": "2024-01-21T10:00:12Z",
    "progress_percentage": 100,
    "counters": {
      "messages_scanned": 150,
      "saved_receipts": 12,
      "errors_count": 0
    }
  }
}
```

## Troubleshooting

### Worker Not Showing in `docker ps`

**Problem**: The prosaas-worker container is not running.

**Solutions**:

1. Check if the service is disabled by profile:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml config | grep -A 10 "prosaas-worker"
   ```

2. Manually start the worker:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d prosaas-worker
   ```

3. Check for startup errors:
   ```bash
   docker logs prosaas-worker
   ```

### Jobs Enqueued But Not Processing

**Problem**: Logs show "JOB ENQUEUED" but never "JOB START".

**Diagnosis**:

1. Check worker is running and connected to Redis:
   ```bash
   docker logs prosaas-worker | grep "Redis connection"
   ```

2. Check queue name matches:
   ```bash
   # In worker logs, verify it's listening to 'default' queue
   docker logs prosaas-worker | grep "Listening on queues"
   ```

3. Check Redis connectivity from worker:
   ```bash
   docker exec -it prosaas-worker redis-cli -h redis ping
   # Should return: PONG
   ```

4. Inspect queued jobs in Redis:
   ```bash
   docker exec -it prosaas-redis redis-cli
   > KEYS rq:queue:*
   > LLEN rq:queue:default
   > LRANGE rq:queue:default 0 -1
   ```

**Solutions**:

1. Restart the worker:
   ```bash
   docker restart prosaas-worker
   ```

2. Check REDIS_URL matches in both API and worker:
   ```bash
   docker exec prosaas-api env | grep REDIS_URL
   docker exec prosaas-worker env | grep REDIS_URL
   # Both should show: redis://redis:6379/0
   ```

### No Receipts Returned After Sync

**Problem**: Sync completes but `/api/receipts` returns empty.

**Diagnosis**:

1. Check job completion logs:
   ```bash
   docker logs prosaas-worker | grep "JOB DONE"
   # Look for saved_receipts count
   ```

2. Check database directly:
   ```bash
   docker exec prosaas-api python -c "
   from server.models_sql import db, Receipt
   from server.app_factory import create_app
   app = create_app()
   with app.app_context():
       count = Receipt.query.filter_by(business_id=123).count()
       print(f'Receipts: {count}')
   "
   ```

3. Check sync run status:
   ```bash
   curl https://prosaas.pro/api/receipts/sync/latest \
     -H "Authorization: Bearer YOUR_TOKEN"
   ```

**Common Causes**:
- No receipt-like emails in the scanned period
- Gmail connection issues (check `gmail_connections` table)
- Extraction failing (check `errors_count` in sync run)

### Multiple Jobs Created on Double-Click

**Problem**: Multiple sync runs created when clicking sync button repeatedly.

**Status**: ✅ Already handled! The code checks for existing running syncs and returns 409 Conflict.

**Verification**:
```bash
# Click sync multiple times
# Check logs for:
docker logs prosaas-api | grep "SYNC ALREADY RUNNING"
```

### Slow Stats API

**Problem**: `/api/receipts/stats` is slow.

**Status**: ✅ Already optimized! Database has these indexes:
- `idx_receipts_business_received` (business_id, received_at)
- `idx_receipts_business_status` (business_id, status)

**Verify indexes exist**:
```sql
SELECT indexname, indexdef 
FROM pg_indexes 
WHERE tablename = 'receipts' 
AND indexname LIKE 'idx_receipts%';
```

## Queue Names Reference

The system uses these queues (in priority order):

1. **high** - Not currently used (reserved for urgent tasks)
2. **default** - Gmail sync jobs, receipt processing
3. **low** - Not currently used (reserved for cleanup tasks)

## Key Files

- `server/worker.py` - Worker entry point
- `server/jobs/gmail_sync_job.py` - Gmail sync job implementation
- `server/routes_receipts.py` - API endpoints for receipts and sync
- `docker-compose.prod.yml` - Production service configuration

## Monitoring Checklist

Daily checks:
- [ ] Worker container is running (`docker ps`)
- [ ] No failed syncs in last 24h (`/api/receipts/sync/latest`)
- [ ] Redis queue is not backing up (`LLEN rq:queue:default` < 10)
- [ ] Worker logs show no errors (`docker logs prosaas-worker`)

## Support

If issues persist:
1. Collect worker logs: `docker logs prosaas-worker > worker.log`
2. Collect API logs: `docker logs prosaas-api > api.log`
3. Check sync run status: `curl /api/receipts/sync/latest`
4. Check Redis queue status: `docker exec prosaas-redis redis-cli LLEN rq:queue:default`
