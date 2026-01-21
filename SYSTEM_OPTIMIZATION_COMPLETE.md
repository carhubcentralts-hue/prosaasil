# System Optimization - Complete Implementation

## Overview

This document describes the comprehensive system optimization implemented to handle high loads without bottlenecks or crashes:

- **WebSocket Calls** (Twilio Realtime API)
- **WhatsApp** (Baileys/Agent Kit) 
- **UI/CRM/API**
- **Heavy Background Work** (Gmail receipts, Playwright screenshots, PDF thumbnails)

## 1. Service Separation

### Architecture

The system is now separated into specialized services that can scale independently:

```
┌─────────────┐
│   Nginx     │ ← Reverse Proxy with WebSocket upgrade
│  (Port 80)  │
└──────┬──────┘
       │
       ├──────→ prosaas-api      (REST only - CRM/UI endpoints)
       ├──────→ prosaas-calls    (WebSocket + Twilio streaming)
       ├──────→ prosaas-worker   (Background jobs: Gmail, Playwright, PDF)
       ├──────→ prosaas-whatsapp (Baileys Node service)
       └──────→ prosaas-frontend (Static files)

Shared Services:
  - Redis (Queue management, locks, heartbeat)
  - PostgreSQL (Managed DB - Supabase/Railway/Neon)
```

### Service Roles

#### prosaas-api (Port 5000)
- **Purpose**: REST API only
- **Handles**: CRM, user management, projects, leads, settings
- **Does NOT handle**: WebSocket calls, heavy processing
- **Resources**: 2 CPU, 2GB RAM
- **Scaling**: Horizontal (multiple instances behind load balancer)

#### prosaas-calls (Port 5000) 
- **Purpose**: WebSocket + Twilio streaming only
- **Handles**: `/ws/twilio-media`, Twilio webhooks, call endpoints
- **Optimized for**: High concurrency, low latency, backpressure
- **Command**: `uvicorn asgi:app --workers 4` (4 workers for concurrency)
- **Resources**: 3 CPU, 3GB RAM
- **Scaling**: Vertical (more workers) + horizontal

#### prosaas-worker (Background)
- **Purpose**: Heavy background tasks
- **Handles**: 
  - Gmail receipts sync (fetch, download attachments, generate previews)
  - Playwright screenshots (HTML→PNG)
  - PDF thumbnail generation
  - OCR processing
- **Queue**: Redis Queue (RQ) with priority queues (high, default, low)
- **Resources**: 2 CPU, 2GB RAM
- **Scaling**: Horizontal (add more workers)

#### prosaas-whatsapp (Port 3300)
- **Purpose**: WhatsApp Business API (Baileys)
- **Handles**: QR code, message sending, webhook processing
- **Resources**: 1 CPU, 1GB RAM

### Deployment

```bash
# Production deployment with service separation
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Services that will start:
# - nginx (reverse proxy)
# - prosaas-api (REST API)
# - prosaas-calls (WebSocket)
# - prosaas-worker (background jobs)
# - baileys (WhatsApp)
# - frontend (static files)
# - redis (queue management)
```

## 2. WebSocket Optimization

### Backpressure Mechanism

WebSocket connections have built-in backpressure to prevent memory exhaustion:

**In `asgi.py`:**
```python
class SyncWebSocketWrapper:
    def __init__(self):
        self.recv_queue = Queue(maxsize=500)  # 10s audio buffer
        self.send_queue = Queue(maxsize=600)  # 12s audio buffer
        
    def send(self, data):
        try:
            self.send_queue.put(data, timeout=2.0)
        except:
            pass  # Drop frame if queue is full (backpressure)
```

**Behavior under load:**
- If queue is full → frame is dropped (no RAM accumulation)
- Audio may skip slightly but connection stays stable
- System remains responsive even with 30-100 concurrent calls

### Uvicorn Workers

The prosaas-calls service uses multiple workers for better concurrency:

```dockerfile
CMD ["uvicorn", "asgi:app", "--host", "0.0.0.0", "--port", "5000", 
     "--ws", "websockets", "--timeout-keep-alive", "75", 
     "--timeout-graceful-shutdown", "30", "--workers", "4"]
```

**Benefits:**
- Each worker handles ~25 concurrent WebSocket connections
- Total capacity: 100+ concurrent calls
- Automatic load balancing across workers
- Graceful restart without dropping connections

### Nginx WebSocket Configuration

**In `docker/nginx/conf.d/prosaas-ssl.conf`:**
```nginx
location /ws/ {
    proxy_pass http://prosaas-calls:5000;
    
    # WebSocket upgrade
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $connection_upgrade;
    
    # Long timeouts for stable connections
    proxy_read_timeout 3600s;
    proxy_send_timeout 3600s;
    proxy_connect_timeout 75s;
    
    # Disable buffering for real-time streaming
    proxy_buffering off;
}
```

**In `docker/nginx/nginx.conf`:**
```nginx
# WebSocket connection upgrade map
map $http_upgrade $connection_upgrade {
    default upgrade;
    '' close;
}
```

## 3. Gmail Receipts - Background Worker

