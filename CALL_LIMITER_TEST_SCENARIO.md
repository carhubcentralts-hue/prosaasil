"""
Integration Test Scenario: Call Limiter Concurrency Control

This document describes how to test the call limiter fix that ensures
only 3 calls run concurrently when initiating outbound calls.

## Test Scenario

### Setup
1. Have a business with valid phone number configured
2. Import 100 leads with valid phone numbers

### Test Case 1: Small Batch (1-3 leads)
**Action:** Select 3 leads and click "Start Calls"
**Expected:**
- All 3 calls start immediately in parallel
- Response contains `calls` array with all 3 call details
- No `run_id` in response (immediate mode)

**API Request:**
```
POST /api/outbound_calls/start
{
  "lead_ids": [1, 2, 3]
}
```

**Expected Response:**
```json
{
  "success": true,
  "message": "הופעלו 3 שיחות מתוך 3",
  "calls": [
    {"lead_id": 1, "call_sid": "CA...", "status": "initiated"},
    {"lead_id": 2, "call_sid": "CA...", "status": "initiated"},
    {"lead_id": 3, "call_sid": "CA...", "status": "initiated"}
  ]
}
```

### Test Case 2: Large Batch (>3 leads)
**Action:** Select 100 leads and click "Start Calls"
**Expected:**
- Only 3 calls start immediately
- System creates a queue (OutboundCallRun)
- Response contains `run_id` and `mode: "bulk_queue"`
- As each call completes, the next queued call starts automatically
- Maximum 3 calls are active at any time

**API Request:**
```
POST /api/outbound_calls/start
{
  "lead_ids": [1, 2, 3, 4, 5, ..., 100]
}
```

**Expected Response:**
```json
{
  "success": true,
  "message": "הופעלו 100 שיחות בתור (3 במקביל)",
  "run_id": 123,
  "queued": 100,
  "mode": "bulk_queue"
}
```

### Monitoring Progress

**Check Queue Status:**
```
GET /api/outbound/runs/123
```

**Expected Response (initial):**
```json
{
  "run_id": 123,
  "status": "running",
  "queued": 97,
  "in_progress": 3,
  "completed": 0,
  "failed": 0,
  "total_leads": 100,
  "concurrency": 3
}
```

**Expected Response (mid-progress):**
```json
{
  "run_id": 123,
  "status": "running",
  "queued": 50,
  "in_progress": 3,
  "completed": 45,
  "failed": 2,
  "total_leads": 100,
  "concurrency": 3
}
```

**Expected Response (completed):**
```json
{
  "run_id": 123,
  "status": "completed",
  "queued": 0,
  "in_progress": 0,
  "completed": 98,
  "failed": 2,
  "total_leads": 100,
  "concurrency": 3
}
```

### Verification Steps

1. **Database Check:** Count active jobs
```sql
SELECT COUNT(*) FROM outbound_call_jobs 
WHERE run_id = 123 AND status = 'calling';
-- Should never exceed 3
```

2. **Logs Check:** Look for concurrency control
```
grep "BulkCall" server.log
# Should show:
# [BulkCall] Starting run 123 with concurrency=3
# [BulkCall] Started call for lead X, job Y
```

3. **Twilio Check:** Count active calls via Twilio API
```python
from twilio.rest import Client
client = Client(account_sid, auth_token)
active_calls = client.calls.list(status='in-progress')
# Should never exceed 3 for this business
```

## How It Works Internally

### Flow for >3 Leads:

1. **API Call** (`/api/outbound_calls/start`)
   - Receives 100 lead_ids
   - Detects len(lead_ids) > 3
   - Calls `_start_bulk_queue(tenant_id, lead_ids)`

2. **Queue Creation** (`_start_bulk_queue`)
   - Creates `OutboundCallRun` with concurrency=3
   - Creates 100 `OutboundCallJob` records (status='queued')
   - Starts background thread: `process_bulk_call_run(run_id)`

3. **Initial Processing** (`process_bulk_call_run`)
   - Picks first 3 queued jobs
   - Creates Twilio calls for each
   - Updates job status to 'calling'
   - Waits for completion signals

4. **Call Completion** (Twilio webhook → `routes_twilio.py`)
   - Call ends, webhook received
   - Updates job status to 'completed' or 'failed'
   - Decrements `run.in_progress_count`
   - **Triggers:** `fill_queue_slots_for_job(job_id)`

5. **Slot Filling** (`fill_queue_slots_for_job`)
   - Checks current active count
   - If < concurrency (3), picks next queued job
   - Starts next call
   - Repeats until queue is empty

6. **Completion**
   - When no more queued jobs AND active_count=0
   - Sets `run.status = 'completed'`
   - Sets `run.completed_at`

## Edge Cases Handled

1. **Exactly 3 leads:** Uses immediate mode (no queue)
2. **4 leads:** Uses queue mode (max 3 concurrent)
3. **Call failures:** Failed calls are tracked, next call starts
4. **Network timeouts:** Atomic locking prevents duplicates
5. **Process crash:** Stuck jobs are cleaned up on restart

## Performance Impact

- **Before Fix:** 100 calls → all 100 initiated immediately → Twilio overload
- **After Fix:** 100 calls → 3 at a time → ~33 batches → controlled load
- **Average time:** If each call is 2 minutes:
  - Before: All start at once (chaos)
  - After: 100 calls / 3 concurrent ≈ 34 batches × 2 min ≈ 68 minutes total

## Benefits

1. ✅ Prevents Twilio API rate limit errors
2. ✅ Better call quality (less network congestion)
3. ✅ Predictable resource usage
4. ✅ Can monitor progress in real-time
5. ✅ Can stop queue if needed (`/api/outbound/stop-queue`)
