# BulkCall Fix Verification Guide

## Summary of Fixes

### 1. ✅ Request Context Issue FIXED
**Problem**: Worker thread tried to access `request.host` causing "Working outside of request context" error

**Solution**:
- Removed `from flask import request` from `twilio_outbound_service.py`
- Added `host` as required parameter to `create_outbound_call()`
- Worker functions now pass `host` from `get_public_host()` (no request context needed)

### 2. ✅ Business-Level Concurrency Limiting ADDED
**Problem**: Workers counted only per-run active calls, not per-business
- Multiple runs could exceed the 3-call limit
- Mixed direct API + bulk queue calls could exceed limit

**Solution**:
- Integrated `call_limiter.py` SSOT into workers
- Workers now check `count_active_outbound_calls(business_id)` 
- Enforces `MAX_OUTBOUND_CALLS_PER_BUSINESS = 3` at business level
- No duplicate logic - uses existing call_limiter

### 3. ✅ No Duplicates / Conflicts
**Existing Protection Preserved**:
- Atomic locking with `dial_lock_token` (lines 1750-1759, 1958-1967)
- Deduplication in `create_outbound_call()` (memory + DB checks)
- call_limiter.py for direct API calls (1-3 leads)
- No conflicts between different limiting mechanisms

---

## How to Verify the Fix

### Test 1: Request Context Fix
**Expected**: No more "Working outside of request context" errors

```bash
# Watch logs while bulk calling
tail -f logs/app.log | grep -i "context\|bulkcall"

# Start 50+ lead bulk call from UI
# Should see:
# ✅ [BulkCall] Starting run X with concurrency=3
# ✅ [BulkCall] Started call for lead=...
# ❌ NO "Working outside of request context" errors
```

### Test 2: Concurrency Limiting (3 max per business)
**Expected**: Never more than 3 active outbound calls per business

```sql
-- Run this query repeatedly during bulk calling
SELECT 
    business_id,
    COUNT(*) as active_count,
    GROUP_CONCAT(status) as statuses
FROM outbound_call_jobs
WHERE status IN ('dialing', 'calling')
GROUP BY business_id;

-- Expected result: active_count <= 3 for each business
```

**OR via logs:**
```bash
# Watch active call counts
tail -f logs/app.log | grep -i "active\|limit\|concurrency"

# Should see:
# ✅ Business X at max outbound limit (3/3), waiting...
# ✅ [FillSlots] Filling slots... (never exceeds 3)
```

### Test 3: Queue Processing (50+ leads)
**Expected**: Queue processes smoothly, 3 at a time

```bash
# Start bulk call with 50 leads
# Watch queue progression
watch -n 2 'psql $DATABASE_URL -c "
SELECT 
    status, 
    COUNT(*) as count 
FROM outbound_call_jobs 
WHERE run_id = YOUR_RUN_ID 
GROUP BY status;
"'

# Expected progression:
# queued: 50, dialing: 0, calling: 0
# queued: 47, dialing: 3, calling: 0
# queued: 47, dialing: 0, calling: 3
# queued: 44, dialing: 0, calling: 3
# ... (as calls complete, new ones start)
# queued: 0, calling: 2, completed: 48
# queued: 0, calling: 0, completed: 50
```

### Test 4: No Duplicate Calls
**Expected**: Each lead gets only 1 call, no duplicates

```sql
-- Check for duplicate calls to same lead
SELECT 
    lead_id,
    COUNT(*) as call_count,
    GROUP_CONCAT(call_sid) as call_sids
FROM outbound_call_jobs
WHERE run_id = YOUR_RUN_ID
GROUP BY lead_id
HAVING COUNT(*) > 1;

-- Expected: Empty result (no duplicates)
```

---

## Code Changes Summary

### File: `server/services/twilio_outbound_service.py`
```python
# BEFORE (caused error):
from flask import request
...
def create_outbound_call(...):
    host = request.headers.get("X-Forwarded-Host") or request.host  # ❌ Fails in worker

# AFTER (fixed):
# No request import
def create_outbound_call(..., host: str, ...):  # ✅ Host passed as parameter
    # Build webhook URL using provided host
    webhook_url = f"https://{host}/webhook/..."
```

### File: `server/routes_outbound.py`
```python
# Worker functions now:
# 1. Get host without request context
host = get_public_host()  # ✅ Uses ENV/config, no request

# 2. Check business-level limits
from server.services.call_limiter import count_active_outbound_calls, MAX_OUTBOUND_CALLS_PER_BUSINESS

business_active = count_active_outbound_calls(run.business_id)

# 3. Respect BOTH limits
while active_in_run < run.concurrency and business_active < MAX_OUTBOUND_CALLS_PER_BUSINESS:
    # Start next call...
```

---

## Key Architecture Points

### SSOT (Single Source of Truth)
- **Call Limiting**: `call_limiter.py` - used by API routes AND workers
- **Call Creation**: `twilio_outbound_service.py` - only place that calls Twilio
- **Concurrency**: `MAX_OUTBOUND_CALLS_PER_BUSINESS = 3` in call_limiter.py

### No Request Context in Workers
- Workers use `get_process_app()` for app context (DB access)
- Workers receive all data as parameters (business_id, host, etc.)
- No use of `request`, `g`, `session`, `current_user`, or `url_for`

### Atomic Locking Prevents Duplicates
1. **Level 1**: Memory cache in `create_outbound_call()`
2. **Level 2**: DB check for active calls
3. **Level 3**: Atomic UPDATE with `dial_lock_token`
4. **Level 4**: Check `result.rowcount` after lock attempt

### Queue Processing Flow
```
1. User marks 50 leads → Creates run with 50 jobs (all status='queued')
2. Worker starts, checks: active_in_run=0, business_active=0
3. Worker can start 3 calls (min(concurrency=3, business_limit=3))
4. Worker atomically locks 3 jobs, sets status='dialing'
5. Worker creates Twilio calls, sets status='calling'
6. When call completes → fill_queue_slots_for_job() fires
7. fill_queue_slots() checks limits, starts next queued job
8. Repeat until queued=0
```

---

## Rollback Plan (if needed)

If issues arise, rollback to previous commit:
```bash
git revert aa5d12b  # Revert concurrency limiting
git revert 6626428  # Revert request context fix
```

But unlikely needed - fixes are minimal and surgical.