### Queue-Based Processing

Gmail sync no longer blocks the API. Instead, it queues a job:

**API Response (202 Accepted):**
```json
{
  "success": true,
  "message": "Sync job queued for processing",
  "job_id": "abc123",
  "status": "queued"
}
```

### Worker Architecture

**Components:**
1. **API Endpoint** (`/api/receipts/sync`) - Returns 202 immediately
2. **Redis Queue** - Stores jobs with priority
3. **Worker Process** (`server/worker.py`) - Processes jobs
4. **Job Handler** (`server/jobs/gmail_sync_job.py`) - Actual sync logic

**Job Processing:**
```python
# 1. Acquire Redis lock (prevents concurrent syncs for same business)
lock_key = f"receipt_sync_lock:{business_id}"
redis_conn.set(lock_key, "locked", nx=True, ex=3600)

# 2. Create sync run record in DB
sync_run = ReceiptSyncRun(business_id=..., status='running')

# 3. Update heartbeat every 30 seconds
sync_run.last_heartbeat_at = datetime.now(timezone.utc)

# 4. Process emails (fetch, download, generate previews)
result = sync_gmail_receipts(...)

# 5. Update status and release lock
sync_run.status = 'completed'
redis_conn.delete(lock_key)
```

### Stale Run Recovery

If a worker crashes, the system detects and recovers:

**Detection (in `/api/receipts/sync`):**
```python
# Check if run is stale:
# 1. No heartbeat for 180 seconds
# 2. OR running for more than 30 minutes

if is_heartbeat_stale or is_runtime_exceeded:
    existing_run.status = 'failed'
    existing_run.error_message = "Stale run auto-failed"
    # Allow new sync to start
```

### Progress Tracking

Monitor sync progress in real-time:

**GET `/api/receipts/sync/status/{run_id}`**
```json
{
  "status": "running",
  "messages_scanned": 450,
  "saved_receipts": 23,
  "progress_percentage": 45,
  "last_heartbeat_at": "2024-01-20T10:30:45Z"
}
```

## 4. WhatsApp Anti-Flood & Deduplication

### Triple-Layer Deduplication

Messages are deduplicated using three methods:

**1. Message ID (Most Reliable)**
```python
baileys_message_id = msg.get('key', {}).get('id', '')
existing = WhatsAppMessage.query.filter(
    provider_message_id == baileys_message_id
).first()
```

**2. JID + Timestamp**
```python
jid = msg.get('key', {}).get('remoteJid', '')
timestamp = msg.get('messageTimestamp', 0)
# Check within 1-second tolerance
```

**3. Content + Phone (Fallback)**
```python
# Check same body + phone within 10 seconds
if (datetime.utcnow() - existing_msg.created_at) < timedelta(seconds=10):
    skip_duplicate()
```

### Flood Handling

**Current Implementation:**
- Dedupe prevents duplicate DB writes
- Each message processed synchronously
- No artificial throttling (messages flow at network speed)

**Future Enhancement (if needed):**
```python
# Batch writes during flood
pending_messages = []
for msg in messages:
    pending_messages.append(WhatsAppMessage(...))
    
    if len(pending_messages) >= 100:
        db.session.bulk_save_objects(pending_messages)
        db.session.commit()
        pending_messages.clear()
```

### Media Security

**Future Enhancement:**
Media URLs should use signed URLs with expiration:

```python
# Generate signed URL (expires in 1 hour)
signed_url = generate_signed_url(
    storage_key=attachment.storage_path,
    expiry_seconds=3600
)

# Send to WhatsApp
wa_service.send_media(
    to=customer_phone,
    media_url=signed_url,
    media_type='image'
)
```

## 5. UI Date Filtering

### Backend Support

Already supports both formats:

```python
# Accepts both camelCase and snake_case
from_date = request.args.get('from_date') or request.args.get('fromDate')
to_date = request.args.get('to_date') or request.args.get('toDate')

# Logs RAW + PARSED for debugging
logger.info(f"RAW: from_date={request.args.get('from_date')}, fromDate={request.args.get('fromDate')}")
logger.info(f"PARSED: from_date={from_date}, to_date={to_date}")

# Returns 400 on parse failure
if parse_error:
    return jsonify({
        "success": False,
        "error": "Invalid from_date format: 'xyz'. Use YYYY-MM-DD"
    }), 400
```

### Frontend (Mobile Fix)

Already has scroll lock prevention:

```typescript
// Lock body scroll on iOS when modal is open
useEffect(() => {
  if (isOpen) {
    scrollYRef.current = window.scrollY;
    
    // Lock body scroll with iOS-compatible method
    document.body.style.position = 'fixed';
    document.body.style.top = `-${scrollYRef.current}px`;
    document.body.style.width = '100%';
    document.body.style.overflow = 'hidden';
  } else {
    // Restore scroll position
    document.body.style.position = '';
    document.body.style.top = '';
    window.scrollTo(0, scrollYRef.current);
  }
}, [isOpen]);
```

## 6. Load Testing

### Expected Performance

**WebSocket Calls:**
- 30-100 concurrent calls without memory climb ✓
- Backpressure prevents RAM exhaustion ✓
- Graceful degradation under extreme load ✓

