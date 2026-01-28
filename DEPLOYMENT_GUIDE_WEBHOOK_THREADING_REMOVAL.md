# Deployment Guide: WhatsApp Webhook Threading Removal

## Overview
This deployment removes legacy threading code from the WhatsApp webhook endpoint, ensuring a single execution path through RQ workers. This eliminates duplicate message processing and race conditions.

## Pre-Deployment Checklist

### 1. Verify Current Architecture ✅
- [ ] Confirm `docker-compose.yml` has separate services:
  - `prosaas-api` (SERVICE_ROLE=api)
  - `worker` (SERVICE_ROLE=worker) 
  - `scheduler` (SERVICE_ROLE=scheduler)
- [ ] Verify Redis is healthy and accessible
- [ ] Verify worker service is running and processing jobs

### 2. Backup Current State ✅
```bash
# Backup current code
git tag pre-webhook-threading-removal

# Verify current webhook is working
curl -X POST http://localhost:5000/webhook/whatsapp/incoming \
  -H "X-Internal-Secret: $INTERNAL_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"tenantId":"1","payload":{"messages":[]}}'
```

### 3. Review Changes ✅
- [ ] Review `server/routes_webhook.py` changes (480 → 123 lines)
- [ ] Verify `server/jobs/webhook_process_job.py` has complete logic
- [ ] Review `WEBHOOK_THREADING_REMOVAL_SUMMARY.md`
- [ ] Run test suite: `python test_webhook_threading_removal.py`

## Deployment Steps

### Step 1: Deploy Code Changes
```bash
# Pull latest changes
git checkout copilot/improve-scheduler-logic
git pull origin copilot/improve-scheduler-logic

# Verify no merge conflicts
git status

# Run pre-deployment tests
python test_webhook_threading_removal.py
python -m compileall server/routes_webhook.py server/jobs/webhook_process_job.py
```

### Step 2: Restart Services (Zero Downtime)
```bash
# Option A: Rolling restart (recommended for production)
docker-compose up -d --no-deps --build prosaas-api
sleep 5  # Wait for health check
docker-compose up -d --no-deps --build worker

# Option B: Full restart (if Option A has issues)
docker-compose restart prosaas-api worker
```

### Step 3: Monitor Logs
```bash
# Monitor API logs - should only see enqueue messages
docker-compose logs -f --tail=100 prosaas-api | grep -i webhook

# Expected: "✅ Enqueued webhook_process_job" or "⏭️ Skipped duplicate webhook"
# Should NOT see: "🚀 [FLASK_WEBHOOK_IN]" or any processing logs

# Monitor worker logs - should see job processing
docker-compose logs -f --tail=100 worker | grep -i webhook

# Expected: "🚀 [WEBHOOK_JOB]", "📨 [WEBHOOK_JOB]", "✅ [WEBHOOK_JOB] Completed"
```

### Step 4: Verify Health
```bash
# Check Redis connectivity
redis-cli -u $REDIS_URL ping
# Expected: PONG

# Check queue stats
curl http://localhost:5000/api/jobs/stats | jq

# Send test webhook
curl -X POST http://localhost:5000/webhook/whatsapp/incoming \
  -H "X-Internal-Secret: $INTERNAL_SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "tenantId":"1",
    "payload":{
      "messages":[{
        "key":{"id":"TEST123","remoteJid":"972501234567@s.whatsapp.net"},
        "message":{"conversation":"Test message"}
      }]
    }
  }'

# Expected response: 200 OK (empty body)
```

## Post-Deployment Verification

### 1. Functional Tests ✅
- [ ] Send test WhatsApp message via Baileys
- [ ] Verify message appears in Redis queue
- [ ] Verify worker processes the job
- [ ] Verify AI response is sent
- [ ] Verify message saved to database
- [ ] Verify no duplicate messages

### 2. Performance Tests ✅
- [ ] Send 10 concurrent webhooks
- [ ] Verify all enqueued within 100ms
- [ ] Verify all processed by worker
- [ ] No duplicate processing

### 3. Error Handling Tests ✅
```bash
# Test 1: Stop Redis temporarily
docker-compose stop redis
curl -X POST http://localhost:5000/webhook/whatsapp/incoming \
  -H "X-Internal-Secret: $INTERNAL_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"tenantId":"1","payload":{"messages":[{"key":{"id":"TEST123"}}]}}'
# Expected: 503 Service Unavailable

# Test 2: Restart Redis
docker-compose start redis
# Resend webhook - should succeed now
```

