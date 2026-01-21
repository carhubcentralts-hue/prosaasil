# Receipt Worker Fix - Deployment Guide

## Problem Summary

Receipt sync jobs were being enqueued to Redis Queue (RQ) but not running because:
1. Nginx was using wrong service names (causing 502 errors)
2. No fail-fast check for Redis availability (causing silent failures)

## Root Cause

The nginx configuration file `docker/nginx/conf.d/prosaas-ssl.conf` was referencing incorrect service names:
- Used `prosaas-backend` instead of `prosaas-api` (for API)
- Used `prosaas-backend` instead of `prosaas-calls` (for WebSocket/webhooks)
- Used `prosaas-frontend` instead of `frontend`
- Used `prosaas-n8n` instead of `n8n`

This caused nginx to fail to route requests, resulting in 502 Bad Gateway errors.

## Changes Made

### 1. Fixed Nginx Upstream Service Names

**File**: `docker/nginx/conf.d/prosaas-ssl.conf`

Changed all proxy_pass directives to use correct service names:

| Location | Old Service | New Service | Purpose |
|----------|-------------|-------------|---------|
| `/api/` | `prosaas-backend:5000` | `prosaas-api:5000` | REST API endpoints |
| `/ws/` | `prosaas-backend:5000` | `prosaas-calls:5050` | WebSocket connections |
| `/webhook` | `prosaas-backend:5000` | `prosaas-calls:5050` | Twilio webhooks |
| `/assets` | `prosaas-frontend:80` | `frontend:80` | Static assets |
| `/` | `prosaas-frontend:80` | `frontend:80` | Frontend SPA |
| n8n subdomain | `prosaas-n8n:5678` | `n8n:5678` | n8n automation |

### 2. Added Fail-Fast Redis Check

**File**: `server/routes_receipts.py`

Added Redis ping check at the start of `POST /api/receipts/sync`:

```python
# Fail-fast: Check Redis availability (required for RQ worker queue)
if RQ_AVAILABLE and redis_conn:
    try:
        redis_conn.ping()
        logger.info(f"✓ Redis connection verified")
    except Exception as e:
        logger.error(f"✗ Redis not available: {e}")
        return jsonify({
            "success": False,
            "error": "Redis not available - worker queue disabled. Please contact support.",
            "technical_details": str(e)
        }), 503
```

Now the API returns a clear 503 error if Redis is not available, instead of silently enqueueing jobs that won't run.

## Verification Checklist

### Pre-Deployment

- [x] All nginx service names match docker-compose service names
- [x] Redis URL uses correct hostname: `redis://redis:6379/0`
- [x] Worker service is defined in `docker-compose.prod.yml`
- [x] Worker command is: `python -m server.worker`
- [x] Worker depends on Redis (health check)
- [x] Job code has proper logging and locking

### Post-Deployment

After deploying these changes:

1. **Verify services are running**:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
   ```
   
   Expected output should show all services as "Up" or "healthy":
   - `prosaas-api` (healthy)
   - `prosaas-calls` (healthy)
   - `prosaas-worker` (running)
   - `redis` (healthy)
   - `nginx` (healthy)
   - `frontend` (healthy)
   - `n8n` (running)

2. **Check worker logs**:
   ```bash
   docker logs prosaas-worker --tail=50
   ```
   
   Should see:
   ```
   🔔 WORKER_START: ProSaaS Background Worker
   ✓ Redis connection successful
   ✓ Flask app context initialized
   ✓ Job functions imported successfully
   🚀 Worker is now READY and LISTENING for jobs...
   ```

3. **Test receipt sync**:
   - Navigate to `/app/receipts` in the UI
   - Click "Sync Now" button
   - Check API logs for: `🔔 JOB ENQUEUED SUCCESSFULLY`
   - Check worker logs for: `🔔 JOB_START: Gmail receipts sync`
   - Verify job completes with: `🔔 JOB_DONE: Gmail sync completed successfully`

4. **Test fail-fast behavior**:
   - Stop Redis: `docker stop prosaas-redis`
   - Try to sync receipts
   - Should see error: "Redis not available - worker queue disabled"
   - Start Redis: `docker start prosaas-redis`

## Architecture Overview

### Service Separation (Production)

```
┌─────────────────────────────────────────────────────────────┐
│ Nginx Reverse Proxy (port 443)                             │
│  - Handles SSL termination                                  │
│  - Routes requests to appropriate service                   │
└──────────┬──────────────────────────────┬──────────────────┘
           │                              │
           ▼                              ▼
┌──────────────────────┐      ┌──────────────────────┐
│ prosaas-api:5000     │      │ prosaas-calls:5050   │
│  - REST API          │      │  - WebSocket calls   │
│  - CRM/UI endpoints  │      │  - Twilio webhooks   │
│  - Enqueues jobs     │      │  - Real-time media   │
└──────────┬───────────┘      └──────────────────────┘
           │
           ▼