**Gmail Receipts:**
- Sync doesn't block API ✓
- Worker handles long-running jobs ✓
- Automatic recovery from crashes ✓

**WhatsApp:**
- 1,000 burst messages don't crash API/DB ✓
- No duplicate messages in database ✓
- Fast processing (no artificial delays) ✓

### Load Testing Commands

```bash
# Test WebSocket concurrency (simulate 50 concurrent calls)
for i in {1..50}; do
  wscat -c wss://prosaas.pro/ws/twilio-media &
done

# Test WhatsApp flood (send 1000 messages rapidly)
for i in {1..1000}; do
  curl -X POST https://prosaas.pro/webhook/incoming \
    -H "Content-Type: application/json" \
    -d '{"messages": [{"key": {"id": "'$RANDOM'", ...}}]}'
done

# Monitor Redis queue
redis-cli -u $REDIS_URL INFO stats

# Monitor worker jobs
curl http://prosaas-worker:9181/  # RQ Dashboard (if installed)
```

## 7. Security Considerations

### Implemented

- [x] Multi-tenant isolation (business_id checks)
- [x] Permission checks via @require_page_access
- [x] Encrypted refresh tokens (Gmail OAuth)
- [x] Redis locks prevent concurrent syncs
- [x] WebSocket subprotocol validation
- [x] CSRF protection on all POST endpoints
- [x] Rate limiting for Gmail API calls
- [x] Signed URLs for attachment downloads

### Future Enhancements

- [ ] WhatsApp media signed URLs (short-lived)
- [ ] IP-based rate limiting on webhook endpoints
- [ ] Additional CodeQL security checks

## 8. Monitoring & Debugging

### Logs to Watch

**Worker logs:**
```bash
docker logs prosaas-worker -f
# Look for:
# - "JOB START: Gmail sync"
# - "JOB COMPLETE: scanned=X, saved=Y"
# - "JOB FAILED: ..."
```

**Redis queue status:**
```bash
redis-cli -u $REDIS_URL
> LLEN rq:queue:default  # Queue length
> KEYS receipt_sync_lock:*  # Active locks
```

**WebSocket connections:**
```bash
docker logs prosaas-calls -f | grep "REALTIME"
# Look for:
# - "WebSocket connected"
# - "START EVENT RECEIVED"
# - "Ghost session" (connections without START)
```

### Health Checks

```bash
# API health
curl https://prosaas.pro/api/health

# Worker health (check if process is running)
docker exec prosaas-worker ps aux | grep worker

# Redis health
redis-cli -u $REDIS_URL PING
```

## 9. Troubleshooting

### Worker Not Processing Jobs

**Symptoms:**
- Sync returns 202 but never completes
- Jobs stuck in "queued" status

**Check:**
```bash
# Is worker running?
docker ps | grep prosaas-worker

# View worker logs
docker logs prosaas-worker

# Check Redis connection
docker exec prosaas-worker redis-cli -u $REDIS_URL PING
```

**Fix:**
```bash
# Restart worker
docker restart prosaas-worker
```

### WebSocket Connections Dropping

**Symptoms:**
- Calls disconnect after a few seconds
- "Ghost session" logs

**Check:**
```bash
# Check nginx logs
docker logs prosaas-nginx | grep ws

# Check calls service
docker logs prosaas-calls | grep "WebSocket"
```

**Fix:**
- Ensure nginx proxy_read_timeout is high (3600s)
- Check firewall isn't closing idle connections
- Verify client sends START event

### WhatsApp Duplicates

**Symptoms:**
- Same message appears twice in database

**Check:**
```bash
# Look for duplicate detection logs
docker logs prosaas-api | grep "Duplicate"

# Query database
SELECT provider_message_id, COUNT(*) 
FROM whatsapp_message 
GROUP BY provider_message_id 
HAVING COUNT(*) > 1;
```

**Fix:**
- Already handled by triple-layer deduplication
- Check if Baileys is sending same message_id twice

## 10. Deployment Checklist

Before deploying to production:

- [ ] Set `REDIS_URL` environment variable
- [ ] Set `DATABASE_URL` (managed PostgreSQL)
- [ ] Set Gmail OAuth credentials (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`)
- [ ] Set encryption key (`ENCRYPTION_KEY` for token encryption)
- [ ] Set R2 credentials (for attachment storage)
- [ ] Update nginx SSL certificates
- [ ] Test worker with `docker compose up prosaas-worker`
- [ ] Test API with `curl https://prosaas.pro/api/health`
- [ ] Test WebSocket with `wscat -c wss://prosaas.pro/ws/twilio-media`
- [ ] Monitor logs for first 24 hours

## 11. Rollback Plan

If issues occur:

```bash
# Rollback to previous docker-compose (no service separation)
docker compose down
docker compose -f docker-compose.yml up -d

# Note: Old version uses threading instead of RQ
# But receipts sync will still work (just blocks API thread)
```

## Support

For questions or issues:
1. Check logs first (docker logs <service>)
2. Review this README
3. Contact DevOps team
