# BulkGate Testing Guide

## Overview

This guide helps verify that BulkGate rate limiting and job locking works correctly for all bulk operations.

## Prerequisites

1. Redis must be running and accessible via REDIS_URL env var
2. System must be deployed with the BulkGate integration changes
3. Test with at least 2 different businesses to verify tenant isolation

## Test Scenarios

### 1. Rate Limiting Test

**Goal**: Verify that exceeding rate limit returns 429 error

**Steps for each endpoint:**

#### Test: Bulk Delete Leads (limit: 2/minute)
```bash
# Enqueue 3 delete operations rapidly
curl -X DELETE http://localhost:5000/api/leads/bulk \
  -H "Content-Type: application/json" \
  -H "Cookie: session=..." \
  -d '{"lead_ids": [1,2,3]}'

# Wait 1 second
curl -X DELETE http://localhost:5000/api/leads/bulk \
  -H "Content-Type: application/json" \
  -H "Cookie: session=..." \
  -d '{"lead_ids": [4,5,6]}'

# This should return 429
curl -X DELETE http://localhost:5000/api/leads/bulk \
  -H "Content-Type: application/json" \
  -H "Cookie: session=..." \
  -d '{"lead_ids": [7,8,9]}'
```

**Expected:**
- First two requests: 202 Accepted
- Third request: 429 Too Many Requests with message "חרגת ממגבלת קצב. מקסימום 2 פעולות בדקה"

#### Test: Bulk Update Leads (limit: 5/minute)
```bash
# Try 6 rapid updates
for i in {1..6}; do
  curl -X PATCH http://localhost:5000/api/leads/bulk \
    -H "Content-Type: application/json" \
    -H "Cookie: session=..." \
    -d '{"lead_ids": [1,2], "updates": {"status": "new"}}'
  sleep 1
done
```

**Expected:**
- First 5 requests: 202 Accepted
- Sixth request: 429 Too Many Requests

#### Test: Delete Imported Leads (limit: 2/minute)
```bash
# Try 3 rapid deletes
for i in {1..3}; do
  curl -X POST http://localhost:5000/api/outbound/bulk-delete-imported \
    -H "Content-Type: application/json" \
    -H "Cookie: session=..." \
    -d '{"delete_all": false, "lead_ids": [1,2,3]}'
  sleep 1
done
```

**Expected:**
- First 2 requests: 202 Accepted
- Third request: 429 Too Many Requests

#### Test: Bulk Enqueue Outbound Calls (limit: 2/minute)
```bash
# Try 3 rapid enqueues
for i in {1..3}; do
  curl -X POST http://localhost:5000/api/outbound/bulk-enqueue \
    -H "Content-Type: application/json" \
    -H "Cookie: session=..." \
    -d '{"lead_ids": [1,2], "concurrency": 3}'
  sleep 1
done
```

**Expected:**
- First 2 requests: 202 Accepted
- Third request: 429 Too Many Requests

#### Test: WhatsApp Broadcast (limit: 3/minute)
```bash
# Try 4 rapid broadcasts
for i in {1..4}; do
  curl -X POST http://localhost:5000/api/whatsapp/broadcast \
    -H "Content-Type: application/json" \
    -H "Cookie: session=..." \
    -d '{"phones": ["+972501234567"], "message_text": "Test"}'
  sleep 1
done
```

**Expected:**
- First 3 requests: 200/202 OK
- Fourth request: 429 Too Many Requests

#### Test: Recording Download (limit: 10/minute)
```bash
# Try 11 rapid downloads
CALL_SID="CAxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
for i in {1..11}; do
  curl http://localhost:5000/api/calls/${CALL_SID}/recording \
    -H "Cookie: session=..."
done
```

**Expected:**
- First 10 requests: 200 or 202 (depending on cache status)
- Eleventh request: 429 Too Many Requests

### 2. Active Job Lock Test

**Goal**: Verify that starting a second operation while first is running returns 429

**Steps:**

1. Start a long-running bulk delete operation
2. While it's running, try to start another bulk delete for the same business
3. Verify second request gets 429 error

```bash
# Terminal 1: Start first delete (will take time)
curl -X DELETE http://localhost:5000/api/leads/bulk \
  -H "Content-Type: application/json" \
  -H "Cookie: session=..." \
  -d '{"lead_ids": [1,2,3,4,5,6,7,8,9,10]}'

# Terminal 2: Immediately try second delete (should fail)
curl -X DELETE http://localhost:5000/api/leads/bulk \
  -H "Content-Type: application/json" \
  -H "Cookie: session=..." \
  -d '{"lead_ids": [11,12,13]}'
```

**Expected:**
- First request: 202 Accepted
- Second request: 429 Too Many Requests with message "פעולה פעילה כבר רצה. נסה שוב בעוד X שניות"

### 3. Lock Release Test

**Goal**: Verify that lock is released after job completes

**Steps:**

1. Start a small bulk operation (completes quickly)
2. Wait for job to complete
3. Start another operation of same type
4. Verify it succeeds

```bash
# Start first operation
curl -X DELETE http://localhost:5000/api/leads/bulk \
  -H "Content-Type: application/json" \
  -H "Cookie: session=..." \
  -d '{"lead_ids": [1,2]}'

# Wait 30 seconds for completion
sleep 30

# Check job status
curl http://localhost:5000/api/background-jobs/<job_id> \
  -H "Cookie: session=..."

# If status is 'completed', try another delete (should succeed)
curl -X DELETE http://localhost:5000/api/leads/bulk \
  -H "Content-Type: application/json" \
  -H "Cookie: session=..." \
  -d '{"lead_ids": [3,4]}'
```