### 4. Monitoring Checklist ✅
- [ ] No errors in API logs
- [ ] No errors in worker logs  
- [ ] Queue depths are normal
- [ ] Response times < 100ms for API
- [ ] Job processing times < 5s for worker
- [ ] No duplicate message IDs in database

## Expected Behavior Changes

### Before Deployment:
- Webhook endpoint does inline processing using threads
- If Redis fails, fallback processes inline
- Logs show processing in API service
- Thread pool limit of 10

### After Deployment:
- Webhook endpoint only enqueues jobs
- If Redis fails, returns 503 (no fallback)
- API logs only show enqueue/skip
- Worker logs show all processing
- No thread pool limits (scales with worker count)

## Rollback Plan

### If Issues Occur:
```bash
# Option 1: Quick rollback (revert to previous code)
git checkout df20cb3^  # Before changes
docker-compose up -d --no-deps --build prosaas-api worker

# Option 2: Restore from backup
git checkout pre-webhook-threading-removal
docker-compose up -d --no-deps --build prosaas-api worker
```

### When to Rollback:
- [ ] API logs show processing (not just enqueue)
- [ ] Webhook responses take > 1 second
- [ ] Duplicate messages in database
- [ ] Worker not processing jobs
- [ ] Error rate > 1%

## Success Criteria

### Must Have ✅
- [ ] API logs only show: `Enqueued webhook_process_job` or `Skipped duplicate`
- [ ] Worker logs show: `[WEBHOOK_JOB]` processing
- [ ] No duplicate messages in database
- [ ] Webhook response time < 100ms
- [ ] Test suite passes: `python test_webhook_threading_removal.py`

### Nice to Have 📊
- [ ] Reduced memory usage in API service (no thread pool)
- [ ] Better worker utilization (can scale independently)
- [ ] Cleaner log separation (API vs Worker)

## Monitoring

### Key Metrics to Watch:
```bash
# API Service
- Webhook response time: < 100ms
- Enqueue success rate: > 99.9%
- Memory usage: Should decrease (no threads)

# Worker Service  
- Job processing time: < 5s
- Job success rate: > 99%
- Queue depth: < 100 jobs

# Redis
- Connection errors: 0
- Memory usage: Stable
```

### Alerting:
- Alert if webhook response time > 500ms
- Alert if worker queue depth > 1000 jobs
- Alert if job failure rate > 5%
- Alert if Redis connection failures

## Common Issues & Solutions

### Issue 1: API returns 503
**Cause**: Redis is down or unreachable
**Solution**: 
```bash
docker-compose logs redis
docker-compose restart redis
```

### Issue 2: Jobs not processing
**Cause**: Worker is down or not listening to queue
**Solution**:
```bash
docker-compose logs worker
docker-compose restart worker
# Verify worker is listening to correct queues
```

### Issue 3: Duplicate messages
**Cause**: Deduplication not working (should not happen)
**Solution**:
```bash
# Check Redis keys
redis-cli -u $REDIS_URL keys "job_lock:webhook:*"
# Should see lock keys with TTL
redis-cli -u $REDIS_URL ttl "job_lock:webhook:baileys:MESSAGE_ID"
```

### Issue 4: Webhook returns 200 but no processing
**Cause**: Job enqueued but worker not processing
**Solution**:
```bash
# Check worker is running
docker-compose ps worker
# Check worker logs for errors
docker-compose logs worker --tail=100
# Check Redis queue
redis-cli -u $REDIS_URL llen rq:queue:default
```

## Support Contacts

- **Primary**: Check logs first
- **Secondary**: Review `WEBHOOK_THREADING_REMOVAL_SUMMARY.md`
- **Escalation**: Rollback if issues persist > 5 minutes

## Final Checklist

Before marking deployment as complete:
- [ ] All tests pass
- [ ] API logs show only enqueue
- [ ] Worker logs show processing
- [ ] No errors in last 10 minutes
- [ ] Performance metrics are normal
- [ ] Test webhook succeeds
- [ ] No duplicate messages
- [ ] Documentation updated
- [ ] Team notified of changes

## Related Documentation

- `WEBHOOK_THREADING_REMOVAL_SUMMARY.md` - Technical details
- `test_webhook_threading_removal.py` - Test suite
- `server/routes_webhook.py` - Modified webhook endpoint
- `server/jobs/webhook_process_job.py` - Job processing logic
- `docker-compose.yml` - Service configuration

---

**Deployment Date**: _____________________
**Deployed By**: _____________________
**Rollback Required**: ☐ Yes  ☐ No
**Notes**: _____________________