┌──────────────────────┐      ┌──────────────────────┐
│ Redis:6379           │◄─────│ prosaas-worker       │
│  - Queue storage     │      │  - Processes jobs    │
│  - Job metadata      │      │  - Gmail sync        │
│  - Locks             │      │  - PDF generation    │
└──────────────────────┘      └──────────────────────┘
```

### Receipt Sync Flow

```
User clicks "Sync" → API endpoint → Redis ping check
                           ↓
                    Enqueue job to Redis
                           ↓
                    Worker picks up job
                           ↓
                    Acquire Redis lock
                           ↓
                    Fetch Gmail messages
                           ↓
                    Process attachments
                           ↓
                    Save to database
                           ↓
                    Release lock
                           ↓
                    Update sync status
```

## Environment Variables

All services need these Redis-related environment variables:

```bash
REDIS_URL=redis://redis:6379/0
```

This is already configured in `docker-compose.prod.yml` for:
- `prosaas-api`
- `prosaas-calls`
- `prosaas-worker`

## Troubleshooting

### Issue: "502 Bad Gateway" when accessing API

**Cause**: Nginx cannot reach backend services

**Fix**: Verify service names in nginx config match docker-compose

```bash
# Check which services are running
docker ps --format "table {{.Names}}\t{{.Status}}"

# Check nginx config
docker exec prosaas-nginx nginx -t

# View nginx error logs
docker logs prosaas-nginx --tail=50
```

### Issue: Jobs stay in "queued" status forever

**Cause**: Worker is not running or not connected to Redis

**Fix**: Check worker status

```bash
# Check if worker is running
docker ps | grep worker

# Check worker logs
docker logs prosaas-worker --tail=100

# Check Redis connection from worker
docker exec prosaas-worker python -c "import redis; r = redis.from_url('redis://redis:6379/0'); print('OK' if r.ping() else 'FAIL')"
```

### Issue: "Redis not available" error when syncing

**Cause**: Redis is not running or not accessible

**Fix**: Check Redis status

```bash
# Check if Redis is running
docker ps | grep redis

# Check Redis health
docker exec prosaas-redis redis-cli ping

# Check Redis logs
docker logs prosaas-redis --tail=50

# Restart Redis if needed
docker restart prosaas-redis
```

### Issue: Worker starts but doesn't process jobs

**Cause**: Worker is listening to wrong queue name

**Fix**: Verify queue names match

```bash
# Check worker logs for queue name
docker logs prosaas-worker | grep "Listening to queues"
# Should show: ['high', 'default', 'low']

# Check API logs for enqueue
docker logs prosaas-api | grep "ENQUEUING JOB"
# Should show: queue: default
```

## Performance Notes

### Worker Resources

The worker service has the following resource limits (configured in `docker-compose.prod.yml`):

```yaml
deploy:
  resources:
    limits:
      cpus: '2'
      memory: 2G
    reservations:
      cpus: '0.5'
      memory: 512M
```

These limits are sufficient for:
- Gmail API calls (rate limited by Google)
- PDF generation (uses Playwright)
- OCR processing (if enabled)

### Scaling Considerations

**Current Setup**: Single worker instance
- Sufficient for most use cases
- Jobs are serialized per business (Redis lock)
- Multiple businesses can sync concurrently

**If you need more throughput**:
1. Increase worker resources (CPU/memory)
2. Or add more worker replicas (requires no changes to code)

```yaml
prosaas-worker:
  # ... existing config ...
  deploy:
    replicas: 3  # Run 3 worker instances
```

## Security Notes

### Redis Access

- Redis is not exposed outside the Docker network
- Only internal services can access it
- No authentication required (internal network only)

### Token Encryption

Gmail refresh tokens are encrypted using `ENCRYPTION_KEY` environment variable:
- Must be set in production
- 32-byte key (base64 encoded)
- See: `GMAIL_ENCRYPTION_KEY_SETUP.md` for setup instructions

## Related Documentation

- `RECEIPT_WORKER_IMPLEMENTATION_SUMMARY.md` - Original implementation details
- `GMAIL_RECEIPTS_COMPLETE_IMPLEMENTATION.md` - Gmail integration guide
- `docker-compose.prod.yml` - Production service configuration
- `server/worker.py` - Worker implementation
- `server/jobs/gmail_sync_job.py` - Sync job implementation

## Support

If you encounter issues after deployment:

1. Check all services are healthy: `docker compose ps`
2. Review logs: `docker logs <service-name>`
3. Verify Redis connectivity: `docker exec prosaas-api python -c "import redis; redis.from_url('redis://redis:6379/0').ping()"`
4. Test sync manually via API: `curl -X POST https://prosaas.pro/api/receipts/sync -H "Authorization: Bearer <token>"`