**Expected:**
- First operation: 202 Accepted
- After completion: Second operation succeeds with 202 Accepted

### 4. Deduplication Test (Recording Downloads)

**Goal**: Verify that identical operations are deduplicated

**Steps:**

```bash
CALL_SID="CAxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# Request 1: Download recording
curl http://localhost:5000/api/calls/${CALL_SID}/recording \
  -H "Cookie: session=..."

# Request 2: Immediately request same recording again
curl http://localhost:5000/api/calls/${CALL_SID}/recording \
  -H "Cookie: session=..."
```

**Expected:**
- First request: 200 or 202
- Second request: Either serves from cache (200) or returns 429 if download in progress

### 5. Cross-Tenant Isolation Test

**Goal**: Verify that rate limits are per-business

**Steps:**

1. Login as Business A
2. Enqueue 2 bulk delete operations (reach limit)
3. Login as Business B
4. Try to enqueue bulk delete operation
5. Verify Business B is NOT rate limited

```bash
# Business A: Use up rate limit
curl -X DELETE http://localhost:5000/api/leads/bulk \
  -H "Cookie: session_business_a=..." \
  -d '{"lead_ids": [1]}'

curl -X DELETE http://localhost:5000/api/leads/bulk \
  -H "Cookie: session_business_a=..." \
  -d '{"lead_ids": [2]}'

# Business B: Should not be rate limited
curl -X DELETE http://localhost:5000/api/leads/bulk \
  -H "Cookie: session_business_b=..." \
  -d '{"lead_ids": [1]}'
```

**Expected:**
- Business A's third request: 429 (if attempted)
- Business B's first request: 202 Accepted (NOT rate limited)

### 6. Redis Failure Graceful Degradation Test

**Goal**: Verify system continues to work if Redis is unavailable

**Steps:**

1. Stop Redis service
2. Try to enqueue a bulk operation
3. Verify it succeeds (logs warning but proceeds)

```bash
# Stop Redis
sudo systemctl stop redis

# Try bulk operation
curl -X DELETE http://localhost:5000/api/leads/bulk \
  -H "Content-Type: application/json" \
  -H "Cookie: session=..." \
  -d '{"lead_ids": [1,2,3]}'

# Check application logs
tail -f /var/log/prosaasil/app.log | grep "BulkGate"
```

**Expected:**
- Operation succeeds with 202 Accepted
- Logs show: "BulkGate check failed (proceeding anyway): ..."
- No 429 errors (rate limiting disabled when Redis unavailable)

## Monitoring

### Check Redis Keys

```bash
# Connect to Redis
redis-cli

# Check rate limiting keys
KEYS bulk_gate:rate:*

# Check active locks
KEYS bulk_gate:lock:*

# Check deduplication keys
KEYS bulk_gate:dedup:*

# Get TTL of a lock
TTL bulk_gate:lock:business_1:delete_leads_bulk

# Get rate count for last minute
ZCOUNT bulk_gate:rate:business_1:delete_leads_bulk -inf +inf
```

### Check Application Logs

```bash
# Filter BulkGate logs
tail -f /var/log/prosaasil/app.log | grep "BULK_GATE"
```

**Expected log patterns:**

```
✅ BULK_GATE: Enqueue allowed business_id=1 operation=delete_leads_bulk rate=1/2
🔒 BULK_GATE: Lock acquired business_id=1 operation=delete_leads_bulk job_id=123 ttl=3600s
📝 BULK_GATE: Enqueue recorded business_id=1 operation=delete_leads_bulk
🔓 BULK_GATE: Lock released business_id=1 operation=delete_leads_bulk
🚫 BULK_GATE: Rate limit exceeded business_id=1 operation=delete_leads_bulk count=3/2
🚫 BULK_GATE: Active job exists business_id=1 operation=delete_leads_bulk ttl=3500s
```

## Rate Limits Reference

| Operation Type | Limit (per minute) | Lock TTL |
|---|---|---|
| delete_leads_bulk | 2 | 1 hour |
| update_leads_bulk | 5 | 30 minutes |
| delete_imported_leads | 2 | 30 minutes |
| enqueue_outbound_calls | 2 | 1 hour |
| broadcast_whatsapp | 3 | 2 hours |
| recording_download | 10 | 5 minutes |

## Troubleshooting

### Lock Not Released

If a lock is stuck (job failed without releasing lock):

```bash
# Manually delete the lock in Redis
redis-cli
DEL bulk_gate:lock:business_1:delete_leads_bulk
```

### Rate Limit Not Resetting

Rate limits auto-expire after 2 minutes. To manually reset:

```bash
redis-cli
DEL bulk_gate:rate:business_1:delete_leads_bulk
```

### Check Job Completion

Verify jobs are releasing locks:

```bash
# Check BackgroundJob status
curl http://localhost:5000/api/background-jobs/<job_id> \
  -H "Cookie: session=..."
```

Expected final status: `completed` or `failed`

## Success Criteria

All tests pass if:
- ✅ Rate limiting returns 429 after exceeding limit
- ✅ Active job lock prevents duplicate operations
- ✅ Locks are released on job completion
- ✅ Deduplication prevents identical operations
- ✅ Tenant isolation works correctly
- ✅ System gracefully degrades if Redis unavailable
- ✅ All logs show expected patterns
- ✅ No stale locks remain after tests
